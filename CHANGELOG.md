# Changelog

Notable changes to Rialo Edge Log are recorded here as the project evolves.

## Unreleased

### Added

- Added a one-time Rialo workflow that binds each device ID to its P-256 public-key fingerprint, signed by the project's published registrar wallet.
- Added independent device-registration checks to both the Python verifier and the browser verifier before new proof bundles are accepted.
- Added signed boot IDs, reset reasons, and optional enclosure-tamper state to telemetry schema 3 while preserving schema-2 verification.
- Added one-minute signed device heartbeats so the public portal reports live presence without waiting for the next anchored batch.
- Added a live hero stream built from recent confirmed Rialo Devnet transactions. Each entry links to its transaction in RialoScan.
- Added GitHub, X, and Telegram profile links to the public portal footer.
- Added OpenGraph and X card metadata with a branded 1200×630 preview image.
- Added explicit proof boundaries and live device presence states to the public portal.

### Fixed

- Preserved stale pending submissions under `network-history/` and retried them automatically when a Devnet reset requires a new program deployment.
- Refreshed devices, selected history, Rialo transactions, and network status automatically every 30 seconds without reloading the portal.
- Retried transient Rialo anchoring failures and recovered unprocessed verified batches after Windows worker restarts.
- Changed the Windows edge tasks from interactive logon triggers to password-backed startup tasks, so telemetry starts before sign-in and continues while Windows is locked.
- Unified public-facing terminology around “Verifiable Telemetry”; “Verified” now remains only for completed proof results.
- Fixed browser verification for readings whose Celsius value is a whole degree, such as `5.0 °C`.
