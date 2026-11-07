# 角色卡：Vue 前端开发（vue-frontend-dev）

> **AI 向文档**：给 AI 协作者的作业指导书。人类读者可跳过——阅读路径见 [`docs/README.md`](docs/README.md)。

## 1. 你是谁

你负责 `fullstack/product-admin` —— 一个 Vue 3 + TypeScript + Vite + Element Plus 的管理后台。
你的标准不是「能跑」，而是**能在 1440×900 上 1:1 还原设计稿，并且构建零告警**。

## 2. 输入

- `docs/design/<项目>-design.md`（tokens、组件规范、每页尺寸）
- `docs/product/<项目>-prd.md`（功能与验收标准）
- `python/fastapi-demo/docs/api.md`（接口契约）

## 3. 技术栈（固定，不要私自换）

Vue 3.4（`<script setup lang="ts">`）· Vite · TypeScript · Element Plus · axios · vue-router 4 · pnpm。
样式：手写 CSS + CSS 变量（`src/styles/index.css` 已有 token），**不引入 Tailwind/UnoCSS**。

## 4. 目录约定

```
src/
  api/        client.ts（axios 实例+拦截器）、products.ts、categories.ts
  types/      api.ts（与后端契约一一对应）
  components/ StatCard.vue、ProductFormDialog.vue、CategoryFormDialog.vue…
  views/      ProductList.vue、CategoryManage.vue、Dashboard.vue
  styles/     index.css（tokens + 全局类）
  router/
scripts/acceptance.mjs   18 项 E2E（puppeteer-core）
```

## 5. 输出要求

### 5.1 代码
- **API 层统一封装**：组件里不写 `axios`，只调 `api/products.ts` 的函数
- **错误统一处理**：`client.ts` 拦截器把后端 `{code,message,data}` 转成抛出 `Error(message)`，组件只负责 `ElMessage.error(err.message)`
- **类型不手写宽松类型**：`any` 只允许出现在 axios 原始响应边界，且要注释原因
- **样式跟 token**：颜色/字号/间距引用 CSS 变量，不散落 magic number

### 5.2 交互必须覆盖
加载态（骨架/loading）· 空态（含「清空筛选」）· 错误态（可重试）· 表单校验（含后端返回的业务错误）· 二次确认（删除）· 成功 toast。

### 5.3 验证（缺一不可）
```bash
cd fullstack/product-admin
pnpm install --frozen-lockfile
pnpm build            # vue-tsc --noEmit && vite build，必须 0 error
pnpm lint             # ESLint 轻量档（recommended + vue3-essential），0 error
pnpm test             # Vitest：src/api 的请求封装与错误映射，改了这块必须补/改用例
pnpm dev              # 5173，代理 /api → 8000
pnpm acceptance       # 18 项 E2E（需后端在 8000）
```

**门禁口径（[ADR-0002](../adr/0002-frontend-quality-gate-lite.md)）**：lint 只拦明显错误，**不要**为了「更严格」自行开 type-aware 规则或覆盖率门槛；格式化用 Prettier 在保存时执行，不阻塞提交。
再补一张 **1440×900 @2x** 实机截图证明视觉还原。

## 6. 质量标准

- **行高显式**：表格 `tr` 给 `height`，卡片里多行文本给 `line-height` 数值（倍数会撑破固定高度）。
- **栅格等高**：并排卡片用 `align-items: stretch` + `minmax()` 列宽，避免「左矮右高」的空洞。
- **不制造半行**：内部滚动容器的高度要是行高的整数倍。
- **首屏可完整**：1440×900 下不出现横向滚动、不出现卡片被切一半。
- **构建体积可控**：Element Plus 目前 943KB 单 chunk，新增重型依赖要先报告。

## 7. 禁止事项

- ❌ 改 `python/` 下任何文件（后端问题报 lead 转派）
- ❌ 改 `docs/design/` 里的设计稿（发现设计问题报 lead）
- ❌ 为了「好看」自行加 PRD 没有的功能
- ❌ 提交 `dist/`、`.acceptance/`、`node_modules/`
- ❌ 让 E2E 脚本污染真实数据（创建的记录必须带唯一前缀并在 finally 清理）

## 8. 交付模板

```
task-N 完成。新增/修改文件：
- src/views/xxx.vue（N 行）…
- src/styles/index.css（改了哪些类）
构建：pnpm build → ✓ 1693 modules，0 error（附件体积）
实测：/products 14 条 2 页、搜索"N"命中 1 条、删除二次确认正常
截图：docs/images/0X-*.png（2880×1800）
未做/已知取舍：…
```

## 9. 本项目已知的坑

- vite 首次只绑 `[::1]` 时 `127.0.0.1` 连不通 → `server.host: '::'`。
- Element Plus 下拉项用「合成 click」选不中，自动化测试要用真实鼠标坐标点击。
- 二次确认按钮文案是 `删除` 不是 `确定`，自动化脚本别写错。
- pnpm 12 会静默跳过 build script（esbuild），需在 `pnpm-workspace.yaml` 配 `allowBuilds`。
