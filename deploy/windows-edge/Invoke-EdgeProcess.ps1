[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("gateway", "anchor", "publisher", "balanceguard")]
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

function Get-RialoRpcRoutes {
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
    return [PSCustomObject]@{
        RpcUrl = $rpcUrl
        CliRpcUrl = $cliRpcUrl
    }
}

function Format-InvariantNumber {
    param([double]$Value)
    return $Value.ToString("G", [Globalization.CultureInfo]::InvariantCulture)
}

switch ($Role) {
    "gateway" {
        $staleSeconds = if ($null -ne $config.gatewayStaleSeconds) {
            [double]$config.gatewayStaleSeconds
        } else {
            120.0
        }
        $pythonArguments = @(
            "-m", "gateway.edge_gateway", "listen",
            "--port", [string]$config.comPort,
            "--stale-seconds", (Format-InvariantNumber $staleSeconds)
        )
    }
    "anchor" {
        $routes = Get-RialoRpcRoutes
        $pythonArguments = @(
            "-m", "gateway.rialo_anchor", "watch",
            "--include-existing",
            "--program-id", [string]$config.programId,
            "--wsl-project-dir", [string]$config.wslProjectDirectory,
            "--rpc-url", [string]$routes.RpcUrl,
            "--cli-rpc-url", [string]$routes.CliRpcUrl
        )
    }
    "balanceguard" {
        $routes = Get-RialoRpcRoutes
        $feePayer = if ($config.rialoFeePayer) {
            [string]$config.rialoFeePayer
        } else {
            "BBjJpGwN3aV3BrMPw6BCZHZue8btcqTTfXouG9Nv9Sz6"
        }
        $lowBalance = if ($null -ne $config.rialoLowBalanceRlo) {
            [double]$config.rialoLowBalanceRlo
        } else {
            0.25
        }
        $airdropAmount = if ($null -ne $config.rialoAirdropAmountRlo) {
            [double]$config.rialoAirdropAmountRlo
        } else {
            1.0
        }
        $recoveryBalance = if ($null -ne $config.rialoRecoveryBalanceRlo) {
            [double]$config.rialoRecoveryBalanceRlo
        } else {
            0.25
        }
        $checkSeconds = if ($null -ne $config.rialoBalanceCheckSeconds) {
            [double]$config.rialoBalanceCheckSeconds
        } else {
            300.0
        }
        $cooldownSeconds = if ($null -ne $config.rialoAirdropCooldownSeconds) {
            [double]$config.rialoAirdropCooldownSeconds
        } else {
            900.0
        }
        $pythonArguments = @(
            "-m", "gateway.rialo_balance_guard",
            "--fee-payer", $feePayer,
            "--rpc-url", [string]$routes.RpcUrl,
            "--wsl-project-dir", [string]$config.wslProjectDirectory,
            "--low-balance-rlo", (Format-InvariantNumber $lowBalance),
            "--airdrop-amount-rlo", (Format-InvariantNumber $airdropAmount),
            "--recovery-balance-rlo", (Format-InvariantNumber $recoveryBalance),
            "--check-seconds", (Format-InvariantNumber $checkSeconds),
            "--airdrop-cooldown-seconds", (Format-InvariantNumber $cooldownSeconds)
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
        if ($process.ExitCode -ne 0) {
            "[$(Get-Date -Format o)] $Role exited with code $($process.ExitCode); restarting in 10 seconds." |
                Add-Content -Path $stderrPath
        }
    }
    catch {
        $_ | Out-String | Add-Content -Path $stderrPath
    }
    finally {
        Remove-Item -Path $pidPath -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 10
}
