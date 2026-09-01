#!/usr/bin/env python3
"""Publish Rialo-verified local batches to a public Edge Log archive."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from gateway.portal import PortalError, PortalStore


ARCHIVE_URL_ENV = "RIALO_EDGE_LOG_ARCHIVE_URL"
INGEST_TOKEN_ENV = "RIALO_EDGE_LOG_INGEST_TOKEN"


class ArchivePublishError(RuntimeError):
    """Raised when a verified batch cannot be published safely."""


def publication_path(batch_id: str, directory: Path) -> Path:
    if not batch_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for character in batch_id):
        raise ArchivePublishError("batch ID contains unsupported characters")
    return directory / f"{batch_id}-publication.json"


def list_publishable_batch_ids(
    data_directory: Path, publication_directory: Path
) -> list[str]:
    batch_directory = data_directory / "batches"
    receipt_directory = data_directory / "receipts"
    candidates: list[tuple[int, str]] = []
    if not batch_directory.exists():
        return []
    for path in batch_directory.glob("*/*.json"):
        if not path.is_file():
            continue
        try:
            batch = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(batch, dict) or not isinstance(batch.get("batch_id"), str):
            continue
        batch_id = batch["batch_id"]
        if not (receipt_directory / f"{batch_id}-rialo.json").is_file():
            continue
        if publication_path(batch_id, publication_directory).is_file():
            continue
        candidates.append((path.stat().st_mtime_ns, batch_id))
    candidates.sort()
    return [batch_id for _, batch_id in candidates]


def validate_archive_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ArchivePublishError("archive URL must start with http:// or https://")
    return value.rstrip("/")


def post_bundle(
    archive_url: str,
    ingest_token: str,
    bundle: dict[str, Any],
    timeout: float = 30.0,
) -> dict[str, Any]:
    if not ingest_token:
        raise ArchivePublishError("ingest token is empty")
    payload = json.dumps(
        bundle, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    request = urllib.request.Request(
        validate_archive_url(archive_url) + "/api/ingest",
        data=payload,
        headers={
            "Authorization": f"Bearer {ingest_token}",
            "Content-Type": "application/json",
            "User-Agent": "rialo-edge-log-gateway/1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(body).get("error", body)
        except json.JSONDecodeError:
            message = body
        raise ArchivePublishError(
            f"archive rejected the batch with HTTP {exc.code}: {message}"
        ) from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ArchivePublishError(f"archive request failed: {exc}") from exc
    if not isinstance(result, dict) or result.get("status") not in {
        "PUBLISHED",
        "ALREADY_PUBLISHED",
    }:
        raise ArchivePublishError("archive returned an unexpected response")
    return result


def load_heartbeat(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchivePublishError(f"cannot read heartbeat {path}: {exc}") from exc
    if (
        not isinstance(value, dict)
        or value.get("message_type") != "device_heartbeat"
        or not isinstance(value.get("device_id"), str)
        or not isinstance(value.get("reading"), dict)
    ):
        raise ArchivePublishError(f"heartbeat has invalid contents: {path}")
    return value


def heartbeat_identity(value: dict[str, Any]) -> str:
    reading = value.get("reading")
    if not isinstance(reading, dict):
        return ""
    return ":".join(
        str(reading.get(name, ""))
        for name in ("boot_id", "sequence", "signature")
    )


def post_heartbeat(
    archive_url: str,
    ingest_token: str,
    heartbeat: dict[str, Any],
    timeout: float = 30.0,
) -> dict[str, Any]:
    if not ingest_token:
        raise ArchivePublishError("ingest token is empty")
    payload = json.dumps(
        heartbeat, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    request = urllib.request.Request(
        validate_archive_url(archive_url) + "/api/heartbeat",
        data=payload,
        headers={
            "Authorization": f"Bearer {ingest_token}",
            "Content-Type": "application/json",
            "User-Agent": "rialo-edge-log-gateway/1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(body).get("error", body)
        except json.JSONDecodeError:
            message = body
        raise ArchivePublishError(
            f"archive rejected the heartbeat with HTTP {exc.code}: {message}"
        ) from exc
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ArchivePublishError(f"heartbeat request failed: {exc}") from exc
    if not isinstance(result, dict) or result.get("status") != "HEARTBEAT_ACCEPTED":
        raise ArchivePublishError("archive returned an unexpected heartbeat response")
    return result


def save_publication(
    directory: Path,
    batch_id: str,
    archive_url: str,
    result: dict[str, Any],
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    destination = publication_path(batch_id, directory)
    temporary = destination.with_suffix(".json.tmp")
    value = {
        "schema_version": 1,
        "status": result["status"],
        "batch_id": batch_id,
        "device_id": result.get("device_id"),
        "archive_url": validate_archive_url(archive_url),
        "published_at_utc": datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z"),
    }
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, destination)
    return destination


def publish_batch_id(
    batch_id: str,
    data_directory: Path,
    publication_directory: Path,
    archive_url: str,
    ingest_token: str,
) -> tuple[Path, dict[str, Any]]:
    store = PortalStore(data_directory)
    try:
        bundle = store.export_bundle(batch_id)
    except PortalError as exc:
        raise ArchivePublishError(str(exc)) from exc
    if bundle.get("rialo_receipt") is None:
        raise ArchivePublishError("batch has no Rialo receipt")
    if bundle.get("device_registration") is None:
        raise ArchivePublishError("device has no verified on-chain registration receipt")
    result = post_bundle(archive_url, ingest_token, bundle)
    receipt = save_publication(
        publication_directory, batch_id, archive_url, result
    )
    return receipt, result


def sync_batches(args: argparse.Namespace) -> int:
    batch_ids = list_publishable_batch_ids(args.data_dir, args.publication_dir)
    if not batch_ids:
        print("No unpublished Rialo-verified batches found.")
        return 0
    failures = 0
    for batch_id in batch_ids:
        try:
            receipt, result = publish_batch_id(
                batch_id,
                args.data_dir,
                args.publication_dir,
                args.archive_url,
                args.ingest_token,
            )
        except ArchivePublishError as exc:
            failures += 1
            print(f"[FAILED] {batch_id}: {exc}", file=sys.stderr)
            continue
        print(f"[{result['status']}] {batch_id}")
        print(f"[RECEIPT] {receipt}")
    return 1 if failures else 0


def watch_batches(args: argparse.Namespace) -> int:
    publication_directory = args.publication_dir
    existing = set(
        list_publishable_batch_ids(args.data_dir, publication_directory)
    )
    known = set() if args.include_existing else existing
    published_heartbeats: dict[Path, str] = {}
    heartbeat_directory = args.heartbeat_dir or args.data_dir / "heartbeats"
    if known:
        print(f"Watching for new verified batches; {len(known)} existing batch(es) left private.")
    else:
        print("Watching for Rialo-verified batches. Press Ctrl+C to stop.")
    try:
        while True:
            candidates = list_publishable_batch_ids(
                args.data_dir, publication_directory
            )
            for batch_id in candidates:
                if batch_id in known:
                    continue
                try:
                    receipt, result = publish_batch_id(
                        batch_id,
                        args.data_dir,
                        publication_directory,
                        args.archive_url,
                        args.ingest_token,
                    )
                except ArchivePublishError as exc:
                    print(f"[FAILED] {batch_id}: {exc}", file=sys.stderr)
                    continue
                known.add(batch_id)
                print(f"[{result['status']}] {batch_id}")
                print(f"[RECEIPT] {receipt}")
            if heartbeat_directory.exists():
                for path in sorted(heartbeat_directory.glob("*.json")):
                    try:
                        heartbeat = load_heartbeat(path)
                        identity = heartbeat_identity(heartbeat)
                        if identity and published_heartbeats.get(path) == identity:
                            continue
                        result = post_heartbeat(
                            args.archive_url, args.ingest_token, heartbeat
                        )
                    except ArchivePublishError as exc:
                        print(f"[HEARTBEAT FAILED] {path}: {exc}", file=sys.stderr)
                        continue
                    published_heartbeats[path] = identity
                    print(
                        f"[HEARTBEAT] {result.get('device_id')} "
                        f"seq={result.get('sequence')}"
                    )
            if args.once:
                return 0
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--publication-dir", type=Path, default=Path("data/publications")
    )
    parser.add_argument(
        "--archive-url", default=os.environ.get(ARCHIVE_URL_ENV, "")
    )
    parser.add_argument(
        "--ingest-token", default=os.environ.get(INGEST_TOKEN_ENV, "")
    )
    parser.add_argument(
        "--heartbeat-dir",
        type=Path,
        help="directory containing latest signed device heartbeats",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    publish = subparsers.add_parser("publish", help="publish one verified batch")
    publish.add_argument("batch_id")
    add_common_arguments(publish)

    sync = subparsers.add_parser("sync", help="publish every unreported verified batch")
    add_common_arguments(sync)

    watch = subparsers.add_parser("watch", help="publish new verified batches")
    watch.add_argument("--poll-seconds", type=float, default=2.0)
    watch.add_argument("--include-existing", action="store_true")
    watch.add_argument("--once", action="store_true")
    add_common_arguments(watch)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.archive_url = validate_archive_url(args.archive_url)
        if not args.ingest_token:
            raise ArchivePublishError(
                f"set {INGEST_TOKEN_ENV} before publishing"
            )
        if args.command == "publish":
            receipt, result = publish_batch_id(
                args.batch_id,
                args.data_dir,
                args.publication_dir,
                args.archive_url,
                args.ingest_token,
            )
            print(f"[{result['status']}] {args.batch_id}")
            print(f"[RECEIPT] {receipt}")
            return 0
        if args.command == "sync":
            return sync_batches(args)
        if args.command == "watch":
            return watch_batches(args)
    except (ArchivePublishError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
