# Learning Lab

个人编程学习与实践仓库，集中记录 Python、前端、Agent 和全栈应用开发过程。

本仓库采用 **Monorepo** 组织方式：按技术领域划分目录，每个具体项目保持相对独立的依赖、运行方式和说明文档。

## 目录结构

```text
my-learning/
├── python/          # Python 基础、脚本、FastAPI 等
├── frontend/        # React、TypeScript 等前端练习
├── agent/           # Agent、工具调用、MCP、RAG 等实验
├── fullstack/       # 前后端结合的完整应用
├── docs/               # 跨项目的学习笔记和规划
├── .editorconfig
├── .gitattributes
├── .gitignore
└── README.md
```

每个子项目建议包含自己的 `README.md`，并在需要时维护独立的依赖文件，例如 `requirements.txt`、`pyproject.toml` 或 `package.json`。

## 项目索引

### Python

| 项目 | 说明 | 状态 |
|---|---|---|
| [fastapi-demo](./python/fastapi-demo/) | FastAPI 接口开发练习：CRUD、联表查询、统计、测试与 CI | 持续开发 |

### Frontend

### Agent

### Fullstack

| 项目 | 说明 | 状态 |
|---|---|---|
| [product-admin](./fullstack/product-admin/) | 简易商品管理后台：Vue 3 + TypeScript + Vite + Element Plus，对接 FastAPI 商品/分类接口；含 PRD、设计稿、API 契约与 18 项端到端验收脚本 | 可用（v1.0） |

商品管理网站的交付与验收说明见 [docs/product-admin/README.md](./docs/product-admin/README.md)，
包含如何启动前后端、P0 需求对照表、验收证据与已知限制。

> 项目名称、状态和说明应随实际进度更新；尚未创建的项目可以删除对应索引。

## 环境与依赖管理

### Python

建议为每个具有独立依赖的 Python 项目创建虚拟环境，不要把 `.venv` 提交到 Git。

```bash
cd python/fastapi-demo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

退出虚拟环境：

```bash
deactivate
```

如果项目使用 `pyproject.toml`，请以该项目 README 中的安装说明为准。

### Frontend

进入具体前端项目后，根据锁文件选择包管理器：

```bash
cd frontend/react-demo   # 换成实际项目目录
npm install
npm run dev
```

如果仓库使用 `pnpm-lock.yaml` 或 `yarn.lock`，应使用对应的包管理器，不要混用锁文件。

### Agent

Agent 项目可能同时包含 Python、前端和外部服务。请在各项目目录中分别说明：
- Python / Node.js 版本要求
- 依赖安装与启动命令
- 所需环境变量
- 模型服务、API 或数据库等外部依赖

## 通用约定

1. 一个目录对应一个边界清晰的练习或项目。
2. 每个可独立运行的项目都应有自己的 README。
3. 不同项目的依赖不要随意混用；出现版本冲突时拆分虚拟环境。
4. 不提交密钥、访问令牌、个人配置、虚拟环境和构建产物。
5. 重要实验应记录目标、关键实现、运行方式和遇到的问题。
6. 项目从练习发展为完整作品后，可以迁移到独立仓库。

## 提交信息建议

采用简洁、可读的提交信息：

```text
feat(agent): add basic tool calling
fix(fastapi): handle missing product
docs: update project index
refactor(react): extract shared component
chore: update gitignore
```

## 安全提醒

将真实密钥放在本地 `.env` 文件中，并提交 `.env.example` 作为变量模板。`.env.example` 只能包含变量名和无敏感信息的示例值，不能放入真实密钥。
