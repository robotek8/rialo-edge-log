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

    def test_background_workers_recover_unfinished_batches(self) -> None:
        runner = (
            ROOT / "deploy" / "windows-edge" / "Invoke-EdgeProcess.ps1"
        ).read_text(encoding="utf-8")

        self.assertEqual(runner.count('"--include-existing"'), 2)

    def test_anchor_has_separate_windows_and_wsl_rpc_routes(self) -> None:
        runner = (
            ROOT / "deploy" / "windows-edge" / "Invoke-EdgeProcess.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn('"--rpc-url", $rpcUrl', runner)
        self.assertIn('"--cli-rpc-url", $cliRpcUrl', runner)
        self.assertIn("ip route show default", runner)
        self.assertIn("[regex]::Match", runner)
        self.assertNotIn("awk '/default/", runner)
        self.assertGreater(
            runner.index("ip route show default"),
            runner.index('"anchor" {'),
        )

    def test_optional_rpc_tunnel_is_resilient_and_host_key_checked(self) -> None:
        tunnel = (
            ROOT / "deploy" / "windows-edge" / "Invoke-RpcTunnel.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn('"BatchMode=yes"', tunnel)
        self.assertIn('"ExitOnForwardFailure=yes"', tunnel)
        self.assertIn('"ServerAliveInterval=30"', tunnel)
        self.assertIn('"ServerAliveCountMax=3"', tunnel)
        self.assertIn('"StrictHostKeyChecking=yes"', tunnel)
        self.assertIn("while ($true)", tunnel)

    def test_installer_registers_tunnel_at_startup_with_restart_policy(self) -> None:
        installer = (
            ROOT / "deploy" / "windows-edge" / "Install-EdgeStack.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn('"RialoEdgeLog-Tunnel"', installer)
        self.assertIn("-RestartCount 999", installer)
        self.assertIn("-RestartInterval", installer)
        self.assertIn("-RemoteAddress \"172.16.0.0/12\"", installer)

    def test_manager_starts_tunnel_before_workers_when_installed(self) -> None:
        manager = (
            ROOT / "deploy" / "windows-edge" / "Manage-EdgeStack.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn('$roles = @("Tunnel") + $roles', manager)


if __name__ == "__main__":
    unittest.main()
