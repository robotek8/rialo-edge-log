[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("gateway", "anchor", "publisher")]
    [string]$Role
)

$ErrorActionPreference = "Stop"
$stateRoot = Join-Path $env:LOCALAPPDATA "RialoEdgeLog"
$configPath = Join-Path $stateRoot "config.json"
$tokenPath = Join-Path $stateRoot "archive-token.dpapi"
$logDirectory = Join-Path $stateRoot "logs"
$pidPath = Join-Path $stateRoot "$Role.pid"

$config = Get-Content -Path $configPath -Raw | ConvertFrom-Json
$python = (Get-Command "py.exe" -ErrorAction Stop).Source
$env:PYTHONUNBUFFERED = "1"
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null

switch ($Role) {
    "gateway" {
        $pythonArguments = @(
            "-m", "gateway.edge_gateway", "listen",
            "--port", [string]$config.comPort
        )
    }
    "anchor" {
        $rpcUrl = if ($config.rpcUrl) {
            [string]$config.rpcUrl
        } else {
            "http://devnet.rialo.io:4100"
        }
        $cliRpcUrl = $rpcUrl
        if ($config.rpcTunnelEnabled) {
            $routeOutput = & wsl.exe -- ip route show default
            $routeMatch = [regex]::Match(
                ($routeOutput -join "`n"),
                "(?m)^default\s+via\s+([0-9.]+)\b"
            )
            if (-not $routeMatch.Success) {
                throw "Could not determine the Windows host address from WSL"
            }
            $wslGateway = $routeMatch.Groups[1].Value
            $cliRpcUrl = "http://${wslGateway}:$($config.rpcTunnelLocalPort)"
        }
        $pythonArguments = @(
            "-m", "gateway.rialo_anchor", "watch",
            "--include-existing",
            "--program-id", [string]$config.programId,
            "--wsl-project-dir", [string]$config.wslProjectDirectory,
            "--rpc-url", $rpcUrl,
            "--cli-rpc-url", $cliRpcUrl
        )
    }
    "publisher" {
        $encryptedToken = (Get-Content -Path $tokenPath -Raw).Trim()
        $secureToken = ConvertTo-SecureString -String $encryptedToken
        $env:RIALO_EDGE_LOG_INGEST_TOKEN = [System.Net.NetworkCredential]::new("", $secureToken).Password
        $env:RIALO_EDGE_LOG_ARCHIVE_URL = [string]$config.archiveUrl
        $pythonArguments = @(
            "-m", "gateway.archive_publisher", "watch",
            "--include-existing",
            "--publication-dir", [string]$config.publicationDirectory
        )
    }
}

while ($true) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdoutPath = Join-Path $logDirectory "$Role-$stamp.out.log"
    $stderrPath = Join-Path $logDirectory "$Role-$stamp.err.log"
    try {
        $process = Start-Process `
            -FilePath $python `
            -ArgumentList $pythonArguments `
            -WorkingDirectory ([string]$config.repoRoot) `
            -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath `
            -PassThru
        Set-Content -Path $pidPath -Value $process.Id -Encoding ASCII
        $process.WaitForExit()
    }
    catch {
        $_ | Out-String | Add-Content -Path $stderrPath
    }
    finally {
        Remove-Item -Path $pidPath -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 10
}
