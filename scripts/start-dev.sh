#!/usr/bin/env bash
# 本地开发：后台启动后端，前台启动前端（Git Bash / WSL / macOS 可用）。
# 用法：在仓库根目录执行  bash scripts/start-dev.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/front-end"
PY="$ROOT/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="python3"
fi

echo "启动后端 http://127.0.0.1:8000 ..."
(cd "$BACKEND" && exec "$PY" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
BACK_PID=$!
sleep 1
trap 'kill $BACK_PID 2>/dev/null || true' EXIT

echo "启动前端 http://127.0.0.1:3000 ..."
cd "$FRONTEND"
npm run dev
