# Public Archive

The archive stores already confirmed telemetry so a visitor can browse a device
history without receiving files from its operator. Each upload is verified
against Rialo before it is accepted.

## Local End-to-End Demo

Terminal 1 starts the archive with a development-only ingestion token:

```powershell
$env:RIALO_EDGE_LOG_INGEST_TOKEN = "change-this-development-token"
python -m archive.server
```

Terminal 2 publishes the gateway's existing confirmed batches:

```powershell
$env:RIALO_EDGE_LOG_ARCHIVE_URL = "http://127.0.0.1:8090"
$env:RIALO_EDGE_LOG_INGEST_TOKEN = "change-this-development-token"
python -m gateway.archive_publisher sync
```

Open `http://127.0.0.1:8090`. The visitor selects a device and historical batch,
then asks the archive to compare it with the Rialo workflow again.

## What the Archive Stores

- signed telemetry readings;
- the device's public key and fingerprint;
- the batch SHA-256 digest;
- the Rialo program, transaction and workflow addresses.

Private device keys, wallets and credentials are never part of an upload.

## Security Boundaries

- `POST /api/ingest` requires the `RIALO_EDGE_LOG_INGEST_TOKEN` bearer token.
- public read and verification endpoints never expose that token.
- a device ID is permanently bound to its first accepted public key.
- conflicting contents under an existing batch ID are rejected.
- only a complete `RIALO_VERIFIED` proof bundle is accepted.

The default server binds to `127.0.0.1` and uses
`data/archive/archive.sqlite3`. A real internet deployment still requires a
durable host, TLS, backups and secret management; do not expose this development
server directly to the internet. Production-ready systemd and Nginx templates
are documented in [`deploy/vps`](../deploy/vps/README.md).
