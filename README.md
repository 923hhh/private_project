# 检测系统

这是一个面向演示与原型验证的检测系统，结合故障诊断、知识检索、任务生成和案例沉淀能力，提供一套从问题输入到处理建议输出的完整流程。

当前仓库采用前后端分离结构：
- `backend/`：FastAPI 后端、数据库迁移、测试与脚本
- `frontend/`：Next.js 前端工作台

公开源码仓库默认不包含本地数据库、样例数据集和演示素材；如需完整演示，请在你自己的环境中准备对应文件。

## 作用

本项目主要用于：

- 接收设备检修或故障相关问题
- 结合知识内容进行检索与分析
- 生成标准化处理步骤与任务
- 记录处理结果并沉淀为案例

## 如何运行

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
DEEPSEEK_API_KEY=sk-xxxxx
DEEPSEEK_API_BASE=https://api.deepseek.com
OPENAI_API_KEY=sk-xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx
DEBUG=false
```

前端需要单独准备环境变量：

```bash
cd frontend
cp .env.example .env.local
```

默认前端后端联调地址为：

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### 3. 初始化数据库

```bash
cd backend
python scripts/init_db.py --init-only
```

### 4. 启动后端

```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后可访问：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

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
5. 展示案例记录、审核或结果沉淀流程
6. 如需补充展示，可在 `/docs` 中查看接口文档
