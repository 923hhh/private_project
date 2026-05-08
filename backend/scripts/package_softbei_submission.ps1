# 生成软件杯「源码包」ZIP：基于当前 HEAD 的 git 树（不含 .git、venv、node_modules 等未跟踪内容）。
# 用法：在仓库根目录执行 .\backend\scripts\package_softbei_submission.ps1
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $root
$dist = Join-Path $root "dist"
if (-not (Test-Path $dist)) {
    New-Item -ItemType Directory -Path $dist | Out-Null
}
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$out = Join-Path $dist "dachuang_project-SB8-src-$stamp.zip"
git archive --format=zip -o $out HEAD
Write-Host "已写入: $out"
Write-Host "请将 PPT、演示视频、截图/录屏等二进制产物单独归档到本地或私有归档位置，勿提交进公开 Git 仓库。"
