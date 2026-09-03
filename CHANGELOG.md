# Changelog

Notable changes to Rialo Edge Log are recorded here as the project evolves.

## Unreleased

### Added

- Deployed the device-registration Venus program at `GVJpRi8SVURsjKbLC84Azk24vV2cK3ib74aXRk5hdatF` on Rialo Devnet.
- Added a one-time Rialo workflow that binds each device ID to its P-256 public-key fingerprint, signed by the project's published registrar wallet.
- Added independent device-registration checks to both the Python verifier and the browser verifier before new proof bundles are accepted.
- Added signed boot IDs, reset reasons, and optional enclosure-tamper state to telemetry schema 3 while preserving schema-2 verification.
- Added one-minute signed device heartbeats so the public portal reports live presence without waiting for the next anchored batch.
- Added a live hero stream built from recent confirmed Rialo Devnet transactions. Each entry links to its transaction in RialoScan.
- Added direct RialoScan links for batch transactions, workflow accounts, and the active Venus program.
- Added GitHub, X, and Telegram profile links to the public portal footer.
- Added OpenGraph and X card metadata with a branded 1200×630 preview image.
- Added explicit proof boundaries and live device presence states to the public portal.

### Fixed

- Parsed the WSL default gateway in PowerShell so the complete route line can
  never be passed to the anchor as a malformed RPC URL.
- Added an optional self-healing SSH tunnel for Windows networks that cannot
  reach Rialo Devnet on port `4100`; Windows verification and the Rialo CLI in
  WSL now receive separate, explicit RPC URLs through the same tunnel.
- Added Task Scheduler restart policies for the tunnel and edge workers, and
  made the stack manager start and stop the tunnel with the other services.
- Encoded the deterministic device-registration workflow slug as hexadecimal, as required by the Rialo CLI.
- Closed archive SQLite connections explicitly so Windows tests and maintenance no longer leave the database locked.
- Matched the OpenGraph preview typography to the public portal and stabilized the hero layout.
- Preserved stale pending submissions under `network-history/` and retried them automatically when a Devnet reset requires a new program deployment.
- Refreshed devices, selected history, Rialo transactions, and network status automatically every 30 seconds without reloading the portal.
- Retried transient Rialo anchoring failures and recovered unprocessed verified batches after Windows worker restarts.
- Changed the Windows edge tasks from interactive logon triggers to password-backed startup tasks, so telemetry starts before sign-in and continues while Windows is locked.
- Unified public-facing terminology around “Verifiable Telemetry”; “Verified” now remains only for completed proof results.
- Fixed browser verification for readings whose Celsius value is a whole degree, such as `5.0 °C`.
