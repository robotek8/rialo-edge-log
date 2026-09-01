# Hidden Windows edge stack

The Windows edge stack keeps three independent workers running without visible
PowerShell windows:

- `Gateway`: receives signed NodeMCU telemetry from COM10;
- `Anchor`: records each completed batch in Rialo Devnet through WSL;
- `Publisher`: uploads only Rialo-verified batches to the HTTPS archive.

`Install-EdgeStack.ps1` registers one scheduled task per worker for the current
Windows user. Each task starts with Windows, before interactive sign-in, and its
wrapper restarts the worker ten seconds after an exit. Locking Windows or leaving
the computer at the sign-in screen does not stop telemetry. Sleep and hibernation
still pause all three workers. Output and error logs are written under
`%LOCALAPPDATA%\RialoEdgeLog\logs`.

The anchor retries temporary Rialo/RPC failures. After a reboot or worker restart,
the anchor and publisher also recover verified batches that were not completed by
an earlier run.

When Devnet is reset and the Venus program receives a new Program ID, the anchor
preserves pending files from the old deployment under `network-history/` and
submits the affected batches again instead of entering a permanent retry loop.

The archive token is stored using Windows DPAPI. It can only be decrypted by
the same Windows account on the same computer. It is never written into the
repository, task command line or log files.

Open PowerShell as Administrator. From the repository root, install or update
the tasks:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\deploy\windows-edge\Install-EdgeStack.ps1
```

The installer asks for the Windows account password so Task Scheduler can run
the workers before sign-in. Enter the account password, not the Windows Hello
PIN. The password is handed directly to Task Scheduler and is not written to
the repository, configuration, command line or logs. Re-run the installer after
changing the Windows account password.

An existing DPAPI-protected archive token is reused during task updates. Use
`-RefreshArchiveToken` only when the VPS ingestion token has been rotated:

```powershell
.\deploy\windows-edge\Install-EdgeStack.ps1 -RefreshArchiveToken
```

Close any manually running gateway, anchor and publisher processes before
starting the tasks:

```powershell
.\deploy\windows-edge\Manage-EdgeStack.ps1 start
.\deploy\windows-edge\Manage-EdgeStack.ps1 status
```

Stop all three workers when firmware maintenance requires exclusive access to
the serial port:

```powershell
.\deploy\windows-edge\Manage-EdgeStack.ps1 stop
```
