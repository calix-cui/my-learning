# 任务队列

> 用户口头下达、尚未排进 11 阶段计划的任务，按「一个接一个来」的顺序记在这里。
> 状态：`TODO` / `IN_PROGRESS` / `BLOCKED` / `DONE`。同一时刻只允许一个 `IN_PROGRESS`。
> 更长的阶段计划见 [`playbooks/05-development-plan-and-mvp-tasks.md`](../playbooks/05-development-plan-and-mvp-tasks.md) 与 [`PROJECT_STATUS.md`](../PROJECT_STATUS.md) §3。

## 队列总览（2026-11-09 登记）

| # | 任务 | 负责角色 | 状态 | 前置 |
|---|---|---|---|---|
| T-UI-01 | 设计体系推翻重建（DESIGN.md + 全部页面设计稿） | UI 设计师 | DONE（待用户确认） | 已产出 PRODUCT.md / DESIGN.md / 5 张稿 |
| T-FE-01 | 按新设计重构全部页面 | Vue 前端 | TODO | T-UI-01 |
| T-FE-02 | 新增【设置】模块 | Vue 前端（+ 后端按需） | IN_PROGRESS（外观已完成） | T-UI-01；口径见 [`../setting design.md`](../setting%20design.md) |
| T-FE-03 | 主题系统（4 套主题 + 明暗/跟随系统） | Vue 前端 | DONE | — |
| T-FE-04 | 状态管理迁到 Pinia（setup store） | Vue 前端 | DONE | 用户 m06333 |
| T-DOC-01 | 设计工具链调研（design-taste-frontend / impeccable） | Lead | IN_PROGRESS | — |

阶段 5「Agent 基础执行循环」仍按 11 阶段计划排在业务队列里，被上面三条 UI/前端任务插队，尚未开始。

---

## T-UI-01 · 设计体系推翻重建

- **用户原话（m06047）**：「@UI 设计师：设计规范与设计稿。推翻所有旧的页面设计，使用 design-taste-frontend Skill，重构当前页面设计。阅读官网 https://impeccable.style/designing/ 和 https://www.tasteskill.dev/guide」。
- **已裁决（m06091）**：
  1. **不碰已归档的商品/分类**，只针对现有界面重新设计，**从零重建、不参考归档实现**；
  2. 设计工具链用 `impeccable`（Operate 模式）产出 **`DESIGN.md`**，旧的 `archive/product-admin/docs/design/design.md` 已由用户删除；
  3. 覆盖**全部页面**：`/login`、`/register`、`/chat`、`/settings`（新增）。
- **现状**：当前应用只有 `/login`、`/register`、`/chat` 三个页面；`DESIGN.md` 与 `PRODUCT.md` 尚未创建（`impeccable context` 报 `NO_PRODUCT_MD`）。
- **已交付（2026-11-09）**：根目录 `PRODUCT.md`（impeccable 产品上下文）+ `DESIGN.md`（YAML token + 8 节规范）；`docs/design/mockups/{01-login,02-register,03-chat,04-settings,05-settings-model}.html` 与 `docs/images/design-*.png`（1440×900 @2x）；`docs/design/README.md` 索引与「与现有实现的差异」清单。
- **验收（草稿，待用户确认后定稿）**：一套可复用的设计 token + 组件规格；每个页面一张 1440×900 设计稿；与现有 Element Plus 组件能对上（不引入第二套 UI 库）；对比度、焦点态、空/错/载三态齐备。

## T-FE-01 · 按新设计重构全部页面

- **用户原话（m06047）**：「@Vue 前端：商品管理后台实现。请你同样根据本地安装的 vue 和前端开发相关的 skill 更新自己的提示词，并在第一步 UI 设计师更新设计之后，根据最新设计，重构当前全部页面」。
- **内容**：先把 `docs/agents/vue-frontend-dev.md` 按本地 Vue 相关 Skill（`vue-best-practices`、`vue-router-best-practices`、`vue-pinia-best-practices`、`vue-testing-best-practices`、`vue-debug-guides`、`frontend-ui-engineering`）更新角色卡，再按 T-UI-01 的产出重构页面。
- **依赖**：T-UI-01 完成并确认。**不得自行改设计**；实现与设计稿不符时报给 Lead。

## T-FE-02 · 新增【设置】模块

- **用户原话（m06047）**：「增加【设置】模块，功能设计参考 @docs/Setting design.md」。
- **已裁决（m06091）**：**不做 workspace**；`docs/setting design.md` 已按「个人助手、单账号、无团队空间」重写（保留 Local/Cloud 双模式、数据归属表、安全要求；设置页首版候选：模型接入 / 账号资料与密码 / 登录设备 / 数据导出与注销 / 外观 / 关于）。
- **仍待确认**：设置页首版具体勾哪些项、API Key 是否允许在页面填写、是否要「注销账号」这种不可逆操作。

---

## T-DOC-01 · 设计工具链调研（Lead）

见本轮答复：`design-taste-frontend` 与 `impeccable` 的分工、可用命令、需要用户配合的点。

---

## T-FE-03 · 主题系统（2026-11-09 已完成）

- **用户原话（m06192）**：「要，做好以后有各种主题的准备，需要设计一套 theme 功能，只添加代码中的配置和对应主题色就可以增加主题」；并要求「前端先完成【主题】功能再继续」。
- **实现**：`frontend/src/theme/`（types / tokens / apply / themes×4）+ `stores/theme.ts` + `components/theme/{ThemeCard,ModeSwitch}.vue` + `components/settings/AppearancePanel.vue` + `views/SettingsView.vue`（路由 `/settings`，侧边栏与用户菜单都可进）。
- **新增主题只需两处**：`theme/themes/<id>.ts` 写 18 个语义色（light + dark），在 `theme/themes/index.ts` 的数组里加一项。色阶（Element Plus 的 light-3/5/7/8/9）由 `color-mix` 自动派生。
- **兼容层**：`styles/index.css` 的旧 `--pa-*` 全部映射到 `--ma-*`，老页面不改代码即跟随主题。
- **验证**：`pnpm type-check` / `lint` / `test`（39 passed，主题相关 8 例）/ `build` 全绿；4 套主题 × 明暗 × 跟随系统的实测截图见 [`docs/design/README.md`](../design/README.md#主题系统2026-11-09-落地)。
- **已知未做**：主题只存 localStorage，**未随账号同步**（换设备要重选）；等「模型接入」一起做设置读写接口时再补 `user_settings`。

---

## T-FE-04 · 状态管理迁到 Pinia（2026-11-09 已完成）

- **用户原话（m06333）**：「把前端改成用 pinia 进行状态管理，使用 vue-best-practices skill 和 vue-pinia-best-practices skill」。
- **迁了什么**：`stores/session.ts`、`stores/theme.ts` 从「模块级 `reactive` + 手写 `readonly`」改成 `defineStore('<id>', () => { … })` setup store：
  - state 一律 `ref`，派生一律 `computed`，动作就是普通函数；
  - **所有 state 都在 `return` 里列出**（vue-pinia-best-practices：「setup store 要把 state 全部 return，否则 devtools / SSR 看不到」）；
  - `stores/theme.ts` 不再把静态的 `themes` 注册表塞进 store——它是配置不是状态，组件直接 `import { themes }`，顺带避开 `storeToRefs` 只处理 ref 的坑（详见下）。
- **接线**：`main.ts` 先 `app.use(createPinia())` 再 `useThemeStore().initTheme()`，最后 `app.use(router)`；路由守卫内部才 `useSessionStore()`，**不在模块顶层取 store**（否则 `getActivePinia was called with no active Pinia`）。
- **组件侧**：`App.vue` 用 `session.displayName` / `session.avatarText`；`AppearancePanel.vue` 用 `storeToRefs(themeStore)` 取 `mode / resolvedMode / currentTheme`，action 直接 `themeStore.setMode()`（`storeToRefs` 不会把函数变成 ref）。
- **踩到的真实坑**：第一版把 `themes` 放进 store 再 `storeToRefs` 解构，页面主题格子**直接空白**——`storeToRefs` 只转换 ref/computed，普通值不会出现在结果里。改成直接从 `@/theme/themes` 引入后恢复。
- **验证**：`pnpm type-check` / `lint` / `format:check` 全过；`pnpm test` **39 passed**（主题 4 例 + 登录 4 例已改成 `setActivePinia(createPinia())` 写法）；`pnpm build` 通过（`index` 83.85 kB gzip 32.86）；`pnpm acceptance:auth` 13/13、`pnpm acceptance:chat` 10/10；4 套主题切换实测正常。
