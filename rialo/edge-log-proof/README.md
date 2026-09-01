# Rialo Edge Log Proof Workflow

This Venus program exposes two workflow functions. `register` stores a one-time
device-ID and public-key-fingerprint binding; `start` stores one proof record for
one signed telemetry batch. It uses `u64` parameters and has been built and
deployed with Rialo 0.18.1.

Each workflow instance records:

- numeric ESP8266 device ID;
- SHA-256 fingerprint of the enrolled P-256 public key;
- SHA-256 digest of the complete signed batch;
- first and last device sequence numbers;
- number of readings.

Both 32-byte hashes are passed as four little-endian `u64` values. The original
public key and telemetry remain off-chain.

The registration transaction's fee payer is the public registrar identity. The
archive and browser require it to match the registrar address published by the
project; a self-asserted registration from another wallet is rejected.

## Build in WSL

```bash
cd rialo/edge-log-proof
cargo check --features implementation
cargo build --manifest-path artifact/Cargo.toml
```

Venus should generate the WIT interface and manifest under `wit/`.

## Deploy

```bash
rialo client program deploy-venus .
```

Save the resulting program ID. Generate an invocation command from a verified
batch on Windows:

```powershell
py -m gateway.rialo_args PATH_TO_BATCH.json --program-id PROGRAM_ID
```

The current Devnet deployment is documented in the repository root README.
