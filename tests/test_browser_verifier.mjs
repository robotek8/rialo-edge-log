import assert from "node:assert/strict";
import test from "node:test";

await import("../portal/verifier.js");

const verifier = globalThis.RialoVerifier;

function hex(bytes) {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function fromHex(value) {
  return Uint8Array.from(value.match(/../g), (pair) => Number.parseInt(pair, 16));
}

function u64(view, offset, value) {
  view.setBigUint64(offset, BigInt(value), true);
}

async function fixture(schemaVersion = 2) {
  const keys = await crypto.subtle.generateKey(
    { name: "ECDSA", namedCurve: "P-256" },
    true,
    ["sign", "verify"],
  );
  const publicKey = new Uint8Array(await crypto.subtle.exportKey("raw", keys.publicKey));
  const fingerprint = hex(new Uint8Array(await crypto.subtle.digest("SHA-256", publicKey)));
  const reading = {
    message_type: "telemetry",
    schema_version: schemaVersion,
    device_id: "edge-0E0473",
    sequence: 10,
    uptime_ms: 50000,
    temperature_milli_c: 4210,
    temperature_c: 4.21,
    simulated: true,
    signature_algorithm: "ecdsa-p256-sha256-raw",
  };
  if (schemaVersion === 3) {
    Object.assign(reading, {
      boot_id: 0xABCDEF01,
      reset_reason: "watchdog_reset",
      tamper_open: false,
    });
  }
  const message = new TextEncoder().encode(
    schemaVersion === 3
      ? "3|edge-0E0473|10|50000|4210|1|2882400001|watchdog_reset|0"
      : "2|edge-0E0473|10|50000|4210|1",
  );
  reading.signature = hex(new Uint8Array(await crypto.subtle.sign(
    { name: "ECDSA", hash: "SHA-256" },
    keys.privateKey,
    message,
  )));

  const batch = {
    schema_version: schemaVersion,
    batch_id: "edge-0E0473-10-10-test",
    device_id: "edge-0E0473",
    created_at_utc: "2026-08-30T12:00:00.000Z",
    first_sequence: 10,
    last_sequence: 10,
    reading_count: 1,
    readings: [reading],
    device_public_key_fingerprint: fingerprint,
    proof: {
      version: schemaVersion,
      algorithm: "sha256",
      digest: "",
      device_signatures_verified: true,
      anchored_on_rialo: false,
    },
  };
  batch.proof.digest = await verifier.calculateBatchDigest(batch);

  const programId = "PROGRAM123";
  const workflow = "WORKFLOW456";
  const transaction = "TRANSACTION789";
  const raw = new Uint8Array(104);
  const view = new DataView(raw.buffer);
  u64(view, 0, 1);
  u64(view, 8, 0x0e0473);
  raw.set(fromHex(fingerprint), 16);
  raw.set(fromHex(batch.proof.digest), 48);
  u64(view, 80, 10);
  u64(view, 88, 10);
  u64(view, 96, 1);

  const bundle = {
    schema_version: 1,
    bundle_type: "rialo-edge-log-proof",
    batch,
    device: {
      device_id: batch.device_id,
      signature_algorithm: "ecdsa-p256-sha256-raw",
      public_key_sec1: hex(publicKey),
      fingerprint_sha256: fingerprint,
    },
    rialo_receipt: {
      schema_version: 1,
      status: "RIALO_VERIFIED",
      batch_id: batch.batch_id,
      program_id: programId,
      transaction_signature: transaction,
      workflow_address: workflow,
    },
  };
  const rpcCall = async (method) => {
    if (method === "getTransaction") {
      return {
        block_height: 123,
        transaction: {
          message: {
            accountKeys: ["PAYER", workflow, programId],
            instructions: [{ programIdIndex: 2, accounts: [0, 1] }],
          },
        },
        meta: { err: null, fee: 5000 },
      };
    }
    return {
      value: {
        owner: programId,
        data: [Buffer.from(raw).toString("base64"), "base64"],
      },
    };
  };
  return { bundle, rpcCall };
}

test("browser independently verifies signatures, digest, transaction and workflow", async () => {
  const { bundle, rpcCall } = await fixture();
  const result = await verifier.verifyProofBundle(bundle, { rpcCall });
  assert.equal(result.status, "RIALO_VERIFIED");
  assert.equal(result.signaturesVerified, 1);
  assert.equal(result.localDigest, result.onchainDigest);
  assert.equal(result.blockHeight, 123);
  assert.equal(result.feeKelvin, 5000);
});

test("browser verifies signed boot and tamper state", async () => {
  const { bundle, rpcCall } = await fixture(3);
  const result = await verifier.verifyProofBundle(bundle, { rpcCall });
  assert.equal(result.status, "RIALO_VERIFIED");
  bundle.batch.readings[0].tamper_open = true;
  await assert.rejects(
    verifier.verifyProofBundle(bundle, { rpcCall }),
    (error) => error.code === "TAMPERED",
  );
});

test("browser digest matches Python for a whole-degree temperature", async () => {
  const batch = {
    schema_version: 2,
    batch_id: "edge-0E0473-1-1-regression",
    device_id: "edge-0E0473",
    first_sequence: 1,
    last_sequence: 1,
    reading_count: 1,
    readings: [{
      message_type: "telemetry",
      schema_version: 2,
      device_id: "edge-0E0473",
      sequence: 1,
      uptime_ms: 5000,
      temperature_milli_c: 5000,
      temperature_c: 5.0,
      simulated: true,
      signature_algorithm: "ecdsa-p256-sha256-raw",
      signature: "00".repeat(64),
    }],
    device_public_key_fingerprint: "11".repeat(32),
  };

  assert.equal(
    await verifier.calculateBatchDigest(batch),
    "13b28d0a556164ccde817d8216f39d31666d74c70f488d0359393c9ec9747e63",
  );
});

test("browser rejects changed telemetry", async () => {
  const { bundle, rpcCall } = await fixture();
  bundle.batch.readings[0].temperature_milli_c = 9999;
  await assert.rejects(
    verifier.verifyProofBundle(bundle, { rpcCall }),
    (error) => error.code === "TAMPERED",
  );
});

test("browser exports a portable proof file", async () => {
  const { bundle } = await fixture();
  const exported = verifier.serializeProofBundle(bundle);
  assert.ok(exported.endsWith("\n"));
  assert.deepEqual(JSON.parse(exported), bundle);
  assert.deepEqual(verifier.parseProofBundle(exported), bundle);
});

test("browser rejects an invalid proof file", () => {
  assert.throws(
    () => verifier.parseProofBundle('{"not":"a proof"}'),
    (error) => error.code === "INVALID_RECEIPT",
  );
  assert.throws(
    () => verifier.parseProofBundle("changed by hand"),
    (error) => error.code === "INVALID_RECEIPT",
  );
});
