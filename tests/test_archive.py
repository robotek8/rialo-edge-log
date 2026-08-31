import base64
import json
import struct
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from archive.server import ArchiveStore, handler_factory
from gateway.archive_publisher import publish_batch_id
from gateway.edge_gateway import (
    create_batch,
    empty_registry,
    enroll_registration,
    save_batch,
    save_registry,
)
from gateway.portal import PortalStore
from gateway.rialo_args import build_arguments
from tests.test_portal import signed_reading


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.data_dir = self.root / "gateway-data"
        private_key = ec.generate_private_key(ec.SECP256R1())
        public_key = private_key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        ).hex()
        self.batch = create_batch(
            [signed_reading(private_key, number) for number in range(10, 13)],
            public_key_hex=public_key,
        )
        save_batch(self.batch, self.data_dir)
        registry = empty_registry()
        enrolled, _ = enroll_registration(
            registry,
            {"device_id": self.batch["device_id"], "public_key_sec1": public_key},
        )
        self.assertTrue(enrolled)
        save_registry(registry, self.data_dir / "device_registry.json")

        self.program_id = "PROGRAM123"
        self.workflow = "WORKFLOW456"
        self.transaction = "TRANSACTION789"
        argument_values = [value for _, value in build_arguments(self.batch)]
        raw_state = struct.pack("<13Q", 1, *argument_values)
        account = {
            "owner": self.program_id,
            "data": [base64.b64encode(raw_state).decode("ascii"), "base64"],
        }
        transaction_result = {
            "transaction": {
                "message": {
                    "accountKeys": ["PAYER", self.workflow, self.program_id],
                    "instructions": [{"programIdIndex": 2, "accounts": [0, 1]}],
                }
            },
            "meta": {"err": None, "fee": 5000},
        }

        class FakeClient:
            def get_transaction(inner_self, signature: str) -> dict:
                self.assertEqual(signature, self.transaction)
                return transaction_result

            def get_account_info(inner_self, address: str) -> dict:
                self.assertEqual(address, self.workflow)
                return account

            def get_balance(inner_self, address: str) -> int:
                self.assertEqual(address, "PAYER")
                return 2_000_000_000

        self.client_factory = lambda _url: FakeClient()
        receipt_dir = self.data_dir / "receipts"
        receipt_dir.mkdir()
        (receipt_dir / f"{self.batch['batch_id']}-rialo.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "RIALO_VERIFIED",
                    "batch_id": self.batch["batch_id"],
                    "program_id": self.program_id,
                    "transaction_signature": self.transaction,
                    "workflow_address": self.workflow,
                }
            ),
            encoding="utf-8",
        )
        self.bundle = PortalStore(self.data_dir).export_bundle(self.batch["batch_id"])
        self.archive = ArchiveStore(
            self.root / "archive.sqlite3", client_factory=self.client_factory
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_ingest_builds_public_device_history(self) -> None:
        result = self.archive.ingest(self.bundle)
        self.assertEqual(result["status"], "PUBLISHED")
        devices = self.archive.list_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0]["device_id"], "edge-0E0473")
        self.assertEqual(devices[0]["batch_count"], 1)
        batches = self.archive.list_batches("edge-0E0473")
        self.assertEqual(batches[0]["first_sequence"], 10)
        self.assertAlmostEqual(batches[0]["temperature"]["average"], 4.211)

    def test_repeated_identical_ingest_is_idempotent(self) -> None:
        self.archive.ingest(self.bundle)
        result = self.archive.ingest(self.bundle)
        self.assertEqual(result["status"], "ALREADY_PUBLISHED")
        self.assertEqual(len(self.archive.list_batches()), 1)

    def test_stored_batch_can_be_reverified_live(self) -> None:
        self.archive.ingest(self.bundle)
        result = self.archive.verify(self.batch["batch_id"])
        self.assertEqual(result["status"], "RIALO_VERIFIED")

    def test_network_status_uses_public_fee_payer_and_balance(self) -> None:
        self.archive.ingest(self.bundle)
        result = self.archive.network_status()
        self.assertEqual(result["network"], "Rialo Devnet")
        self.assertEqual(result["fee_payer"], "PAYER")
        self.assertEqual(result["balance_rlo"], 2.0)
        self.assertEqual(result["latest_fee_rlo"], 0.000005)
        self.assertEqual(result["anchored_transactions_24h"], 1)
        self.assertFalse(result["low_balance"])

    def test_daily_estimate_follows_five_minute_batch_interval(self) -> None:
        estimate = self.archive._daily_anchor_estimate(
            ["2026-08-31T10:00:00Z", "2026-08-31T10:05:00Z"]
        )
        self.assertEqual(estimate, 288)

    def test_public_batch_detail_contains_independent_proof_material(self) -> None:
        self.archive.ingest(self.bundle)
        detail = self.archive.get_batch(self.batch["batch_id"])
        bundle = detail["proof_bundle"]
        self.assertEqual(bundle["batch"]["proof"]["digest"], self.batch["proof"]["digest"])
        self.assertEqual(bundle["device"]["public_key_sec1"], self.bundle["device"]["public_key_sec1"])

    def test_http_ingest_requires_token_and_publisher_can_upload(self) -> None:
        static_directory = Path(__file__).resolve().parent.parent / "portal"
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            handler_factory(self.archive, static_directory, "correct-token"),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        archive_url = f"http://127.0.0.1:{server.server_port}"
        try:
            request = urllib.request.Request(
                archive_url + "/api/ingest",
                data=json.dumps(self.bundle).encode("utf-8"),
                headers={"Authorization": "Bearer wrong-token"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(context.exception.code, 401)

            publication, result = publish_batch_id(
                self.batch["batch_id"],
                self.data_dir,
                self.root / "publications",
                archive_url,
                "correct-token",
            )
            self.assertEqual(result["status"], "PUBLISHED")
            self.assertTrue(publication.is_file())

            with urllib.request.urlopen(archive_url + "/api/devices", timeout=2) as response:
                devices = json.load(response)
            self.assertEqual(devices["count"], 1)

            with urllib.request.urlopen(
                archive_url + "/api/network-status", timeout=2
            ) as response:
                network = json.load(response)
            self.assertEqual(network["fee_payer"], "PAYER")
            self.assertEqual(network["balance_rlo"], 2.0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
