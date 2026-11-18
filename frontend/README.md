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
| 状态 | Pinia 4（setup store 写法：`stores/session.ts`、`stores/theme.ts`、`stores/chat.ts`） |
| Markdown | markdown-it 15 + DOMPurify 3（只用于助手消息渲染） |
| 主题 | 自研 `src/theme/`（20 个语义色 × light/dark，4 套主题，运行时可切） |

## 会话地址

`/chat` 打开空白草稿。首次发送创建会话后，地址更新为 `/chat/:conversationId`，例如 `/chat/123`。打开已有会话、刷新或使用浏览器历史时，按地址加载会话及执行记录。需要登录时，登录成功后回到原地址。

## 浏览器调试日志

用 `pnpm dev` 启动前端，在浏览器控制台启用 Verbose（详细），搜索 `[my-agent]`。聊天从 `chat.view.send`、`agent.send` 跟到 `agent.sse` 和 `agent.store.*`，审批请求可以用 `agent.approval` 定位。用 `conversationId`、`runId` 和步骤号对照前后端日志。

高频的普通 SSE 分片只单独记录首个，结束时提供分片数和总字符数。Markdown 更新按渲染帧记录字符数和滚动位置。日志只包含摘要，生产构建会移除这些语句。

Tool 设置、MCP 市场和 Skill 管理接口用 `tool-skill.api.request`、`tool-skill.api.response`、`tool-skill.api.error` 查看请求与结果。Skill 目录在认证初始化时获取，设置页可重新扫描，聊天切换读取账号缓存。运行中用 `agent.sse` 和 `agent.store.timeline` 查找工具、审批与技能事件。

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

## 前端开发约定（新增代码必须遵守）

**动手先读根目录 [`DESIGN.md`](../DESIGN.md)**：颜色、字号、间距、圆角、组件样式都以它为准；改完 UI 要在同一个提交里把改动回写进去。

以下几条是硬约定，评审时按它执行。

### 1. 多用 div，减少嵌套层数

- **能用一层就用一层**：不要为了「语义好看」叠出 `div > div > span > span` 这种壳；容器一律用 `div`，只有**行内文字**才用 `span`。
- 判断标准：这个元素只负责布局（宽度/间距/flex）→ 用 `div`；它直接包文字、且需要和相邻文字同流 → 用 `span`。
- 一个组件模板里，从根到叶子**尽量不超过 4 层**；超过就说明有可以合并的包装层。
- 不要再写「为了加一个 class 而包一层 div」：class 直接加在已有的那一层上。
- 反例：`<div class="wrap"><div class="inner"><span class="text">…</span></div></div>` → 正例：`<div class="wrap">…</div>`。
- 例外：`<Teleport>`、`<Transition>`、`<template v-for>` 这类框架必需的结构不算嵌套。

### 2. 新建会话是「草稿态」

点「新建会话」只调 `chat.startNew()`：界面切到空白会话，**不发请求**；第一条消息发出时才建会话（`ensureConversation()`）。删掉当前会话或刷新后无会话，也回到草稿态。判断界面状态用 `chat.draft` / `chat.activeId`，不要假设「打开着会话 = 后端有记录」。

### 3. 交互反馈统一用渐变

hover 用 `linear-gradient(90deg, ink 7%, ink 3%)`：给元素加 `u-tint` 类（`u-tint--soft` / `u-tint--danger`），由全局 CSS 用伪元素 opacity 做 0.15s 淡入；**不要**直接写 `:hover { background: linear-gradient(...) }`（渐变不可动画，会瞬切）。按下 `12% → 7%`，禁止整块纯色 hover，也不做位移/放大（详见 `DESIGN.md` §8.2）。

### 4. 不要轻易加分割线

小模块之间用间距、底色与阴影分组；只有 Markdown 语义（表格、引用块）、输入框聚焦态、低对比度退化三种例外（详见 `DESIGN.md`「边界规则」）。

### 5. 可点元素必须可键盘访问

用真实 `<button>`；确实需要 `div` 时，补 `role="button"` + `tabindex="0"` + `@keydown.enter` / `@keydown.space`，否则 ESLint 的 a11y 规则会拦。

## 代码规范与检查

按 [ADR-0002](../docs/adr/0002-frontend-quality-gate-lite.md) 的「轻量档」配置：只拦会出错的问题，不追求类型感知规则与格式统一率。

```bash
pnpm lint          # ESLint 全量检查（CI 会跑，有 error 即失败）
pnpm lint:fix      # 自动修可修的问题
pnpm format        # Prettier 格式化（本地用，不进 CI 阻断）
pnpm format:check  # 只检查格式，不写入
pnpm test          # Vitest 单测：纯逻辑 + 组件，共 64 例，不连后端
pnpm test:coverage # 同上，额外出覆盖率报告（coverage/index.html，不设门槛）
pnpm test:watch    # 监听模式，开发时用
```

| 项 | 配置 | 说明 |
| --- | --- | --- |
| ESLint | `eslint.config.js`（flat config，ESLint 10） | `@eslint/js` recommended + `typescript-eslint` recommended + `eslint-plugin-vue` flat/essential + `eslint-plugin-vuejs-accessibility` recommended + `eslint-config-prettier` 收尾 |
| 关闭项 | 不启用 type-aware 规则 | 需要 `parserOptions.projectService`，跑得慢、误报多；`vue-tsc --noEmit` 已经把类型错拦在构建里 |
| Prettier | `.prettierrc.json` | 单引号、无分号、行宽 100、`trailingComma: all`；**不参与 CI**，避免为格式改代码 |
| Vitest | `vitest.config.ts` | 默认 `environment: node` 跑纯逻辑；组件测试在文件顶部写 `// @vitest-environment happy-dom` 切 DOM（`src/test/setup.ts` 补 `matchMedia` / `ResizeObserver` / `Element.scrollTo`） |
| 组件测试 | `@vue/test-utils` + `happy-dom` + `@pinia/testing` | 断言「用户能看到什么、点了会怎样」而不是内部实现；需要 store 时用 `createTestingPinia`（`stubActions: true` 断言调用、`false` 验真实行为） |
| 覆盖率 | `@vitest/coverage-v8` | `pnpm test:coverage` 出报告；**不设门槛**——组件覆盖率虚高没有意义，页面流程由 E2E 兜底 |
| DevTools | `vite-plugin-vue-devtools` | `pnpm dev` 时提供组件树 / Pinia 状态 / 路由 / 性能面板（只在开发期注入，不进产物） |
| CI | `.github/workflows/ci.yml` 的 `frontend` job | 三条：`pnpm build`（含 `vue-tsc`）、`pnpm lint`、`pnpm test` |

四条红线（出现即本次改动不算完成）：构建失败、ESLint 报 error、引入未声明的依赖、E2E 用例退化。

单测边界：组件测**行为**（渲染出什么、点击后 emit / store 怎么变），不写快照、不断言 class 名与 DOM 结构；页面级完整流程（登录拦截、流式对话）交给 E2E 与人工验收。

> 端到端脚本（都要前后端在跑）：`pnpm acceptance:chat`（对话流 10 项）、`pnpm acceptance:agent`（深度回答与工具时间线，10 项）、`pnpm acceptance:auth`（注册→登录→刷新→退出→再登录，13 项）、`pnpm acceptance:settings`（模型接入→测试连接→改显示名→设备→导出→注销→主题同步，15 项）、`pnpm acceptance:tools`（设置窗口可点→工具启停→每日上限→审批拒绝→审批批准→刷新无残留，9 项）。
> `pnpm acceptance:scroll`（打开会话贴底→滚到顶部翻两页→正在读的那条不跳位→入口收起，10 项）、`pnpm acceptance:route`（深链→刷新→侧栏切换→后退/前进→设置浮层共存→非法路径回落，11 项）与 `pnpm acceptance:recovery`（断流后提示与锁定→只读核对→恢复正文；连 `run_started` 都没收到时按 `request_id` 认领，20 项）不需要后端：它自己拦截 `/api` 返回模拟数据与断开的 SSE，只要一个 dev server 在跑（`pnpm dev --port 5199`）。
> `pnpm acceptance:live` 是唯一打真实模型的一组：真实 Chrome + 真实后端 + 真实 DeepSeek，14 项，需要后端 8000 在跑且 `.env` 配好模型。
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
| `/chat` | 对话（左会话列表 + 右消息区，SSE 逐字渲染，助手消息按 Markdown 渲染；普通聊天按需调用工具，可展开执行过程。「深度回答」调整兼容模型的推理强度） | `views/ChatView.vue`、`components/chat/*`、`stores/chat.ts`、`api/chat.ts`、`api/agent.ts`、`utils/markdown.ts` |
| `/settings` | **悬浮窗**（不是独立页面）：`/chat?settings=1` 之上盖一层，关掉回原处；内含模型接入 / 账号资料 / 登录设备 / 外观 / 数据管理五节 | `components/settings/SettingsDialog.vue`、`views/SettingsView.vue`、`components/settings/*`、`stores/settings.ts` |
| `/` / 其他 | 重定向到 `/chat`；未登录时守卫改送 `/login?redirect=...` | `src/router/index.ts` |

未登录只剩登录/注册两个页面可达：`router.beforeEach` 先向后端确认一次登录态（`GET /api/auth/me`），再决定放行或跳转。
任何接口返回 401 时，`src/api/client.ts` 会清本地状态并跳登录页（启动探测请求带 `skipAuthRedirect` 豁免）。

**接口字段、错误文案的唯一来源是 [`docs/api.md`](../docs/api.md)**，本文件只说明前端怎么用。

### 对话页行为

消息区域读取 `chat.feedItems`：`stores/chat/feed.ts` 将消息、运行摘要和当前过程投影为统一展示项，`ChatMessageList` / `ChatExecutionItem` 负责渲染。Store 本身只是组合根（`stores/chat.ts`，475 行）：会话列表与当前 id 在 `conversations.ts`，每个会话的运行时状态容器在 `threads.ts`，历史分页与刷新核对在 `history.ts`，三者用 `createX(deps)` 工厂接线（见 [ADR-0017](../docs/adr/0017-chat-store-module-boundaries.md)）。执行项使用会话内稳定标识，完成时保留过程及详情展开状态，助手正文只输出一次；分页只含助手消息时也能展示过程。滚动与帧合并交给 `composables/useChatScroll.ts`：切会话才无条件贴底，流式分片和步骤只跟随「仍在底部」的用户（阈值 80px），往上翻页由 `keepAnchor` 补回新增高度。地址与会话状态的双向同步在 `composables/useChatRoute.ts`：`/chat/:id` 打开会话、`/chat` 回草稿态、首条消息建库后把地址换成真实 id、删除或打不开时退回 `/chat`，且只在对话路由上改写地址（设置浮层不会吃掉会话地址）。每次运行的正文预览、步骤、审批和状态统一存于 `Execution`；`execution.ts` 收拢发送与审批连接生命周期，`events.ts` 按 seq 去重步骤。创建会话前锁定发送，断流后查询历史并显示「重新核对状态」，不会自动重发；结果未知或待审批时禁止新发送。审批、步骤读取失败保留错误，不以空数据替代。若开始事件丢失而尚无运行 ID，需刷新页面核对历史，当前接口不支持按 request_id 查询或自动续流。

- 左栏：会话列表按 `update_time` 倒序，hover 显示「改名 / 删除」两个内联按钮；空态提示「还没有会话，点「新建」开始」。会话状态由 `stores/chat.ts` 持有，侧栏与对话页共用同一份。
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
│   ├── auth-acceptance.mjs    # 账号端到端验收（13 项：注册→刷新→退出→再登录）
│   ├── chat-recovery-acceptance.mjs # 断流恢复验收（12 项：模拟 API/SSE，不依赖后端）
│   ├── chat-scroll-acceptance.mjs   # 滚动验收（10 项：贴底、两次翻页锚点，不依赖后端）
│   └── chat-route-acceptance.mjs    # 会话地址验收（11 项：深链、刷新、后退/前进，不依赖后端）
└── src/
    ├── main.ts                # 挂载 Element Plus（zh-cn）+ router
    ├── App.vue                # 外壳：左栏 + 对话区 + 设置悬浮窗（登录页不套外壳）
    ├── components/
    │   ├── layout/            # AsideView（左栏：品牌 + 会话列表 + 账号区，挂载时拉一次会话列表）
    │   ├── ui/                # 通用组件库：AppIcon（内联 SVG）/ IconButton（圆形）/ SoftButton（阴影当边界）
    │   ├── chat/              # ThreadList / ThreadItem / ChatToolbar / ChatEmpty / ChatMessage / ChatComposer / AgentTimeline
    │   ├── theme/             # ThemeCard / ModeSwitch
    │   └── settings/          # SettingsDialog（悬浮窗）+ Model/Account/Devices/Data/Appearance/Tools/Market/Skills 面板

    ├── env.d.ts               # .vue 模块类型声明
    ├── router/index.ts        # 路由 + 登录守卫（未登录只能进 /login、/register）
    ├── api/
    │   ├── client.ts          # axios 实例 + 统一响应/错误拦截 + 401 跳登录
    │   ├── chat.ts            # 对话 6 个接口封装 + SSE 流式解析
    │   ├── agent.ts           # agent 流式（工具循环）+ 运行回放
    │   ├── auth.ts            # 账号 7 个接口封装
    │   └── unauthorized.ts    # 401 回调注册（避免 client 与 store 互相 import）
    ├── stores/
    │   ├── session.ts         # Pinia：登录态（user / loaded / 登录登出清除）
    │   ├── chat.ts            # Pinia 组合根：当前会话 + 发送/审批接线 + 视图派生值（侧栏与对话页共用）
    │   ├── chat/
    │   │   ├── threads.ts     # 每个会话的运行时状态容器、取消句柄、请求去重
    │   │   ├── conversations.ts # 会话列表、当前 id、账号代次、建/改/删
    │   │   ├── history.ts     # 历史分页、刷新对齐、步骤与审批重查
    │   │   ├── execution.ts   # 发送/审批状态机与 runExecution
    │   │   ├── events.ts      # SSE 事件归并（按 seq 去重）
    │   │   └── feed.ts        # 消息 + 运行 → 展示项的纯投影
    │   ├── settings.ts        # Pinia：模型标签、主题偏好
    │   └── theme.ts           # Pinia：主题（themeId / mode / 跟随系统 / 落盘）
    ├── theme/
    │   ├── types.ts           # 20 个语义色 schema + 静态 token 类型
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
    │   └── SettingsView.vue   # 设置内容（导航 + 五节面板，由 SettingsDialog 承载）
    └── styles/index.css       # 设计 token 兜底 + reset + Element Plus 令牌映射 + 认证页共用样式
```

`public/` 放品牌资产：`logo.png`（侧栏与登录页，256×256）、`favicon.ico`、`favicon-16/32.png`、`apple-touch-icon.png`、`android-chrome-192/512.png`、`site.webmanifest`。图标源文件在仓库根 `images/`，改图后重新 `sips -Z 256 images/logo.png --out frontend/public/logo.png` 并覆盖同名文件即可。

## 设计说明

设计规范见根目录 [`DESIGN.md`](../DESIGN.md)（颜色 / 字体 / 间距 / 组件 / 断点），页面稿见 [`docs/design/`](../docs/design/README.md)。

- 颜色只有一个出口：`:root` 上的 `--ma-*` 语义变量，由 `src/theme/apply.ts` 在运行时写入；组件**不写死色值**。
- 换主题 = 重写这批变量，不重渲染组件；Element Plus 的主色阶由 `color-mix()` 从 `accent` 派生，不必为每套主题手写。
- 设计基准宽度 1440px，桌面优先；≤960px 只保证不崩，不做重排版。

## 已知限制

- 主题的优先级是「账号 > 本机 `localStorage`」：登录后从 `/api/settings/appearance` 拉取，切换时本地立即生效、异步写回账号。
- 模型 Key 存在后端 `user_settings`（Fernet 加密），前端只拿到末四位；服务端没配 `APP_SECRET_KEY` 时只能改其他字段。
- 未实现多 Agent 切换（后端已预留 `agent_key` 字段，界面暂无入口）。
- 会话列表一次性拉 50 条，没有分页器（数量级小，够用）。
- 没有「停止生成」按钮：流式过程中只能等它结束或切走会话。
- 移动端只保证不崩（`<960px` 侧栏收窄到 220px），没有为小屏重排对话布局。
