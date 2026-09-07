from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateway.rialo_balance_guard import (
    build_airdrop_invocation,
    is_insufficient_funds_for_rent,
    recover_rent_failed_pending,
    rlo_to_kelvins,
)


FEE_PAYER = "BBjJpGwN3aV3BrMPw6BCZHZue8btcqTTfXouG9Nv9Sz6"
SIGNATURE = "4tH5gvkk3q55r3mcQAYJGRj7sxvrWmjqL7ZKdUKWvfyZoDErZBfqufgdrPutVyLN3EM1FRBdbq4qmUgrask5fb6E"


class FakeClient:
    def get_transaction(self, signature: str):
        self.signature = signature
        return {
            "transaction": {
                "message": {
                    "accountKeys": [FEE_PAYER],
                }
            },
            "meta": {
                "err": {
                    "InsufficientFundsForRent": {
                        "account_index": 0,
                    }
                }
            },
        }


class RialoBalanceGuardTests(unittest.TestCase):
    def test_rlo_conversion_matches_devnet_units(self) -> None:
        self.assertEqual(rlo_to_kelvins(1.0), 1_000_000_000)
        self.assertEqual(rlo_to_kelvins(0.25), 250_000_000)

    def test_detects_nested_insufficient_rent_error(self) -> None:
        error = {"TransactionError": {"InsufficientFundsForRent": {"account_index": 0}}}
        self.assertTrue(is_insufficient_funds_for_rent(error))
        self.assertFalse(is_insufficient_funds_for_rent({"Other": "failure"}))

    def test_airdrop_invocation_uses_existing_wsl_wallet(self) -> None:
        command = build_airdrop_invocation(1.0, "~/rialo-edge-log")
        self.assertEqual(command[:4], ["wsl.exe", "--", "bash", "-lc"])
        self.assertIn("rialo client airdrop --amount 1", command[4])
        self.assertIn("$HOME", command[4])

    def test_rent_failed_pending_is_archived_for_fresh_resubmission(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            receipt_dir = Path(temp)
            pending = receipt_dir / "batch-rialo.pending.json"
            pending.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "SUBMITTED_UNVERIFIED",
                        "batch_id": "batch",
                        "program_id": "program",
                        "transaction_signature": SIGNATURE,
                    }
                ),
                encoding="utf-8",
            )

            archived = recover_rent_failed_pending(
                receipt_dir,
                FEE_PAYER,
                FakeClient(),
            )

            self.assertEqual(len(archived), 1)
            self.assertFalse(pending.exists())
            self.assertTrue(archived[0].exists())
            self.assertTrue(
                archived[0].with_suffix(archived[0].suffix + ".error.json").exists()
            )


if __name__ == "__main__":
    unittest.main()
