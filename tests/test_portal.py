import base64
import http.client
import json
import struct
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from gateway.edge_gateway import (
    canonical_reading_payload,
    create_batch,
    empty_registry,
    enroll_registration,
    save_batch,
    save_registry,
)
from gateway.portal import PortalStore, handler_factory
from gateway.rialo_args import (
    build_arguments,
    build_registration_arguments,
    registration_workflow_slug,
)


def signed_reading(
    private_key: ec.EllipticCurvePrivateKey, sequence: int
) -> dict:
    reading = {
        "message_type": "telemetry",
        "schema_version": 2,
        "device_id": "edge-0E0473",
        "sequence": sequence,
        "uptime_ms": sequence * 5000,
        "temperature_milli_c": 4200 + sequence,
        "temperature_c": (4200 + sequence) / 1000.0,
        "simulated": True,
        "signature_algorithm": "ecdsa-p256-sha256-raw",
        "signature": "0" * 128,
    }
    der = private_key.sign(
        canonical_reading_payload(reading), ec.ECDSA(hashes.SHA256())
    )
    r_value, s_value = decode_dss_signature(der)
    reading["signature"] = (
        r_value.to_bytes(32, "big") + s_value.to_bytes(32, "big")
    ).hex()
    return reading


class PortalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temporary.name)
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self.private_key.public_key().public_bytes(
            serialization.Encoding.X962,
            serialization.PublicFormat.UncompressedPoint,
        ).hex()
        self.batch = create_batch(
            [signed_reading(self.private_key, number) for number in range(1, 4)],
            public_key_hex=self.public_key,
        )
        self.batch_path = save_batch(self.batch, self.data_dir)

        registry = empty_registry()
        enrolled, _ = enroll_registration(
            registry,
            {
                "device_id": self.batch["device_id"],
                "public_key_sec1": self.public_key,
            },
        )
        self.assertTrue(enrolled)
        save_registry(registry, self.data_dir / "device_registry.json")

        self.program_id = "PROGRAM123"
        self.workflow = "WORKFLOW456"
        self.transaction = "TRANSACTION789"
        self.registration_workflow = "REGISTRATIONWORKFLOW"
        self.registration_transaction = "REGISTRATIONTRANSACTION"
        argument_values = [value for _, value in build_arguments(self.batch)]
        raw_state = struct.pack("<13Q", 1, *argument_values)
        self.account = {
            "owner": self.program_id,
            "data": [base64.b64encode(raw_state).decode("ascii"), "base64"],
        }
        self.transaction_result = {
            "transaction": {
                "message": {
                    "accountKeys": ["PAYER", self.workflow, self.program_id],
                    "instructions": [{"programIdIndex": 2, "accounts": [0, 1]}],
                }
            },
            "meta": {"err": None},
        }
        registration_values = [
            value
            for _, value in build_registration_arguments(
                self.batch["device_id"],
                self.batch["device_public_key_fingerprint"],
            )
        ]
        registration_raw_state = struct.pack(
            "<13Q", 1, *registration_values, *([0] * 7)
        )
        self.registration_account = {
            "owner": self.program_id,
            "data": [
                base64.b64encode(registration_raw_state).decode("ascii"),
                "base64",
            ],
        }
        self.registration_transaction_result = {
            "transaction": {
                "message": {
                    "accountKeys": [
                        "PAYER",
                        self.registration_workflow,
                        self.program_id,
                    ],
                    "instructions": [{"programIdIndex": 2, "accounts": [0, 1]}],
                }
            },
            "meta": {"err": None},
        }
        receipt_dir = self.data_dir / "receipts"
        receipt_dir.mkdir()
        self.receipt_path = receipt_dir / f"{self.batch['batch_id']}-rialo.json"
        self.receipt_path.write_text(
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

        registration_dir = self.data_dir / "registrations"
        registration_dir.mkdir()
        (registration_dir / f"{self.batch['device_id']}-rialo-registration.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "RIALO_DEVICE_REGISTERED",
                    "device_id": self.batch["device_id"],
                    "public_key_fingerprint": self.batch[
                        "device_public_key_fingerprint"
                    ],
                    "program_id": self.program_id,
                    "transaction_signature": self.registration_transaction,
                    "workflow_address": self.registration_workflow,
                    "workflow_slug": registration_workflow_slug(
                        self.batch["device_id"]
                    ),
                    "registrar": "PAYER",
                }
            ),
            encoding="utf-8",
        )

        transaction_result = self.transaction_result
        account = self.account
        registration_transaction_result = self.registration_transaction_result
        registration_account = self.registration_account

        class FakeClient:
            def get_transaction(self, signature: str) -> dict:
                if signature == "TRANSACTION789":
                    return transaction_result
                if signature == "REGISTRATIONTRANSACTION":
                    return registration_transaction_result
                raise AssertionError("unexpected transaction")

            def get_account_info(self, address: str) -> dict:
                if address == "WORKFLOW456":
                    return account
                if address == "REGISTRATIONWORKFLOW":
                    return registration_account
                raise AssertionError("unexpected workflow")

        self.store = PortalStore(
            self.data_dir,
            client_factory=lambda _url: FakeClient(),
            expected_device_registrar="PAYER",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_lists_real_batches_and_receipt_status(self) -> None:
        batches = self.store.list_batches()
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["status"], "ANCHORED")
        self.assertEqual(batches[0]["first_sequence"], 1)
        self.assertAlmostEqual(batches[0]["temperature"]["average"], 4.202)

    def test_batch_detail_includes_public_browser_verification_bundle(self) -> None:
        detail = self.store.get_batch(self.batch["batch_id"])
        bundle = detail["proof_bundle"]
        self.assertEqual(bundle["bundle_type"], "rialo-edge-log-proof")
        self.assertEqual(bundle["schema_version"], 2)
        self.assertEqual(
            bundle["device_registration"]["status"], "RIALO_DEVICE_REGISTERED"
        )
        self.assertEqual(bundle["batch"]["proof"]["digest"], self.batch["proof"]["digest"])
        self.assertEqual(bundle["device"]["public_key_sec1"], self.public_key)

    def test_exported_bundle_verifies_against_rialo(self) -> None:
        bundle = self.store.export_bundle(self.batch["batch_id"])
        result = self.store.verify_bundle(bundle)
        self.assertEqual(result["status"], "RIALO_VERIFIED")
        self.assertTrue(result["rialo_verified"])
        self.assertTrue(result["device_registration_verified"])
        self.assertEqual(bundle["device"]["public_key_sec1"], self.public_key)

    def test_changed_exported_bundle_is_detected(self) -> None:
        bundle = self.store.export_bundle(self.batch["batch_id"])
        bundle["batch"]["readings"][0]["temperature_c"] += 10.0
        bundle["batch"]["readings"][0]["temperature_milli_c"] += 10_000
        result = self.store.verify_bundle(bundle)
        self.assertEqual(result["status"], "TAMPERED")

    def test_tamper_demo_never_changes_original_batch(self) -> None:
        before = self.batch_path.read_bytes()
        result = self.store.simulate_tampering(self.batch["batch_id"])
        self.assertEqual(result["status"], "TAMPERED")
        self.assertFalse(result["original_file_changed"])
        self.assertEqual(self.batch_path.read_bytes(), before)

    def test_unanchored_batch_can_still_pass_local_verification(self) -> None:
        self.receipt_path.unlink()
        result = self.store.verify(self.batch["batch_id"])
        self.assertEqual(result["status"], "LOCAL_VERIFIED")
        self.assertFalse(result["rialo_verified"])

    def test_http_server_exposes_dashboard_and_batch_api(self) -> None:
        static_directory = Path(__file__).resolve().parent.parent / "portal"
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), handler_factory(self.store, static_directory)
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection(
                "127.0.0.1", server.server_port, timeout=2
            )
            connection.request("GET", "/api/batches")
            response = connection.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(payload["count"], 1)

            connection.request("GET", "/")
            response = connection.getresponse()
            html = response.read().decode("utf-8")
            self.assertEqual(response.status, 200)
            self.assertIn("Verifiable Telemetry", html)
            self.assertIn('id="lang-en"', html)
            self.assertIn('id="lang-ru"', html)
            self.assertIn('id="chart-tooltip"', html)
            self.assertIn('id="batch-pagination"', html)
            self.assertIn('id="proof-stream-track"', html)
            self.assertIn('id="download-proof-btn"', html)
            self.assertIn('rel="icon" href="/favicon.svg"', html)
            self.assertIn('rel="manifest" href="/site.webmanifest"', html)
            self.assertIn('/verifier.js', html)
            self.assertIn('href="https://github.com/robotek8/rialo-edge-log"', html)
            self.assertIn('href="https://x.com/ra5alghul"', html)
            self.assertIn('href="https://t.me/Ras_a1_Ghu1"', html)
            self.assertIn('property="og:image" content="https://rialo-edge-log.xyz/og-image.png?v=3"', html)
            self.assertIn('name="twitter:card" content="summary_large_image"', html)
            self.assertIn('id="limits-title"', html)

            connection.request("GET", "/favicon.svg")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Content-Type"), "image/svg+xml; charset=utf-8")
            self.assertIn(b"#FF7A1A", response.read())

            for icon_path in ("/github.svg", "/x.svg", "/telegram.svg"):
                connection.request("GET", icon_path)
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    response.getheader("Content-Type"),
                    "image/svg+xml; charset=utf-8",
                )
                self.assertIn(b'viewBox="0 0 24 24"', response.read())

            connection.request("GET", "/og-image.png")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Content-Type"), "image/png")
            self.assertTrue(response.read().startswith(b"\x89PNG\r\n\x1a\n"))
            connection.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_portal_auto_refreshes_live_archive_data(self) -> None:
        static_directory = Path(__file__).resolve().parent.parent / "portal"
        script = (static_directory / "app.js").read_text(encoding="utf-8")
        self.assertIn("const AUTO_REFRESH_INTERVAL_MS = 30_000;", script)
        self.assertIn("loadSelectedDeviceHistory()", script)
        self.assertIn('document.addEventListener("visibilitychange"', script)
        self.assertNotIn("window.setInterval(renderDevices", script)


if __name__ == "__main__":
    unittest.main()
