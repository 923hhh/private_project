# 本地开发一键启动：自动拉起后端（18000）与前端（3000）。
# 用法：
#   .\scripts\start-dev.ps1
#   .\scripts\start-dev.ps1 -EnableFrontendTunnel
#   .\scripts\start-dev.ps1 -EnableFrontendTunnel -TunnelSubdomain faultdiag-demo
param(
    [switch]$EnableFrontendTunnel,
    [switch]$EnableBackendTunnel,
    [ValidateSet("cloudflared", "localtunnel")]
    [string]$TunnelProvider = "cloudflared",
    [string]$TunnelSubdomain = "",
    # cloudflared 转发目标主机：默认 localhost。若遇到 127.0.0.1/localhost 被系统代理拦截，可传入 Next 输出的 Network IP（例如 172.29.249.98）
    [string]$TunnelOriginHost = "localhost",
    # 前端启动模式：dev=开发热更新（不建议穿透给外网），share=生产模式（适合穿透给外网展示）
    [ValidateSet("dev", "share")]
    [string]$FrontendMode = "dev"
)

$ErrorActionPreference = "Stop"
$BackendHost = "127.0.0.1"
$BackendPort = 18000
$FrontendHost = "127.0.0.1"
$FrontendPort = 3000
$BackendBaseUrl = "http://$BackendHost`:$BackendPort"
$FrontendBaseUrl = "http://$FrontendHost`:$FrontendPort"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Backend = Join-Path $RepoRoot "backend"
$Frontend = Join-Path $RepoRoot "frontend"
if (-not (Test-Path $Frontend)) {
    $Frontend = Join-Path $RepoRoot "front-end"
}

if (-not (Test-Path $Backend)) {
    throw "未找到 backend 目录：$Backend"
}
if (-not (Test-Path $Frontend)) {
    throw "未找到前端目录（尝试了 frontend/front-end）：$RepoRoot"
}

function Get-ListeningProcessIds {
    param(
        [int]$Port
    )

    $connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    return @($connections | Select-Object -ExpandProperty OwningProcess -Unique)
}

function Get-ProcessSnapshot {
    $items = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $byId = @{}
    foreach ($item in $items) {
        $byId[[int]$item.ProcessId] = $item
    }
    return $byId
}

function Get-ProcessDescendantIds {
    param(
        [int]$RootProcessId,
        [hashtable]$ProcessSnapshot
    )

    $result = New-Object System.Collections.Generic.List[int]
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($RootProcessId)

    while ($queue.Count -gt 0) {
        $currentId = $queue.Dequeue()
        if (-not $result.Contains($currentId)) {
            [void]$result.Add($currentId)
        }

        foreach ($process in $ProcessSnapshot.Values) {
            if ([int]$process.ParentProcessId -eq $currentId) {
                $childId = [int]$process.ProcessId
                if (-not $result.Contains($childId)) {
                    $queue.Enqueue($childId)
                }
            }
        }
    }

    return @($result.ToArray())
}

function Write-ProcessTree {
    param(
        [int]$ProcessId,
        [hashtable]$ProcessSnapshot,
        [string]$Indent = "",
        [System.Collections.Generic.HashSet[int]]$Visited = $(New-Object 'System.Collections.Generic.HashSet[int]')
    )

    if ($Visited.Contains($ProcessId)) {
        return
    }
    [void]$Visited.Add($ProcessId)

    $process = $ProcessSnapshot[$ProcessId]
    if (-not $process) {
        Write-Host ("{0}- PID {1} <已退出>" -f $Indent, $ProcessId) -ForegroundColor DarkGray
        return
    }

    $name = $process.Name
    $parentId = [int]$process.ParentProcessId
    Write-Host ("{0}- PID {1} {2} (Parent={3})" -f $Indent, $ProcessId, $name, $parentId) -ForegroundColor DarkCyan

    $children = @(
        $ProcessSnapshot.Values |
            Where-Object { [int]$_.ParentProcessId -eq $ProcessId } |
            Sort-Object ProcessId
    )
    foreach ($child in $children) {
        Write-ProcessTree -ProcessId ([int]$child.ProcessId) -ProcessSnapshot $ProcessSnapshot -Indent ($Indent + "  ") -Visited $Visited
    }
}

function Stop-ListeningProcesses {
    param(
        [int]$Port,
        [string]$ServiceName
    )

    $initialProcessIds = Get-ListeningProcessIds -Port $Port
    if ($initialProcessIds.Count -eq 0) {
        return
    }

    Write-Host "$ServiceName 端口 $Port 已被占用，正在清理旧进程..." -ForegroundColor Yellow
    $deadline = (Get-Date).AddSeconds(12)
    $attempt = 0
    while ((Get-Date) -lt $deadline) {
        $processIds = Get-ListeningProcessIds -Port $Port
        if ($processIds.Count -eq 0) {
            Write-Host "$ServiceName 端口 $Port 已释放。" -ForegroundColor Green
            return
        }

        $snapshot = Get-ProcessSnapshot
        Write-Host "$ServiceName 当前占用 $Port 的进程树：" -ForegroundColor Yellow
        foreach ($processId in $processIds) {
            Write-ProcessTree -ProcessId $processId -ProcessSnapshot $snapshot
        }

        $killOrder = New-Object System.Collections.Generic.List[int]
        foreach ($processId in $processIds) {
            $relatedIds = @(Get-ProcessDescendantIds -RootProcessId $processId -ProcessSnapshot $snapshot)
            foreach ($relatedId in ($relatedIds | Sort-Object -Descending)) {
                if (-not $killOrder.Contains($relatedId)) {
                    [void]$killOrder.Add($relatedId)
                }
            }
        }

        foreach ($processId in $killOrder) {
            try {
                $process = Get-Process -Id $processId -ErrorAction Stop
                Write-Host ("  - 停止 PID {0} ({1})" -f $processId, $process.ProcessName) -ForegroundColor DarkYellow
                Stop-Process -Id $processId -Force -ErrorAction Stop
            } catch {
                $stillListening = Get-ListeningProcessIds -Port $Port
                if ($stillListening -contains $processId) {
                    Write-Host ("  - 停止 PID {0} 失败：{1}" -f $processId, $_.Exception.Message) -ForegroundColor Red
                } else {
                    Write-Host ("  - PID {0} 已退出，继续检查端口占用..." -f $processId) -ForegroundColor DarkYellow
                }
            }
        }

        $attempt++
        Start-Sleep -Milliseconds (400 + [Math]::Min($attempt * 150, 600))
    }

    throw "$ServiceName 端口 $Port 清理后仍被占用，请手动检查。"
}

function Wait-ForTcpPort {
    param(
        [string]$Host,
        [int]$Port,
        [int]$TimeoutSeconds = 60,
        [string]$ServiceName = "服务"
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-NetConnection -ComputerName $Host -Port $Port -InformationLevel Quiet -WarningAction SilentlyContinue) {
            Write-Host "$ServiceName 端口 $Port 已就绪。" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 1
    }

    return $false
}

function Wait-ForHttpHealthy {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 60,
        [string]$ServiceName = "服务"
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                Write-Host "$ServiceName 健康检查通过：$Url" -ForegroundColor Green
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds 1
    }

    return $false
}

$VenvPy = Join-Path $RepoRoot "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPy)) {
    $VenvPy = "python"
    Write-Host "未找到 venv\Scripts\python.exe，将使用 PATH 中的 python。" -ForegroundColor Yellow
}

Write-Host "正在执行后端数据库迁移（alembic upgrade head）..." -ForegroundColor Yellow
Push-Location $Backend
try {
    & $VenvPy "scripts/init_db.py" --init-only
} finally {
    Pop-Location
}
Write-Host "数据库迁移完成。" -ForegroundColor Green

$FrontendEnvLocal = Join-Path $Frontend ".env.local"
if (-not (Test-Path $FrontendEnvLocal)) {
    @"
NEXT_PUBLIC_API_BASE_URL=$BackendBaseUrl
"@ | Set-Content -Path $FrontendEnvLocal -Encoding UTF8
    Write-Host "已创建 frontend/.env.local 并写入 NEXT_PUBLIC_API_BASE_URL。" -ForegroundColor Green
} else {
    $envContent = Get-Content -Path $FrontendEnvLocal -Raw
    if ($envContent -match "(?m)^NEXT_PUBLIC_API_BASE_URL=") {
        $envContent = [regex]::Replace($envContent, "(?m)^NEXT_PUBLIC_API_BASE_URL=.*$", "NEXT_PUBLIC_API_BASE_URL=$BackendBaseUrl")
    } else {
        $envContent = $envContent.TrimEnd() + "`r`nNEXT_PUBLIC_API_BASE_URL=$BackendBaseUrl`r`n"
    }
    Set-Content -Path $FrontendEnvLocal -Value $envContent -Encoding UTF8
    Write-Host "已更新 frontend/.env.local 的 NEXT_PUBLIC_API_BASE_URL 为 $BackendBaseUrl。" -ForegroundColor Green
}

$FrontendNodeModules = Join-Path $Frontend "node_modules"
if (-not (Test-Path $FrontendNodeModules)) {
    Write-Host "检测到前端依赖未安装，正在执行 npm install（首次可能较慢）..." -ForegroundColor Yellow
    Push-Location $Frontend
    try {
        npm install
    } finally {
        Pop-Location
    }
}

function Ensure-Cloudflared {
    param(
        [string]$RepoRootPath
    )
    $toolsDir = Join-Path $RepoRootPath ".tools"
    if (-not (Test-Path $toolsDir)) {
        New-Item -ItemType Directory -Path $toolsDir | Out-Null
    }
    $bin = Join-Path $toolsDir "cloudflared.exe"
    if (Test-Path $bin) {
        return $bin
    }
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Write-Host "未检测到 cloudflared，正在下载到 $bin ..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri $url -OutFile $bin -UseBasicParsing
    } catch {
        throw "cloudflared 下载失败：$($_.Exception.Message)。你也可以手动下载并放到 $bin"
    }
    return $bin
}

$backendLine = @"
Set-Location -LiteralPath '$Backend'
Write-Host '后端: $BackendBaseUrl  (Ctrl+C 停止)' -ForegroundColor Cyan
& '$VenvPy' -m uvicorn app.main:app --reload --host $BackendHost --port $BackendPort
"@

$frontendLine = @"
Set-Location -LiteralPath '$Frontend'
Write-Host '前端: $FrontendBaseUrl  (Ctrl+C 停止)' -ForegroundColor Cyan
if ('$FrontendMode' -eq 'share') {
  Write-Host '前端以 share 模式启动（next build + next start），适合内网穿透。' -ForegroundColor Magenta
  npm run share
} else {
  npm run dev
}
"@

$cloudflaredPath = $null
if (($EnableFrontendTunnel -or $EnableBackendTunnel) -and $TunnelProvider -eq "cloudflared") {
    $cloudflaredPath = Ensure-Cloudflared -RepoRootPath $RepoRoot
}

$tunnelLine = ""
if ($EnableFrontendTunnel) {
    if ($TunnelProvider -eq "cloudflared") {
        $originUrl = "http://$TunnelOriginHost`:$FrontendPort"
        $tunnelLine = @"
Set-Location -LiteralPath '$Frontend'
Write-Host '前端内网穿透（cloudflared）已启动（Ctrl+C 停止）。' -ForegroundColor Magenta
Write-Host '提示：若仅穿透前端，外网访问建议切演示模式。' -ForegroundColor Yellow
# 兼容某些环境的系统代理/鉴权拦截：确保 localhost 不走代理
\$env:NO_PROXY='localhost,127.0.0.1'
\$env:no_proxy='localhost,127.0.0.1'
\$env:HTTP_PROXY=''
\$env:http_proxy=''
\$env:HTTPS_PROXY=''
\$env:https_proxy=''
Write-Host '若仍报 Unauthorized，可尝试关闭系统代理/Clash 或改用本机网卡 IP（见脚本注释）。' -ForegroundColor Yellow
Write-Host 'Origin: $originUrl' -ForegroundColor Cyan
# 等待前端端口就绪（share 模式 build 期间端口未监听，外网会看到 503）
\$maxWaitSec = 60
\$waited = 0
while (\$waited -lt \$maxWaitSec) {
  \$ok = Test-NetConnection -ComputerName '$TunnelOriginHost' -Port $FrontendPort -InformationLevel Quiet
  if (\$ok) { break }
  Start-Sleep -Seconds 1
  \$waited++
}
if (\$waited -ge \$maxWaitSec) {
  Write-Host '警告：等待前端端口超时，仍将尝试启动穿透。若外网 503，请确认前端已启动完成。' -ForegroundColor Yellow
} else {
  Write-Host '前端端口已就绪，开始建立公网隧道…' -ForegroundColor Green
}
# 显式 Host 头保持为 localhost:$FrontendPort，兼容 Next dev 对 Host 校验/热更新
& '$cloudflaredPath' tunnel --url $originUrl --protocol http2 --http-host-header localhost:$FrontendPort
"@
    } else {
        $tunnelCommand = if ([string]::IsNullOrWhiteSpace($TunnelSubdomain)) {
            "npm run tunnel"
        } else {
            "npx localtunnel --port $FrontendPort --subdomain $TunnelSubdomain"
        }
        $tunnelLine = @"
Set-Location -LiteralPath '$Frontend'
Write-Host '前端内网穿透（localtunnel）已启动（Ctrl+C 停止）。' -ForegroundColor Magenta
Write-Host '提示：若后端未穿透，建议前端切演示模式。' -ForegroundColor Yellow
$tunnelCommand
"@
    }
}

$backendTunnelLine = ""
if ($EnableBackendTunnel) {
    if ($TunnelProvider -eq "cloudflared") {
        $backendOriginUrl = "http://$TunnelOriginHost`:$BackendPort"
        $backendTunnelLine = @"
Set-Location -LiteralPath '$Backend'
Write-Host '后端内网穿透（cloudflared）已启动（Ctrl+C 停止）。' -ForegroundColor Magenta
Write-Host 'Origin: $backendOriginUrl' -ForegroundColor Cyan
\$env:NO_PROXY='localhost,127.0.0.1'
\$env:no_proxy='localhost,127.0.0.1'
\$env:HTTP_PROXY=''
\$env:http_proxy=''
\$env:HTTPS_PROXY=''
\$env:https_proxy=''
& '$cloudflaredPath' tunnel --url $backendOriginUrl --protocol http2 --http-host-header localhost:$BackendPort
"@
    } else {
        $backendTunnelLine = @"
Set-Location -LiteralPath '$Backend'
Write-Host '后端内网穿透（localtunnel）不建议：请使用 cloudflared。' -ForegroundColor Yellow
"@
    }
}

Stop-ListeningProcesses -Port $BackendPort -ServiceName "后端"
Stop-ListeningProcesses -Port $FrontendPort -ServiceName "前端"

Start-Process powershell.exe -ArgumentList @("-NoExit", "-NoProfile", "-Command", $backendLine)
Start-Sleep -Seconds 1
Start-Process powershell.exe -ArgumentList @("-NoExit", "-NoProfile", "-Command", $frontendLine)

$backendReady = Wait-ForTcpPort -Host $BackendHost -Port $BackendPort -TimeoutSeconds 45 -ServiceName "后端"
if (-not $backendReady) {
    throw "后端进程已拉起，但端口 $BackendPort 在 45 秒内未监听成功。"
}

$backendHealthy = Wait-ForHttpHealthy -Url "$BackendBaseUrl/health" -TimeoutSeconds 45 -ServiceName "后端"
if (-not $backendHealthy) {
    throw "后端端口已监听，但 /health 在 45 秒内未通过，请检查启动窗口日志。"
}

$frontendReady = Wait-ForTcpPort -Host $FrontendHost -Port $FrontendPort -TimeoutSeconds 90 -ServiceName "前端"
if (-not $frontendReady) {
    throw "前端进程已拉起，但端口 $FrontendPort 在 90 秒内未监听成功。"
}

if ($EnableFrontendTunnel) {
    Start-Sleep -Milliseconds 500
    Start-Process powershell.exe -ArgumentList @("-NoExit", "-NoProfile", "-Command", $tunnelLine)
}
if ($EnableBackendTunnel) {
    Start-Sleep -Milliseconds 500
    Start-Process powershell.exe -ArgumentList @("-NoExit", "-NoProfile", "-Command", $backendTunnelLine)
}
Write-Host "后端与前端已完成验活：后端 :$BackendPort，前端 :$FrontendPort。" -ForegroundColor Green
if ($EnableFrontendTunnel) {
    Write-Host "已额外启动前端内网穿透窗口（会输出公网访问地址）。Provider=$TunnelProvider" -ForegroundColor Magenta
}
if ($EnableBackendTunnel) {
    Write-Host "已额外启动后端内网穿透窗口（会输出公网访问地址）。" -ForegroundColor Magenta
    Write-Host "外网真实数据访问需要将该后端公网地址写入 frontend/.env.local 的 NEXT_PUBLIC_API_BASE_URL。" -ForegroundColor Yellow
}
Write-Host "后端文档: $BackendBaseUrl/docs" -ForegroundColor Cyan
Write-Host "前端地址: $FrontendBaseUrl" -ForegroundColor Cyan
