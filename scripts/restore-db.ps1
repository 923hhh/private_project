# 恢复数据库（支持 SQLite / PostgreSQL）
# 用法：
#   .\scripts\restore-db.ps1 -BackupFile ".\deploy\backups\sqlite-backup-20260413-120000.db"
#   .\scripts\restore-db.ps1 -BackupFile ".\deploy\backups\postgres-backup-20260413-120000.sql" -DatabaseUrl "postgresql+asyncpg://user:pass@127.0.0.1:5432/dbname"
param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [string]$DatabaseUrl = ""
)
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backupPath = (Resolve-Path $BackupFile).Path

function Resolve-DatabaseUrl {
    param([string]$InputUrl)
    if ($InputUrl -and $InputUrl.Trim() -ne "") {
        return $InputUrl.Trim()
    }
    $envPath = Join-Path $RepoRoot ".env"
    if (Test-Path $envPath) {
        $line = (Get-Content $envPath | Where-Object { $_ -match "^DATABASE_URL=" } | Select-Object -First 1)
        if ($line) {
            return $line.Split("=", 2)[1].Trim()
        }
    }
    throw "未提供 DatabaseUrl，且未在 .env 找到 DATABASE_URL。"
}

function Restore-Sqlite {
    param([string]$Url, [string]$Backup)
    $prefix = "sqlite+aiosqlite:///"
    $relativePath = $Url.Substring($prefix.Length)
    $dbPath = if ([System.IO.Path]::IsPathRooted($relativePath)) { $relativePath } else { Join-Path $RepoRoot $relativePath }
    $dbDir = Split-Path -Parent $dbPath
    if (-not (Test-Path $dbDir)) {
        New-Item -ItemType Directory -Path $dbDir | Out-Null
    }
    Copy-Item -LiteralPath $Backup -Destination $dbPath -Force
    Write-Host "SQLite 恢复完成: $dbPath" -ForegroundColor Green
}

function Restore-Postgres {
    param([string]$Url, [string]$Backup)
    if (-not (Get-Command psql -ErrorAction SilentlyContinue)) {
        throw "未找到 psql，请先安装 PostgreSQL 客户端并加入 PATH。"
    }
    $normalized = $Url -replace "^postgresql\+asyncpg://", "postgresql://"
    & psql $normalized -f $Backup
    Write-Host "PostgreSQL 恢复完成: $Backup" -ForegroundColor Green
}

if (-not (Test-Path $backupPath)) {
    throw "备份文件不存在: $backupPath"
}

$url = Resolve-DatabaseUrl -InputUrl $DatabaseUrl
if ($url.StartsWith("sqlite+aiosqlite:///")) {
    Restore-Sqlite -Url $url -Backup $backupPath
} elseif ($url.StartsWith("postgresql+asyncpg://")) {
    Restore-Postgres -Url $url -Backup $backupPath
} else {
    throw "暂不支持的 DATABASE_URL: $url"
}
