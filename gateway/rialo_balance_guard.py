#!/usr/bin/env python3
"""Keep the Rialo DevNet fee payer funded and recover rent-failed submissions."""

from __future__ import annotations

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from gateway.rialo_verify import KELVINS_PER_RLO, RialoRpcClient, RialoVerificationError


DEFAULT_FEE_PAYER = "BBjJpGwN3aV3BrMPw6BCZHZue8btcqTTfXouG9Nv9Sz6"
DEFAULT_LOW_BALANCE_RLO = 0.25
DEFAULT_AIRDROP_AMOUNT_RLO = 1.0
DEFAULT_CHECK_SECONDS = 300.0
DEFAULT_AIRDROP_COOLDOWN_SECONDS = 900.0
DEFAULT_RECOVERY_BALANCE_RLO = 0.25
DEFAULT_WSL_PROJECT_DIR = "~/rialo-edge-log"


class RialoBalanceGuardError(RuntimeError):
    """Raised when the balance guard cannot complete a requested action safely."""


def rlo_to_kelvins(value: float) -> int:
    if value < 0:
        raise ValueError("RLO value cannot be negative")
    return int(value * KELVINS_PER_RLO)


def kelvins_to_rlo(value: int) -> float:
    return value / KELVINS_PER_RLO


def is_insufficient_funds_for_rent(error: Any) -> bool:
    if isinstance(error, dict):
        if "InsufficientFundsForRent" in error:
            return True
        return any(is_insufficient_funds_for_rent(value) for value in error.values())
    if isinstance(error, list):
        return any(is_insufficient_funds_for_rent(value) for value in error)
    return False


def transaction_fee_payer(transaction_result: dict[str, Any]) -> str | None:
    transaction = transaction_result.get("transaction")
    message = transaction.get("message") if isinstance(transaction, dict) else None
    keys = message.get("accountKeys") if isinstance(message, dict) else None
    if not isinstance(keys, list) or not keys:
        return None
    first = keys[0]
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        value = first.get("pubkey")
        return value if isinstance(value, str) else None
    return None


def transaction_error(transaction_result: dict[str, Any]) -> Any:
    meta = transaction_result.get("meta")
    return meta.get("err") if isinstance(meta, dict) else None


def wsl_directory_expression(path: str) -> str:
    if path == "~":
        return '"$HOME"'
    if path.startswith("~/"):
        suffix = path[2:]
        if not suffix:
            return '"$HOME"'
        return f'"$HOME"/{shlex.quote(suffix)}'
    return shlex.quote(path)


def build_airdrop_invocation(amount_rlo: float, wsl_project_dir: str) -> list[str]:
    if amount_rlo <= 0:
        raise ValueError("airdrop amount must be positive")
    amount = format(amount_rlo, "g")
    script = (
        'export PATH="$HOME/.local/share/rialo/bin:$PATH"; '
        f"cd -- {wsl_directory_expression(wsl_project_dir)} "
        f"&& rialo client airdrop --amount {amount}"
    )
    return ["wsl.exe", "--", "bash", "-lc", script]


def invoke_airdrop(
    amount_rlo: float,
    wsl_project_dir: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> str:
    completed = runner(
        build_airdrop_invocation(amount_rlo, wsl_project_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    if completed.returncode != 0:
        raise RialoBalanceGuardError(
            f"Rialo airdrop exited with code {completed.returncode}: {output}"
        )
    return output


def load_pending(path: Path) -> tuple[str, str] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    signature = value.get("transaction_signature")
    batch_id = value.get("batch_id")
    if not isinstance(signature, str) or not isinstance(batch_id, str):
        return None
    return batch_id, signature


def archive_failed_pending(path: Path, transaction_error_value: Any) -> Path:
    destination_dir = path.parent / "failed"
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / path.name
    if destination.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        destination = destination_dir / f"{path.stem}-{stamp}{path.suffix}"
    shutil.move(str(path), str(destination))
    metadata_path = destination.with_suffix(destination.suffix + ".error.json")
    metadata_path.write_text(
        json.dumps(
            {
                "archived_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "transaction_error": transaction_error_value,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def recover_rent_failed_pending(
    receipt_dir: Path,
    fee_payer: str,
    client: RialoRpcClient,
) -> list[Path]:
    recovered: list[Path] = []
    for path in sorted(receipt_dir.glob("*.pending.json")):
        pending = load_pending(path)
        if pending is None:
            continue
        _, signature = pending
        try:
            transaction = client.get_transaction(signature)
        except RialoVerificationError:
            continue
        error = transaction_error(transaction)
        if not is_insufficient_funds_for_rent(error):
            continue
        if transaction_fee_payer(transaction) != fee_payer:
            continue
        recovered.append(archive_failed_pending(path, error))
    return recovered


def run_guard(args: argparse.Namespace) -> int:
    client = RialoRpcClient(args.rpc_url)
    low_kelvins = rlo_to_kelvins(args.low_balance_rlo)
    recovery_kelvins = rlo_to_kelvins(args.recovery_balance_rlo)
    last_airdrop_attempt = 0.0

    print(
        "Rialo balance guard started: "
        f"fee_payer={args.fee_payer} "
        f"low={args.low_balance_rlo:g} RLO "
        f"airdrop={args.airdrop_amount_rlo:g} RLO"
    )

    while True:
        try:
            balance = client.get_balance(args.fee_payer)
            print(
                f"[BALANCE] {args.fee_payer} "
                f"{kelvins_to_rlo(balance):.9f} RLO ({balance} kelvins)"
            )

            now = time.monotonic()
            if balance < low_kelvins:
                if now - last_airdrop_attempt >= args.airdrop_cooldown_seconds:
                    last_airdrop_attempt = now
                    print(
                        f"[LOW BALANCE] requesting {args.airdrop_amount_rlo:g} RLO from DevNet faucet"
                    )
                    output = invoke_airdrop(
                        args.airdrop_amount_rlo,
                        args.wsl_project_dir,
                    )
                    if output:
                        print(f"[AIRDROP] {output}")
                    time.sleep(args.post_airdrop_wait_seconds)
                    balance = client.get_balance(args.fee_payer)
                    print(
                        f"[BALANCE AFTER AIRDROP] "
                        f"{kelvins_to_rlo(balance):.9f} RLO ({balance} kelvins)"
                    )
                else:
                    remaining = max(
                        0.0,
                        args.airdrop_cooldown_seconds - (now - last_airdrop_attempt),
                    )
                    print(f"[AIRDROP COOLDOWN] {remaining:.0f}s remaining")

            if balance >= recovery_kelvins:
                archived = recover_rent_failed_pending(
                    args.receipt_dir,
                    args.fee_payer,
                    client,
                )
                for path in archived:
                    print(
                        "[RECOVERED PENDING] archived permanently failed rent transaction: "
                        f"{path}"
                    )
                if archived:
                    print(
                        f"[RECOVERY] {len(archived)} failed pending transaction(s) released for fresh submission"
                    )
        except (OSError, ValueError, RialoVerificationError, RialoBalanceGuardError) as exc:
            print(f"[BALANCE GUARD ERROR] {exc}", file=sys.stderr)

        if args.once:
            return 0
        time.sleep(args.check_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fee-payer", default=DEFAULT_FEE_PAYER)
    parser.add_argument("--rpc-url", default="http://devnet.rialo.io:4100")
    parser.add_argument("--receipt-dir", type=Path, default=Path("data/receipts"))
    parser.add_argument("--wsl-project-dir", default=DEFAULT_WSL_PROJECT_DIR)
    parser.add_argument("--low-balance-rlo", type=float, default=DEFAULT_LOW_BALANCE_RLO)
    parser.add_argument("--airdrop-amount-rlo", type=float, default=DEFAULT_AIRDROP_AMOUNT_RLO)
    parser.add_argument("--recovery-balance-rlo", type=float, default=DEFAULT_RECOVERY_BALANCE_RLO)
    parser.add_argument("--check-seconds", type=float, default=DEFAULT_CHECK_SECONDS)
    parser.add_argument(
        "--airdrop-cooldown-seconds",
        type=float,
        default=DEFAULT_AIRDROP_COOLDOWN_SECONDS,
    )
    parser.add_argument("--post-airdrop-wait-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.low_balance_rlo < 0 or args.airdrop_amount_rlo <= 0:
        print("ERROR: invalid balance guard thresholds", file=sys.stderr)
        return 2
    if args.recovery_balance_rlo < args.low_balance_rlo:
        print("ERROR: recovery balance cannot be below low balance threshold", file=sys.stderr)
        return 2
    if args.check_seconds <= 0 or args.airdrop_cooldown_seconds < 0:
        print("ERROR: invalid balance guard timing", file=sys.stderr)
        return 2
    return run_guard(args)


if __name__ == "__main__":
    raise SystemExit(main())
