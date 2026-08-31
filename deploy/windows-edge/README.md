# Hidden Windows edge stack

The Windows edge stack keeps three independent workers running without visible
PowerShell windows:

- `Gateway`: receives signed NodeMCU telemetry from COM10;
- `Anchor`: records each completed batch in Rialo Devnet through WSL;
- `Publisher`: uploads only Rialo-verified batches to the HTTPS archive.

`Install-EdgeStack.ps1` registers one scheduled task per worker for the current
Windows user. Each task starts at logon and its wrapper restarts the worker ten
seconds after an exit. Output and error logs are written under
`%LOCALAPPDATA%\RialoEdgeLog\logs`.

The archive token is stored using Windows DPAPI. It can only be decrypted by
the same Windows account on the same computer. It is never written into the
repository, task command line or log files.

From the repository root, install the tasks once:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\deploy\windows-edge\Install-EdgeStack.ps1
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

