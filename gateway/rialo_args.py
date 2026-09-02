#!/usr/bin/env python3
"""Create a Rialo Venus invocation command from a verified proof batch."""

from __future__ import annotations

import argparse
import json
import shlex
from hashlib import sha256
from pathlib import Path
from typing import Any

from gateway.edge_gateway import verify_batch_file


def hex_digest_to_u64_words(value: str) -> list[int]:
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError("digest is not valid hexadecimal") from exc
    if len(raw) != 32:
        raise ValueError("digest must contain exactly 32 bytes")
    return [int.from_bytes(raw[offset : offset + 8], "little") for offset in range(0, 32, 8)]


def device_id_to_u64(device_id: str) -> int:
    prefix = "edge-"
    if not device_id.startswith(prefix):
        raise ValueError("device_id must start with edge-")
    try:
        return int(device_id[len(prefix) :], 16)
    except ValueError as exc:
        raise ValueError("device_id suffix must be hexadecimal") from exc


def build_arguments(batch: dict[str, Any]) -> list[tuple[str, int]]:
    fingerprint_words = hex_digest_to_u64_words(
        batch["device_public_key_fingerprint"]
    )
    digest_words = hex_digest_to_u64_words(batch["proof"]["digest"])

    arguments: list[tuple[str, int]] = [
        ("device_id", device_id_to_u64(batch["device_id"])),
    ]
    arguments.extend(
        (f"public_key_fingerprint_{index}", value)
        for index, value in enumerate(fingerprint_words)
    )
    arguments.extend(
        (f"batch_digest_{index}", value)
        for index, value in enumerate(digest_words)
    )
    arguments.extend(
        [
            ("first_sequence", int(batch["first_sequence"])),
            ("last_sequence", int(batch["last_sequence"])),
            ("reading_count", int(batch["reading_count"])),
        ]
    )
    return arguments


def registration_workflow_slug(device_id: str) -> str:
    canonical_device_id = f"{device_id_to_u64(device_id):016x}"
    value = f"rialo-edge-log/device-registration/{canonical_device_id}"
    return sha256(value.encode("ascii")).hexdigest()


def build_registration_arguments(
    device_id: str, public_key_fingerprint: str
) -> list[tuple[str, int]]:
    arguments: list[tuple[str, int]] = [
        ("device_id", device_id_to_u64(device_id)),
    ]
    arguments.extend(
        (f"public_key_fingerprint_{index}", value)
        for index, value in enumerate(
            hex_digest_to_u64_words(public_key_fingerprint)
        )
    )
    return arguments


def build_registration_command(
    device_id: str,
    public_key_fingerprint: str,
    program_id: str,
    rpc_url: str | None = None,
) -> str:
    parts = [
        "rialo",
        "client",
        "program",
    ]
    if rpc_url:
        parts.extend(["--url", shlex.quote(rpc_url)])
    parts.extend(
        [
            "invoke",
            "--program-dir",
            "rialo/edge-log-proof",
            "--function",
            "register",
            "--arg",
            f"workflow_pda_slug={registration_workflow_slug(device_id)}",
        ]
    )
    for name, value in build_registration_arguments(
        device_id, public_key_fingerprint
    ):
        parts.extend(["--arg", f"{name}={value}"])
    parts.append(program_id)
    return " ".join(parts)


def build_command(
    batch: dict[str, Any], program_id: str, rpc_url: str | None = None
) -> str:
    parts = [
        "rialo",
        "client",
        "program",
    ]
    if rpc_url:
        parts.extend(["--url", shlex.quote(rpc_url)])
    parts.extend(
        [
            "invoke",
            "--program-dir",
            "rialo/edge-log-proof",
            "--function",
            "start",
            "--arg",
            "workflow_pda_slug=random",
        ]
    )
    for name, value in build_arguments(batch):
        parts.extend(["--arg", f"{name}={value}"])
    parts.append(program_id)
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("batch", type=Path)
    parser.add_argument(
        "--registry", type=Path, default=Path("data/device_registry.json")
    )
    parser.add_argument("--program-id", default="<PROGRAM_ID>")
    args = parser.parse_args()

    valid, message = verify_batch_file(args.batch, args.registry)
    if not valid:
        print(f"TAMPERED: {message}")
        return 1

    try:
        batch = json.loads(args.batch.read_text(encoding="utf-8"))
        command = build_command(batch, args.program_id)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1

    print(f"VERIFIED: {message}")
    print(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
