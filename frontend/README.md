# My Agent 前端（frontend）

My Agent 的聊天界面，基于 Vue 3 + TypeScript + Vite + Element Plus 实现，对接 FastAPI 的对话接口。
商品 / 分类 / 概览页已于 2026-11-08 归档到 [`archive/product-admin/frontend/`](../archive/product-admin/README.md)，本目录只保留对话相关代码。

## 技术栈

| 类别 | 选型 |
| --- | --- |
| 框架 | Vue 3.5（组合式 API + `<script setup>`） |
| 语言 | TypeScript 5.7（`vue-tsc --noEmit` 全量类型检查） |
| 构建 | Vite 6 |
| UI | Element Plus 2.x + @element-plus/icons-vue（中文语言包 zh-cn） |
| 请求 | axios（统一响应拦截器）+ 原生 `fetch`（SSE 流式） |
| 路由 | vue-router 4（HTML5 history 模式，每个页面路由级懒加载） |
| 状态 | Pinia 4（setup store 写法：`stores/session.ts`、`stores/theme.ts`） |
| Markdown | markdown-it 15 + DOMPurify 3（只用于助手消息渲染） |
| 主题 | 自研 `src/theme/`（18 个语义色 × light/dark，4 套主题，运行时可切） |

## 启动方式

```bash
# 1. 安装依赖（Node 24 / pnpm 12，本机已验证）
pnpm install

# 2. 启动开发服务器：http://127.0.0.1:5173
pnpm dev

# 3. 生产构建（先类型检查再打包，产物输出到 dist/）
pnpm build

# 4. 预览构建产物：http://127.0.0.1:4173
pnpm preview

# 单独执行类型检查
pnpm type-check
```

> 端口约定：dev 5173、preview 4173，均不会占用后端 8000 端口；`strictPort: true` 保证端口被占用时直接报错而不是静默换端口。
> 想一条命令起前后端：仓库根 `./scripts/dev.sh`。

## 代码规范与检查

按 [ADR-0002](../docs/adr/0002-frontend-quality-gate-lite.md) 的「轻量档」配置：只拦会出错的问题，不追求类型感知规则与格式统一率。

```bash
pnpm lint          # ESLint 全量检查（CI 会跑，有 error 即失败）
pnpm lint:fix      # 自动修可修的问题
pnpm format        # Prettier 格式化（本地用，不进 CI 阻断）
pnpm format:check  # 只检查格式，不写入
pnpm test          # Vitest 单测（src/api + src/stores + src/theme + src/utils，39 个用例，无 DOM、不连后端）
pnpm test:watch    # 监听模式，开发时用
```

| 项 | 配置 | 说明 |
| --- | --- | --- |
| ESLint | `eslint.config.js`（flat config，ESLint 10） | `@eslint/js` recommended + `typescript-eslint` recommended + `eslint-plugin-vue` flat/essential + `eslint-config-prettier` 收尾 |
| 关闭项 | 不启用 type-aware 规则 | 需要 `parserOptions.projectService`，跑得慢、误报多；`vue-tsc --noEmit` 已经把类型错拦在构建里 |
| Prettier | `.prettierrc.json` | 单引号、无分号、行宽 100、`trailingComma: all`；**不参与 CI**，避免为格式改代码 |
| Vitest | `vitest.config.ts` | 测 `src/api` 的请求封装与错误映射、`src/utils/markdown.ts` 的渲染与消毒，`environment: node`，不设覆盖率门槛 |
| CI | `.github/workflows/ci.yml` 的 `frontend` job | 三条：`pnpm build`（含 `vue-tsc`）、`pnpm lint`、`pnpm test` |

四条红线（出现即本次改动不算完成）：构建失败、ESLint 报 error、引入未声明的依赖、E2E 用例退化。

单测边界：`src/views` 不写组件快照——那部分由 E2E 兜底（对话 10 项 `pnpm acceptance:chat`）与人工验收。

> 对话 E2E 跑前跑后都会清空会话。它默认打 5173 的 dev server；如果你刚改过前端代码（HMR 可能中途整页重载），改用 `pnpm build && pnpm preview` 后 `BASE=http://127.0.0.1:4173 pnpm acceptance:chat`，结果更稳定。

## 与后端联调

- 后端地址：`http://127.0.0.1:8000`（FastAPI，代码位于仓库 `backend/`）。
- 开发与预览环境都通过 Vite proxy 把 `/api` 与 `/healthz` 转发到后端，因此前端代码里只写相对路径，无需处理浏览器跨域。
- axios 实例（`src/api/client.ts`）：`baseURL = '/api'`、超时 10s。
- 流式接口单独用 `fetch`（`src/api/chat.ts` 的 `sendMessageStream`）：`POST /api/conversations/{id}/messages/stream`，按 `\n\n` 分帧解析 SSE，30s+ 的超时不由 axios 管。
- 统一响应约定：成功 `{ code: 200, message: "请求成功", data: ... }`；失败 HTTP 4xx/5xx + `{ code, message, data }`。
  - 响应拦截器在 `code !== 200` 时抛出携带后端 `message` 的错误，并用 `ElMessage.error` 展示；
  - 无响应（后端未启动、超时、断网）统一提示「网络异常，请确认后端已启动」；
  - 422 参数校验失败时展示后端 message，并尽量读取 `data` 中的字段错误。

启动后端（在 `backend/` 目录）：

```bash
make run          # 等价于 uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 页面说明

| 路由 | 页面 | 组件 |
| --- | --- | --- |
| `/login` | 登录（公开） | `views/LoginView.vue`、`stores/session.ts` |
| `/register` | 注册（公开，注册即登录） | `views/RegisterView.vue` |
| `/chat` | 对话（左会话列表 + 右消息区，SSE 逐字渲染，助手消息按 Markdown 渲染） | `views/ChatView.vue`、`api/chat.ts`、`utils/markdown.ts` |
| `/` / 其他 | 重定向到 `/chat`；未登录时守卫改送 `/login?redirect=...` | `src/router/index.ts` |

未登录只剩登录/注册两个页面可达：`router.beforeEach` 先向后端确认一次登录态（`GET /api/auth/me`），再决定放行或跳转。
任何接口返回 401 时，`src/api/client.ts` 会清本地状态并跳登录页（启动探测请求带 `skipAuthRedirect` 豁免）。

**接口字段、错误文案的唯一来源是 [`docs/api.md`](../docs/api.md)**，本文件只说明前端怎么用。

### 对话页行为

- 左栏：会话列表按 `update_time` 倒序，hover 显示「改名 / 删除」两个内联按钮；空态提示「还没有会话，点「新建会话」开始」。
- 右栏：消息气泡，用户消息纯文本、助手消息 Markdown；流式时显示「正在输入…」，结束后落到完整消息并带模型名。
- 输入框：Enter 发送、Shift+Enter 换行，最多 4000 字并显示计数；发送中禁用；失败保留原文并提示后端 message。
- 首条消息自动生成会话标题（取前 30 字），并同步刷新列表。

## 目录结构

```
frontend/
├── index.html                 # lang="zh-CN"，标题「My Agent」
├── vite.config.ts             # 5173/4173 端口、/api proxy、构建拆包
├── eslint.config.js           # ESLint flat config
├── vitest.config.ts           # Vitest 配置（node 环境）
├── tsconfig.json / tsconfig.node.json
├── package.json
├── README.md
├── scripts/
│   ├── chat-acceptance.mjs    # 对话端到端验收（10 项，CDP 驱动真实浏览器）
│   └── auth-acceptance.mjs    # 账号端到端验收（13 项：注册→刷新→退出→再登录）
└── src/
    ├── main.ts                # 挂载 Element Plus（zh-cn）+ router
    ├── App.vue                # 侧栏 + 顶栏 + <router-view>（登录页不套外壳）
    ├── components/
    │   ├── theme/             # ThemeCard / ModeSwitch
    │   └── settings/          # AppearancePanel

    ├── env.d.ts               # .vue 模块类型声明
    ├── router/index.ts        # 路由 + 登录守卫（未登录只能进 /login、/register）
    ├── api/
    │   ├── client.ts          # axios 实例 + 统一响应/错误拦截 + 401 跳登录
    │   ├── chat.ts            # 对话 6 个接口封装 + SSE 流式解析
    │   ├── auth.ts            # 账号 7 个接口封装
    │   └── unauthorized.ts    # 401 回调注册（避免 client 与 store 互相 import）
    ├── stores/
    │   ├── session.ts         # Pinia：登录态（user / loaded / 登录登出清除）
    │   └── theme.ts           # Pinia：主题（themeId / mode / 跟随系统 / 落盘）
    ├── theme/
    │   ├── types.ts           # 18 个语义色 schema + 静态 token 类型
    │   ├── tokens.ts          # 字体/圆角/间距/宽度
    │   ├── apply.ts           # 编译 CSS 变量 + 派生 Element Plus 色阶
    │   └── themes/            # pine / sand / indigo / graphite（各含 light+dark）
    ├── types/api.ts           # 与后端一一对应的 TS 类型（对话 + 账号）
    ├── utils/
    │   ├── markdown.ts        # markdown-it + DOMPurify 渲染
    │   └── markdown.test.ts
    ├── views/
    │   ├── ChatView.vue       # 对话页
    │   ├── LoginView.vue      # 登录页
    │   ├── RegisterView.vue   # 注册页
    │   └── SettingsView.vue   # 设置页（外观已实现，其余分节待建）
    └── styles/index.css       # 设计 token CSS 变量 + 全局基础样式
```

## 设计说明

设计规范见根目录 [`DESIGN.md`](../DESIGN.md)（颜色 / 字体 / 间距 / 组件 / 断点），页面稿见 [`docs/design/`](../docs/design/README.md)。

- 颜色只有一个出口：`:root` 上的 `--ma-*` 语义变量，由 `src/theme/apply.ts` 在运行时写入；组件**不写死色值**。
- 换主题 = 重写这批变量，不重渲染组件；Element Plus 的主色阶由 `color-mix()` 从 `accent` 派生，不必为每套主题手写。
- 设计基准宽度 1440px，桌面优先；≤960px 只保证不崩，不做重排版。

## 已知限制

- 主题选择只存 `localStorage`，**不随账号同步**（换设备要重选；等设置读写接口时补 `user_settings`）。
- 设置页只实现了「外观」，「模型接入 / 账号资料 / 登录设备 / 数据管理」四个分节还是占位。
- 未实现多 Agent 切换（后端已预留 `agent_key` 字段，界面暂无入口）。
- 会话列表一次性拉 50 条，没有分页器（数量级小，够用）。
- 没有「停止生成」按钮：流式过程中只能等它结束或切走会话。
- 没有移动端适配。
