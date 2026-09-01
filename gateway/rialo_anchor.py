#!/usr/bin/env python3
"""Submit verified telemetry batches to Rialo through the CLI installed in WSL."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from gateway.rialo_args import build_command
from gateway.rialo_verify import (
    DEFAULT_RPC_URL,
    RialoRpcClient,
    RialoVerificationError,
    compare_batch_to_state,
    decode_account_state,
    extract_workflow_address,
    load_verified_batch,
    save_receipt,
)


BASE58_PATTERN = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")
BATCH_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,200}$")
TRANSACTION_PATTERN = re.compile(
    r"^Transaction:\s+([1-9A-HJ-NP-Za-km-z]{80,100})\s*$", re.MULTILINE
)
DEFAULT_WSL_PROJECT_DIR = "~/rialo-edge-log"


class RialoAnchorError(RuntimeError):
    """Raised when a verified batch cannot be anchored safely."""


def validate_program_id(value: str) -> str:
    if not 32 <= len(value) <= 64 or not BASE58_PATTERN.fullmatch(value):
        raise RialoAnchorError("program ID is not valid base58")
    return value


def receipt_path(batch: dict[str, Any], receipt_dir: Path) -> Path:
    batch_id = batch.get("batch_id")
    if not isinstance(batch_id, str) or not BATCH_ID_PATTERN.fullmatch(batch_id):
        raise RialoAnchorError("batch ID contains unsupported characters")
    return receipt_dir / f"{batch_id}-rialo.json"


def pending_receipt_path(batch: dict[str, Any], receipt_dir: Path) -> Path:
    batch_id = batch.get("batch_id")
    if not isinstance(batch_id, str) or not BATCH_ID_PATTERN.fullmatch(batch_id):
        raise RialoAnchorError("batch ID contains unsupported characters")
    return receipt_dir / f"{batch_id}-rialo.pending.json"


def save_pending_submission(
    batch: dict[str, Any],
    receipt_dir: Path,
    program_id: str,
    transaction_signature: str,
) -> Path:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    destination = pending_receipt_path(batch, receipt_dir)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "SUBMITTED_UNVERIFIED",
                "batch_id": batch["batch_id"],
                "program_id": program_id,
                "transaction_signature": transaction_signature,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


def load_pending_submission(
    batch: dict[str, Any], receipt_dir: Path, program_id: str
) -> str | None:
    path = pending_receipt_path(batch, receipt_dir)
    if not path.exists():
        return None
    try:
        pending = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RialoAnchorError(f"cannot read pending submission {path}: {exc}") from exc
    if (
        not isinstance(pending, dict)
        or pending.get("status") != "SUBMITTED_UNVERIFIED"
        or pending.get("batch_id") != batch["batch_id"]
        or pending.get("program_id") != program_id
        or not isinstance(pending.get("transaction_signature"), str)
    ):
        raise RialoAnchorError(f"pending submission has invalid contents: {path}")
    return pending["transaction_signature"]


def wsl_directory_expression(path: str) -> str:
    if path == "~":
        return '"$HOME"'
    if path.startswith("~/"):
        suffix = path[2:]
        if not suffix:
            return '"$HOME"'
        return f'"$HOME"/{shlex.quote(suffix)}'
    return shlex.quote(path)


def build_wsl_invocation(
    batch: dict[str, Any], program_id: str, wsl_project_dir: str
) -> list[str]:
    validate_program_id(program_id)
    rialo_command = build_command(batch, program_id)
    script = (
        'export PATH="$HOME/.local/share/rialo/bin:$PATH"; '
        f"cd -- {wsl_directory_expression(wsl_project_dir)} && {rialo_command}"
    )
    return ["wsl.exe", "--", "bash", "-lc", script]


def extract_transaction_signature(output: str) -> str:
    match = TRANSACTION_PATTERN.search(output)
    if match is None:
        raise RialoAnchorError("Rialo CLI output contains no transaction signature")
    return match.group(1)


def invoke_rialo_cli(
    batch: dict[str, Any],
    program_id: str,
    wsl_project_dir: str,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[str, str]:
    command = build_wsl_invocation(batch, program_id, wsl_project_dir)
    try:
        completed = runner(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise RialoAnchorError(f"cannot start WSL: {exc}") from exc

    output = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    if completed.returncode != 0:
        raise RialoAnchorError(
            f"Rialo CLI exited with code {completed.returncode}:\n{output}"
        )
    return extract_transaction_signature(output), output


def wait_for_transaction(
    client: RialoRpcClient,
    signature: str,
    timeout_seconds: float,
    poll_seconds: float = 2.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return client.get_transaction(signature)
        except RialoVerificationError as exc:
            last_error = exc
            time.sleep(poll_seconds)
    raise RialoAnchorError(
        f"transaction was not readable from Rialo RPC within {timeout_seconds:g} seconds: "
        f"{last_error}"
    )


def wait_for_workflow_state(
    client: RialoRpcClient,
    workflow_address: str,
    program_id: str,
    timeout_seconds: float,
    poll_seconds: float = 2.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return decode_account_state(
                client.get_account_info(workflow_address), program_id
            )
        except RialoVerificationError as exc:
            last_error = exc
            time.sleep(poll_seconds)
    raise RialoAnchorError(
        f"workflow account was not readable within {timeout_seconds:g} seconds: "
        f"{last_error}"
    )


def submit_batch(
    batch_path: Path,
    registry_path: Path,
    receipt_dir: Path,
    program_id: str,
    rpc_url: str,
    wsl_project_dir: str,
    rpc_wait_seconds: float,
    force: bool = False,
    client: RialoRpcClient | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> tuple[Path, str, str, str]:
    validate_program_id(program_id)
    batch, _ = load_verified_batch(batch_path, registry_path)
    if "device_public_key_fingerprint" not in batch:
        raise RialoAnchorError("only signed telemetry batches can be anchored")

    destination = receipt_path(batch, receipt_dir)
    if destination.exists() and not force:
        raise RialoAnchorError(
            f"batch already has a Rialo receipt: {destination}; use --force to resubmit"
        )

    signature = None if force else load_pending_submission(
        batch, receipt_dir, program_id
    )
    if signature is None:
        signature, cli_output = invoke_rialo_cli(
            batch, program_id, wsl_project_dir, runner=runner
        )
        save_pending_submission(batch, receipt_dir, program_id, signature)
    else:
        cli_output = f"Resuming submitted transaction: {signature}"

    active_client = client or RialoRpcClient(rpc_url)
    transaction = wait_for_transaction(
        active_client, signature, timeout_seconds=rpc_wait_seconds
    )
    workflow_address = extract_workflow_address(transaction, program_id)
    state = wait_for_workflow_state(
        active_client,
        workflow_address,
        program_id,
        timeout_seconds=rpc_wait_seconds,
    )
    mismatches = compare_batch_to_state(batch, state)
    if mismatches:
        raise RialoAnchorError(
            f"submitted workflow state differs from the batch: {', '.join(mismatches)}"
        )

    saved = save_receipt(
        receipt_dir,
        batch,
        program_id,
        signature,
        transaction,
        workflow_address,
        state,
    )
    pending_receipt_path(batch, receipt_dir).unlink(missing_ok=True)
    return saved, signature, workflow_address, cli_output


def batch_receipt_exists(batch_path: Path, receipt_dir: Path) -> bool:
    try:
        batch = json.loads(batch_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(batch, dict):
        return False
    try:
        return receipt_path(batch, receipt_dir).exists()
    except RialoAnchorError:
        return False


def list_batch_files(batch_dir: Path) -> list[Path]:
    return sorted(
        (path for path in batch_dir.glob("*/*.json") if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, str(path)),
    )


def watch_batches(args: argparse.Namespace) -> int:
    known = set() if args.include_existing else set(list_batch_files(args.batch_dir))
    retry_after: dict[Path, float] = {}
    if known:
        print(f"Watching for new batches; {len(known)} existing file(s) left untouched.")
    else:
        print("Watching for telemetry batches. Press Ctrl+C to stop.")

    try:
        while True:
            current = list_batch_files(args.batch_dir)
            now = time.monotonic()
            pending = [
                path
                for path in current
                if path not in known and now >= retry_after.get(path, 0.0)
            ]
            cycle_failed = False
            for path in pending:
                if batch_receipt_exists(path, args.receipt_dir):
                    known.add(path)
                    retry_after.pop(path, None)
                    print(f"[SKIP] {path}: Rialo receipt already exists")
                    continue
                print(f"[FOUND] {path}")
                try:
                    receipt, signature, workflow, _ = submit_batch(
                        path,
                        args.registry,
                        args.receipt_dir,
                        args.program_id,
                        args.rpc_url,
                        args.wsl_project_dir,
                        args.rpc_wait_seconds,
                    )
                except (RialoAnchorError, RialoVerificationError) as exc:
                    cycle_failed = True
                    retry_after[path] = time.monotonic() + args.retry_seconds
                    print(
                        f"[RETRY IN {args.retry_seconds:g}s] {path}: {exc}",
                        file=sys.stderr,
                    )
                    continue
                known.add(path)
                retry_after.pop(path, None)
                print(f"[ANCHORED] {signature}")
                print(f"[WORKFLOW] {workflow}")
                print(f"[RECEIPT] {receipt}")
            if args.once:
                return 1 if cycle_failed else 0
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--program-id", required=True)
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    parser.add_argument(
        "--registry", type=Path, default=Path("data/device_registry.json")
    )
    parser.add_argument(
        "--receipt-dir", type=Path, default=Path("data/receipts")
    )
    parser.add_argument("--wsl-project-dir", default=DEFAULT_WSL_PROJECT_DIR)
    parser.add_argument("--rpc-wait-seconds", type=float, default=90.0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    submit = subparsers.add_parser("submit", help="anchor one verified batch")
    submit.add_argument("batch", type=Path)
    submit.add_argument("--force", action="store_true")
    add_common_arguments(submit)

    watch = subparsers.add_parser("watch", help="anchor new batches as they appear")
    watch.add_argument("--batch-dir", type=Path, default=Path("data/batches"))
    watch.add_argument("--poll-seconds", type=float, default=2.0)
    watch.add_argument(
        "--retry-seconds",
        type=float,
        default=30.0,
        help="wait before retrying a batch after a transient anchoring failure",
    )
    watch.add_argument(
        "--include-existing",
        action="store_true",
        help="also submit existing unreceipted batches",
    )
    watch.add_argument("--once", action="store_true")
    add_common_arguments(watch)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "submit":
            receipt, signature, workflow, cli_output = submit_batch(
                args.batch,
                args.registry,
                args.receipt_dir,
                args.program_id,
                args.rpc_url,
                args.wsl_project_dir,
                args.rpc_wait_seconds,
                force=args.force,
            )
            if cli_output:
                print(cli_output)
            print("RIALO VERIFIED: submitted workflow state matches the batch")
            print(f"Workflow: {workflow}")
            print(f"Transaction: {signature}")
            print(f"Receipt: {receipt}")
            return 0
        if args.command == "watch":
            return watch_batches(args)
    except (KeyError, TypeError, ValueError, RialoAnchorError, RialoVerificationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
