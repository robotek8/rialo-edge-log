# Serial Gateway

The gateway reads newline-delimited JSON telemetry from the NodeMCU, enrolls its
public key, verifies every ECDSA P-256 signature, groups 60 accepted readings
into a deterministic batch and calculates its SHA-256 proof.

## Windows Setup

Run these commands from the repository directory:

```powershell
python -m pip install -r gateway/requirements.txt
python -m gateway.edge_gateway ports
```

First generate and flash the signed firmware as described in
[`firmware/nodemcu_signed`](../firmware/nodemcu_signed).

Close Arduino Serial Monitor before starting the gateway because only one
application can use the COM port at a time. Replace `COM5` with the detected
port:

```powershell
python -m gateway.edge_gateway listen --port COM5
```

The first valid registration is saved to `data/device_registry.json`. This is a
local trust-on-first-use registry. With the simulator's five-second interval, a
60-reading batch is saved once every five minutes under `data/batches/`. Use
`--batch-size 12` only for a short one-minute demonstration.

The gateway also writes the latest verified reading to `data/heartbeats/` once
per minute. The publisher forwards that small signed heartbeat to the archive,
so public ONLINE/STALE/OFFLINE status no longer waits for the next five-minute
batch. Set `--heartbeat-seconds 0` only when heartbeat publication must be
disabled.

## Verify a Batch

```powershell
python -m gateway.edge_gateway verify data/batches/edge-A1B2C3/BATCH_FILE.json
```

An unchanged batch produces:

```text
VERIFIED: device signatures and local proof match; Rialo proof was not checked
```

Changing a reading without changing its proof produces:

```text
TAMPERED: SHA-256 proof does not match the batch
```

This command checks the device signatures and local SHA-256 proof only. It does
not contact Rialo.

## Verify a Historical Batch Against Rialo

After recording a batch with the Rialo workflow, pass its transaction signature
and deployed program ID to the historical verifier:

```powershell
python -m gateway.rialo_verify PATH_TO_BATCH.json `
  --transaction TRANSACTION_SIGNATURE `
  --program-id PROGRAM_ID
```

The verifier performs four checks:

1. verifies every ECDSA P-256 device signature;
2. recalculates the local batch SHA-256 digest;
3. discovers the workflow account from the confirmed Rialo transaction;
4. reads and compares the workflow state from Rialo DevNet.

A complete match produces:

```text
LOCAL VERIFIED: device signatures and local proof match; Rialo proof was not checked
RIALO VERIFIED: workflow state matches the historical batch
```

A local receipt containing the transaction signature, workflow address, block
height and digest is saved under `data/receipts/`. Generated telemetry and
receipts are ignored by Git and remain local.

## Automatically Anchor New Batches

The Rialo CLI remains inside WSL while the serial gateway runs on Windows. Start
the watcher from PowerShell before collecting telemetry:

```powershell
python -m gateway.rialo_anchor watch `
  --program-id PROGRAM_ID
```

The watcher leaves existing files untouched by default. For every new batch it:

1. verifies the device signatures and local SHA-256 proof;
2. invokes the deployed Venus program through `wsl.exe`;
3. waits until the transaction is readable from Rialo DevNet;
4. reads the created workflow state and compares it with the batch;
5. saves a `RIALO_VERIFIED` receipt under `data/receipts/`.

The default WSL project directory is `~/rialo-edge-log`. Override it when the
repository is stored elsewhere:

```powershell
python -m gateway.rialo_anchor watch `
  --program-id PROGRAM_ID `
  --wsl-project-dir /home/USER/OTHER_DIRECTORY
```

One existing batch can be submitted explicitly:

```powershell
python -m gateway.rialo_anchor submit PATH_TO_BATCH.json `
  --program-id PROGRAM_ID
```

The submit command refuses to resend a batch that already has a receipt unless
`--force` is supplied. `watch --include-existing` can submit an entire existing
backlog, so use it carefully: each unreceipted batch creates a DevNet
transaction. For longer runs, increase the serial gateway's `--batch-size` to
reduce the transaction rate.

## Open the Telemetry Portal Locally

Start the portal from the repository root:

```powershell
python -m gateway.portal
```

Open `http://127.0.0.1:8080` in a browser. The portal stays bound to the local
computer by default and reads the existing `data/batches/`, `data/receipts/`
and `data/device_registry.json` files.

The local view uses the same device-history interface as the public archive. It
lets an operator:

1. select a registered device;
2. browse every local batch by timestamp and sequence range;
3. inspect its temperature history and proof metadata;
4. run a fresh device-signature, SHA-256 and Rialo RPC verification.

## Automatically Publish to an Archive

The public archive removes all file sharing from the visitor flow. After a
batch receives its Rialo receipt, a separate publisher sends it to the archive
through an authenticated API.

Set the archive address and its private ingestion token in PowerShell:

```powershell
$env:RIALO_EDGE_LOG_ARCHIVE_URL = "https://YOUR_ARCHIVE"
$env:RIALO_EDGE_LOG_INGEST_TOKEN = "YOUR_PRIVATE_TOKEN"
```

Publish every existing confirmed batch once:

```powershell
python -m gateway.archive_publisher sync
```

Or publish newly confirmed batches automatically:

```powershell
python -m gateway.archive_publisher watch
```

`watch` leaves existing batches private by default. Add `--include-existing`
only when the operator intentionally wants to make the old telemetry public.
Successful publications are recorded under `data/publications/` and are not
committed to Git.

While `watch` is running, it also retries changed heartbeat files from
`data/heartbeats/`. The archive verifies the reading signature and enrolled
device key before updating live presence, temperature, boot ID, reset reason,
or tamper state.

An archive visitor opens the device link, selects a period and receives one of
these results:

- `RIALO_VERIFIED`: device signatures, local batch and Rialo workflow match;
- `LOCAL_VERIFIED`: local cryptography matches, but the bundle has no Rialo receipt;
- `TAMPERED`: the telemetry, identity, receipt or Rialo state does not match;
- `CHAIN_UNAVAILABLE`: local verification passed, but DevNet RPC could not be reached.

The publisher transfers raw telemetry, the public device key and the Rialo
receipt. It never transfers the device private key, wallet or credentials.
