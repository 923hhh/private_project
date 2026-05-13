# 检测系统

这是一个面向演示与原型验证的检测系统，结合故障诊断、知识检索、任务生成和案例沉淀能力，提供一套从问题输入到处理建议输出的完整流程。

当前仓库采用前后端分离结构：
- `backend/`：FastAPI 后端、数据库迁移、测试与脚本
- `frontend/`：Next.js 前端工作台

公开源码仓库默认不包含本地数据库、私有手册、评测产物和敏感演示素材；如需完整演示，请在你自己的环境中准备合规文件。

仓库中提供了可公开使用的评测模板与多模态说明：

- `datasets/validation/motorcycle_engine_retrieval_eval.csv`
- `datasets/validation/motorcycle_engine_multimodal_eval.csv`
- `datasets/img/README.md`

更完整的联调与部署说明见 [docs/全流程跑通指南.md](docs/%E5%85%A8%E6%B5%81%E7%A8%8B%E8%B7%91%E9%80%9A%E6%8C%87%E5%8D%97.md)、[docs/README.md](docs/README.md) 与 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

## 作用

本项目主要用于：

- 接收设备检修或故障相关问题
- 结合知识内容进行检索与分析
- 生成标准化处理步骤与任务
- 记录处理结果并沉淀为案例

## 如何运行

当前最推荐的启动方式是直接使用：

```powershell
.\scripts\start-dev.ps1
```

该脚本会自动：

- 启动后端与前端
- 执行数据库初始化
- 自动更新 `frontend/.env.local` 中的 `NEXT_PUBLIC_API_BASE_URL`

按当前项目默认配置，一键启动后的访问地址是：

- 前端：`http://127.0.0.1:3000`
- 后端：`http://127.0.0.1:18000`
- 后端文档：`http://127.0.0.1:18000/docs`

如需手工启动，可按下面步骤执行。

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

建议使用独立虚拟环境运行。

### 2. 配置环境变量

根目录提供了 [`.env.example`](.env.example) 作为模板：

```bash
cp .env.example .env
```

至少需要确认这些配置项：

```env
DATABASE_URL=sqlite+aiosqlite:///./sensor_data.db
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_API_BASE=https://api.deepseek.com
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
DEBUG=false
```

前端需要单独准备环境变量：

```bash
cd frontend
cp .env.example .env.local
```

手工联调时，请将前端后端联调地址设为：

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:18000
```

如果要启用知识检索，请额外准备可用的 embedding 服务；如本地无法加载 reranker，可在 `.env` 中设置 `ENABLE_RERANKER=false`。详细说明见 [docs/全流程跑通指南.md](docs/%E5%85%A8%E6%B5%81%E7%A8%8B%E8%B7%91%E9%80%9A%E6%8C%87%E5%8D%97.md)。

### 3. 初始化数据库

```bash
cd backend
python scripts/init_db.py --init-only
```

### 4. 启动后端

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 18000
```

启动后可访问：

- `http://127.0.0.1:18000/health`
- `http://127.0.0.1:18000/docs`

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

- `http://127.0.0.1:3000`

## 演示流程

推荐按以下顺序演示：

1. 启动后端服务并访问 `/health`
2. 启动前端并进入工作台
3. 在知识检索页面输入问题并查看命中结果
4. 根据检索结果生成任务或处理步骤
5. 如需检修域联调，请先在本地初始化登录账号后再访问登录页
6. 展示案例记录、审核或结果沉淀流程
7. 如需补充展示，可在 `/docs` 中查看接口文档
