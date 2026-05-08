# MVP 部署说明

本文档面向演示/MVP 场景，目标是让一台新的 Linux 服务器可以按步骤部署并运行本项目。

## 部署目标

- 后端服务可启动
- 数据库可初始化
- 浏览器可访问 `/health`、`/docs` 和 SSE 接口
- Next.js 前端（`frontend/`）能连上后端 API

## 方案选择

### 方案 A：SQLite 单机演示

适合本机演示或单机展示。

- 优点：最简单，依赖最少
- 缺点：不适合多人并发或长期运行

### 方案 B：PostgreSQL + FastAPI

适合校园服务器或云服务器演示。

- 优点：更接近真实部署
- 缺点：准备步骤更多

演示/MVP 默认建议先完成方案 A，再升级到方案 B。

## 环境准备

以 Ubuntu 22.04 为例：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

如使用 PostgreSQL 容器，还需要：

```bash
sudo apt install -y docker.io docker-compose-plugin
```

## 获取代码

```bash
git clone <your-repo-url>
cd <repo-root>
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

## 配置环境变量

```bash
cp .env.example .env
```

然后编辑 `.env`，补全真实 API Key。

### SQLite 演示配置

```env
DATABASE_URL=sqlite+aiosqlite:///./sensor_data.db
DEBUG=false
```

### PostgreSQL 演示配置

先启动数据库：

```bash
docker compose up -d postgres
```

然后将 `.env` 改为：

```env
DATABASE_URL=postgresql+asyncpg://fault_user:change_me@127.0.0.1:5432/fault_detection
DEBUG=false
```

如果修改了 `docker-compose.yml` 的环境变量，请同步改数据库连接串。

## 初始化数据库

在仓库根目录已激活 venv 的前提下，进入 `backend/` 再执行脚本（Alembic 与 `app` 包路径均相对此目录）：

```bash
cd backend
python scripts/init_db.py --init-only
```

说明：

- 该脚本会执行 Alembic 迁移
- 不再依赖应用启动阶段的自动建表

## 启动服务

开发/演示模式（工作目录须在 `backend/`）：

```bash
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问验证：

```bash
curl http://127.0.0.1:8000/health
```

## 浏览器联调

- 打开 `http://<server-ip>:8000/docs` 查看接口
- 在部署机或本机构建并启动 `frontend`（`npm install` 后执行 `npm run build` / `npm start` 或 `npm run dev`），将环境变量中的 API 基址指向 `http://<server-ip>:8000`
- 或通过 `/docs` 试调 `POST /api/v1/diagnose` 与 `GET /api/v1/diagnose/stream`（SSE）

公开源码仓库默认不附带 `datasets/` 内容；如果需要导入样例 CSV、PDF 或知识语料，请在部署机上自行准备并将路径传给对应脚本。

## 持续运行

如需后台常驻，推荐使用 systemd。样例见：

- [deploy/systemd/fault-detection.service.example](../deploy/systemd/fault-detection.service.example)

## 备份与恢复（上线前建议）

仓库根目录提供了最小化数据库备份/恢复脚本：

```powershell
.\scripts\backup-db.ps1
.\scripts\restore-db.ps1 -BackupFile ".\deploy\backups\sqlite-backup-20260413-120000.db"
```

如使用 PostgreSQL，可通过 `-DatabaseUrl` 传入连接串（脚本内部调用 `pg_dump` / `psql`）。

## 最小验收清单

- 在 `backend/` 下执行 `python scripts/init_db.py --init-only` 成功
- `curl /health` 返回正常
- `/docs` 可访问
- 前端能连上后端并完成一次主链路演示（或 `/docs` 完成 SSE 诊断试调）
- `pytest -q` 可运行

## 常见问题

### 1. `aiosqlite` 缺失

确认你运行的是项目虚拟环境中的 Python，而不是系统 Python。

### 2. SSE 长时间无响应

- 检查 API Key 是否有效
- 检查模型调用是否超时
- 检查浏览器页面中的后端地址是否正确

### 3. 数据库连接失败

- 确认 `.env` 中 `DATABASE_URL` 正确
- 如使用 PostgreSQL，确认容器已启动
- 先访问 `/health` 判断后端能否连上数据库
