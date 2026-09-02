[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "status")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$stateRoot = Join-Path $env:LOCALAPPDATA "RialoEdgeLog"
$roles = @("Gateway", "Anchor", "Publisher")
if ($null -ne (Get-ScheduledTask -TaskName "RialoEdgeLog-Tunnel" -ErrorAction SilentlyContinue)) {
    $roles = @("Tunnel") + $roles
}

switch ($Action) {
    "start" {
        foreach ($role in $roles) {
            Start-ScheduledTask -TaskName "RialoEdgeLog-$role"
        }
        Start-Sleep -Seconds 2
    }
    "stop" {
        foreach ($role in $roles) {
            Stop-ScheduledTask -TaskName "RialoEdgeLog-$role" -ErrorAction SilentlyContinue
        }
        foreach ($role in $roles) {
            $pidPath = Join-Path $stateRoot "$($role.ToLowerInvariant()).pid"
            if (Test-Path $pidPath) {
                $processId = Get-Content -Path $pidPath -ErrorAction SilentlyContinue
                if ($processId -match "^\d+$") {
                    Stop-Process -Id ([int]$processId) -Force -ErrorAction SilentlyContinue
                }
                Remove-Item -Path $pidPath -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

foreach ($role in $roles) {
    $task = Get-ScheduledTask -TaskName "RialoEdgeLog-$role" -ErrorAction SilentlyContinue
    if ($null -eq $task) {
        Write-Host "${role}: NOT INSTALLED"
    }
    else {
        Write-Host "${role}: $($task.State)"
    }
}
