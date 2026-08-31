#!/usr/bin/env python3
"""Read signed ESP8266 telemetry, create proof batches, and verify them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature


SCHEMA_VERSION_UNSIGNED = 1
SCHEMA_VERSION_SIGNED = 2
REGISTRY_SCHEMA_VERSION = 1
SIGNATURE_ALGORITHM = "ecdsa-p256-sha256-raw"
DEFAULT_BAUD_RATE = 115200
DEFAULT_BATCH_SIZE = 60
DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
HEX_PATTERN = re.compile(r"^[0-9a-fA-F]+$")


class TelemetryError(ValueError):
    """Raised when telemetry, registration, or a batch is invalid."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def validate_device_id(value: Any) -> str:
    if not isinstance(value, str) or not DEVICE_ID_PATTERN.fullmatch(value):
        raise TelemetryError("device_id contains unsupported characters")
    return value


def parse_telemetry_line(line: str) -> dict[str, Any]:
    """Parse and normalize one JSON telemetry line."""
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise TelemetryError("line is not valid JSON") from exc

    if not isinstance(value, dict):
        raise TelemetryError("telemetry must be a JSON object")

    schema_version = value.get("schema_version")
    if isinstance(schema_version, bool) or schema_version not in {
        SCHEMA_VERSION_UNSIGNED,
        SCHEMA_VERSION_SIGNED,
    }:
        raise TelemetryError(f"unsupported schema_version: {schema_version!r}")

    required = {
        "schema_version",
        "device_id",
        "sequence",
        "uptime_ms",
        "temperature_c",
        "simulated",
    }
    if schema_version == SCHEMA_VERSION_SIGNED:
        required.update(
            {
                "message_type",
                "temperature_milli_c",
                "signature_algorithm",
                "signature",
            }
        )
    missing = sorted(required.difference(value))
    if missing:
        raise TelemetryError(f"missing fields: {', '.join(missing)}")

    device_id = validate_device_id(value["device_id"])

    sequence = value["sequence"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
        raise TelemetryError("sequence must be a positive integer")

    uptime_ms = value["uptime_ms"]
    if isinstance(uptime_ms, bool) or not isinstance(uptime_ms, int) or uptime_ms < 0:
        raise TelemetryError("uptime_ms must be a non-negative integer")

    temperature = value["temperature_c"]
    if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
        raise TelemetryError("temperature_c must be a number")
    if not -100.0 <= float(temperature) <= 200.0:
        raise TelemetryError("temperature_c is outside the accepted prototype range")

    simulated = value["simulated"]
    if not isinstance(simulated, bool):
        raise TelemetryError("simulated must be true or false")

    normalized: dict[str, Any] = {
        "schema_version": schema_version,
        "device_id": device_id,
        "sequence": sequence,
        "uptime_ms": uptime_ms,
        "temperature_c": float(temperature),
        "simulated": simulated,
    }

    if schema_version == SCHEMA_VERSION_SIGNED:
        if value["message_type"] != "telemetry":
            raise TelemetryError("signed reading message_type must be telemetry")

        temperature_milli_c = value["temperature_milli_c"]
        if (
            isinstance(temperature_milli_c, bool)
            or not isinstance(temperature_milli_c, int)
            or not -100_000 <= temperature_milli_c <= 200_000
        ):
            raise TelemetryError("temperature_milli_c is invalid")
        if abs(float(temperature) * 1000.0 - temperature_milli_c) > 0.51:
            raise TelemetryError("temperature fields do not represent the same value")

        if value["signature_algorithm"] != SIGNATURE_ALGORITHM:
            raise TelemetryError("unsupported signature algorithm")
        signature = value["signature"]
        if (
            not isinstance(signature, str)
            or len(signature) != 128
            or not HEX_PATTERN.fullmatch(signature)
        ):
            raise TelemetryError("signature must be a 64-byte hexadecimal value")

        normalized.update(
            {
                "message_type": "telemetry",
                "temperature_milli_c": temperature_milli_c,
                "signature_algorithm": SIGNATURE_ALGORITHM,
                "signature": signature.lower(),
            }
        )

    return normalized


def parse_registration_line(line: str) -> dict[str, str | int]:
    try:
        value = json.loads(line)
    except json.JSONDecodeError as exc:
        raise TelemetryError("registration is not valid JSON") from exc
    if not isinstance(value, dict):
        raise TelemetryError("registration must be a JSON object")

    required = {
        "message_type",
        "schema_version",
        "device_id",
        "signature_algorithm",
        "public_key_sec1",
    }
    missing = sorted(required.difference(value))
    if missing:
        raise TelemetryError(f"registration missing fields: {', '.join(missing)}")
    if value["message_type"] != "device_registration":
        raise TelemetryError("message_type is not device_registration")
    if value["schema_version"] != REGISTRY_SCHEMA_VERSION:
        raise TelemetryError("unsupported registration schema")
    device_id = validate_device_id(value["device_id"])
    if value["signature_algorithm"] != SIGNATURE_ALGORITHM:
        raise TelemetryError("unsupported registration signature algorithm")

    public_key_hex = value["public_key_sec1"]
    if (
        not isinstance(public_key_hex, str)
        or len(public_key_hex) != 130
        or not public_key_hex.startswith("04")
        or not HEX_PATTERN.fullmatch(public_key_hex)
    ):
        raise TelemetryError("public key must be an uncompressed P-256 SEC1 point")

    try:
        ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), bytes.fromhex(public_key_hex)
        )
    except ValueError as exc:
        raise TelemetryError(f"public key cannot be loaded: {exc}") from exc

    return {
        "message_type": "device_registration",
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "device_id": device_id,
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "public_key_sec1": public_key_hex.lower(),
    }


def canonical_reading_payload(reading: dict[str, Any]) -> bytes:
    if reading.get("schema_version") != SCHEMA_VERSION_SIGNED:
        raise TelemetryError("only signed schema version 2 has a signature payload")
    return (
        f"2|{reading['device_id']}|{reading['sequence']}|{reading['uptime_ms']}|"
        f"{reading['temperature_milli_c']}|{1 if reading['simulated'] else 0}"
    ).encode("ascii")


def verify_reading_signature(reading: dict[str, Any], public_key_hex: str) -> bool:
    try:
        public_key = ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256R1(), bytes.fromhex(public_key_hex)
        )
        raw_signature = bytes.fromhex(reading["signature"])
        r_value = int.from_bytes(raw_signature[:32], "big")
        s_value = int.from_bytes(raw_signature[32:], "big")
        der_signature = encode_dss_signature(r_value, s_value)
        public_key.verify(
            der_signature,
            canonical_reading_payload(reading),
            ec.ECDSA(hashes.SHA256()),
        )
        return True
    except (InvalidSignature, KeyError, TypeError, ValueError, TelemetryError):
        return False


def public_key_fingerprint(public_key_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()


def empty_registry() -> dict[str, Any]:
    return {"schema_version": REGISTRY_SCHEMA_VERSION, "devices": {}}


def load_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_registry()
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TelemetryError(f"cannot read device registry: {exc}") from exc
    if (
        not isinstance(registry, dict)
        or registry.get("schema_version") != REGISTRY_SCHEMA_VERSION
        or not isinstance(registry.get("devices"), dict)
    ):
        raise TelemetryError("device registry has an invalid structure")
    return registry


def save_registry(registry: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def enroll_registration(
    registry: dict[str, Any], registration: dict[str, Any]
) -> tuple[bool, str]:
    device_id = registration["device_id"]
    public_key_hex = registration["public_key_sec1"]
    existing = registry["devices"].get(device_id)
    if existing is not None:
        if existing.get("public_key_sec1") != public_key_hex:
            return False, "registered device presented a different public key"
        return True, "device public key already enrolled"

    registry["devices"][device_id] = {
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "public_key_sec1": public_key_hex,
        "fingerprint_sha256": public_key_fingerprint(public_key_hex),
        "enrolled_at_utc": isoformat_utc(utc_now()),
        "trust_model": "local-trust-on-first-use",
    }
    return True, "new device public key enrolled locally"


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def proof_payload(batch: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "schema_version": batch["schema_version"],
        "batch_id": batch["batch_id"],
        "device_id": batch["device_id"],
        "first_sequence": batch["first_sequence"],
        "last_sequence": batch["last_sequence"],
        "reading_count": batch["reading_count"],
        "readings": batch["readings"],
    }
    if "device_public_key_fingerprint" in batch:
        payload["device_public_key_fingerprint"] = batch[
            "device_public_key_fingerprint"
        ]
    return payload


def calculate_proof(batch: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(proof_payload(batch))).hexdigest()


def create_batch(
    readings: Iterable[dict[str, Any]],
    created_at: datetime | None = None,
    public_key_hex: str | None = None,
) -> dict[str, Any]:
    normalized = list(readings)
    if not normalized:
        raise TelemetryError("cannot create an empty batch")

    device_id = normalized[0]["device_id"]
    if any(reading["device_id"] != device_id for reading in normalized):
        raise TelemetryError("a batch cannot contain multiple device IDs")

    sequences = [reading["sequence"] for reading in normalized]
    if any(current <= previous for previous, current in zip(sequences, sequences[1:])):
        raise TelemetryError("reading sequences must increase within a batch")

    timestamp = created_at or utc_now()
    compact_timestamp = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    batch_id = f"{device_id}-{sequences[0]}-{sequences[-1]}-{compact_timestamp}"

    batch: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION_SIGNED if public_key_hex else SCHEMA_VERSION_UNSIGNED,
        "batch_id": batch_id,
        "device_id": device_id,
        "created_at_utc": isoformat_utc(timestamp),
        "first_sequence": sequences[0],
        "last_sequence": sequences[-1],
        "reading_count": len(normalized),
        "readings": normalized,
    }
    if public_key_hex:
        batch["device_public_key_fingerprint"] = public_key_fingerprint(public_key_hex)

    batch["proof"] = {
        "version": 2 if public_key_hex else 1,
        "algorithm": "sha256",
        "digest": calculate_proof(batch),
        "device_signatures_verified": bool(public_key_hex),
        "anchored_on_rialo": False,
    }
    return batch


def save_batch(batch: dict[str, Any], data_directory: Path) -> Path:
    batches_directory = data_directory / "batches" / batch["device_id"]
    batches_directory.mkdir(parents=True, exist_ok=True)
    destination = batches_directory / f"{batch['batch_id']}.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(batch, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, destination)
    return destination


def verify_batch(
    batch: dict[str, Any], public_key_hex: str | None = None
) -> tuple[bool, str]:
    try:
        readings = batch["readings"]
        if not isinstance(readings, list) or not readings:
            return False, "readings are missing or empty"
        normalized = [
            parse_telemetry_line(json.dumps(reading, allow_nan=False))
            for reading in readings
        ]

        if batch["device_id"] != normalized[0]["device_id"]:
            return False, "batch device_id does not match its readings"
        if any(reading["device_id"] != batch["device_id"] for reading in normalized):
            return False, "batch contains a reading from another device"
        if batch["first_sequence"] != normalized[0]["sequence"]:
            return False, "first_sequence does not match the readings"
        if batch["last_sequence"] != normalized[-1]["sequence"]:
            return False, "last_sequence does not match the readings"
        if batch["reading_count"] != len(normalized):
            return False, "reading_count does not match the readings"

        sequences = [reading["sequence"] for reading in normalized]
        if any(current <= previous for previous, current in zip(sequences, sequences[1:])):
            return False, "reading sequences do not increase"

        signed = normalized[0]["schema_version"] == SCHEMA_VERSION_SIGNED
        if any(
            (reading["schema_version"] == SCHEMA_VERSION_SIGNED) != signed
            for reading in normalized
        ):
            return False, "batch mixes signed and unsigned readings"
        expected_batch_schema = SCHEMA_VERSION_SIGNED if signed else SCHEMA_VERSION_UNSIGNED
        if batch.get("schema_version") != expected_batch_schema:
            return False, "batch schema version does not match its readings"

        if signed:
            if not public_key_hex:
                return False, "device public key is not available"
            fingerprint = public_key_fingerprint(public_key_hex)
            if batch.get("device_public_key_fingerprint") != fingerprint:
                return False, "batch public-key fingerprint does not match the registry"
            if not all(
                verify_reading_signature(reading, public_key_hex)
                for reading in normalized
            ):
                return False, "one or more device signatures are invalid"

        proof = batch["proof"]
        if proof["algorithm"] != "sha256":
            return False, "unsupported proof algorithm"
        expected = proof["digest"]
        actual = calculate_proof(batch)
        if not isinstance(expected, str) or expected != actual:
            return False, "SHA-256 proof does not match the batch"
    except (KeyError, TypeError, ValueError, TelemetryError) as exc:
        return False, f"invalid batch structure: {exc}"

    prefix = "device signatures and local proof match" if signed else "local proof matches"
    if batch["proof"].get("anchored_on_rialo") is not True:
        return True, f"{prefix}; Rialo proof was not checked"
    return True, f"{prefix}; proof is marked as anchored"


def verify_batch_file(path: Path, registry_path: Path | None = None) -> tuple[bool, str]:
    try:
        batch = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"cannot read batch file: {exc}"
    if not isinstance(batch, dict):
        return False, "batch file must contain a JSON object"

    public_key_hex: str | None = None
    if batch.get("schema_version") == SCHEMA_VERSION_SIGNED:
        if registry_path is None:
            return False, "device registry path is required for a signed batch"
        try:
            registry = load_registry(registry_path)
            entry = registry["devices"].get(batch.get("device_id"))
            if entry:
                public_key_hex = entry.get("public_key_sec1")
        except TelemetryError as exc:
            return False, str(exc)
    return verify_batch(batch, public_key_hex)


def import_serial_modules() -> tuple[Any, Any]:
    try:
        import serial  # type: ignore[import-not-found]
        from serial.tools import list_ports  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "dependencies are missing; install them with: "
            "python -m pip install -r gateway/requirements.txt"
        ) from exc
    return serial, list_ports


def list_serial_ports() -> int:
    _, list_ports = import_serial_modules()
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return 1
    for port in ports:
        print(f"{port.device}: {port.description}")
    return 0


def open_serial_connection(serial_module: Any, port: str, baud_rate: int) -> Any:
    """Open a serial port without deliberately toggling NodeMCU reset lines."""
    connection = serial_module.Serial(
        port=None,
        baudrate=baud_rate,
        timeout=1,
        dsrdtr=False,
        rtscts=False,
    )
    connection.dtr = False
    connection.rts = False
    connection.port = port
    connection.open()
    connection.reset_input_buffer()
    return connection


def decode_serial_line(raw: bytes) -> str | None:
    """Drop boot noise and recover a JSON record that starts mid-line."""
    raw = raw.strip()
    if not raw:
        return None

    json_start = raw.find(b"{")
    if json_start >= 0:
        raw = raw[json_start:]

    try:
        return raw.decode("utf-8").strip() or None
    except UnicodeDecodeError:
        return None


def listen_to_serial(
    port: str,
    baud_rate: int,
    batch_size: int,
    data_directory: Path,
    registry_path: Path,
) -> int:
    if batch_size < 1:
        raise ValueError("batch size must be at least one")

    serial, _ = import_serial_modules()
    registry = load_registry(registry_path)
    buffer: list[dict[str, Any]] = []
    previous_sequence: int | None = None
    active_device: str | None = None

    print(f"Listening on {port} at {baud_rate} baud. Press Ctrl+C to stop.")
    print(f"A signed proof batch will be written every {batch_size} readings.")

    try:
        with open_serial_connection(serial, port, baud_rate) as connection:
            while True:
                raw = connection.readline()
                if not raw:
                    continue
                line = decode_serial_line(raw)
                if not line:
                    continue
                if not line.startswith("{"):
                    print(f"[DEVICE] {line}")
                    continue

                try:
                    envelope = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[REJECTED] line is not valid JSON: {line}")
                    continue

                if isinstance(envelope, dict) and envelope.get("message_type") == "device_registration":
                    try:
                        registration = parse_registration_line(line)
                        enrolled, message = enroll_registration(registry, registration)
                    except TelemetryError as exc:
                        print(f"[REJECTED] {exc}")
                        continue
                    if not enrolled:
                        print(f"[SECURITY] {message}")
                        continue
                    save_registry(registry, registry_path)
                    fingerprint = public_key_fingerprint(registration["public_key_sec1"])
                    print(f"[ENROLLED] {registration['device_id']} key={fingerprint[:16]}...")
                    continue

                try:
                    reading = parse_telemetry_line(line)
                except TelemetryError as exc:
                    print(f"[REJECTED] {exc}: {line}")
                    continue

                if reading["schema_version"] != SCHEMA_VERSION_SIGNED:
                    print("[REJECTED] unsigned telemetry; flash the signed firmware")
                    continue

                entry = registry["devices"].get(reading["device_id"])
                if not entry:
                    print("[REJECTED] device public key is not enrolled; reset the NodeMCU")
                    continue
                public_key_hex = entry["public_key_sec1"]
                if not verify_reading_signature(reading, public_key_hex):
                    print(f"[SECURITY] invalid signature from {reading['device_id']}")
                    continue

                if active_device is not None and reading["device_id"] != active_device:
                    print("[WARNING] Device changed; discarding the unfinished batch.")
                    buffer.clear()
                    previous_sequence = None
                if previous_sequence is not None and reading["sequence"] <= previous_sequence:
                    print("[WARNING] Sequence restarted; discarding the unfinished batch.")
                    buffer.clear()

                active_device = reading["device_id"]
                previous_sequence = reading["sequence"]
                buffer.append(reading)
                print(
                    f"[SIGNED {len(buffer):02d}/{batch_size:02d}] "
                    f"{reading['device_id']} seq={reading['sequence']} "
                    f"temperature={reading['temperature_c']:.3f} C"
                )

                if len(buffer) >= batch_size:
                    batch = create_batch(buffer, public_key_hex=public_key_hex)
                    path = save_batch(batch, data_directory)
                    print(f"[BATCH] {batch['proof']['digest']}")
                    print(f"[SAVED] {path}")
                    buffer.clear()
    except KeyboardInterrupt:
        print("\nStopped.")
    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        print("Close Arduino Serial Monitor and check the COM port.", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ports", help="list available serial ports")

    listen = subparsers.add_parser("listen", help="collect signed serial telemetry")
    listen.add_argument("--port", required=True, help="serial port, for example COM5")
    listen.add_argument("--baud", type=int, default=DEFAULT_BAUD_RATE)
    listen.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    listen.add_argument("--data-dir", type=Path, default=Path("data"))
    listen.add_argument("--registry", type=Path)

    verify = subparsers.add_parser("verify", help="verify one saved batch")
    verify.add_argument("path", type=Path)
    verify.add_argument(
        "--registry", type=Path, default=Path("data/device_registry.json")
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "ports":
            return list_serial_ports()
        if args.command == "listen":
            registry_path = args.registry or args.data_dir / "device_registry.json"
            return listen_to_serial(
                args.port, args.baud, args.batch_size, args.data_dir, registry_path
            )
        if args.command == "verify":
            valid, message = verify_batch_file(args.path, args.registry)
            status = "VERIFIED" if valid else "TAMPERED"
            print(f"{status}: {message}")
            return 0 if valid else 1
    except (RuntimeError, ValueError, TelemetryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
