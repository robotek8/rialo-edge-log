[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("start", "stop", "status")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$stateRoot = Join-Path $env:LOCALAPPDATA "RialoEdgeLog"
$roles = @("Gateway", "Anchor", "Publisher")
if ($null -ne (Get-ScheduledTask -TaskName "RialoEdgeLog-BalanceGuard" -ErrorAction SilentlyContinue)) {
    $roles = @("BalanceGuard") + $roles
}
if ($null -ne (Get-ScheduledTask -TaskName "RialoEdgeLog-Tunnel" -ErrorAction SilentlyContinue)) {
    $roles = @("Tunnel") + $roles
}

function Stop-ProcessTree {
    param(
        [Parameter(Mandatory = $true)]
        [int]$RootProcessId
    )

    $processes = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
    if ($null -eq $processes) {
        Stop-Process -Id $RootProcessId -Force -ErrorAction SilentlyContinue
        return
    }

    $childrenByParent = @{}
    foreach ($process in $processes) {
        $parentId = [int]$process.ParentProcessId
        if (-not $childrenByParent.ContainsKey($parentId)) {
            $childrenByParent[$parentId] = @()
        }
        $childrenByParent[$parentId] += [int]$process.ProcessId
    }

    $stack = New-Object System.Collections.Stack
    $order = New-Object System.Collections.Generic.List[int]
    $stack.Push($RootProcessId)
    while ($stack.Count -gt 0) {
        $current = [int]$stack.Pop()
        $order.Add($current)
        if ($childrenByParent.ContainsKey($current)) {
            foreach ($childId in $childrenByParent[$current]) {
                $stack.Push([int]$childId)
            }
        }
    }

    for ($index = $order.Count - 1; $index -ge 0; $index--) {
        Stop-Process -Id $order[$index] -Force -ErrorAction SilentlyContinue
    }
}

switch ($Action) {
    "start" {
        foreach ($role in $roles) {
            Start-ScheduledTask -TaskName "RialoEdgeLog-$role"
        }
        Start-Sleep -Seconds 2
    }
    "stop" {
        $trackedPids = @{}
        foreach ($role in $roles) {
            $pidPath = Join-Path $stateRoot "$($role.ToLowerInvariant()).pid"
            if (Test-Path $pidPath) {
                $processId = Get-Content -Path $pidPath -ErrorAction SilentlyContinue
                if ($processId -match "^\d+$") {
                    $trackedPids[$role] = [int]$processId
                }
            }
        }

        foreach ($role in $roles) {
            Stop-ScheduledTask -TaskName "RialoEdgeLog-$role" -ErrorAction SilentlyContinue
        }

        foreach ($role in $roles) {
            if ($trackedPids.ContainsKey($role)) {
                Stop-ProcessTree -RootProcessId $trackedPids[$role]
            }
            $pidPath = Join-Path $stateRoot "$($role.ToLowerInvariant()).pid"
            Remove-Item -Path $pidPath -Force -ErrorAction SilentlyContinue
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
