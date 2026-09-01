#!/usr/bin/env python3
"""Serve an immutable public archive of Rialo-verified telemetry batches."""

from __future__ import annotations

import argparse
import hmac
import json
import mimetypes
import os
import sqlite3
import sys
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence
from urllib.parse import unquote, urlparse

from gateway.edge_gateway import (
    SIGNED_SCHEMA_VERSIONS,
    parse_telemetry_line,
    public_key_fingerprint,
    verify_reading_signature,
)
from gateway.portal import PortalError, PortalStore, temperature_stats
from gateway.rialo_verify import (
    DEFAULT_DEVICE_REGISTRAR,
    DEFAULT_RPC_URL,
    KELVINS_PER_RLO,
    RialoRpcClient,
    RialoVerificationError,
    extract_fee_payer,
)


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8090
MAX_INGEST_BYTES = 2_000_000
MAX_HEARTBEAT_BYTES = 32_000
TOKEN_ENVIRONMENT_VARIABLE = "RIALO_EDGE_LOG_INGEST_TOKEN"
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


class ArchiveError(RuntimeError):
    """Raised when an archive operation cannot be completed safely."""


def utc_now_text() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class ArchiveStore:
    def __init__(
        self,
        database_path: Path,
        rpc_url: str = DEFAULT_RPC_URL,
        client_factory: Callable[[str], RialoRpcClient] | None = None,
        expected_device_registrar: str = DEFAULT_DEVICE_REGISTRAR,
    ) -> None:
        self.database_path = database_path
        self.rpc_url = rpc_url
        self.client_factory = client_factory
        self.expected_device_registrar = expected_device_registrar
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    public_key_sec1 TEXT NOT NULL,
                    public_key_fingerprint TEXT NOT NULL,
                    first_seen_utc TEXT NOT NULL,
                    last_seen_utc TEXT NOT NULL,
                    batch_count INTEGER NOT NULL DEFAULT 0,
                    heartbeat_at_utc TEXT,
                    heartbeat_sequence INTEGER,
                    heartbeat_uptime_ms INTEGER,
                    heartbeat_boot_id INTEGER,
                    heartbeat_reset_reason TEXT,
                    heartbeat_tamper_open INTEGER,
                    heartbeat_temperature_c REAL
                );

                CREATE TABLE IF NOT EXISTS batches (
                    batch_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES devices(device_id),
                    created_at_utc TEXT NOT NULL,
                    first_sequence INTEGER NOT NULL,
                    last_sequence INTEGER NOT NULL,
                    reading_count INTEGER NOT NULL,
                    batch_digest TEXT NOT NULL,
                    transaction_signature TEXT NOT NULL,
                    workflow_address TEXT NOT NULL,
                    program_id TEXT NOT NULL,
                    ingested_at_utc TEXT NOT NULL,
                    bundle_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS batches_device_created
                ON batches(device_id, created_at_utc DESC);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(devices)").fetchall()
            }
            migrations = {
                "heartbeat_at_utc": "TEXT",
                "heartbeat_sequence": "INTEGER",
                "heartbeat_uptime_ms": "INTEGER",
                "heartbeat_boot_id": "INTEGER",
                "heartbeat_reset_reason": "TEXT",
                "heartbeat_tamper_open": "INTEGER",
                "heartbeat_temperature_c": "REAL",
            }
            for name, column_type in migrations.items():
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE devices ADD COLUMN {name} {column_type}"
                    )

    def _verifier(self) -> PortalStore:
        return PortalStore(
            Path("__archive_verifier__"),
            rpc_url=self.rpc_url,
            client_factory=self.client_factory,
            expected_device_registrar=self.expected_device_registrar,
        )

    def _client(self) -> RialoRpcClient:
        factory = self.client_factory or (lambda url: RialoRpcClient(url))
        return factory(self.rpc_url)

    @staticmethod
    def _normalized_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
        normalized = deepcopy(bundle)
        normalized.pop("exported_at_utc", None)
        return normalized

    def ingest(self, bundle: dict[str, Any]) -> dict[str, Any]:
        verification = self._verifier().verify_bundle(bundle)
        if verification.get("status") != "RIALO_VERIFIED":
            raise ArchiveError(
                "archive accepts only complete RIALO_VERIFIED bundles: "
                + str(verification.get("message") or verification.get("status"))
            )

        batch = bundle.get("batch")
        device = bundle.get("device")
        receipt = bundle.get("rialo_receipt")
        if not all(isinstance(value, dict) for value in (batch, device, receipt)):
            raise ArchiveError("proof bundle is incomplete")

        fields = {
            "batch_id": batch.get("batch_id"),
            "device_id": batch.get("device_id"),
            "created_at_utc": batch.get("created_at_utc"),
            "public_key_sec1": device.get("public_key_sec1"),
            "public_key_fingerprint": batch.get("device_public_key_fingerprint"),
            "batch_digest": (
                batch.get("proof", {}).get("digest")
                if isinstance(batch.get("proof"), dict)
                else None
            ),
            "transaction_signature": receipt.get("transaction_signature"),
            "workflow_address": receipt.get("workflow_address"),
            "program_id": receipt.get("program_id"),
        }
        if any(not isinstance(value, str) or not value for value in fields.values()):
            raise ArchiveError("proof bundle has missing identity or Rialo fields")
        for name in ("first_sequence", "last_sequence", "reading_count"):
            value = batch.get(name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ArchiveError(f"proof bundle has invalid {name}")

        normalized = self._normalized_bundle(bundle)
        serialized = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        ingested_at = utc_now_text()

        with self._connection() as connection:
            existing_device = connection.execute(
                "SELECT public_key_sec1, public_key_fingerprint FROM devices WHERE device_id = ?",
                (fields["device_id"],),
            ).fetchone()
            if existing_device and (
                existing_device["public_key_sec1"] != fields["public_key_sec1"]
                or existing_device["public_key_fingerprint"]
                != fields["public_key_fingerprint"]
            ):
                raise ArchiveError("device ID is already bound to another public key")

            existing_batch = connection.execute(
                "SELECT bundle_json FROM batches WHERE batch_id = ?",
                (fields["batch_id"],),
            ).fetchone()
            if existing_batch:
                if existing_batch["bundle_json"] != serialized:
                    raise ArchiveError("batch ID already exists with different contents")
                return {
                    "status": "ALREADY_PUBLISHED",
                    "batch_id": fields["batch_id"],
                    "device_id": fields["device_id"],
                }

            if existing_device is None:
                connection.execute(
                    """
                    INSERT INTO devices (
                        device_id, public_key_sec1, public_key_fingerprint,
                        first_seen_utc, last_seen_utc, batch_count
                    ) VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (
                        fields["device_id"],
                        fields["public_key_sec1"],
                        fields["public_key_fingerprint"],
                        batch["created_at_utc"],
                        batch["created_at_utc"],
                    ),
                )

            connection.execute(
                """
                INSERT INTO batches (
                    batch_id, device_id, created_at_utc, first_sequence,
                    last_sequence, reading_count, batch_digest,
                    transaction_signature, workflow_address, program_id,
                    ingested_at_utc, bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fields["batch_id"],
                    fields["device_id"],
                    fields["created_at_utc"],
                    batch["first_sequence"],
                    batch["last_sequence"],
                    batch["reading_count"],
                    fields["batch_digest"],
                    fields["transaction_signature"],
                    fields["workflow_address"],
                    fields["program_id"],
                    ingested_at,
                    serialized,
                ),
            )
            connection.execute(
                """
                UPDATE devices
                SET last_seen_utc = ?, batch_count = batch_count + 1
                WHERE device_id = ?
                """,
                (fields["created_at_utc"], fields["device_id"]),
            )

        return {
            "status": "PUBLISHED",
            "batch_id": fields["batch_id"],
            "device_id": fields["device_id"],
        }

    def ingest_heartbeat(self, heartbeat: dict[str, Any]) -> dict[str, Any]:
        if (
            heartbeat.get("message_type") != "device_heartbeat"
            or heartbeat.get("schema_version") != 1
        ):
            raise ArchiveError("heartbeat envelope is invalid")
        device_id = heartbeat.get("device_id")
        device = heartbeat.get("device")
        raw_reading = heartbeat.get("reading")
        if not isinstance(device_id, str) or not isinstance(device, dict) or not isinstance(raw_reading, dict):
            raise ArchiveError("heartbeat identity or reading is missing")
        public_key = device.get("public_key_sec1")
        fingerprint = device.get("fingerprint_sha256")
        if not isinstance(public_key, str) or not isinstance(fingerprint, str):
            raise ArchiveError("heartbeat public key is missing")
        if public_key_fingerprint(public_key) != fingerprint:
            raise ArchiveError("heartbeat public-key fingerprint does not match")
        try:
            reading = parse_telemetry_line(
                json.dumps(raw_reading, ensure_ascii=False, allow_nan=False)
            )
        except (TypeError, ValueError) as exc:
            raise ArchiveError(f"heartbeat telemetry is invalid: {exc}") from exc
        if reading["schema_version"] not in SIGNED_SCHEMA_VERSIONS:
            raise ArchiveError("heartbeat telemetry is not signed")
        if reading["device_id"] != device_id:
            raise ArchiveError("heartbeat device IDs do not match")
        if not verify_reading_signature(reading, public_key):
            raise ArchiveError("heartbeat signature is invalid")

        received_at = utc_now_text()
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT public_key_sec1, public_key_fingerprint FROM devices WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            if existing is None:
                raise ArchiveError("device must publish one verified batch before heartbeats")
            if (
                existing["public_key_sec1"] != public_key
                or existing["public_key_fingerprint"] != fingerprint
            ):
                raise ArchiveError("heartbeat key does not match the registered device")
            connection.execute(
                """
                UPDATE devices
                SET last_seen_utc = ?, heartbeat_at_utc = ?,
                    heartbeat_sequence = ?, heartbeat_uptime_ms = ?,
                    heartbeat_boot_id = ?, heartbeat_reset_reason = ?,
                    heartbeat_tamper_open = ?, heartbeat_temperature_c = ?
                WHERE device_id = ?
                """,
                (
                    received_at,
                    received_at,
                    reading["sequence"],
                    reading["uptime_ms"],
                    reading.get("boot_id"),
                    reading.get("reset_reason"),
                    int(reading["tamper_open"]) if "tamper_open" in reading else None,
                    reading["temperature_c"],
                    device_id,
                ),
            )
        return {
            "status": "HEARTBEAT_ACCEPTED",
            "device_id": device_id,
            "sequence": reading["sequence"],
            "received_at_utc": received_at,
        }

    @staticmethod
    def _batch_summary(row: sqlite3.Row) -> dict[str, Any]:
        bundle = json.loads(row["bundle_json"])
        batch = bundle["batch"]
        readings = [
            reading
            for reading in batch.get("readings", [])
            if isinstance(reading, dict)
        ]
        boot_ids = [reading.get("boot_id") for reading in readings if reading.get("boot_id") is not None]
        tamper_states = [
            reading.get("tamper_open")
            for reading in readings
            if isinstance(reading.get("tamper_open"), bool)
        ]
        return {
            "batch_id": row["batch_id"],
            "device_id": row["device_id"],
            "created_at_utc": row["created_at_utc"],
            "first_sequence": row["first_sequence"],
            "last_sequence": row["last_sequence"],
            "reading_count": row["reading_count"],
            "digest": row["batch_digest"],
            "transaction_signature": row["transaction_signature"],
            "workflow_address": row["workflow_address"],
            "temperature": temperature_stats(batch.get("readings")),
            "simulated": bool(
                readings
                and all(
                    reading.get("simulated") is True
                    for reading in readings
                )
            ),
            "boot_id": boot_ids[-1] if boot_ids else None,
            "reset_reason": readings[0].get("reset_reason") if readings else None,
            "tamper_open": any(tamper_states) if tamper_states else None,
            "status": "ANCHORED",
        }

    def list_devices(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT d.*, b.bundle_json, b.last_sequence, b.created_at_utc AS latest_batch_utc
                FROM devices d
                JOIN batches b ON b.batch_id = (
                    SELECT batch_id FROM batches
                    WHERE device_id = d.device_id
                    ORDER BY created_at_utc DESC, batch_id DESC LIMIT 1
                )
                ORDER BY d.last_seen_utc DESC, d.device_id
                """
            ).fetchall()
        devices = []
        for row in rows:
            bundle = json.loads(row["bundle_json"])
            stats = temperature_stats(bundle["batch"].get("readings"))
            devices.append(
                {
                    "device_id": row["device_id"],
                    "public_key_fingerprint": row["public_key_fingerprint"],
                    "first_seen_utc": row["first_seen_utc"],
                    "last_seen_utc": row["last_seen_utc"],
                    "latest_seen_utc": row["heartbeat_at_utc"] or row["latest_batch_utc"],
                    "batch_count": row["batch_count"],
                    "last_sequence": row["heartbeat_sequence"] or row["last_sequence"],
                    "latest_batch_utc": row["latest_batch_utc"],
                    "latest_temperature_c": (
                        row["heartbeat_temperature_c"]
                        if row["heartbeat_temperature_c"] is not None
                        else stats["average"]
                    ),
                    "heartbeat_at_utc": row["heartbeat_at_utc"],
                    "uptime_ms": row["heartbeat_uptime_ms"],
                    "boot_id": row["heartbeat_boot_id"],
                    "reset_reason": row["heartbeat_reset_reason"],
                    "tamper_open": (
                        bool(row["heartbeat_tamper_open"])
                        if row["heartbeat_tamper_open"] is not None
                        else None
                    ),
                }
            )
        return devices

    def list_batches(self, device_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM batches"
        parameters: tuple[str, ...] = ()
        if device_id is not None:
            query += " WHERE device_id = ?"
            parameters = (device_id,)
        query += " ORDER BY created_at_utc DESC, batch_id DESC"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._batch_summary(row) for row in rows]

    def get_batch(self, batch_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
        if row is None:
            raise ArchiveError("batch was not found")
        bundle = json.loads(row["bundle_json"])
        summary = self._batch_summary(row)
        summary["readings"] = [
            {
                "sequence": reading.get("sequence"),
                "temperature_c": reading.get("temperature_c"),
                "uptime_ms": reading.get("uptime_ms"),
                "boot_id": reading.get("boot_id"),
                "reset_reason": reading.get("reset_reason"),
                "tamper_open": reading.get("tamper_open"),
                "simulated": reading.get("simulated"),
            }
            for reading in bundle["batch"].get("readings", [])
            if isinstance(reading, dict)
        ]
        summary["public_key_fingerprint"] = bundle["batch"].get(
            "device_public_key_fingerprint"
        )
        summary["program_id"] = row["program_id"]
        summary["proof_bundle"] = bundle
        return summary

    def verify(self, batch_id: str) -> dict[str, Any]:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT bundle_json FROM batches WHERE batch_id = ?", (batch_id,)
            ).fetchone()
        if row is None:
            raise ArchiveError("batch was not found")
        return self._verifier().verify_bundle(json.loads(row["bundle_json"]))

    @staticmethod
    def _daily_anchor_estimate(created_at_values: list[str]) -> int | None:
        timestamps: list[datetime] = []
        for value in created_at_values:
            try:
                timestamps.append(
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                )
            except (TypeError, ValueError):
                continue
        timestamps.sort()
        intervals = [
            (later - earlier).total_seconds()
            for earlier, later in zip(timestamps, timestamps[1:])
            if 0 < (later - earlier).total_seconds() <= 86_400
        ]
        if not intervals:
            return None
        intervals.sort()
        typical_interval = intervals[len(intervals) // 2]
        return max(1, round(86_400 / typical_interval))

    def network_status(self) -> dict[str, Any]:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=24)
        ).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with self._connection() as connection:
            latest = connection.execute(
                """
                SELECT transaction_signature FROM batches
                ORDER BY created_at_utc DESC, batch_id DESC LIMIT 1
                """
            ).fetchone()
            recent_count = connection.execute(
                "SELECT COUNT(*) FROM batches WHERE created_at_utc >= ?",
                (cutoff,),
            ).fetchone()[0]
            recent_rows = connection.execute(
                """
                SELECT created_at_utc FROM batches
                ORDER BY created_at_utc DESC, batch_id DESC LIMIT 25
                """
            ).fetchall()
        if latest is None:
            raise ArchiveError("no Rialo transactions are archived yet")

        try:
            client = self._client()
            transaction = client.get_transaction(latest["transaction_signature"])
            fee_payer = extract_fee_payer(transaction)
            balance_kelvin = client.get_balance(fee_payer)
        except RialoVerificationError as exc:
            raise ArchiveError(f"Rialo network status is unavailable: {exc}") from exc

        meta = transaction.get("meta")
        fee_kelvin = meta.get("fee") if isinstance(meta, dict) else None
        if isinstance(fee_kelvin, bool) or not isinstance(fee_kelvin, int):
            fee_kelvin = None
        estimated_anchors = self._daily_anchor_estimate(
            [row["created_at_utc"] for row in recent_rows]
        )
        estimated_spend = (
            fee_kelvin * estimated_anchors
            if fee_kelvin is not None and estimated_anchors is not None
            else None
        )
        days_remaining = (
            balance_kelvin / estimated_spend
            if estimated_spend is not None and estimated_spend > 0
            else None
        )
        balance_rlo = balance_kelvin / KELVINS_PER_RLO
        return {
            "status": "ok",
            "network": "Rialo Devnet",
            "fee_payer": fee_payer,
            "balance_kelvin": balance_kelvin,
            "balance_rlo": balance_rlo,
            "latest_fee_kelvin": fee_kelvin,
            "latest_fee_rlo": (
                fee_kelvin / KELVINS_PER_RLO if fee_kelvin is not None else None
            ),
            "anchored_transactions_24h": recent_count,
            "estimated_transactions_24h": estimated_anchors,
            "estimated_spend_24h_kelvin": estimated_spend,
            "estimated_spend_24h_rlo": (
                estimated_spend / KELVINS_PER_RLO
                if estimated_spend is not None
                else None
            ),
            "estimated_days_remaining": days_remaining,
            "low_balance": balance_rlo < 0.1,
            "checked_at_utc": utc_now_text(),
        }


class ArchiveHandler(BaseHTTPRequestHandler):
    store: ArchiveStore
    static_directory: Path
    ingest_token: str

    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write("[archive] " + format % args + "\n")

    def _send_json(self, value: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def _send_static(self, request_path: str) -> None:
        filename = STATIC_FILES.get(request_path)
        if filename is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = (self.static_directory / filename).read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
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
    def _identifier(path: str, prefix: str) -> str | None:
        if not path.startswith(prefix):
            return None
        value = unquote(path[len(prefix) :]).strip("/")
        return value if value and "/" not in value else None

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                self._send_json({"status": "ok"})
                return
            if path == "/api/devices":
                devices = self.store.list_devices()
                self._send_json({"devices": devices, "count": len(devices)})
                return
            if path == "/api/network-status":
                self._send_json(self.store.network_status())
                return
            device_id = self._identifier(path, "/api/devices/")
            if device_id is not None:
                batches = self.store.list_batches(device_id)
                self._send_json(
                    {"device_id": device_id, "batches": batches, "count": len(batches)}
                )
                return
            if path == "/api/batches":
                batches = self.store.list_batches()
                self._send_json({"batches": batches, "count": len(batches)})
                return
            batch_id = self._identifier(path, "/api/batches/")
            if batch_id is not None:
                self._send_json(self.store.get_batch(batch_id))
                return
            self._send_static(path)
        except ArchiveError as exc:
            status = (
                HTTPStatus.SERVICE_UNAVAILABLE
                if path == "/api/network-status"
                else HTTPStatus.NOT_FOUND
            )
            self._send_json({"error": str(exc)}, status)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/ingest":
                authorization = self.headers.get("Authorization", "")
                expected = f"Bearer {self.ingest_token}"
                if not self.ingest_token or not hmac.compare_digest(
                    authorization, expected
                ):
                    self._send_json(
                        {"error": "valid ingest token is required"},
                        HTTPStatus.UNAUTHORIZED,
                    )
                    return
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > MAX_INGEST_BYTES:
                    raise ArchiveError("proof bundle must be between 1 byte and 2 MB")
                value = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(value, dict):
                    raise ArchiveError("proof bundle must be a JSON object")
                self._send_json(self.store.ingest(value), HTTPStatus.CREATED)
                return

            if path == "/api/heartbeat":
                authorization = self.headers.get("Authorization", "")
                expected = f"Bearer {self.ingest_token}"
                if not self.ingest_token or not hmac.compare_digest(
                    authorization, expected
                ):
                    self._send_json(
                        {"error": "valid ingest token is required"},
                        HTTPStatus.UNAUTHORIZED,
                    )
                    return
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > MAX_HEARTBEAT_BYTES:
                    raise ArchiveError("heartbeat must be between 1 byte and 32 KB")
                value = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(value, dict):
                    raise ArchiveError("heartbeat must be a JSON object")
                self._send_json(
                    self.store.ingest_heartbeat(value), HTTPStatus.ACCEPTED
                )
                return

            suffix = "/verify"
            if path.startswith("/api/batches/") and path.endswith(suffix):
                batch_id = unquote(path[len("/api/batches/") : -len(suffix)]).strip("/")
                if not batch_id or "/" in batch_id:
                    raise ArchiveError("batch was not found")
                self._send_json(self.store.verify(batch_id))
                return
            self._send_json({"error": "endpoint was not found"}, HTTPStatus.NOT_FOUND)
        except (ArchiveError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def handler_factory(
    store: ArchiveStore, static_directory: Path, ingest_token: str
) -> type[ArchiveHandler]:
    class ConfiguredArchiveHandler(ArchiveHandler):
        pass

    ConfiguredArchiveHandler.store = store
    ConfiguredArchiveHandler.static_directory = static_directory
    ConfiguredArchiveHandler.ingest_token = ingest_token
    return ConfiguredArchiveHandler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--database", type=Path, default=Path("data/archive/archive.sqlite3")
    )
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "portal",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ingest_token = os.environ.get(TOKEN_ENVIRONMENT_VARIABLE, "")
    if not ingest_token:
        print(
            f"ERROR: set {TOKEN_ENVIRONMENT_VARIABLE} before starting the archive",
            file=sys.stderr,
        )
        return 1
    if not args.static_dir.is_dir():
        print(f"ERROR: portal assets were not found: {args.static_dir}", file=sys.stderr)
        return 1
    store = ArchiveStore(args.database, args.rpc_url)
    server = ThreadingHTTPServer(
        (args.host, args.port),
        handler_factory(store, args.static_dir, ingest_token),
    )
    print(f"Rialo Edge Log public archive: http://{args.host}:{server.server_port}")
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
