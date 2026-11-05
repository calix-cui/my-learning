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

## 与后端联调

- 后端地址：`http://127.0.0.1:8000`（FastAPI，代码位于仓库 `python/fastapi-demo/`）。
- 开发与预览环境都通过 Vite proxy 把 `/api` 转发到后端，因此前端代码里只写相对路径 `/api/...`，无需处理浏览器跨域。
- axios 实例（`src/api/client.ts`）：`baseURL = '/api'`、超时 10s。
- 统一响应约定：成功 `{ code: 200, message: "请求成功", data: ... }`；失败 HTTP 4xx/5xx + `{ code, message, data }`。
  - 响应拦截器在 `code !== 200` 时抛出携带后端 `message` 的错误，并用 `ElMessage.error` 展示；
  - 无响应（后端未启动、超时、断网）统一提示「网络异常，请确认后端已启动」；
  - 422 参数校验失败时展示后端 message，并尽量读取 `data` 中的字段错误。

启动后端（在 `python/fastapi-demo/` 目录）：

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 页面说明

| 路由 | 页面 | 功能 |
| --- | --- | --- |
| `/` | 重定向到 `/products` | — |
| `/products` | 商品列表 | 统计条（商品总数 / 分类数 / 当前筛选结果）、关键词回车查询、分类筛选、10/20/50 分页、新增、编辑、删除（二次确认，删空当前页自动回上一页）、两种空态（搜索无结果 / 还没有商品） |
| `/categories` | 分类管理 | 统计条（分类总数 / 已归类商品 / 空分类）、分类列表与商品数占比条、新增、改名、删除（分类下有商品时后端返回 409 并提示） |
| `/dashboard` | 概览 | 商品总数、分类数、上架商品、下架商品、各分类商品数分布（含暂无商品的分类）、上架状态环形图、库存预警（库存 ≤ 20）、最近新增的 4 件商品 |

### 表单校验（与后端字段对齐）

- 商品名称：必填，1–50 个字符；
- 所属分类：必填，选项来自 `GET /api/categories`；
- 商品价格：必填，非负，最多两位小数（校验正则 `^\d+(\.\d{1,2})?$`，错误文案「价格最多 2 位小数，且不能小于 0」），提交时按字符串发送，由后端按 `decimal(10,2)` 落库；
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
    ├── router/index.ts        # /products、/categories、/dashboard
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

配色与布局对齐 `docs/design/` 下的设计稿与 mockups：中性蓝主色 `#2563EB`、页面底色 `#F5F7FA`、卡片白底 + `#E5E7EB` 描边、8px 圆角，状态标签用绿/灰区分上下架，全部颜色以 CSS 变量定义在 `src/styles/index.css` 的 `:root` 中。页面为 1440px 宽度设计的自适应布局：统计条 3 列、表格按容器宽度伸缩、窄屏（≤960px）统计条自动变 2 列。

## 已知限制

- 未实现登录/权限，后台默认单角色直接进入。
- 未实现批量删除、批量上下架、商品图片上传、导出等扩展功能（P0 范围外）。
- 概览页的「上架商品 / 下架商品 / 库存预警」由一次拉取的前 100 条商品在前端计算（后端无聚合接口），商品超过 100 条时统计会有偏差；「各分类商品数」来自 `GET /api/categories/statistics`，始终准确。
- 分类列表接口非分页接口，分类数量很多时一次性渲染（当前数据量级可接受）。
