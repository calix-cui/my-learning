# 商品管理后台（product-admin）

「简易商品管理网站」的前端管理后台，基于 Vue 3 + TypeScript + Vite + Element Plus 实现，对接 FastAPI 商品服务。

## 技术栈

| 类别 | 选型 |
| --- | --- |
| 框架 | Vue 3.5（组合式 API + `<script setup>`） |
| 语言 | TypeScript 5.7（`vue-tsc --noEmit` 全量类型检查） |
| 构建 | Vite 6 |
| UI | Element Plus 2.x + @element-plus/icons-vue（中文语言包 zh-cn） |
| 请求 | axios（统一响应拦截器） |
| 路由 | vue-router 4（HTML5 history 模式） |

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

## 代码规范与检查

按 [ADR-0002](../docs/adr/0002-frontend-quality-gate-lite.md) 的「轻量档」配置：只拦会出错的问题，不追求类型感知规则与格式统一率。

```bash
pnpm lint          # ESLint 全量检查（CI 会跑，有 error 即失败）
pnpm lint:fix      # 自动修可修的问题
pnpm format        # Prettier 格式化（本地用，不进 CI 阻断）
pnpm format:check  # 只检查格式，不写入
pnpm test          # Vitest 单测（src/api，17 个用例，无 DOM、不连后端）
pnpm test:watch    # 监听模式，开发时用
```

| 项 | 配置 | 说明 |
| --- | --- | --- |
| ESLint | `eslint.config.js`（flat config，ESLint 10） | `@eslint/js` recommended + `typescript-eslint` recommended + `eslint-plugin-vue` flat/essential + `eslint-config-prettier` 收尾 |
| 关闭项 | 不启用 type-aware 规则 | 需要 `parserOptions.projectService`，跑得慢、误报多；`vue-tsc --noEmit` 已经把类型错拦在构建里 |
| Prettier | `.prettierrc.json` | 单引号、无分号、行宽 100、`trailingComma: all`；**不参与 CI**，避免为格式改代码 |
| Vitest | `vitest.config.ts` | 只测 `src/api` 的请求封装与错误映射，`environment: node`，不引 jsdom、不设覆盖率门槛 |
| CI | `.github/workflows/ci.yml` 的 `frontend` job | 三条：`pnpm build`（含 `vue-tsc`）、`pnpm lint`、`pnpm test` |

四条红线（出现即本次改动不算完成）：构建失败、ESLint 报 error、引入未声明的依赖、E2E 用例退化。

单测边界：`src/views`、`src/components` 不写组件快照——那部分由 E2E 兜底（商品 18 项 `pnpm acceptance`、对话 10 项 `pnpm acceptance:chat`）与人工验收；

> 对话 E2E 跑前跑后都会清空会话。它默认打 5173 的 dev server；如果你刚改过前端代码（HMR 可能中途整页重载），改用 `pnpm build && pnpm preview` 后 `BASE=http://127.0.0.1:4173 pnpm acceptance:chat`，结果更稳定。
单测只锁定「请求怎么发、错误怎么翻译成中文提示」这类改起来最容易静默出错的逻辑。
升级触发条件写在 ADR-0002 里（前端 > 8000 行 / 组件 > 40 个 / 同类事故 ≥ 2 次 / E2E > 30 条）。

## 与后端联调

- 后端地址：`http://127.0.0.1:8000`（FastAPI，代码位于仓库 `backend/`）。
- 开发与预览环境都通过 Vite proxy 把 `/api` 转发到后端，因此前端代码里只写相对路径 `/api/...`，无需处理浏览器跨域。
- axios 实例（`src/api/client.ts`）：`baseURL = '/api'`、超时 10s。
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
| `/` | 重定向到 `/products` | `src/router/index.ts` |
| `/products` | 商品列表 | `views/ProductList.vue` + `components/ProductFormDialog.vue` |
| `/categories` | 分类管理 | `views/CategoryManage.vue` + `components/CategoryFormDialog.vue` |
| `/dashboard` | 概览 | `views/Dashboard.vue` |
| `/chat` | 对话（会话列表 + 消息区，SSE 逐字渲染，阶段 4） | `views/ChatView.vue`、`api/chat.ts` |

**每个页面的字段、状态、空态与交互细节在 [`docs/design/design.md`](../docs/design/design.md) 与 [`docs/product/prd.md`](../docs/product/prd.md)** —— 那里是设计与需求的唯一来源，本文件只列路由归属。

### 表单校验（与后端字段对齐）

- 商品名称：必填，1–50 个字符；
- 所属分类：必填，选项来自 `GET /api/categories`；
- 商品价格：必填，非负，最多两位小数（校验正则 `^\d+(\.\d{1,2})?$`，错误文案「价格最多 2 位小数，且不能小于 0」），提交时按字符串发送，由后端按 `decimal(8,2)` 落库；
- 库存数量：必填，≥ 0 的整数；
- 上架状态：`el-switch`，对应后端 `shelf_status` 布尔字段；
- 提交中按钮 loading 且禁止关闭弹窗，成功后刷新列表；失败保留弹窗并展示后端 message。

## 目录结构

```
product-admin/
├── index.html                 # lang="zh-CN"，标题「商品管理后台」
├── vite.config.ts             # 5173/4173 端口、/api proxy、构建拆包
├── tsconfig.json              # 应用源码 TS 配置
├── tsconfig.node.json         # Node 侧配置（composite，供 tsconfig 引用）
├── package.json
├── README.md
└── src/
    ├── main.ts                # 挂载 Element Plus（zh-cn）+ router
    ├── App.vue                # 侧栏（200px）+ 顶栏 + <router-view>
    ├── env.d.ts               # .vue 模块类型声明
    ├── router/index.ts        # /products、/categories、/dashboard、/chat
    ├── api/
    │   ├── client.ts          # axios 实例 + 统一响应/错误拦截
    │   ├── products.ts        # 商品 6 个接口封装
    │   └── categories.ts      # 分类 5 个接口封装
    ├── types/api.ts           # 与后端一一对应的 TS 类型
    ├── assets/
    │   └── empty-state.svg          # 空态插画（设计稿风格）
    ├── components/
    │   ├── ProductFormDialog.vue    # 新增/编辑商品弹窗（含校验）
    │   ├── CategoryFormDialog.vue   # 新增/改名分类弹窗
    │   └── StatCard.vue             # 统计卡片
    ├── views/
    │   ├── ProductList.vue
    │   ├── CategoryManage.vue
    │   └── Dashboard.vue
    └── styles/index.css       # 设计 token CSS 变量 + 全局样式
```

## 设计说明

配色与布局对齐 `docs/design/` 下的设计稿与 mockups：中性蓝主色 `#2563EB`、页面底色 `#F5F7FA`、卡片白底 + `#E5E7EB` 描边、8px 圆角，状态标签用绿/灰区分上下架，全部颜色以 CSS 变量定义在 `src/styles/index.css` 的 `:root` 中。设计基准宽度 1440px；表格与容器随窗口伸缩，**不承诺 ≤1280px 的移动端布局**（见 `docs/design/design.md`「响应式与可访问性」）。

## 已知限制

- 未实现登录/权限，后台默认单角色直接进入。
- 未实现批量删除、批量上下架、商品图片上传、导出等扩展功能（P0 范围外）。
- 概览页的「上架商品 / 下架商品 / 库存预警」由一次拉取的前 100 条商品在前端计算（后端无聚合接口），商品超过 100 条时统计会有偏差；「各分类商品数」来自 `GET /api/categories/statistics`，始终准确。
- 分类列表接口非分页接口，分类数量很多时一次性渲染（当前数据量级可接受）。
