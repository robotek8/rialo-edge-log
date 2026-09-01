(function attachRialoVerifier(global) {
  "use strict";

  const DEFAULT_RPC_URL = "https://devnet.rialoscan.org/api/rpc";
  const DEFAULT_DEVICE_REGISTRAR = "BBjJpGwN3aV3BrMPw6BCZHZue8btcqTTfXouG9Nv9Sz6";
  const TEXT_ENCODER = new TextEncoder();

  class VerificationError extends Error {
    constructor(code, message) {
      super(message);
      this.name = "VerificationError";
      this.code = code;
    }
  }

  function assert(condition, message, code = "TAMPERED") {
    if (!condition) throw new VerificationError(code, message);
  }

  function hexToBytes(value) {
    assert(typeof value === "string" && value.length % 2 === 0 && /^[0-9a-f]+$/i.test(value), "Invalid hexadecimal value");
    return Uint8Array.from(value.match(/../g), (pair) => Number.parseInt(pair, 16));
  }

  function bytesToHex(value) {
    return Array.from(value, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }

  function base64ToBytes(value) {
    try {
      const binary = global.atob
        ? global.atob(value)
        : global.Buffer.from(value, "base64").toString("binary");
      return Uint8Array.from(binary, (character) => character.charCodeAt(0));
    } catch (_error) {
      throw new VerificationError("TAMPERED", "Workflow account data is not valid base64");
    }
  }

  function canonicalJson(value, propertyName = "") {
    if (value === null) return "null";
    if (Array.isArray(value)) {
      return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
    }
    if (typeof value === "object") {
      const fields = Object.keys(value).sort().map((key) => (
        `${JSON.stringify(key)}:${canonicalJson(value[key], key)}`
      ));
      return `{${fields.join(",")}}`;
    }
    if (typeof value === "number") {
      assert(Number.isFinite(value), "Proof contains a non-finite number");
      // The gateway normalizes temperature_c to a Python float. Python's
      // json.dumps keeps the decimal point for whole-valued floats (5.0),
      // while JSON.stringify shortens the same value to 5. Preserve the
      // gateway representation so both sides hash identical bytes.
      if (propertyName === "temperature_c" && Number.isInteger(value)) {
        return Object.is(value, -0) ? "-0.0" : `${value}.0`;
      }
      return JSON.stringify(value);
    }
    return JSON.stringify(value);
  }

  function proofPayload(batch) {
    const payload = {
      schema_version: batch.schema_version,
      batch_id: batch.batch_id,
      device_id: batch.device_id,
      first_sequence: batch.first_sequence,
      last_sequence: batch.last_sequence,
      reading_count: batch.reading_count,
      readings: batch.readings,
    };
    if (Object.hasOwn(batch, "device_public_key_fingerprint")) {
      payload.device_public_key_fingerprint = batch.device_public_key_fingerprint;
    }
    return payload;
  }

  async function sha256Hex(value) {
    const digest = await global.crypto.subtle.digest("SHA-256", value);
    return bytesToHex(new Uint8Array(digest));
  }

  async function calculateBatchDigest(batch) {
    const canonical = canonicalJson(proofPayload(batch));
    return sha256Hex(TEXT_ENCODER.encode(canonical));
  }

  function canonicalReading(reading) {
    if (reading.schema_version === 3) {
      return TEXT_ENCODER.encode(
        `3|${reading.device_id}|${reading.sequence}|${reading.uptime_ms}|${reading.temperature_milli_c}|${reading.simulated ? 1 : 0}|${reading.boot_id}|${reading.reset_reason}|${reading.tamper_open ? 1 : 0}`,
      );
    }
    return TEXT_ENCODER.encode(
      `2|${reading.device_id}|${reading.sequence}|${reading.uptime_ms}|${reading.temperature_milli_c}|${reading.simulated ? 1 : 0}`,
    );
  }

  async function verifyDeviceSignatures(batch, publicKeyHex) {
    let key;
    try {
      key = await global.crypto.subtle.importKey(
        "raw",
        hexToBytes(publicKeyHex),
        { name: "ECDSA", namedCurve: "P-256" },
        false,
        ["verify"],
      );
    } catch (_error) {
      throw new VerificationError("TAMPERED", "Device public key is invalid");
    }
    let verified = 0;
    for (const reading of batch.readings) {
      assert([2, 3].includes(reading.schema_version), "Unsigned reading found in a signed batch");
      const valid = await global.crypto.subtle.verify(
        { name: "ECDSA", hash: "SHA-256" },
        key,
        hexToBytes(reading.signature),
        canonicalReading(reading),
      );
      assert(valid, `Invalid device signature at sequence ${reading.sequence}`);
      verified += 1;
    }
    return verified;
  }

  async function defaultRpcCall(method, params, rpcUrl = DEFAULT_RPC_URL) {
    let response;
    try {
      response = await fetch(rpcUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
      });
    } catch (error) {
      throw new VerificationError("CHAIN_UNAVAILABLE", `Independent Rialo RPC request failed: ${error.message}`);
    }
    if (!response.ok) {
      throw new VerificationError("CHAIN_UNAVAILABLE", `Independent Rialo RPC returned HTTP ${response.status}`);
    }
    const payload = await response.json();
    if (payload.error) {
      throw new VerificationError("CHAIN_UNAVAILABLE", payload.error.message || "Independent Rialo RPC returned an error");
    }
    return payload.result;
  }

  function accountKey(value) {
    if (typeof value === "string") return value;
    return value && typeof value.pubkey === "string" ? value.pubkey : null;
  }

  function transactionContainsWorkflow(transactionResult, programId, workflowAddress) {
    assert(transactionResult, "Rialo transaction was not found", "CHAIN_UNAVAILABLE");
    assert(transactionResult.meta && transactionResult.meta.err == null, "Rialo transaction was not successful");
    const message = transactionResult.transaction && transactionResult.transaction.message;
    assert(message && Array.isArray(message.accountKeys) && Array.isArray(message.instructions), "Rialo transaction is incomplete");
    const keys = message.accountKeys.map(accountKey);
    return message.instructions.some((instruction) => {
      const programIndex = Number(instruction.programIdIndex);
      const accounts = instruction.accounts;
      return Number.isInteger(programIndex)
        && keys[programIndex] === programId
        && Array.isArray(accounts)
        && accounts.length >= 2
        && keys[Number(accounts[1])] === workflowAddress;
    });
  }

  function transactionFeePayer(transactionResult) {
    const message = transactionResult
      && transactionResult.transaction
      && transactionResult.transaction.message;
    assert(message && Array.isArray(message.accountKeys) && message.accountKeys.length > 0, "Rialo transaction fee payer is missing");
    const payer = accountKey(message.accountKeys[0]);
    assert(payer, "Rialo transaction fee payer is invalid");
    return payer;
  }

  function readU64(view, offset) {
    return view.getBigUint64(offset, true);
  }

  function decodeWorkflowAccount(accountResult, programId) {
    const account = accountResult && accountResult.value;
    assert(account, "Rialo workflow account was not found", "CHAIN_UNAVAILABLE");
    assert(account.owner === programId, "Workflow account belongs to another program");
    assert(Array.isArray(account.data) && account.data[1] === "base64", "Workflow account data has an unsupported format");
    const raw = base64ToBytes(account.data[0]);
    assert(raw.length >= 104, "Workflow account state is incomplete");
    const view = new DataView(raw.buffer, raw.byteOffset, raw.byteLength);
    assert(readU64(view, 0) !== 0n, "Workflow account is not initialized");
    return {
      deviceId: readU64(view, 8),
      publicKeyFingerprint: bytesToHex(raw.slice(16, 48)),
      batchDigest: bytesToHex(raw.slice(48, 80)),
      firstSequence: readU64(view, 80),
      lastSequence: readU64(view, 88),
      readingCount: readU64(view, 96),
    };
  }

  function deviceIdToU64(deviceId) {
    assert(typeof deviceId === "string" && /^edge-[0-9a-f]+$/i.test(deviceId), "Device ID cannot be encoded for Rialo");
    return BigInt(`0x${deviceId.slice(5)}`);
  }

  function registrationWorkflowSlug(deviceId) {
    return `device-${deviceIdToU64(deviceId).toString(16)}`;
  }

  function verifyRegistrationIdentity(registration, batch, receipt, expectedRegistrar) {
    assert(registration && registration.schema_version === 1, "Device registration receipt is missing", "INVALID_RECEIPT");
    assert(registration.status === "RIALO_DEVICE_REGISTERED", "Device registration status is invalid", "INVALID_RECEIPT");
    assert(registration.device_id === batch.device_id, "Device registration belongs to another device", "INVALID_RECEIPT");
    assert(registration.public_key_fingerprint === batch.device_public_key_fingerprint, "Device registration contains another public key", "INVALID_RECEIPT");
    assert(registration.program_id === receipt.program_id, "Device registration uses another program", "INVALID_RECEIPT");
    assert(registration.workflow_slug === registrationWorkflowSlug(batch.device_id), "Device registration workflow slug is invalid", "INVALID_RECEIPT");
    assert(registration.registrar === expectedRegistrar, "Device registration signer is not trusted", "INVALID_RECEIPT");
    for (const field of ["transaction_signature", "workflow_address", "registrar"]) {
      assert(typeof registration[field] === "string" && registration[field], `Device registration ${field} is missing`, "INVALID_RECEIPT");
    }
  }

  function verifyRegistrationState(registration, batch, transaction, account) {
    assert(
      transactionContainsWorkflow(
        transaction,
        registration.program_id,
        registration.workflow_address,
      ),
      "Registration transaction does not point to the claimed workflow",
    );
    assert(transactionFeePayer(transaction) === registration.registrar, "Device registrar does not match the registration transaction");
    const state = decodeWorkflowAccount(account, registration.program_id);
    assert(state.deviceId === deviceIdToU64(batch.device_id), "Registered on-chain device ID does not match");
    assert(state.publicKeyFingerprint === batch.device_public_key_fingerprint, "Registered on-chain public key does not match");
    assert(state.batchDigest === "00".repeat(32), "Device registration contains a batch digest");
    assert(state.firstSequence === 0n, "Device registration first sequence is not zero");
    assert(state.lastSequence === 0n, "Device registration last sequence is not zero");
    assert(state.readingCount === 0n, "Device registration reading count is not zero");
  }

  function transactionMetadata(transactionResult) {
    const transaction = transactionResult.transaction || {};
    return {
      blockHeight: transactionResult.block_height ?? transactionResult.blockHeight ?? transactionResult.slot ?? null,
      blockTime: transactionResult.block_time ?? transactionResult.blockTime ?? transaction.validFrom ?? null,
      feeKelvin: transactionResult.meta && transactionResult.meta.fee != null
        ? transactionResult.meta.fee
        : null,
    };
  }

  function serializeProofBundle(bundle) {
    assert(bundle && bundle.bundle_type === "rialo-edge-log-proof", "Proof bundle is missing", "INVALID_RECEIPT");
    return `${JSON.stringify(bundle, null, 2)}\n`;
  }

  function parseProofBundle(text) {
    assert(typeof text === "string" && text.trim(), "Proof file is empty", "INVALID_RECEIPT");
    let bundle;
    try {
      bundle = JSON.parse(text);
    } catch (_error) {
      throw new VerificationError("INVALID_RECEIPT", "Proof file is not valid JSON");
    }
    assert(bundle && bundle.bundle_type === "rialo-edge-log-proof", "This is not a Rialo Edge Log proof file", "INVALID_RECEIPT");
    return bundle;
  }

  async function verifyProofBundle(bundle, options = {}) {
    assert(global.crypto && global.crypto.subtle, "Web Crypto is unavailable", "UNSUPPORTED_BROWSER");
    assert(bundle && bundle.bundle_type === "rialo-edge-log-proof", "Proof bundle is missing");
    const batch = bundle.batch;
    const device = bundle.device;
    const receipt = bundle.rialo_receipt;
    assert(batch && device && receipt, "Proof bundle is incomplete", "INVALID_RECEIPT");
    assert(device.device_id === batch.device_id && receipt.batch_id === batch.batch_id, "Proof identities do not match", "INVALID_RECEIPT");
    assert(Array.isArray(batch.readings) && batch.readings.length === batch.reading_count, "Reading count does not match the batch");
    assert(batch.readings.length > 0, "The batch has no readings");
    assert(batch.first_sequence === batch.readings[0].sequence, "First sequence does not match the readings");
    assert(batch.last_sequence === batch.readings.at(-1).sequence, "Last sequence does not match the readings");

    const fingerprint = await sha256Hex(hexToBytes(device.public_key_sec1));
    assert(fingerprint === batch.device_public_key_fingerprint, "Device public-key fingerprint does not match");
    const signaturesVerified = await verifyDeviceSignatures(batch, device.public_key_sec1);
    const localDigest = await calculateBatchDigest(batch);
    assert(localDigest === batch.proof.digest, "Recalculated SHA-256 digest does not match the archive");

    const rpcCall = options.rpcCall || ((method, params) => defaultRpcCall(method, params, options.rpcUrl));
    const requests = [
      rpcCall("getTransaction", [{ signature: receipt.transaction_signature }]),
      rpcCall("getAccountInfo", [{ address: receipt.workflow_address, encoding: "base64" }]),
    ];
    const registration = bundle.schema_version === 2
      ? bundle.device_registration
      : null;
    if (bundle.schema_version === 2) {
      verifyRegistrationIdentity(
        registration,
        batch,
        receipt,
        options.expectedRegistrar || DEFAULT_DEVICE_REGISTRAR,
      );
      requests.push(
        rpcCall("getTransaction", [{ signature: registration.transaction_signature }]),
        rpcCall("getAccountInfo", [{ address: registration.workflow_address, encoding: "base64" }]),
      );
    }
    const [transaction, account, registrationTransaction, registrationAccount] = await Promise.all(requests);
    assert(transactionContainsWorkflow(transaction, receipt.program_id, receipt.workflow_address), "Transaction does not point to the claimed Rialo workflow");
    const workflow = decodeWorkflowAccount(account, receipt.program_id);
    assert(workflow.deviceId === deviceIdToU64(batch.device_id), "On-chain device ID does not match");
    assert(workflow.publicKeyFingerprint === batch.device_public_key_fingerprint, "On-chain public-key fingerprint does not match");
    assert(workflow.batchDigest === localDigest, "On-chain digest does not match the telemetry");
    assert(workflow.firstSequence === BigInt(batch.first_sequence), "On-chain first sequence does not match");
    assert(workflow.lastSequence === BigInt(batch.last_sequence), "On-chain last sequence does not match");
    assert(workflow.readingCount === BigInt(batch.reading_count), "On-chain reading count does not match");

    if (registration) {
      verifyRegistrationState(
        registration,
        batch,
        registrationTransaction,
        registrationAccount,
      );
    }

    return {
      status: "RIALO_VERIFIED",
      signaturesVerified,
      localDigest,
      onchainDigest: workflow.batchDigest,
      transactionSignature: receipt.transaction_signature,
      workflowAddress: receipt.workflow_address,
      programId: receipt.program_id,
      deviceRegistrationVerified: Boolean(registration),
      registrationTransactionSignature: registration
        ? registration.transaction_signature
        : null,
      registrationWorkflowAddress: registration
        ? registration.workflow_address
        : null,
      registrationRegistrar: registration ? registration.registrar : null,
      rpcUrl: options.rpcUrl || DEFAULT_RPC_URL,
      ...transactionMetadata(transaction),
    };
  }

  global.RialoVerifier = {
    DEFAULT_RPC_URL,
    DEFAULT_DEVICE_REGISTRAR,
    VerificationError,
    calculateBatchDigest,
    parseProofBundle,
    serializeProofBundle,
    verifyProofBundle,
  };
})(typeof window !== "undefined" ? window : globalThis);
