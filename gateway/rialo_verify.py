#!/usr/bin/env python3
"""Verify a historical local telemetry batch against Rialo DevNet state."""

from __future__ import annotations

import argparse
import base64
import json
import os
import struct
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gateway.edge_gateway import verify_batch_file
from gateway.rialo_args import device_id_to_u64


DEFAULT_RPC_URL = "http://devnet.rialo.io:4100"
WORKFLOW_STATE_SIZE = 104
KELVINS_PER_RLO = 1_000_000_000


class RialoVerificationError(RuntimeError):
    """Raised when Rialo data cannot be fetched or decoded safely."""


class RialoRpcClient:
    def __init__(self, url: str = DEFAULT_RPC_URL, timeout: float = 20.0) -> None:
        self.url = url
        self.timeout = timeout

    def call(self, method: str, params: list[dict[str, Any]]) -> Any:
        body = json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RialoVerificationError(f"Rialo RPC request failed: {exc}") from exc

        if not isinstance(payload, dict):
            raise RialoVerificationError("Rialo RPC returned an invalid response")
        if payload.get("error") is not None:
            error = payload["error"]
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise RialoVerificationError(f"Rialo RPC error: {message}")
        if "result" not in payload:
            raise RialoVerificationError("Rialo RPC response has no result")
        return payload["result"]

    def get_transaction(self, signature: str) -> dict[str, Any]:
        result = self.call("getTransaction", [{"signature": signature}])
        if not isinstance(result, dict):
            raise RialoVerificationError("Rialo transaction was not found")
        return result

    def get_account_info(self, address: str) -> dict[str, Any]:
        result = self.call(
            "getAccountInfo", [{"address": address, "encoding": "base64"}]
        )
        if not isinstance(result, dict) or not isinstance(result.get("value"), dict):
            raise RialoVerificationError("Rialo workflow account was not found")
        return result["value"]

    def get_balance(self, address: str) -> int:
        result = self.call("getBalance", [{"address": address}])
        value: Any = result
        if isinstance(value, dict):
            value = value.get("value", value.get("kelvins"))
        if isinstance(value, dict):
            value = value.get("kelvins", value.get("value"))
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RialoVerificationError("Rialo balance response is invalid")
        return value


def extract_fee_payer(transaction_result: dict[str, Any]) -> str:
    transaction = transaction_result.get("transaction")
    message = transaction.get("message") if isinstance(transaction, dict) else None
    account_keys = message.get("accountKeys") if isinstance(message, dict) else None
    if not isinstance(account_keys, list) or not account_keys:
        raise RialoVerificationError("transaction fee payer is missing")
    first = account_keys[0]
    if isinstance(first, str) and first:
        return first
    if isinstance(first, dict):
        address = first.get("pubkey")
        if isinstance(address, str) and address:
            return address
    raise RialoVerificationError("transaction fee payer is invalid")


def extract_workflow_address(
    transaction_result: dict[str, Any], program_id: str
) -> str:
    transaction = transaction_result.get("transaction")
    meta = transaction_result.get("meta")
    if not isinstance(transaction, dict) or not isinstance(meta, dict):
        raise RialoVerificationError("transaction response is incomplete")
    if meta.get("err") is not None:
        raise RialoVerificationError("Rialo transaction did not succeed")

    message = transaction.get("message")
    if not isinstance(message, dict):
        raise RialoVerificationError("transaction message is missing")
    account_keys = message.get("accountKeys")
    instructions = message.get("instructions")
    if not isinstance(account_keys, list) or not isinstance(instructions, list):
        raise RialoVerificationError("transaction accounts or instructions are missing")

    for instruction in instructions:
        if not isinstance(instruction, dict):
            continue
        program_index = instruction.get("programIdIndex")
        accounts = instruction.get("accounts")
        if (
            isinstance(program_index, int)
            and 0 <= program_index < len(account_keys)
            and account_keys[program_index] == program_id
            and isinstance(accounts, list)
            and len(accounts) >= 2
            and isinstance(accounts[1], int)
            and 0 <= accounts[1] < len(account_keys)
        ):
            address = account_keys[accounts[1]]
            if isinstance(address, str):
                return address
    raise RialoVerificationError("workflow account is not present in the transaction")


def decode_workflow_state(encoded: str) -> dict[str, Any]:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise RialoVerificationError("workflow state is not valid base64") from exc
    if len(raw) < WORKFLOW_STATE_SIZE:
        raise RialoVerificationError(
            f"workflow state is {len(raw)} bytes; expected at least {WORKFLOW_STATE_SIZE}"
        )

    values = struct.unpack_from("<13Q", raw)
    return {
        "discriminator": values[0],
        "device_id": values[1],
        "device_public_key_fingerprint": raw[16:48].hex(),
        "batch_digest": raw[48:80].hex(),
        "first_sequence": values[10],
        "last_sequence": values[11],
        "reading_count": values[12],
    }


def decode_account_state(account: dict[str, Any], program_id: str) -> dict[str, Any]:
    if account.get("owner") != program_id:
        raise RialoVerificationError("workflow account is owned by another program")
    data = account.get("data")
    if (
        not isinstance(data, list)
        or len(data) != 2
        or not isinstance(data[0], str)
        or data[1] != "base64"
    ):
        raise RialoVerificationError("workflow account data has an unsupported encoding")
    state = decode_workflow_state(data[0])
    if state["discriminator"] == 0:
        raise RialoVerificationError("workflow account is not initialized")
    return state


def compare_batch_to_state(
    batch: dict[str, Any], state: dict[str, Any]
) -> list[str]:
    expected = {
        "device_id": device_id_to_u64(batch["device_id"]),
        "device_public_key_fingerprint": batch[
            "device_public_key_fingerprint"
        ].lower(),
        "batch_digest": batch["proof"]["digest"].lower(),
        "first_sequence": int(batch["first_sequence"]),
        "last_sequence": int(batch["last_sequence"]),
        "reading_count": int(batch["reading_count"]),
    }
    return [
        name
        for name, expected_value in expected.items()
        if state.get(name) != expected_value
    ]


def save_receipt(
    directory: Path,
    batch: dict[str, Any],
    program_id: str,
    transaction_signature: str,
    transaction_result: dict[str, Any],
    workflow_address: str,
    state: dict[str, Any],
) -> Path:
    receipt = {
        "schema_version": 1,
        "verified_at_utc": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
        "batch_id": batch["batch_id"],
        "device_id": batch["device_id"],
        "program_id": program_id,
        "transaction_signature": transaction_signature,
        "workflow_address": workflow_address,
        "block_height": transaction_result.get("block_height"),
        "batch_digest": state["batch_digest"],
        "first_sequence": state["first_sequence"],
        "last_sequence": state["last_sequence"],
        "reading_count": state["reading_count"],
        "status": "RIALO_VERIFIED",
    }
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{batch['batch_id']}-rialo.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, destination)
    return destination


def load_verified_batch(path: Path, registry_path: Path) -> tuple[dict[str, Any], str]:
    valid, message = verify_batch_file(path, registry_path)
    if not valid:
        raise RialoVerificationError(f"local batch failed verification: {message}")
    try:
        batch = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RialoVerificationError(f"cannot read batch file: {exc}") from exc
    if not isinstance(batch, dict):
        raise RialoVerificationError("batch file must contain a JSON object")
    return batch, message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument("--transaction", required=True)
    parser.add_argument("--program-id", required=True)
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    parser.add_argument(
        "--registry", type=Path, default=Path("data/device_registry.json")
    )
    parser.add_argument(
        "--receipt-dir", type=Path, default=Path("data/receipts")
    )
    parser.add_argument("--no-receipt", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        batch, local_message = load_verified_batch(args.batch, args.registry)
        client = RialoRpcClient(args.rpc_url)
        transaction_result = client.get_transaction(args.transaction)
        workflow_address = extract_workflow_address(
            transaction_result, args.program_id
        )
        account = client.get_account_info(workflow_address)
        state = decode_account_state(account, args.program_id)
        mismatches = compare_batch_to_state(batch, state)
        if mismatches:
            print(f"RIALO MISMATCH: {', '.join(mismatches)}")
            return 1

        print(f"LOCAL VERIFIED: {local_message}")
        print("RIALO VERIFIED: workflow state matches the historical batch")
        print(f"Workflow: {workflow_address}")
        print(f"Transaction: {args.transaction}")
        if not args.no_receipt:
            receipt = save_receipt(
                args.receipt_dir,
                batch,
                args.program_id,
                args.transaction,
                transaction_result,
                workflow_address,
                state,
            )
            print(f"Receipt: {receipt}")
        return 0
    except (KeyError, TypeError, ValueError, RialoVerificationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
