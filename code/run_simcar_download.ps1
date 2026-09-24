param(
    [int]$Limit = 0,
    [int]$RetryMinutes = 5,
    [int]$MaxAttempts = 30
)

# download_simcar_documents.py now does its own per-record retry/backoff and a
# fast preflight check (exit code 75 = portal unreachable, checked BEFORE any
# record is touched). This wrapper only needs to wait out a portal outage; it
# no longer hammers the host every minute forever - a stalled prior run did
# exactly that for ~1h40 without ever getting past record 1 (see
# runner_stalled_20260904_0623.log.bak in the output directory).
$ErrorActionPreference = 'Continue'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = 'python'
$Downloader = Join-Path $PSScriptRoot 'download_simcar_documents.py'
$InputCsv = Join-Path $ProjectRoot 'data\pre\car_proxy\car_atp_joined_20260818.csv'
$OutputDir = 'data\raw\simcar_documents\validated_car_pdfs'
$LogFile = Join-Path $OutputDir 'runner.log'

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -LiteralPath $LogFile -Value "$stamp attempt $attempt/$MaxAttempts start"
    & $Python $Downloader --input $InputCsv --output $OutputDir --limit $Limit --timeout 45 --workers 6 *>> $LogFile
    $code = $LASTEXITCODE
    if ($code -ne 75) {
        Add-Content -LiteralPath $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') finished exit=$code"
        exit $code
    }
    Add-Content -LiteralPath $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') portal_unavailable, retry in $RetryMinutes min"
    Start-Sleep -Seconds ($RetryMinutes * 60)
}
Add-Content -LiteralPath $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') giving up after $MaxAttempts attempts"
exit 75
