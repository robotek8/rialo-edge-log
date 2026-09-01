#!/usr/bin/env python3
"""Serve a local dashboard for inspecting and verifying Rialo Edge Log batches."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from copy import deepcopy
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.parse import unquote, urlparse

from gateway.edge_gateway import (
    SIGNED_SCHEMA_VERSIONS,
    TelemetryError,
    load_registry,
    verify_batch,
    verify_batch_file,
)
from gateway.rialo_verify import (
    DEFAULT_DEVICE_REGISTRAR,
    DEFAULT_RPC_URL,
    RialoRpcClient,
    RialoVerificationError,
    compare_batch_to_state,
    decode_account_state,
    extract_workflow_address,
    verify_registration_receipt,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
STATIC_FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/app.js": "app.js",
    "/verifier.js": "verifier.js",
    "/styles.css": "styles.css",
    "/github.svg": "github.svg",
    "/x.svg": "x.svg",
    "/telegram.svg": "telegram.svg",
    "/og-image.png": "og-image.png",
    "/fonts/Oswald-Variable.ttf": "fonts/Oswald-Variable.ttf",
    "/favicon.svg": "favicon.svg",
    "/favicon.ico": "favicon.ico",
    "/apple-touch-icon.png": "apple-touch-icon.png",
    "/icon-192.png": "icon-192.png",
    "/icon-512.png": "icon-512.png",
    "/site.webmanifest": "site.webmanifest",
}


class PortalError(RuntimeError):
    """Raised when local portal data cannot be read safely."""


def read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortalError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise PortalError(f"{path.name} must contain a JSON object")
    return value


def temperature_stats(readings: Any) -> dict[str, float | None]:
    if not isinstance(readings, list):
        return {"minimum": None, "average": None, "maximum": None}
    values = [
        float(reading["temperature_c"])
        for reading in readings
        if isinstance(reading, dict)
        and isinstance(reading.get("temperature_c"), (int, float))
        and not isinstance(reading.get("temperature_c"), bool)
    ]
    if not values:
        return {"minimum": None, "average": None, "maximum": None}
    return {
        "minimum": min(values),
        "average": sum(values) / len(values),
        "maximum": max(values),
    }


class PortalStore:
    """Read local batches and run local or live Rialo verification."""

    def __init__(
        self,
        data_directory: Path = Path("data"),
        registry_path: Path | None = None,
        rpc_url: str = DEFAULT_RPC_URL,
        client_factory: Callable[[str], RialoRpcClient] | None = None,
        expected_device_registrar: str = DEFAULT_DEVICE_REGISTRAR,
    ) -> None:
        self.data_directory = data_directory
        self.batch_directory = data_directory / "batches"
        self.receipt_directory = data_directory / "receipts"
        self.registration_directory = data_directory / "registrations"
        self.registry_path = registry_path or data_directory / "device_registry.json"
        self.rpc_url = rpc_url
        self.client_factory = client_factory or (lambda url: RialoRpcClient(url))
        self.expected_device_registrar = expected_device_registrar

    def _batch_paths(self) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        if not self.batch_directory.exists():
            return paths
        for path in self.batch_directory.glob("*/*.json"):
            if not path.is_file():
                continue
            try:
                batch = read_json_object(path)
            except PortalError:
                continue
            batch_id = batch.get("batch_id")
            if isinstance(batch_id, str) and batch_id and batch_id not in paths:
                paths[batch_id] = path
        return paths

    def _batch_path(self, batch_id: str) -> Path:
        path = self._batch_paths().get(batch_id)
        if path is None:
            raise PortalError("batch was not found")
        return path

    def _receipt_path(self, batch_id: str) -> Path:
        return self.receipt_directory / f"{batch_id}-rialo.json"

    def _load_receipt(self, batch_id: str) -> dict[str, Any] | None:
        path = self._receipt_path(batch_id)
        if not path.is_file():
            return None
        receipt = read_json_object(path)
        if receipt.get("batch_id") != batch_id:
            raise PortalError("receipt belongs to another batch")
        return receipt

    def _load_registration(self, device_id: str) -> dict[str, Any] | None:
        path = self.registration_directory / f"{device_id}-rialo-registration.json"
        if not path.is_file():
            return None
        receipt = read_json_object(path)
        if receipt.get("device_id") != device_id:
            raise PortalError("device registration belongs to another device")
        return receipt

    def _summary(
        self, batch: dict[str, Any], receipt: dict[str, Any] | None
    ) -> dict[str, Any]:
        readings = batch.get("readings")
        normalized_readings = [
            reading for reading in readings or [] if isinstance(reading, dict)
        ] if isinstance(readings, list) else []
        boot_ids = [
            reading.get("boot_id")
            for reading in normalized_readings
            if reading.get("boot_id") is not None
        ]
        tamper_states = [
            reading.get("tamper_open")
            for reading in normalized_readings
            if isinstance(reading.get("tamper_open"), bool)
        ]
        return {
            "batch_id": batch.get("batch_id"),
            "device_id": batch.get("device_id"),
            "created_at_utc": batch.get("created_at_utc"),
            "first_sequence": batch.get("first_sequence"),
            "last_sequence": batch.get("last_sequence"),
            "reading_count": batch.get("reading_count"),
            "digest": (
                batch.get("proof", {}).get("digest")
                if isinstance(batch.get("proof"), dict)
                else None
            ),
            "temperature": temperature_stats(readings),
            "simulated": bool(
                isinstance(readings, list)
                and readings
                and all(
                    isinstance(reading, dict) and reading.get("simulated") is True
                    for reading in readings
                )
            ),
            "boot_id": boot_ids[-1] if boot_ids else None,
            "reset_reason": (
                normalized_readings[0].get("reset_reason")
                if normalized_readings else None
            ),
            "tamper_open": any(tamper_states) if tamper_states else None,
            "status": "ANCHORED" if receipt else "LOCAL_ONLY",
            "transaction_signature": (
                receipt.get("transaction_signature") if receipt else None
            ),
            "workflow_address": receipt.get("workflow_address") if receipt else None,
        }

    def list_batches(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for batch_id, path in self._batch_paths().items():
            try:
                batch = read_json_object(path)
                receipt = self._load_receipt(batch_id)
                summaries.append(self._summary(batch, receipt))
            except PortalError:
                continue
        summaries.sort(
            key=lambda item: (str(item.get("created_at_utc") or ""), item["batch_id"]),
            reverse=True,
        )
        return summaries

    def list_devices(self) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for batch in self.list_batches():
            device_id = batch.get("device_id")
            if isinstance(device_id, str):
                grouped.setdefault(device_id, []).append(batch)
        devices: list[dict[str, Any]] = []
        for device_id, batches in grouped.items():
            latest = batches[0]
            oldest = batches[-1]
            source = read_json_object(self._batch_path(latest["batch_id"]))
            devices.append(
                {
                    "device_id": device_id,
                    "public_key_fingerprint": source.get(
                        "device_public_key_fingerprint"
                    ),
                    "first_seen_utc": oldest.get("created_at_utc"),
                    "last_seen_utc": latest.get("created_at_utc"),
                    "batch_count": len(batches),
                    "last_sequence": latest.get("last_sequence"),
                    "latest_batch_utc": latest.get("created_at_utc"),
                    "latest_temperature_c": latest.get("temperature", {}).get(
                        "average"
                    ),
                }
            )
        devices.sort(
            key=lambda item: (str(item.get("last_seen_utc") or ""), item["device_id"]),
            reverse=True,
        )
        return devices

    def get_batch(self, batch_id: str) -> dict[str, Any]:
        batch = read_json_object(self._batch_path(batch_id))
        receipt = self._load_receipt(batch_id)
        detail = self._summary(batch, receipt)
        detail["readings"] = [
            {
                "sequence": reading.get("sequence"),
                "temperature_c": reading.get("temperature_c"),
                "uptime_ms": reading.get("uptime_ms"),
                "boot_id": reading.get("boot_id"),
                "reset_reason": reading.get("reset_reason"),
                "tamper_open": reading.get("tamper_open"),
                "simulated": reading.get("simulated"),
            }
            for reading in batch.get("readings", [])
            if isinstance(reading, dict)
        ]
        detail["public_key_fingerprint"] = batch.get(
            "device_public_key_fingerprint"
        )
        detail["receipt"] = receipt
        detail["proof_bundle"] = self.export_bundle(batch_id)
        return detail

    def export_bundle(self, batch_id: str) -> dict[str, Any]:
        batch = read_json_object(self._batch_path(batch_id))
        public_key = self._public_key(batch)
        registration = self._load_registration(str(batch.get("device_id")))
        bundle = {
            "schema_version": 2 if registration is not None else 1,
            "bundle_type": "rialo-edge-log-proof",
            "exported_at_utc": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "batch": batch,
            "device": {
                "device_id": batch.get("device_id"),
                "signature_algorithm": "ecdsa-p256-sha256-raw",
                "public_key_sec1": public_key,
                "fingerprint_sha256": batch.get(
                    "device_public_key_fingerprint"
                ),
            },
            "rialo_receipt": self._load_receipt(batch_id),
        }
        if registration is not None:
            bundle["device_registration"] = registration
        return bundle

    def _public_key(self, batch: dict[str, Any]) -> str | None:
        if batch.get("schema_version") not in SIGNED_SCHEMA_VERSIONS:
            return None
        try:
            registry = load_registry(self.registry_path)
        except TelemetryError as exc:
            raise PortalError(str(exc)) from exc
        entry = registry["devices"].get(batch.get("device_id"))
        if not isinstance(entry, dict) or not isinstance(
            entry.get("public_key_sec1"), str
        ):
            raise PortalError("device public key is not present in the registry")
        return entry["public_key_sec1"]

    def verify(self, batch_id: str) -> dict[str, Any]:
        path = self._batch_path(batch_id)
        local_valid, local_message = verify_batch_file(path, self.registry_path)
        if not local_valid:
            return {
                "status": "TAMPERED",
                "message": local_message,
                "local_verified": False,
                "rialo_verified": False,
            }

        receipt = self._load_receipt(batch_id)
        if receipt is None:
            return {
                "status": "LOCAL_VERIFIED",
                "message": "Device signatures and local proof match. No Rialo receipt exists for this batch.",
                "local_verified": True,
                "rialo_verified": False,
            }

        return self.verify_bundle(self.export_bundle(batch_id))

    def _verify_against_rialo(
        self, batch: dict[str, Any], receipt: dict[str, Any]
    ) -> dict[str, Any]:
        if receipt.get("batch_id") != batch.get("batch_id"):
            return {
                "status": "INVALID_RECEIPT",
                "message": "The Rialo receipt belongs to another batch.",
                "local_verified": True,
                "rialo_verified": False,
            }
        required = {
            "program_id",
            "transaction_signature",
            "workflow_address",
        }
        if any(not isinstance(receipt.get(name), str) for name in required):
            return {
                "status": "INVALID_RECEIPT",
                "message": "The local Rialo receipt is incomplete.",
                "local_verified": True,
                "rialo_verified": False,
            }

        try:
            client = self.client_factory(self.rpc_url)
            transaction = client.get_transaction(receipt["transaction_signature"])
            workflow = extract_workflow_address(transaction, receipt["program_id"])
            if workflow != receipt["workflow_address"]:
                return {
                    "status": "TAMPERED",
                    "message": "The transaction points to a different workflow account than the receipt.",
                    "local_verified": True,
                    "rialo_verified": False,
                }
            state = decode_account_state(
                client.get_account_info(workflow), receipt["program_id"]
            )
            mismatches = compare_batch_to_state(batch, state)
        except RialoVerificationError as exc:
            return {
                "status": "CHAIN_UNAVAILABLE",
                "message": f"Local proof matches, but Rialo could not be checked: {exc}",
                "local_verified": True,
                "rialo_verified": False,
            }

        if mismatches:
            return {
                "status": "TAMPERED",
                "message": "Rialo workflow differs from the local batch: "
                + ", ".join(mismatches),
                "local_verified": True,
                "rialo_verified": False,
            }
        return {
            "status": "RIALO_VERIFIED",
            "message": "Device signatures, local proof and historical Rialo workflow all match.",
            "local_verified": True,
            "rialo_verified": True,
            "transaction_signature": receipt["transaction_signature"],
            "workflow_address": workflow,
        }

    def verify_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        if (
            bundle.get("schema_version") not in {1, 2}
            or bundle.get("bundle_type") != "rialo-edge-log-proof"
            or not isinstance(bundle.get("batch"), dict)
            or not isinstance(bundle.get("device"), dict)
        ):
            raise PortalError("file is not a Rialo Edge Log proof bundle")

        batch = bundle["batch"]
        device = bundle["device"]
        if device.get("device_id") != batch.get("device_id"):
            return {
                "status": "TAMPERED",
                "message": "Device identity in the proof file does not match the batch.",
                "local_verified": False,
                "rialo_verified": False,
            }
        public_key = device.get("public_key_sec1")
        if batch.get("schema_version") in SIGNED_SCHEMA_VERSIONS and not isinstance(
            public_key, str
        ):
            return {
                "status": "TAMPERED",
                "message": "The proof file has no device public key.",
                "local_verified": False,
                "rialo_verified": False,
            }
        local_valid, local_message = verify_batch(batch, public_key)
        if not local_valid:
            return {
                "status": "TAMPERED",
                "message": local_message,
                "local_verified": False,
                "rialo_verified": False,
            }

        receipt = bundle.get("rialo_receipt")
        if receipt is None:
            return {
                "status": "LOCAL_VERIFIED",
                "message": "Device signatures and batch proof match, but this file has no Rialo receipt.",
                "local_verified": True,
                "rialo_verified": False,
            }
        if not isinstance(receipt, dict):
            return {
                "status": "INVALID_RECEIPT",
                "message": "The Rialo receipt in the proof file is malformed.",
                "local_verified": True,
                "rialo_verified": False,
            }
        result = self._verify_against_rialo(batch, receipt)
        if result.get("status") != "RIALO_VERIFIED":
            return result
        if bundle.get("schema_version") == 1:
            result["device_registration_verified"] = False
            return result

        registration = bundle.get("device_registration")
        if not isinstance(registration, dict):
            return {
                "status": "INVALID_RECEIPT",
                "message": "The proof file has no on-chain device registration.",
                "local_verified": True,
                "rialo_verified": False,
                "device_registration_verified": False,
            }
        fingerprint = batch.get("device_public_key_fingerprint")
        if not isinstance(fingerprint, str):
            return {
                "status": "TAMPERED",
                "message": "The device fingerprint is missing.",
                "local_verified": True,
                "rialo_verified": False,
                "device_registration_verified": False,
            }
        try:
            verified_registration = verify_registration_receipt(
                str(batch.get("device_id")),
                fingerprint,
                registration,
                self.client_factory(self.rpc_url),
                expected_program_id=receipt.get("program_id"),
                expected_registrar=self.expected_device_registrar,
            )
        except RialoVerificationError as exc:
            return {
                "status": "CHAIN_UNAVAILABLE",
                "message": f"Batch proof matches, but device registration could not be checked: {exc}",
                "local_verified": True,
                "rialo_verified": False,
                "device_registration_verified": False,
            }
        result.update(
            {
                "message": "Device registration, signatures, batch proof and historical Rialo workflow all match.",
                "device_registration_verified": True,
                "registration_transaction_signature": verified_registration[
                    "transaction_signature"
                ],
                "registration_workflow_address": verified_registration[
                    "workflow_address"
                ],
                "registration_registrar": verified_registration["registrar"],
            }
        )
        return result

    def simulate_tampering(self, batch_id: str) -> dict[str, Any]:
        batch = read_json_object(self._batch_path(batch_id))
        readings = batch.get("readings")
        if not isinstance(readings, list) or not readings:
            raise PortalError("batch has no reading to modify")
        changed = deepcopy(batch)
        temperature = changed["readings"][0].get("temperature_c")
        if not isinstance(temperature, (int, float)) or isinstance(temperature, bool):
            raise PortalError("first reading has no numeric temperature")
        changed["readings"][0]["temperature_c"] = float(temperature) + 1.0
        if isinstance(changed["readings"][0].get("temperature_milli_c"), int):
            changed["readings"][0]["temperature_milli_c"] += 1000
        valid, message = verify_batch(changed, self._public_key(batch))
        return {
            "status": "UNEXPECTED_VALID" if valid else "TAMPERED",
            "message": (
                "In-memory copy unexpectedly passed verification."
                if valid
                else f"Tampering detected in an in-memory copy: {message}. The original file was not changed."
            ),
            "original_file_changed": False,
        }


class PortalHandler(BaseHTTPRequestHandler):
    store: PortalStore
    static_directory: Path

    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write("[portal] " + format % args + "\n")

    def _send_json(
        self,
        value: Any,
        status: HTTPStatus = HTTPStatus.OK,
        filename: str | None = None,
    ) -> None:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{filename}"'
            )
        self.end_headers()
        self.wfile.write(payload)

    def _send_error_json(self, message: str, status: HTTPStatus) -> None:
        self._send_json({"error": message}, status)

    def _send_static(self, request_path: str) -> None:
        filename = STATIC_FILES.get(request_path)
        if filename is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        path = self.static_directory / filename
        try:
            payload = path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {
            "application/javascript",
            "image/svg+xml",
        }:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self' https://devnet.rialoscan.org; "
            "base-uri 'none'; frame-ancestors 'none'",
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    @staticmethod
    def _batch_action(path: str) -> tuple[str, str] | None:
        prefix = "/api/batches/"
        if not path.startswith(prefix):
            return None
        remainder = path[len(prefix) :]
        if not remainder:
            return None
        parts = remainder.split("/")
        batch_id = unquote(parts[0])
        action = parts[1] if len(parts) == 2 else "detail" if len(parts) == 1 else ""
        if not batch_id or not action:
            return None
        return batch_id, action

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/batches":
                batches = self.store.list_batches()
                self._send_json({"batches": batches, "count": len(batches)})
                return
            if path == "/api/devices":
                devices = self.store.list_devices()
                self._send_json({"devices": devices, "count": len(devices)})
                return
            if path.startswith("/api/devices/"):
                device_id = unquote(path[len("/api/devices/") :]).strip("/")
                if not device_id or "/" in device_id:
                    raise PortalError("device was not found")
                batches = [
                    batch
                    for batch in self.store.list_batches()
                    if batch.get("device_id") == device_id
                ]
                self._send_json(
                    {"device_id": device_id, "batches": batches, "count": len(batches)}
                )
                return
            action = self._batch_action(path)
            if action and action[1] == "detail":
                self._send_json(self.store.get_batch(action[0]))
                return
            if action and action[1] == "export":
                bundle = self.store.export_bundle(action[0])
                self._send_json(bundle, filename=f"{action[0]}-proof.json")
                return
            self._send_static(path)
        except PortalError as exc:
            self._send_error_json(str(exc), HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/verify-bundle":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 2_000_000:
                    raise PortalError("proof file must be between 1 byte and 2 MB")
                value = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(value, dict):
                    raise PortalError("proof file must contain a JSON object")
                self._send_json(self.store.verify_bundle(value))
            except (UnicodeDecodeError, json.JSONDecodeError, PortalError) as exc:
                self._send_error_json(str(exc), HTTPStatus.BAD_REQUEST)
            return
        action = self._batch_action(path)
        if action is None or action[1] not in {"verify", "tamper-demo"}:
            self._send_error_json("endpoint was not found", HTTPStatus.NOT_FOUND)
            return
        try:
            result = (
                self.store.verify(action[0])
                if action[1] == "verify"
                else self.store.simulate_tampering(action[0])
            )
            self._send_json(result)
        except PortalError as exc:
            self._send_error_json(str(exc), HTTPStatus.NOT_FOUND)


def handler_factory(
    store: PortalStore, static_directory: Path
) -> type[PortalHandler]:
    class ConfiguredPortalHandler(PortalHandler):
        pass

    ConfiguredPortalHandler.store = store
    ConfiguredPortalHandler.static_directory = static_directory
    return ConfiguredPortalHandler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "portal",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.static_dir.is_dir():
        print(f"ERROR: portal assets were not found: {args.static_dir}", file=sys.stderr)
        return 1
    store = PortalStore(args.data_dir, args.registry, args.rpc_url)
    server = ThreadingHTTPServer(
        (args.host, args.port), handler_factory(store, args.static_dir)
    )
    print(f"Rialo Edge Log portal: http://{args.host}:{server.server_port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
