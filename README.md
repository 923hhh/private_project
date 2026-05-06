# 工业故障检测与检修知识系统

基于 FastAPI、LangGraph 和工业传感器数据的故障诊断后端项目，支持同步诊断、SSE 流式诊断和简单的浏览器调试页联调。

当前定位是面向演示与原型验证的 MVP 级交付：重点保证主链路可演示、可部署、可复现、可验证，而不是追求商用生产级复杂能力。

当前项目聚焦于“设备检修知识与作业助手”这一产品方向，现有工业故障诊断链路保留为**智能分析子模块**，不再作为主产品入口。

当前后端已完成一轮**中等架构重组**：在不改变 FastAPI、PostgreSQL、Alembic 的前提下，引入了 `bootstrap / shared / modules / integrations / persistence` 五层结构，并为 `React + Next.js` 正式前端预留稳定 API 边界。

当前仓库已启动**正式前端工程化阶段**：`frontend/` 目录下已新增 `Next.js + React + TypeScript` 正式工作台骨架，并新增面向正式前端的工作台概览与 Agent 协作统一接口。Python 后端与测试、迁移、脚本集中在 `backend/`，与前端目录物理分离。

## 当前能力

- `POST /api/v1/diagnose`：返回完整诊断报告
- `GET /api/v1/diagnose/stream`：通过 SSE 返回节点进度和最终报告
- `GET /api/v1/workbench/overview`：返回正式工作台首页所需的统计卡片、固定检索词、Agent 能力摘要和最近业务项
- `POST /api/v1/agents/assist`：统一触发知识召回、作业规划、风险校验与案例沉淀建议
- `GET /api/v1/agents/runs/{id}`：回放最近一次 Agent 协作结果
- `POST /api/v1/knowledge/documents`：导入检修知识文本并自动拆分为可检索分段
- `POST /api/v1/knowledge/imports/preview`：在正式导入前预览 PDF 或图片 OCR 的页数/分段数、预览摘录和处理提示
- `GET /api/v1/knowledge/imports`：查看最近的知识导入任务列表与状态
- `POST /api/v1/knowledge/imports`：上传 PDF 手册或故障图片并创建正式知识导入任务，自动提取文本、切分分段并写入知识库
- `GET /api/v1/knowledge/imports/{id}`：查看单个知识导入任务的状态、页数、分段数和失败原因
- `GET /api/v1/knowledge/documents`：查看正式知识中心的文档列表与分段数
- `GET /api/v1/knowledge/documents/{id}`：查看指定知识文档的详细元数据，用于来源回溯和命中调试
- `GET /api/v1/knowledge/documents/{id}/chunks`：预览指定知识文档的前若干个分段内容
- `POST /api/v1/knowledge/search`：按文本、设备型号、单张故障图片联合检索知识条目，返回出处、有效检索词、图片识别线索和处理提示
- `POST /api/v1/tasks`：根据知识引用生成标准化检修任务和作业步骤
- `PATCH /api/v1/tasks/{id}/steps/{step_id}`：更新检修步骤执行状态与备注
- `POST /api/v1/cases`：上传待审核检修案例，沉淀任务执行结果和知识引用
- `POST /api/v1/cases/{id}/corrections`：对检索结果、模型输出和总结进行人工修正
- `POST /api/v1/cases/{id}/review`：审核案例并在通过后自动入库为知识文档
- `GET /api/v1/cases`：查看案例列表与审核状态
- `GET /api/v1/history`：查看最近的检修任务历史
- `GET /api/v1/export/{id}`：导出检修任务摘要、步骤和知识引用
- `GET /health`：检查服务和数据库连通性
- `frontend/`：正式前端（Next.js），提供工作台、知识检索、PDF/图片导入、任务、案例、历史、Agent 协作与检修域页面；流式能力见各页内 `EventSource` 与后端 SSE 接口
- Alembic 管理数据库 schema，不再依赖隐式建表
- 当前测试结果：本机 `pytest -q` 约 `130 passed, 2 skipped`（量级以实际为准）；GitHub 上见 [`.github/workflows/ci.yml`](.github/workflows/ci.yml)（`push` / `pull_request` / `workflow_dispatch` 触发）。依赖真实 LLM 的抽检请在配置 `.env` 后自行设计用例，在浏览器或 `/docs` 中调用接口完成。

## 当前产品定义

- 当前产品定义：`设备检修知识与作业助手`
- 当前演示对象：`摩托车发动机检修`
- 当前主线：`输入检修问题 -> 检索知识 -> 生成作业指引 -> 沉淀案例 -> 审核入库`
- 当前保留子模块：`工业故障诊断 / SSE 流式分析`

设计与交付口径以仓库内 **`docs/MVP 产品需求文档.md`**、**`docs/系统架构文档.md`** 为准。公开源码仓库默认不包含演示材料、本地数据库与样例数据集；如需演示素材，请在你自己的环境中另行准备。

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

建议使用项目内 `venv` 或你自己的独立虚拟环境，避免系统 Python 缺失 `aiosqlite`。

### 2. 配置环境变量

仓库提供了 [`.env.example`](.env.example) 作为模板。

至少需要确认：

```env
DATABASE_URL=sqlite+aiosqlite:///./sensor_data.db
DEEPSEEK_API_KEY=sk-xxxxx
DEEPSEEK_API_BASE=https://api.deepseek.com
OPENAI_API_KEY=sk-xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx
DEBUG=false
```

本地真实密钥只保存在 `.env`，不要提交到仓库。

### 3. 初始化数据库

在 `backend/` 下执行：

```bash
cd backend
python scripts/init_db.py --init-only
```

该命令会执行 `alembic upgrade head`，确保数据库结构与迁移脚本一致。

如需将 PDF 维修手册直接导入知识库：

```bash
python scripts/import_knowledge_pdf.py "摩托车发动机维修手册.pdf" --equipment-type "摩托车发动机"
```

说明：公开源码仓库默认不附带 `datasets/` 内容；如果你需要导入样例 CSV 或 PDF，请自行准备文件并将路径传给脚本。

### 4. 启动后端

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/health`

### 5. 打开前端入口

根目录**静态演示 HTML 已移除**，请仅通过 **Next.js** 访问 UI：在 `frontend/` 下执行 `npm install` / `npm run dev`，并将 `frontend/.env.example` 复制为 `frontend/.env.local` 后按需修改 `NEXT_PUBLIC_API_BASE_URL`（默认 `http://127.0.0.1:8000`）。

**智能分析（时间窗诊断）**：可调用 `POST /api/v1/diagnose`、`GET /api/v1/diagnose/stream`（SSE），或在 Swagger `http://127.0.0.1:8000/docs` 中试调。

## 演示流程

推荐按以下顺序演示：

1. 启动后端服务
2. 访问 `/health`
3. 启动 `frontend`（`npm run dev`），从工作台进入知识检索、任务、案例等页面
4. 先展示知识检索命中结果和引用来源
5. 再展示标准化检修任务与案例沉淀流程
6. 如需展示智能分析 / Agent 流式过程，使用前端对应页面或 `/docs` 中 SSE 接口试调
7. 接口文档：`/docs`

联调以 **`/health`**、**`/docs`** 与前端工作台页面为准。

## 部署

当前阶段建议先保证“新机器按文档就能跑起来”。

- 后端容器镜像：见 [Dockerfile](Dockerfile)
- 数据库容器：见 [docker-compose.yml](docker-compose.yml)
- 最小部署说明：见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- Linux systemd 样例：见 [deploy/systemd/fault-detection.service.example](deploy/systemd/fault-detection.service.example)

## 自动化验证

仓库新增了 GitHub Actions workflow：

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

默认在 `push` 和 `pull_request` 时执行（工作目录为 `backend/`）：

```bash
cd backend
pytest -q
```

仓库内预置的离线评测可通过以下命令复现：

```bash
cd backend
..\venv\Scripts\python.exe scripts\run_softbei_eval.py
```

当前评测结果会写入 `backend/evaluation/softbei_eval_results.json`（本地生成，已列入 `.gitignore`，克隆后需先运行上述命令才会出现）。

## 项目结构

```text
backend/
  app/                  FastAPI 应用、路由、服务、智能体
  app/bootstrap/        应用工厂、lifespan、中间件、路由装配
  app/shared/           配置、数据库、日志等共享基础设施
  app/modules/          按业务域组织的知识、任务、案例、诊断模块
  app/integrations/     图片分析、PDF 导入、智能体/LLM 适配
  app/persistence/      面向业务域整理的模型导出层
  alembic/              Alembic 迁移环境与版本脚本
  scripts/              初始化数据库和导入数据脚本
  tests/                异步接口、流式链路和回归测试
  evaluation/           离线评测用例、配置与结果样例
docs/                   核心文档（部署说明、MVP 需求、系统架构）；详见 docs/README.md
deploy/systemd/         Linux 部署示例
frontend/               Next.js 正式前端工程骨架（工作台 / 知识 / OCR 导入 / 任务 / 案例 / 历史 / Agent）
Dockerfile              构建镜像时仅复制 backend/ 作为运行上下文
```

## 当前还没做的事

以下内容在当前 MVP 阶段通常应继续推进：

- 真实浏览器联调验收
- 云服务器部署验证
- CI 实际接入 GitHub 仓库并跑通
- 更系统的日志、监控和告警
- 如有需要，再补 Nginx、HTTPS、鉴权、权限控制

如需额外准备演示 PPT、视频、截图和数据集，建议保存在本地或单独的私有归档位置，不要放进公开源码仓库。
