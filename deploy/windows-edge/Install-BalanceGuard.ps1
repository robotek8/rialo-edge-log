#Requires -RunAsAdministrator

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$stateRoot = Join-Path $env:LOCALAPPDATA "RialoEdgeLog"
$configPath = Join-Path $stateRoot "config.json"
$runnerPath = Join-Path $PSScriptRoot "Invoke-EdgeProcess.ps1"
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "Rialo Edge Log configuration was not found: $configPath"
}
if (-not (Test-Path -LiteralPath $runnerPath -PathType Leaf)) {
    throw "Edge process runner was not found: $runnerPath"
}

$config = Get-Content -Path $configPath -Raw | ConvertFrom-Json
if (-not $config.repoRoot) {
    throw "Rialo Edge Log configuration does not contain repoRoot."
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero)
$trigger = New-ScheduledTaskTrigger -AtStartup
$arguments = "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runnerPath`" -Role balanceguard"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments

Write-Host "This only adds/updates RialoEdgeLog-BalanceGuard. Existing Gateway, Anchor, Publisher and Tunnel tasks are not modified."
Write-Host "Enter the Windows account password for $identity."
Write-Host "Use the account password, not the Windows Hello PIN."
$credential = Get-Credential -UserName $identity -Message "Rialo Edge Log balance guard"
if ($null -eq $credential) {
    throw "Windows credentials are required to install the balance guard task."
}
$password = $credential.GetNetworkCredential().Password
if ([string]::IsNullOrWhiteSpace($password)) {
    throw "The Windows account password cannot be empty."
}

try {
    Register-ScheduledTask `
        -TaskName "RialoEdgeLog-BalanceGuard" `
        -Action $action `
        -Trigger $trigger `
        -User $identity `
        -Password $password `
        -RunLevel Limited `
        -Settings $settings `
        -Description "Keep the Rialo DevNet fee payer funded and release rent-failed pending submissions" `
        -Force | Out-Null
}
finally {
    $password = $null
    $credential = $null
}

Start-ScheduledTask -TaskName "RialoEdgeLog-BalanceGuard"
Start-Sleep -Seconds 2
$task = Get-ScheduledTask -TaskName "RialoEdgeLog-BalanceGuard"
Write-Host "BalanceGuard: $($task.State)"
Write-Host "Logs: $(Join-Path $stateRoot 'logs')"
