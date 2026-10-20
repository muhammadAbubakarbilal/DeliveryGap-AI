param(
    [switch]$SkipAdminSeed,
    [System.Security.SecureString]$AdminPassword
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$NodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$Manifest = Join-Path $Root ".cache\local-services.json"
$Cache = Join-Path $Root ".cache"

function Test-LocalPort([int]$Port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Stop-ProcessTree([int]$RootId) {
    $processes = @(Get-CimInstance Win32_Process)
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $pending.Enqueue($RootId)
    $descendants = [System.Collections.Generic.List[int]]::new()
    while ($pending.Count -gt 0) {
        $parentId = $pending.Dequeue()
        foreach ($child in $processes | Where-Object { $_.ParentProcessId -eq $parentId }) {
            $pending.Enqueue([int]$child.ProcessId)
            $descendants.Add([int]$child.ProcessId)
        }
    }
    foreach ($processId in @($descendants.ToArray()) + @($RootId) | Select-Object -Unique) {
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
}

if (-not (Test-Path $Python)) {
    throw "Python virtual environment missing. Create it and install dependencies before starting."
}
if (-not $NodeCommand) {
    throw "Node.js is unavailable. Install the Node.js version required by the project."
}
if (-not (Test-Path (Join-Path $Root "apps\web\node_modules\next\dist\bin\next"))) {
    throw "Frontend dependencies are missing. Run pnpm.cmd install --frozen-lockfile first."
}
if (Test-Path $Manifest) {
    throw "A local service manifest already exists. Run scripts\stop-local.ps1 before restarting."
}

New-Item -ItemType Directory -Force -Path $Cache | Out-Null
foreach ($port in @(3000, 8000)) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
    try {
        $listener.Start()
    }
    catch {
        throw "Port $port is already in use. Stop that service before starting the demo."
    }
    finally {
        $listener.Stop()
    }
}

$environmentNames = @(
    "DATABASE_URL",
    "DATABASE_URL_UNPOOLED",
    "NEON_AUTH_BASE_URL",
    "NEON_AUTH_JWKS_URL",
    "APP_ORIGIN",
    "COOKIE_SECURE",
    "SOURCE_STORAGE_BACKEND",
    "LOCAL_STORAGE_PATH",
    "PYTHONPATH",
    "SEED_ADMIN_EMAIL",
    "SEED_ADMIN_NAME",
    "SEED_ADMIN_PASSWORD"
)
$originalEnvironment = @{}
foreach ($name in $environmentNames) {
    $originalEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

$started = @()
try {
    $env:DATABASE_URL = "sqlite:///./.cache/deliverygap-demo.db"
    $env:DATABASE_URL_UNPOOLED = "sqlite:///./.cache/deliverygap-demo.db"
    $env:NEON_AUTH_BASE_URL = ""
    $env:NEON_AUTH_JWKS_URL = ""
    $env:APP_ORIGIN = "http://localhost:3000"
    $env:COOKIE_SECURE = "false"
    $env:SOURCE_STORAGE_BACKEND = "filesystem"
    $env:LOCAL_STORAGE_PATH = ".cache/source-objects"
    $env:PYTHONPATH = (Join-Path $Root "apps\api")
    $env:SEED_ADMIN_EMAIL = if ($env:SEED_ADMIN_EMAIL) { $env:SEED_ADMIN_EMAIL } else { "admin@deliverygap.example.com" }
    $env:SEED_ADMIN_NAME = if ($env:SEED_ADMIN_NAME) { $env:SEED_ADMIN_NAME } else { "Workspace Admin" }

    Push-Location $Root
    try {
        & $Python -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            throw "Local SQLite migrations failed with exit code $LASTEXITCODE."
        }

        if (-not $SkipAdminSeed) {
            $securePassword = $AdminPassword
            if (-not $securePassword) {
                $securePassword = Read-Host "Local administrator password (12+ characters)" -AsSecureString
            }
            $passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
            try {
                $env:SEED_ADMIN_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
            }
            finally {
                [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
            }
            if ($env:SEED_ADMIN_PASSWORD.Length -lt 12) {
                throw "Administrator password must contain at least 12 characters."
            }
            & $Python -m app.seed
            if ($LASTEXITCODE -ne 0) {
                throw "Local administrator setup failed with exit code $LASTEXITCODE."
            }
        }

        $api = Start-Process -FilePath $Python -ArgumentList @(
            "-m", "uvicorn", "app.main:app", "--app-dir", "apps/api",
            "--host", "127.0.0.1", "--port", "8000"
        ) -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $Cache "local-api.log") `
            -RedirectStandardError (Join-Path $Cache "local-api-error.log")
        $started += [pscustomobject]@{ name = "api"; id = $api.Id; startTicks = $api.StartTime.ToUniversalTime().Ticks }

        $worker = Start-Process -FilePath $Python -ArgumentList @("scripts/local_worker.py") `
            -WorkingDirectory $Root -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $Cache "local-worker.log") `
            -RedirectStandardError (Join-Path $Cache "local-worker-error.log")
        $started += [pscustomobject]@{ name = "worker"; id = $worker.Id; startTicks = $worker.StartTime.ToUniversalTime().Ticks }

        $web = Start-Process -FilePath $NodeCommand.Source -ArgumentList @(
            "node_modules\next\dist\bin\next", "dev", "--hostname", "127.0.0.1", "--port", "3000"
        ) -WorkingDirectory (Join-Path $Root "apps\web") -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $Cache "local-web.log") `
            -RedirectStandardError (Join-Path $Cache "local-web-error.log")
        $started += [pscustomobject]@{ name = "web"; id = $web.Id; startTicks = $web.StartTime.ToUniversalTime().Ticks }
    }
    finally {
        Pop-Location
    }

    $ready = $false
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        if (-not (Get-Process -Id $api.Id -ErrorAction SilentlyContinue)) {
            throw "API stopped during startup. Inspect .cache\local-api-error.log."
        }
        if (-not (Get-Process -Id $web.Id -ErrorAction SilentlyContinue)) {
            throw "Frontend stopped during startup. Inspect .cache\local-web-error.log."
        }
        if (-not (Get-Process -Id $worker.Id -ErrorAction SilentlyContinue)) {
            throw "Local worker stopped during startup. Inspect .cache\local-worker-error.log."
        }
        $apiReady = $false
        $apiProbeError = ""
        try {
            $apiResponse = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/api/v1/health/ready" -TimeoutSec 2
            $apiReady = $apiResponse.StatusCode -eq 200
        }
        catch {
            $apiProbeError = $_.Exception.Message
        }
        $webListening = Test-LocalPort -Port 3000
        if ($apiReady -and $webListening) {
                $ready = $true
                break
        }
        if (($attempt % 10) -eq 0) {
            Write-Host "Waiting for local services (API ready: $apiReady; web port listening: $webListening; API probe: $apiProbeError)."
        }
        Start-Sleep -Seconds 2
    }
    if (-not $ready) {
        throw "Local services did not become ready within 180 seconds. Inspect .cache\local-*-error.log."
    }

    $started | ConvertTo-Json | Set-Content -LiteralPath $Manifest -Encoding UTF8
    Write-Host "DeliveryGap AI local demo is ready:"
    Write-Host "  Web:      http://localhost:3000"
    Write-Host "  API:      http://localhost:8000"
    Write-Host "  Database: isolated SQLite at .cache\deliverygap-demo.db"
    Write-Host "  Storage:  .cache\source-objects"
    Write-Host "  Worker:   local DB-polling worker (real job handlers)"
    Write-Host "Stop with: .\scripts\stop-local.ps1"
}
catch {
    foreach ($service in $started) {
        Stop-ProcessTree ([int]$service.id)
    }
    throw
}
finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $originalEnvironment[$name], "Process")
    }
}
