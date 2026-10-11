param([int]$WebPort=5173,[int]$ApiPort=8000,[switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$financeRoot = $PSScriptRoot
$financeBackend = Join-Path $financeRoot 'backend'
$financeFrontend = Join-Path $financeRoot 'frontend'
$financeRuntime = Join-Path $financeRoot '.runtime'
foreach ($financePort in @($ApiPort,$WebPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $financePort -ErrorAction SilentlyContinue) {
        throw "Port $financePort is occupied. Stop recorded finance services first or choose another WebPort."
    }
}
New-Item -ItemType Directory -Force -Path $financeRuntime | Out-Null
Set-Location -LiteralPath $financeBackend
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
if (-not $SkipInstall) {
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed' }
}
Set-Location -LiteralPath $financeFrontend
if (-not $SkipInstall) {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
}
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
$financePython = Join-Path $financeBackend '.venv\Scripts\python.exe'
$financeNode = (Get-Command node.exe).Source
$financeVite = Join-Path $financeFrontend 'node_modules\vite\bin\vite.js'
$financeApiArgs = @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', [string]$ApiPort)
if (Test-Path (Join-Path $financeRoot '.env')) { $financeApiArgs += @('--env-file', '..\.env') }
$financeApi = Start-Process -FilePath $financePython -WorkingDirectory $financeBackend -ArgumentList $financeApiArgs -WindowStyle Hidden -RedirectStandardOutput (Join-Path $financeRuntime 'api.log') -RedirectStandardError (Join-Path $financeRuntime 'api-error.log') -PassThru
$env:FINANCE_API_INTERNAL_URL = "http://127.0.0.1:$ApiPort"
$financeWeb = Start-Process -FilePath $financeNode -WorkingDirectory $financeFrontend -ArgumentList ('"' + $financeVite + '"'), 'preview', '--host', '127.0.0.1', '--port', "$WebPort", '--strictPort' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $financeRuntime 'web.log') -RedirectStandardError (Join-Path $financeRuntime 'web-error.log') -PassThru
$financeWorker = Start-Process -FilePath $financePython -WorkingDirectory $financeBackend -ArgumentList '-m', 'app.worker' -WindowStyle Hidden -RedirectStandardOutput (Join-Path $financeRuntime 'worker.log') -RedirectStandardError (Join-Path $financeRuntime 'worker-error.log') -PassThru
$financeProcesses = @(
    @{ id=$financeApi.Id; executable=$financePython; started=$financeApi.StartTime.ToUniversalTime().Ticks },
    @{ id=$financeWeb.Id; executable=$financeNode; started=$financeWeb.StartTime.ToUniversalTime().Ticks },
    @{ id=$financeWorker.Id; executable=$financePython; started=$financeWorker.StartTime.ToUniversalTime().Ticks }
)
$financeProcesses | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $financeRuntime 'processes.json')
Start-Sleep -Seconds 2
if ($financeApi.HasExited -or $financeWeb.HasExited -or $financeWorker.HasExited) { throw 'A service failed to start. Check .runtime/*-error.log; verify installed dependencies and available ports.' }
Write-Host "Dashboard: http://localhost:$WebPort | API: http://localhost:$ApiPort/docs"
Write-Host 'Use Stop-Finance.ps1 to stop these background services. Logs are in .runtime.'


