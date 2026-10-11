param([switch]$SkipInstall)
$env:FINANCE_LOCAL_OWNER_ACCESS='true'
$env:FINANCE_LOCAL_OWNER_EMAIL='bhuvanjakkula@gmail.com'
$env:FINANCE_LOCAL_OWNER_ORG='finance-qa-20261008'
& (Join-Path $PSScriptRoot 'Start-Finance.ps1') -WebPort 5174 -ApiPort 8001 -SkipInstall:$SkipInstall
