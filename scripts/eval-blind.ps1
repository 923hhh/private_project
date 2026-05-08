# 运行盲测评估（固定盲测样本）
# 用法：在仓库根目录执行 .\scripts\eval-blind.ps1
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $RepoRoot "backend"
$VenvPy = Join-Path $RepoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    $VenvPy = "python"
}

Set-Location -LiteralPath $Backend

& $VenvPy scripts/run_softbei_eval.py `
    --cases-path "evaluation/softbei_blind_eval_cases.json" `
    --output-path "evaluation/softbei_blind_eval_results.json" `
    --db-name "softbei_blind_eval_day3"

Write-Host "盲测完成：backend/evaluation/softbei_blind_eval_results.json" -ForegroundColor Green
