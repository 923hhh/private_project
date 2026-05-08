# 一键执行后端质量门禁（pytest + 软件杯固定评测 + 功能3/4门禁判定）
# 用法：在仓库根目录执行 .\scripts\eval-all.ps1
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $RepoRoot "backend"
$VenvPy = Join-Path $RepoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    $VenvPy = "python"
}

Set-Location -LiteralPath $Backend

Write-Host "==> [1/3] 运行 pytest -q" -ForegroundColor Cyan
& $VenvPy -m pytest -q

Write-Host "==> [2/3] 运行软件杯固定评测" -ForegroundColor Cyan
& $VenvPy scripts/run_softbei_eval.py

Write-Host "==> [3/3] 运行功能3/4自动化门禁判定" -ForegroundColor Cyan
& $VenvPy scripts/check_softbei_gate.py

Write-Host "质量门禁完成。结果文件: backend/evaluation/softbei_eval_results.json" -ForegroundColor Green
