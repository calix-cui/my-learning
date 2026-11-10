# 任务队列

> 用户口头下达、尚未排进 11 阶段计划的任务，按「一个接一个来」的顺序记在这里。
> 状态：`TODO` / `IN_PROGRESS` / `BLOCKED` / `DONE`。同一时刻只允许一个 `IN_PROGRESS`。
> 更长的阶段计划见 [`playbooks/05-development-plan-and-mvp-tasks.md`](../playbooks/05-development-plan-and-mvp-tasks.md) 与 [`PROJECT_STATUS.md`](../PROJECT_STATUS.md) §3。

## 队列总览（2026-11-09 登记）

| # | 任务 | 负责角色 | 状态 | 前置 |
|---|---|---|---|---|
| T-UI-01 | 设计体系推翻重建（DESIGN.md + 全部页面设计稿） | UI 设计师 | DONE（待用户确认） | 已产出 PRODUCT.md / DESIGN.md / 5 张稿 |
| T-FE-01 | 按新设计重构全部页面 | Vue 前端 | DONE | 提交见 `docs/plan/TASKS.md` §T-FE-01 记录 |
| T-FE-02 | 新增【设置】模块 | Vue 前端（+ 后端按需） | DONE | T-UI-01；口径见 [`../setting design.md`](../setting%20design.md)、[ADR-0009](../adr/0009-per-user-model-settings.md) |
| T-FE-03 | 主题系统（4 套主题 + 明暗/跟随系统） | Vue 前端 | DONE | — |
| T-FE-04 | 状态管理迁到 Pinia（setup store） | Vue 前端 | DONE | 用户 m06333 |
| T-DOC-01 | 设计工具链调研（design-taste-frontend / impeccable） | Lead | DONE | 交付 `docs/design/toolchain.md` |

阶段 5「Agent 基础执行循环 + Tool Calling」已按 11 阶段计划完成（2026-11-10，T1–T7），见本文末「阶段 5」一节与 [`../agent.md`](../agent.md)。

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

## T-FE-01 · 按新设计重构全部页面（DONE）

- **落地（2026-11-09）**：外壳（264px 侧栏 + 48px 顶栏 + 1080 内容区）、对话页（720 阅读列 + 气泡 + 输入盒）、登录/注册（400 卡片 + 衬线标题 + logo）、设置页（200 导航 + 560 表单）全部按 `DESIGN.md` 与 `docs/design/mockups/` 重写；会话状态提升到 `stores/chat.ts` 供侧栏与页面共用；`styles/index.css` 从 `--pa-*` 兼容层收敛为「token 兜底 + reset + el 映射 + 认证页共用样式」。
- **顺带完成**：品牌资产接入（`frontend/public/` 的 logo 与 favicon 全套、`site.webmanifest`、`index.html` 的 icon/theme-color）；组件拆分 `components/chat/{ThreadList,ChatMessage,ChatComposer}.vue`。
- **验证**：`pnpm type-check` / `lint` / `format:check` / `build` 通过；`pnpm test` 50 passed；`pnpm acceptance:auth` 13/13、`pnpm acceptance:chat` 10/10；实体截图见 `docs/images/ui-0*.png`。
- **用户原话（m06047）**：「@Vue 前端：商品管理后台实现。请你同样根据本地安装的 vue 和前端开发相关的 skill 更新自己的提示词，并在第一步 UI 设计师更新设计之后，根据最新设计，重构当前全部页面」。
- **内容**：先把 `docs/agents/vue-frontend-dev.md` 按本地 Vue 相关 Skill（`vue-best-practices`、`vue-router-best-practices`、`vue-pinia-best-practices`、`vue-testing-best-practices`、`vue-debug-guides`、`frontend-ui-engineering`）更新角色卡，再按 T-UI-01 的产出重构页面。
- **依赖**：T-UI-01 完成并确认。**不得自行改设计**；实现与设计稿不符时报给 Lead。

## T-FE-02 · 新增【设置】模块

- **用户原话（m06047）**：「增加【设置】模块，功能设计参考 @docs/Setting design.md」。
- **已裁决（m06091）**：**不做 workspace**；`docs/setting design.md` 已按「个人助手、单账号、无团队空间」重写（保留 Local/Cloud 双模式、数据归属表、安全要求；设置页首版候选：模型接入 / 账号资料与密码 / 登录设备 / 数据导出与注销 / 外观 / 关于）。
- **已定（2026-11-09）**：五节全部落地——模型接入（Key 加密存 `user_settings`，界面只显示末四位）/ 账号资料（显示名 + 改密码）/ 登录设备（复用 `/api/auth/sessions`）/ 外观 / 数据管理（导出 JSON·Markdown + 注销账号，需再输密码并输入「注销」）。
- **落地记录**：
  - 后端：`user_settings` 表 + `app/common/crypto.py`（Fernet，主密钥 `APP_SECRET_KEY`）+ `/api/settings/{model,model/test,export}` + `PATCH/DELETE /api/auth/me`；聊天改用 `get_user_llm`，按账号取模型，未保存过则回落环境变量（决策见 ADR-0009）。
  - 前端：`stores/settings.ts`、`components/settings/{Model,Account,Devices,Data}Panel.vue`，设置页五节全部可点；顶栏模型标签改为「账号里配置的模型」。
  - 修的真问题：① `App.vue` 只在 `onMounted` 取设置 → 登录页首屏时还没登录，登录后标签永远「未配置」，改成 `watch(isLoggedIn)`；② `User.conversations` 没有 `cascade="all, delete-orphan"`，注销时 SQLAlchemy 先把 `user_id` 置空 → MySQL `1048 Column 'user_id' cannot be null`，补级联并加回归用例。
  - 验证：后端 148 例 / 94.22%（含设置服务 11、设置接口 15）；前端 54 例（含 ModelPanel 4）；`pnpm acceptance:settings` **13/13**；`acceptance:auth` 13/13、`acceptance:chat` 10/10。

---

## T-DOC-01 · 设计工具链调研（Lead，DONE）

- **交付**：[`docs/design/toolchain.md`](../design/toolchain.md)——两工具实测差异表、可复现命令流程（`context` → `init` → `document` → `shape` → `critique`/`audit`/`polish`/`harden` → `detect`）、仓库该提交哪些文件、重跑时机、四条被否方案。
- **结论**：App 界面由 `impeccable` 的 Operate 模式主导，`design-taste-frontend` 只借排版/间距/动效/文案细则。
- **关键证据**：官网提到的 `references/app-screens.md` 在本地 2.5.1 与上游 `skills/taste-skill/references/`（20 个文件）中都不存在，属未发布路线，不能当方案依据。

---

## T-FE-03 · 主题系统（2026-11-09 已完成）

- **用户原话（m06192）**：「要，做好以后有各种主题的准备，需要设计一套 theme 功能，只添加代码中的配置和对应主题色就可以增加主题」；并要求「前端先完成【主题】功能再继续」。
- **实现**：`frontend/src/theme/`（types / tokens / apply / themes×4）+ `stores/theme.ts` + `components/theme/{ThemeCard,ModeSwitch}.vue` + `components/settings/AppearancePanel.vue` + `views/SettingsView.vue`（路由 `/settings`，侧边栏与用户菜单都可进）。
- **新增主题只需两处**：`theme/themes/<id>.ts` 写 18 个语义色（light + dark），在 `theme/themes/index.ts` 的数组里加一项。色阶（Element Plus 的 light-3/5/7/8/9）由 `color-mix` 自动派生。
- **兼容层**：`styles/index.css` 的旧 `--pa-*` 全部映射到 `--ma-*`，老页面不改代码即跟随主题。
- **验证**：`pnpm type-check` / `lint` / `test`（39 passed，主题相关 8 例）/ `build` 全绿；4 套主题 × 明暗 × 跟随系统的实测截图见 [`docs/design/README.md`](../design/README.md#主题系统2026-11-09-落地)。
- **跨设备同步（2026-11-10 补齐）**：`user_settings` 加 `theme_id` / `theme_mode`，接口 `GET|PUT /api/settings/appearance`；登录后拉一次（账号 > 本机），切换主题时本地立即生效、异步写回。设置 E2E 加了两条：「切换主题后写回账号」「清空本机缓存后主题从账号恢复」。
- **顺带修的坑**：外观与模型共用一行，最初导致「只改主题的新账号」被判成「已配置模型」而丢掉环境变量默认值 → 加 `model_configured` 列区分。

---

## T-FE-05 前端测试与质量基建（DONE 2026-11-09）

- **目标**：按本地 Vue 相关 Skill 补齐前端缺失的工具，让「组件行为」也能被自动化拦住。
- **新增**：`@vue/test-utils` + `happy-dom` + `@pinia/testing`（组件测试）、`@vitest/coverage-v8`（`pnpm test:coverage`）、`eslint-plugin-vuejs-accessibility`（a11y 静态检查）、`vite-plugin-vue-devtools`（开发期面板）。
- **不装**：`@vitest/eslint-plugin`（要求 TS ≥6，本项目 5.7）、Playwright（已有 puppeteer 验收脚本 + 组件测试）。
- **实体改动**：`vitest.config.ts`（vue 插件 + `src/test/setup.ts`）、`eslint.config.js`（a11y recommended + `coverage/**` 忽略）、`vite.config.ts`（devtools 插件）、`package.json`（`test:coverage`）、新增 3 个组件测试。
- **顺带修的 a11y 真问题**：`ModeSwitch` 的 label 未与 input 关联（补 `id`/`for`）；`ChatView` 会话列表项用 `div @click` → 改为内部 `<button>`，键盘可 Tab 可 Enter，`aria-current` 标记当前会话。
- **验证**：`pnpm test` **50 passed**（组件 11 例）；`pnpm type-check` / `lint` / `format:check` / `build` 全过；`pnpm acceptance:auth` 13/13、`acceptance:chat` 10/10；覆盖率可出报告（未设门槛）。
- **记录**：ADR-0002 追加「修订记录（2026-11-09）」，说明组件测试与覆盖率的加入理由与边界。

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

## 阶段 5 · Agent 执行循环（2026-11-10 已完成）

- **用户原话（m07755）**：「按 T1 → T7 顺序做吧。」设计见 [`../agent.md`](../agent.md)，决策见 [ADR-0010](../adr/0010-agent-execution-loop.md)。
- **T1 模型层**（`51bd80d`）：`LLMClient.chat_with_tools()`；Fake 支持剧本重放；OpenAI 兼容实现上送 `tools` + `tool_choice=auto`、原样带回 `tool_calls`。真实 DeepSeek 实测 `finish_reason: tool_calls`。
- **T2 两表**（`0dfe0eb`）：`agent_runs`（状态/步数/模型/起止时间）+ `agent_steps`（seq/kind/工具名/参数/ok/耗时），`(run_id,seq)` 唯一；迁移 `d8812afe7ea7`。
- **T3 工具层**（`f7360d8`）：`calculator`（ast 白名单，`^` 当幂）、`now`、`search_conversations`（按用户隔离）+ 注册表；未知工具返回 `ok=false` 而不是抛错。
- **T4 执行器**（`c79941d`）：8 步预算、单工具 2s、连续 3 次失败中止；每步先落库再推事件；断流时 `finally` 把 run 标 failed。
- **T5 接口**（`1f6d336`）：`POST /api/conversations/{id}/agent/stream`（SSE）+ `GET .../agent/runs`（回放），开流前的 404/400/409 仍是普通 JSON。
- **T6 前端**：`stores/chat.ts` 增 `agentMode`（持久化）/`agentSteps`/`sendWithAgent()`/`loadAgentRuns()`；`AgentTimeline.vue` 渲染过程；时间线插在**最后一条用户消息之后**，保证「问 → 过程 → 答」顺序。
- **T7 文档与 E2E**：`docs/api.md` §6、`docs/how-it-works.md` §4.5、`pnpm acceptance:agent` 10 项（含刷新回放、关掉开关走普通对话、后端运行记录）。
- **过程中修掉的真问题**：
  1. `assistant_text` 曾对「最终答复」也发一次，导致同内容出现两条步骤 → 改为「有 content 且有 tool_calls 才记 Thought」。
  2. `config_from_row` 只判「有没有行」，导致同步过主题的账号把 env 里的 DeepSeek 顶成 fake → 改判 `model_configured`。
  3. 会话标题曾取助手答复（侧栏出现「等于 **243**」）→ 改取用户原话。
  4. E2E 等 `.chat__row--assistant` 会命中流式占位气泡，reload 一掐就把未提交的流回滚掉 → 改为等「没有 `.chat__bubble--streaming` 且发送按钮不再 loading」。
