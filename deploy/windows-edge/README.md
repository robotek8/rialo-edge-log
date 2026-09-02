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

## Optional RPC tunnel

Some home networks block Rialo Devnet's TCP port `4100` even though a VPS can
reach it. In that case the installer can register a fourth startup task,
`RialoEdgeLog-Tunnel`. It maintains an authenticated SSH port forward through a
trusted VPS, restarts after connection failures, and gives both the Windows
verifier and the Rialo CLI inside WSL a working RPC route. The direct RPC route
remains the default.

Create a dedicated SSH key and authorize its public half on a restricted,
unprivileged VPS account. Make one interactive SSH connection first so the VPS
host key is pinned in the Windows account's `known_hosts` file. Then install or
update the stack from an Administrator PowerShell window:

```powershell
$key = Join-Path $env:LOCALAPPDATA "RialoEdgeLog\rialo-rpc-tunnel"
.\deploy\windows-edge\Install-EdgeStack.ps1 `
    -RpcTunnelHost "vps.example.com" `
    -RpcTunnelUser "rialo-rpc" `
    -RpcTunnelKeyPath $key
```

The local tunnel listens on port `44100` by default. Its firewall rule accepts
only the WSL NAT address range; SSH still verifies the pinned VPS host key and
exits if port forwarding cannot be established. Use the same installer without
`-RpcTunnelHost` to disable and remove the tunnel task.

When Devnet is reset and the Venus program receives a new Program ID, the anchor
preserves pending files from the old deployment under `network-history/` and
submits the affected batches again instead of entering a permanent retry loop.
Pass the replacement explicitly with `-ProgramId NEW_PROGRAM_ID` when updating
the scheduled tasks after such a reset.

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
starting the tasks. The manager starts the tunnel first when it is installed:

```powershell
.\deploy\windows-edge\Manage-EdgeStack.ps1 start
.\deploy\windows-edge\Manage-EdgeStack.ps1 status
```

Stop the complete stack when firmware maintenance requires exclusive access to
the serial port:

```powershell
.\deploy\windows-edge\Manage-EdgeStack.ps1 stop
```
