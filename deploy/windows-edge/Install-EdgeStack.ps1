#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$ComPort = "COM10",
    [string]$ProgramId = "GVJpRi8SVURsjKbLC84Azk24vV2cK3ib74aXRk5hdatF",
    [string]$ArchiveUrl = "https://rialo-edge-log.xyz",
    [string]$WslProjectDir = "~/rialo-edge-log",
    [string]$RpcUrl = "http://devnet.rialo.io:4100",
    [string]$RpcTunnelHost = "",
    [string]$RpcTunnelUser = "root",
    [string]$RpcTunnelKeyPath = "",
    [int]$RpcTunnelLocalPort = 44100,
    [switch]$RefreshArchiveToken
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$stateRoot = Join-Path $env:LOCALAPPDATA "RialoEdgeLog"
$configPath = Join-Path $stateRoot "config.json"
$tokenPath = Join-Path $stateRoot "archive-token.dpapi"
$runnerPath = Join-Path $PSScriptRoot "Invoke-EdgeProcess.ps1"
$tunnelRunnerPath = Join-Path $PSScriptRoot "Invoke-RpcTunnel.ps1"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name

New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stateRoot "logs") -Force | Out-Null

if ($RefreshArchiveToken -or -not (Test-Path $tokenPath)) {
    $secureToken = Read-Host "Paste the VPS ingestion token" -AsSecureString
    $plainToken = [System.Net.NetworkCredential]::new("", $secureToken).Password
    if ($plainToken -notmatch "^[0-9a-f]{64}$") {
        throw "The ingestion token must contain exactly 64 hexadecimal characters."
    }
    $plainToken = $null
    ConvertFrom-SecureString -SecureString $secureToken | Set-Content -Path $tokenPath -Encoding ASCII
}
else {
    Write-Host "Reusing the existing DPAPI-protected archive token."
}

$rpcTunnelEnabled = -not [string]::IsNullOrWhiteSpace($RpcTunnelHost)
if ($rpcTunnelEnabled) {
    if ([string]::IsNullOrWhiteSpace($RpcTunnelKeyPath)) {
        $RpcTunnelKeyPath = Join-Path $stateRoot "rialo-rpc-tunnel"
    }
    $RpcTunnelKeyPath = [IO.Path]::GetFullPath($RpcTunnelKeyPath)
    if (-not (Test-Path -LiteralPath $RpcTunnelKeyPath -PathType Leaf)) {
        throw "RPC tunnel private key was not found: $RpcTunnelKeyPath"
    }
    $RpcUrl = "http://127.0.0.1:$RpcTunnelLocalPort"
}

[ordered]@{
    repoRoot = $repoRoot
    comPort = $ComPort
    programId = $ProgramId
    archiveUrl = $ArchiveUrl
    publicationDirectory = "data\publications-vps"
    wslProjectDirectory = $WslProjectDir
    rpcUrl = $RpcUrl
    rpcTunnelEnabled = $rpcTunnelEnabled
    rpcTunnelHost = $RpcTunnelHost
    rpcTunnelUser = $RpcTunnelUser
    rpcTunnelKeyPath = $RpcTunnelKeyPath
    rpcTunnelLocalPort = $RpcTunnelLocalPort
    rpcTunnelDestinationHost = "devnet.rialo.io"
    rpcTunnelDestinationPort = 4100
} | ConvertTo-Json | Set-Content -Path $configPath -Encoding UTF8

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)
$trigger = New-ScheduledTaskTrigger -AtStartup

Write-Host "Enter the Windows account password for $identity."
Write-Host "Use the account password, not the Windows Hello PIN. Task Scheduler stores it securely."
$windowsCredential = Get-Credential -UserName $identity -Message "Rialo Edge Log background tasks"
if ($null -eq $windowsCredential) {
    throw "Windows credentials are required to run the edge stack before sign-in."
}
$windowsPassword = $windowsCredential.GetNetworkCredential().Password
if ([string]::IsNullOrWhiteSpace($windowsPassword)) {
    throw "The Windows account password cannot be empty."
}

try {
    if ($rpcTunnelEnabled) {
        $tunnelArguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$tunnelRunnerPath`""
        $tunnelAction = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $tunnelArguments
        Register-ScheduledTask `
            -TaskName "RialoEdgeLog-Tunnel" `
            -Action $tunnelAction `
            -Trigger $trigger `
            -User $identity `
            -Password $windowsPassword `
            -RunLevel Limited `
            -Settings $settings `
            -Description "Secure Rialo RPC tunnel through the configured VPS" `
            -Force | Out-Null

        Get-NetFirewallRule -DisplayName "Rialo Edge Log RPC tunnel from WSL" -ErrorAction SilentlyContinue |
            Remove-NetFirewallRule
        New-NetFirewallRule `
            -DisplayName "Rialo Edge Log RPC tunnel from WSL" `
            -Direction Inbound `
            -Action Allow `
            -Protocol TCP `
            -LocalPort $RpcTunnelLocalPort `
            -RemoteAddress "172.16.0.0/12" | Out-Null
    }
    else {
        Unregister-ScheduledTask -TaskName "RialoEdgeLog-Tunnel" -Confirm:$false -ErrorAction SilentlyContinue
        Get-NetFirewallRule -DisplayName "Rialo Edge Log RPC tunnel from WSL" -ErrorAction SilentlyContinue |
            Remove-NetFirewallRule
    }

    foreach ($role in @("Gateway", "Anchor", "Publisher")) {
        $taskName = "RialoEdgeLog-$role"
        $arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runnerPath`" -Role $($role.ToLowerInvariant())"
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -User $identity `
            -Password $windowsPassword `
            -RunLevel Limited `
            -Settings $settings `
            -Description "Rialo Edge Log $role background worker" `
            -Force | Out-Null
    }
}
finally {
    $windowsPassword = $null
    $windowsCredential = $null
}

Write-Host "Installed Rialo Edge Log tasks for $identity."
Write-Host "Configuration: $configPath"
Write-Host "The workers now start with Windows and do not wait for interactive sign-in."
Write-Host "Run .\deploy\windows-edge\Manage-EdgeStack.ps1 start after closing the manual workers."
