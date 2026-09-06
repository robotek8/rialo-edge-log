from __future__ import annotations

import inspect
import unittest

from gateway import edge_gateway


class GatewayReliabilityRegressionTests(unittest.TestCase):
    def test_signed_status_schema_is_a_signed_schema(self) -> None:
        self.assertIn(
            edge_gateway.SCHEMA_VERSION_SIGNED_STATUS,
            edge_gateway.SIGNED_SCHEMA_VERSIONS,
        )

    def test_listener_accepts_all_signed_schema_versions(self) -> None:
        source = inspect.getsource(edge_gateway.listen_to_serial)
        self.assertIn(
            'reading["schema_version"] not in SIGNED_SCHEMA_VERSIONS',
            source,
        )
        self.assertNotIn(
            'reading["schema_version"] != SCHEMA_VERSION_SIGNED',
            source,
        )

    def test_stale_watchdog_is_enabled_by_default(self) -> None:
        self.assertGreater(edge_gateway.DEFAULT_STALE_SECONDS, 0)
        parser = edge_gateway.build_parser()
        args = parser.parse_args(["listen", "--port", "COM10"])
        self.assertEqual(args.stale_seconds, edge_gateway.DEFAULT_STALE_SECONDS)


if __name__ == "__main__":
    unittest.main()
