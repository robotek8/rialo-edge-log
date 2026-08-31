#!/usr/bin/env python3
"""Generate a P-256 device key and an Arduino header outside Git."""

from __future__ import annotations

import argparse
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def format_byte_array(value: bytes) -> str:
    rows = []
    for offset in range(0, len(value), 8):
        chunk = value[offset : offset + 8]
        rows.append("    " + ", ".join(f"0x{byte:02X}" for byte in chunk))
    return ",\n".join(rows)


def generate_header(output: Path) -> str:
    if output.exists():
        raise FileExistsError(
            f"{output} already exists; it was not overwritten to avoid rotating the device key"
        )

    private_key = ec.generate_private_key(ec.SECP256R1())
    private_value = private_key.private_numbers().private_value.to_bytes(32, "big")
    public_value = private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )

    header = f"""#pragma once

#include <stdint.h>

// Generated locally. Never commit this file or reuse this key on another device.
static unsigned char DEVICE_PRIVATE_KEY[32] = {{
{format_byte_array(private_value)}
}};

static const char DEVICE_PUBLIC_KEY_HEX[] =
    \"{public_value.hex()}\";
"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(header, encoding="utf-8")
    return public_value.hex()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        public_key = generate_header(args.output)
    except (FileExistsError, OSError) as exc:
        print(f"Error: {exc}")
        return 1
    print(f"Created private device key: {args.output}")
    print(f"Public key: {public_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

