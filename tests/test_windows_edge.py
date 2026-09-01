from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsEdgeDeploymentTests(unittest.TestCase):
    def test_tasks_start_before_interactive_sign_in(self) -> None:
        installer = (
            ROOT / "deploy" / "windows-edge" / "Install-EdgeStack.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("#Requires -RunAsAdministrator", installer)
        self.assertIn("New-ScheduledTaskTrigger -AtStartup", installer)
        self.assertIn("-User $identity", installer)
        self.assertIn("-Password $windowsPassword", installer)
        self.assertNotIn("New-ScheduledTaskTrigger -AtLogOn", installer)
        self.assertNotIn("-LogonType Interactive", installer)

    def test_task_update_reuses_protected_archive_token(self) -> None:
        installer = (
            ROOT / "deploy" / "windows-edge" / "Install-EdgeStack.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("[switch]$RefreshArchiveToken", installer)
        self.assertIn("-not (Test-Path $tokenPath)", installer)
        self.assertIn("Reusing the existing DPAPI-protected archive token", installer)


if __name__ == "__main__":
    unittest.main()
