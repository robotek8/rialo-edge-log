import base64
import json
import struct
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from gateway.device_keys import generate_header
from gateway.edge_gateway import (
    DEFAULT_BATCH_SIZE,
    TelemetryError,
    calculate_proof,
    canonical_reading_payload,
    create_batch,
    decode_serial_line,
    empty_registry,
    enroll_registration,
    parse_telemetry_line,
    public_key_fingerprint,
    save_batch,
    save_registry,
    verify_batch,
    verify_batch_file,
    verify_reading_signature,
)
from gateway.rialo_args import (
    build_arguments,
    build_command,
    device_id_to_u64,
    hex_digest_to_u64_words,
)
from gateway.rialo_anchor import (
    RialoAnchorError,
    batch_receipt_exists,
    build_wsl_invocation,
    extract_transaction_signature,
    pending_receipt_path,
    receipt_path,
    save_pending_submission,
    submit_batch,
    watch_batches,
)
from gateway.rialo_verify import (
    RialoRpcClient,
    compare_batch_to_state,
    decode_account_state,
    decode_workflow_state,
    extract_workflow_address,
    extract_fee_payer,
    save_receipt,
)


def reading(sequence: int, temperature: float = 4.2) -> dict:
    return {
        "schema_version": 1,
        "device_id": "edge-A1B2C3",
        "sequence": sequence,
        "uptime_ms": sequence * 5000,
        "temperature_c": temperature,
        "simulated": True,
    }


def signed_reading(private_key: ec.EllipticCurvePrivateKey, sequence: int) -> dict:
    value = {
        "message_type": "telemetry",
        "schema_version": 2,
        "device_id": "edge-A1B2C3",
        "sequence": sequence,
        "uptime_ms": sequence * 5000,
        "temperature_milli_c": 4200 + sequence,
        "temperature_c": (4200 + sequence) / 1000.0,
        "simulated": True,
        "signature_algorithm": "ecdsa-p256-sha256-raw",
        "signature": "0" * 128,
    }
    der_signature = private_key.sign(
        canonical_reading_payload(value), ec.ECDSA(hashes.SHA256())
    )
    r_value, s_value = decode_dss_signature(der_signature)
    value["signature"] = (
        r_value.to_bytes(32, "big") + s_value.to_bytes(32, "big")
    ).hex()
    return value


def public_key_hex(private_key: ec.EllipticCurvePrivateKey) -> str:
    return private_key.public_key().public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    ).hex()


class TelemetryParsingTests(unittest.TestCase):
    def test_serial_sync_discards_non_utf8_boot_noise(self) -> None:
        self.assertIsNone(decode_serial_line(b"\xff\xfe\x80 boot noise\r\n"))

    def test_serial_sync_recovers_json_after_partial_line(self) -> None:
        raw = b"\xff\xfejunk" + json.dumps(reading(7)).encode() + b"\r\n"
        self.assertEqual(
            decode_serial_line(raw),
            json.dumps(reading(7)),
        )

    def test_parses_valid_firmware_line(self) -> None:
        result = parse_telemetry_line(json.dumps(reading(1)))
        self.assertEqual(result["device_id"], "edge-A1B2C3")
        self.assertEqual(result["temperature_c"], 4.2)

    def test_rejects_plain_startup_message(self) -> None:
        with self.assertRaises(TelemetryError):
            parse_telemetry_line("Rialo Edge Log - telemetry simulator")

    def test_rejects_missing_field(self) -> None:
        value = reading(1)
        del value["uptime_ms"]
        with self.assertRaises(TelemetryError):
            parse_telemetry_line(json.dumps(value))

    def test_rejects_invalid_temperature(self) -> None:
        with self.assertRaises(TelemetryError):
            parse_telemetry_line(json.dumps(reading(1, 999.0)))

    def test_parses_signed_reading(self) -> None:
        private_key = ec.generate_private_key(ec.SECP256R1())
        result = parse_telemetry_line(json.dumps(signed_reading(private_key, 1)))
        self.assertEqual(result["schema_version"], 2)
        self.assertEqual(len(result["signature"]), 128)


class DeviceSignatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = public_key_hex(self.private_key)
        self.value = signed_reading(self.private_key, 1)

    def test_valid_signature_is_accepted(self) -> None:
        self.assertTrue(verify_reading_signature(self.value, self.public_key))

    def test_changed_temperature_is_rejected_by_signature(self) -> None:
        self.value["temperature_milli_c"] += 1000
        self.value["temperature_c"] += 1.0
        self.assertFalse(verify_reading_signature(self.value, self.public_key))

    def test_public_key_is_bound_to_signed_batch(self) -> None:
        values = [signed_reading(self.private_key, number) for number in range(1, 4)]
        batch = create_batch(values, public_key_hex=self.public_key)
        valid, message = verify_batch(batch, self.public_key)
        self.assertTrue(valid)
        self.assertIn("device signatures", message)
        self.assertEqual(
            batch["device_public_key_fingerprint"],
            public_key_fingerprint(self.public_key),
        )

    def test_registry_refuses_key_change(self) -> None:
        registry = empty_registry()
        registration = {
            "device_id": "edge-A1B2C3",
            "public_key_sec1": self.public_key,
        }
        enrolled, _ = enroll_registration(registry, registration)
        self.assertTrue(enrolled)

        another_key = ec.generate_private_key(ec.SECP256R1())
        registration["public_key_sec1"] = public_key_hex(another_key)
        enrolled, message = enroll_registration(registry, registration)
        self.assertFalse(enrolled)
        self.assertIn("different public key", message)


class BatchProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timestamp = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)
        self.batch = create_batch(
            [reading(1, 4.20), reading(2, 4.21), reading(3, 4.19)],
            created_at=self.timestamp,
        )

    def test_proof_is_deterministic(self) -> None:
        self.assertEqual(calculate_proof(self.batch), calculate_proof(self.batch))

    def test_default_batch_covers_five_minutes_at_five_second_interval(self) -> None:
        self.assertEqual(DEFAULT_BATCH_SIZE, 60)

    def test_original_batch_is_verified(self) -> None:
        valid, message = verify_batch(self.batch)
        self.assertTrue(valid)
        self.assertIn("local proof matches", message)

    def test_changed_temperature_is_detected(self) -> None:
        self.batch["readings"][1]["temperature_c"] = 14.21
        valid, message = verify_batch(self.batch)
        self.assertFalse(valid)
        self.assertIn("does not match", message)

    def test_changed_metadata_is_detected(self) -> None:
        self.batch["reading_count"] = 100
        valid, message = verify_batch(self.batch)
        self.assertFalse(valid)
        self.assertIn("reading_count", message)

    def test_saved_batch_can_be_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = save_batch(self.batch, Path(directory))
            valid, _ = verify_batch_file(path)
            self.assertTrue(valid)


class DeviceKeyGeneratorTests(unittest.TestCase):
    def test_generates_ignored_arduino_header_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "device_secrets.h"
            public_key = generate_header(path)
            content = path.read_text(encoding="utf-8")
            self.assertEqual(len(public_key), 130)
            self.assertIn("DEVICE_PRIVATE_KEY[32]", content)
            self.assertIn(public_key, content)
            with self.assertRaises(FileExistsError):
                generate_header(path)


class RialoArgumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = public_key_hex(self.private_key)
        values = [signed_reading(self.private_key, number) for number in range(1, 4)]
        self.batch = create_batch(values, public_key_hex=self.public_key)

    def test_digest_is_split_into_four_little_endian_words(self) -> None:
        digest = "0001020304050607" + "00" * 24
        words = hex_digest_to_u64_words(digest)
        self.assertEqual(words[0], 0x0706050403020100)
        self.assertEqual(len(words), 4)

    def test_device_id_is_parsed_from_hexadecimal_suffix(self) -> None:
        self.assertEqual(device_id_to_u64("edge-0E0473"), 0x0E0473)

    def test_builds_all_twelve_workflow_arguments(self) -> None:
        arguments = build_arguments(self.batch)
        self.assertEqual(len(arguments), 12)
        self.assertEqual(arguments[0], ("device_id", 0xA1B2C3))
        self.assertEqual(arguments[-1], ("reading_count", 3))

    def test_command_uses_working_venus_invocation_shape(self) -> None:
        command = build_command(self.batch, "PROGRAM123")
        self.assertIn("--program-dir rialo/edge-log-proof", command)
        self.assertIn("--function start", command)
        self.assertIn("--arg workflow_pda_slug=random", command)
        self.assertTrue(command.endswith("PROGRAM123"))


class RialoHistoricalVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = public_key_hex(self.private_key)
        values = [signed_reading(self.private_key, number) for number in range(73, 85)]
        self.batch = create_batch(values, public_key_hex=self.public_key)
        argument_values = [value for _, value in build_arguments(self.batch)]
        self.raw_state = struct.pack("<13Q", 1, *argument_values)
        self.program_id = "PROGRAM123"
        self.workflow_address = "WORKFLOW456"

    def test_decodes_all_workflow_state_fields(self) -> None:
        state = decode_workflow_state(base64.b64encode(self.raw_state).decode("ascii"))
        self.assertEqual(state["device_id"], 0xA1B2C3)
        self.assertEqual(
            state["device_public_key_fingerprint"],
            self.batch["device_public_key_fingerprint"],
        )
        self.assertEqual(state["batch_digest"], self.batch["proof"]["digest"])
        self.assertEqual(state["first_sequence"], 73)
        self.assertEqual(state["last_sequence"], 84)
        self.assertEqual(state["reading_count"], 12)

    def test_extracts_workflow_account_from_successful_transaction(self) -> None:
        transaction = {
            "transaction": {
                "message": {
                    "accountKeys": [
                        "PAYER",
                        self.workflow_address,
                        "SYSTEM",
                        self.program_id,
                    ],
                    "instructions": [
                        {"programIdIndex": 3, "accounts": [0, 1, 2]}
                    ],
                }
            },
            "meta": {"err": None},
        }
        self.assertEqual(
            extract_workflow_address(transaction, self.program_id),
            self.workflow_address,
        )

    def test_extracts_public_fee_payer(self) -> None:
        transaction = {
            "transaction": {"message": {"accountKeys": ["PAYER", "WORKFLOW"]}}
        }
        self.assertEqual(extract_fee_payer(transaction), "PAYER")

    def test_balance_response_is_read_in_kelvins(self) -> None:
        class FakeBalanceClient(RialoRpcClient):
            def call(self, method: str, params: list[dict]) -> dict:
                self.assert_request = (method, params)
                return {"value": {"kelvins": 2_500_000_000}}

        client = FakeBalanceClient()
        self.assertEqual(client.get_balance("PAYER"), 2_500_000_000)
        self.assertEqual(
            client.assert_request,
            ("getBalance", [{"address": "PAYER"}]),
        )

    def test_matching_batch_and_rialo_state_have_no_differences(self) -> None:
        account = {
            "owner": self.program_id,
            "data": [base64.b64encode(self.raw_state).decode("ascii"), "base64"],
        }
        state = decode_account_state(account, self.program_id)
        self.assertEqual(compare_batch_to_state(self.batch, state), [])

    def test_changed_historical_batch_digest_is_reported(self) -> None:
        state = decode_workflow_state(base64.b64encode(self.raw_state).decode("ascii"))
        self.batch["proof"]["digest"] = "00" * 32
        self.assertEqual(compare_batch_to_state(self.batch, state), ["batch_digest"])

    def test_receipt_records_the_onchain_location(self) -> None:
        state = decode_workflow_state(base64.b64encode(self.raw_state).decode("ascii"))
        with tempfile.TemporaryDirectory() as directory:
            path = save_receipt(
                Path(directory),
                self.batch,
                self.program_id,
                "TRANSACTION789",
                {"block_height": 123},
                self.workflow_address,
                state,
            )
            receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "RIALO_VERIFIED")
        self.assertEqual(receipt["workflow_address"], self.workflow_address)
        self.assertEqual(receipt["block_height"], 123)


class RialoAnchoringTests(unittest.TestCase):
    def test_watcher_retries_transient_anchor_failure(self) -> None:
        batch_path = Path("data/batches/edge-A1B2C3/batch.json")
        args = SimpleNamespace(
            include_existing=True,
            batch_dir=Path("data/batches"),
            receipt_dir=Path("data/receipts"),
            registry=Path("data/device_registry.json"),
            program_id="PROGRAM123",
            rpc_url="http://example.invalid",
            wsl_project_dir="~/rialo-edge-log",
            rpc_wait_seconds=1.0,
            poll_seconds=0.0,
            retry_seconds=0.0,
            once=False,
        )
        success = (Path("receipt.json"), "signature", "workflow", "")

        with (
            patch(
                "gateway.rialo_anchor.list_batch_files",
                return_value=[batch_path],
            ),
            patch(
                "gateway.rialo_anchor.batch_receipt_exists",
                return_value=False,
            ),
            patch(
                "gateway.rialo_anchor.submit_batch",
                side_effect=[RialoAnchorError("temporary RPC error"), success],
            ) as submit,
            patch(
                "gateway.rialo_anchor.time.sleep",
                side_effect=[None, KeyboardInterrupt],
            ),
        ):
            result = watch_batches(args)

        self.assertEqual(result, 0)
        self.assertEqual(submit.call_count, 2)

    def setUp(self) -> None:
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = public_key_hex(self.private_key)
        self.batch = create_batch(
            [signed_reading(self.private_key, number) for number in range(1, 4)],
            public_key_hex=self.public_key,
        )
        self.program_id = "AfbPSJCLnmAAxhG66QoSV1Pp3WbTY6VNx55SZoKBnB7x"

    def test_builds_wsl_command_from_windows_without_shelling_out(self) -> None:
        command = build_wsl_invocation(
            self.batch, self.program_id, "~/rialo-edge-log"
        )
        self.assertEqual(command[:4], ["wsl.exe", "--", "bash", "-lc"])
        self.assertIn(
            'export PATH="$HOME/.local/share/rialo/bin:$PATH"', command[4]
        )
        self.assertIn('cd -- "$HOME"/rialo-edge-log', command[4])
        self.assertIn("rialo client program invoke", command[4])
        self.assertIn(self.program_id, command[4])

    def test_extracts_transaction_signature_from_cli_output(self) -> None:
        signature = (
            "2WbkTi4SB7449Yhy8Rwo1XwxwiGZLdn1dDqYhL4TYqnoTsStGXKuayH2Wch"
            "FYnkD1jntoaW5mPYcCjRKJMFqBRXL"
        )
        output = f"Invoked start\nTransaction: {signature}\n"
        self.assertEqual(extract_transaction_signature(output), signature)

    def test_receipt_path_is_stable_for_a_batch(self) -> None:
        expected = Path("data/receipts") / f"{self.batch['batch_id']}-rialo.json"
        self.assertEqual(receipt_path(self.batch, Path("data/receipts")), expected)

    def test_pending_submission_preserves_transaction_for_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = save_pending_submission(
                self.batch, root, self.program_id, "TRANSACTION789"
            )
            pending = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(pending["status"], "SUBMITTED_UNVERIFIED")
        self.assertEqual(pending["transaction_signature"], "TRANSACTION789")

    def test_existing_final_receipt_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            batch_path = root / "batch.json"
            batch_path.write_text(json.dumps(self.batch), encoding="utf-8")
            final = receipt_path(self.batch, root / "receipts")
            final.parent.mkdir(parents=True)
            final.write_text("{}", encoding="utf-8")
            self.assertTrue(batch_receipt_exists(batch_path, root / "receipts"))

    def test_submit_verifies_rpc_state_and_saves_receipt(self) -> None:
        signature = (
            "2WbkTi4SB7449Yhy8Rwo1XwxwiGZLdn1dDqYhL4TYqnoTsStGXKuayH2Wch"
            "FYnkD1jntoaW5mPYcCjRKJMFqBRXL"
        )
        workflow = "2zFvYcDgb4US6RHcPhvTVAQTcTK8T9R6hf9iNLHANUsp"
        raw_state = struct.pack(
            "<13Q", 1, *(value for _, value in build_arguments(self.batch))
        )
        transaction = {
            "block_height": 456,
            "transaction": {
                "message": {
                    "accountKeys": ["PAYER", workflow, "SYSTEM", self.program_id],
                    "instructions": [{"programIdIndex": 3, "accounts": [0, 1, 2]}],
                }
            },
            "meta": {"err": None},
        }
        account = {
            "owner": self.program_id,
            "data": [base64.b64encode(raw_state).decode("ascii"), "base64"],
        }

        class FakeClient:
            def get_transaction(self, requested_signature: str) -> dict:
                if requested_signature != signature:
                    raise AssertionError("unexpected transaction signature")
                return transaction

            def get_account_info(self, requested_address: str) -> dict:
                if requested_address != workflow:
                    raise AssertionError("unexpected workflow address")
                return account

        def fake_runner(*args, **kwargs) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout=f"Invoked start\nTransaction: {signature}\n",
                stderr="",
            )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "device_registry.json"
            save_registry(
                {
                    "schema_version": 1,
                    "devices": {
                        self.batch["device_id"]: {
                            "public_key_sec1": self.public_key,
                        }
                    },
                },
                registry_path,
            )
            batch_path = save_batch(self.batch, root)
            saved, saved_signature, saved_workflow, _ = submit_batch(
                batch_path,
                registry_path,
                root / "receipts",
                self.program_id,
                "http://example.invalid",
                "~/rialo-edge-log",
                1.0,
                client=FakeClient(),
                runner=fake_runner,
            )
            receipt = json.loads(saved.read_text(encoding="utf-8"))
            pending = pending_receipt_path(self.batch, root / "receipts")
            pending_exists = pending.exists()

        self.assertEqual(saved_signature, signature)
        self.assertEqual(saved_workflow, workflow)
        self.assertEqual(receipt["status"], "RIALO_VERIFIED")
        self.assertEqual(receipt["block_height"], 456)
        self.assertFalse(pending_exists)


if __name__ == "__main__":
    unittest.main()
