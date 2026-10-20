$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Manifest = Join-Path $Root ".cache\local-services.json"

if (-not (Test-Path $Manifest)) {
    Write-Host "No local service manifest found; no processes were stopped."
    exit 0
}

$services = Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json
$processes = @(Get-CimInstance Win32_Process)
foreach ($service in @($services)) {
    $process = Get-Process -Id ([int]$service.id) -ErrorAction SilentlyContinue
    if (-not $process) {
        continue
    }
    if ($process.StartTime.ToUniversalTime().Ticks -ne [long]$service.startTicks) {
        Write-Warning "PID $($service.id) was reused; leaving it untouched."
        continue
    }
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $pending.Enqueue([int]$service.id)
    $descendants = [System.Collections.Generic.List[int]]::new()
    while ($pending.Count -gt 0) {
        $parentId = $pending.Dequeue()
        foreach ($child in $processes | Where-Object { $_.ParentProcessId -eq $parentId }) {
            $pending.Enqueue([int]$child.ProcessId)
            $descendants.Add([int]$child.ProcessId)
        }
    }
    foreach ($processId in @($descendants.ToArray()) + @([int]$service.id) | Select-Object -Unique) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Stopped $($service.name) process tree rooted at PID $($service.id)."
}

Remove-Item -LiteralPath $Manifest -Force
