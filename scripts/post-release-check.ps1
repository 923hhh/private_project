# 发布后运行状态快照（可重复执行，建议 T+1h/T+4h/T+8h/T+24h）
# 用法：
#   .\scripts\post-release-check.ps1
#   .\scripts\post-release-check.ps1 -BaseUrl "http://127.0.0.1:8000"
param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$OutDir = Join-Path $RepoRoot "deploy\observability"
if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = Join-Path $OutDir ("post-release-check-" + $stamp + ".json")

$healthOk = $false
$docsOk = $false
$healthBody = $null
$docsStatus = $null

try {
    $healthResp = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 10
    $healthOk = ($healthResp.StatusCode -eq 200)
    $healthBody = $healthResp.Content
} catch {
    $healthBody = $_.Exception.Message
}

try {
    $docsResp = Invoke-WebRequest -Uri "$BaseUrl/docs" -UseBasicParsing -TimeoutSec 10
    $docsStatus = $docsResp.StatusCode
    $docsOk = ($docsResp.StatusCode -eq 200)
} catch {
    $docsStatus = $_.Exception.Message
}

$snapshot = [ordered]@{
    timestamp = (Get-Date).ToString("s")
    base_url = $BaseUrl
    health_ok = $healthOk
    docs_ok = $docsOk
    docs_status = $docsStatus
    health_response = $healthBody
}

$snapshot | ConvertTo-Json -Depth 6 | Out-File -FilePath $outFile -Encoding utf8
Write-Host "运行快照已写入: $outFile" -ForegroundColor Green
