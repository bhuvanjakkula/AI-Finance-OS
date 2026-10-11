$ErrorActionPreference = 'Stop'
$financeState = Join-Path $PSScriptRoot '.runtime\processes.json'
if (-not (Test-Path -LiteralPath $financeState)) { Write-Host 'No recorded services.'; exit }
$financeServices = Get-Content -LiteralPath $financeState -Raw | ConvertFrom-Json
foreach ($financeService in $financeServices) {
    $financeProcess = Get-Process -Id $financeService.id -ErrorAction SilentlyContinue
    if ($financeProcess -and $financeProcess.Path -eq $financeService.executable -and $financeProcess.StartTime.ToUniversalTime().Ticks -eq $financeService.started) {
        Stop-Process -Id $financeProcess.Id
    }
}
Write-Host 'Recorded finance services stopped.'
