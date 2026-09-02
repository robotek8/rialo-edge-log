[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$stateRoot = Join-Path $env:LOCALAPPDATA "RialoEdgeLog"
$configPath = Join-Path $stateRoot "config.json"
$logDirectory = Join-Path $stateRoot "logs"
$ssh = Join-Path $env:WINDIR "System32\OpenSSH\ssh.exe"

$config = Get-Content -Path $configPath -Raw | ConvertFrom-Json
if (-not $config.rpcTunnelEnabled) {
    throw "RPC tunnel is not enabled in $configPath"
}
if (-not (Test-Path -LiteralPath ([string]$config.rpcTunnelKeyPath) -PathType Leaf)) {
    throw "RPC tunnel private key was not found"
}

New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

while ($true) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdoutPath = Join-Path $logDirectory "tunnel-$stamp.out.log"
    $stderrPath = Join-Path $logDirectory "tunnel-$stamp.err.log"
    $forward = "0.0.0.0:$($config.rpcTunnelLocalPort):$($config.rpcTunnelDestinationHost):$($config.rpcTunnelDestinationPort)"
    $destination = "$($config.rpcTunnelUser)@$($config.rpcTunnelHost)"
    $quotedKeyPath = '"' + [string]$config.rpcTunnelKeyPath + '"'
    $arguments = @(
        "-N", "-T",
        "-i", $quotedKeyPath,
        "-o", "BatchMode=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "StrictHostKeyChecking=yes",
        "-L", $forward,
        $destination
    )

    try {
        $process = Start-Process `
            -FilePath $ssh `
            -ArgumentList $arguments `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -PassThru
        $process.WaitForExit()
    }
    catch {
        $_ | Out-String | Add-Content -Path $stderrPath
    }

    Start-Sleep -Seconds 10
}
