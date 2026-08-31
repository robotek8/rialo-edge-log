[CmdletBinding()]
param(
    [string]$ComPort = "COM10",
    [string]$ProgramId = "AfbPSJCLnmAAxhG66QoSV1Pp3WbTY6VNx55SZoKBnB7x",
    [string]$ArchiveUrl = "https://rialo-edge-log.xyz",
    [string]$WslProjectDir = "~/rialo-edge-log"
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$stateRoot = Join-Path $env:LOCALAPPDATA "RialoEdgeLog"
$configPath = Join-Path $stateRoot "config.json"
$tokenPath = Join-Path $stateRoot "archive-token.dpapi"
$runnerPath = Join-Path $PSScriptRoot "Invoke-EdgeProcess.ps1"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name

New-Item -ItemType Directory -Path $stateRoot -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stateRoot "logs") -Force | Out-Null

$secureToken = Read-Host "Paste the NEW VPS ingestion token" -AsSecureString
$plainToken = [System.Net.NetworkCredential]::new("", $secureToken).Password
if ($plainToken -notmatch "^[0-9a-f]{64}$") {
    throw "The ingestion token must contain exactly 64 hexadecimal characters."
}
$plainToken = $null
ConvertFrom-SecureString -SecureString $secureToken | Set-Content -Path $tokenPath -Encoding ASCII

[ordered]@{
    repoRoot = $repoRoot
    comPort = $ComPort
    programId = $ProgramId
    archiveUrl = $ArchiveUrl
    publicationDirectory = "data\publications-vps"
    wslProjectDirectory = $WslProjectDir
} | ConvertTo-Json | Set-Content -Path $configPath -Encoding UTF8

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited

foreach ($role in @("Gateway", "Anchor", "Publisher")) {
    $taskName = "RialoEdgeLog-$role"
    $arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runnerPath`" -Role $($role.ToLowerInvariant())"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Principal $principal `
        -Settings $settings `
        -Description "Rialo Edge Log $role worker" `
        -Force | Out-Null
}

Write-Host "Installed Rialo Edge Log tasks for $identity."
Write-Host "Configuration: $configPath"
Write-Host "Run .\deploy\windows-edge\Manage-EdgeStack.ps1 start after closing the three manual workers."

