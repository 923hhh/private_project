# 备份数据库（支持 SQLite / PostgreSQL）
# 用法：
#   .\scripts\backup-db.ps1
#   .\scripts\backup-db.ps1 -DatabaseUrl "postgresql+asyncpg://user:pass@127.0.0.1:5432/dbname"
param(
    [string]$DatabaseUrl = ""
)
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$BackupDir = Join-Path $RepoRoot "deploy\backups"
if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

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

function Backup-Sqlite {
    param([string]$Url)
    $prefix = "sqlite+aiosqlite:///"
    $relativePath = $Url.Substring($prefix.Length)
    $dbPath = if ([System.IO.Path]::IsPathRooted($relativePath)) { $relativePath } else { Join-Path $RepoRoot $relativePath }
    if (-not (Test-Path $dbPath)) {
        throw "SQLite 文件不存在: $dbPath"
    }
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $dest = Join-Path $BackupDir ("sqlite-backup-" + $stamp + ".db")
    Copy-Item -LiteralPath $dbPath -Destination $dest -Force
    Write-Host "SQLite 备份完成: $dest" -ForegroundColor Green
}

function Backup-Postgres {
    param([string]$Url)
    if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) {
        throw "未找到 pg_dump，请先安装 PostgreSQL 客户端并加入 PATH。"
    }
    $normalized = $Url -replace "^postgresql\+asyncpg://", "postgresql://"
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $dest = Join-Path $BackupDir ("postgres-backup-" + $stamp + ".sql")
    & pg_dump $normalized -f $dest
    Write-Host "PostgreSQL 备份完成: $dest" -ForegroundColor Green
}

$url = Resolve-DatabaseUrl -InputUrl $DatabaseUrl
if ($url.StartsWith("sqlite+aiosqlite:///")) {
    Backup-Sqlite -Url $url
} elseif ($url.StartsWith("postgresql+asyncpg://")) {
    Backup-Postgres -Url $url
} else {
    throw "暂不支持的 DATABASE_URL: $url"
}
