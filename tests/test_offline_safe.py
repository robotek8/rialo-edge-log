from __future__ import annotations

import unittest

from gateway.archive_publisher import (
    ArchivePublishError,
    DEFAULT_OFFLINE_RETRY_SECONDS,
    is_transient_archive_error,
)


class OfflineSafePublisherTests(unittest.TestCase):
    def test_network_failures_enter_offline_backoff(self) -> None:
        self.assertTrue(
            is_transient_archive_error(
                ArchivePublishError("archive request failed: timed out")
            )
        )
        self.assertTrue(
            is_transient_archive_error(
                ArchivePublishError("heartbeat request failed: network is unreachable")
            )
        )

    def test_server_rejections_are_not_treated_as_connectivity_loss(self) -> None:
        self.assertFalse(
            is_transient_archive_error(
                ArchivePublishError("archive rejected the batch with HTTP 401: denied")
            )
        )

    def test_offline_retry_default_is_deliberately_slow(self) -> None:
        self.assertEqual(DEFAULT_OFFLINE_RETRY_SECONDS, 60.0)


if __name__ == "__main__":
    unittest.main()
