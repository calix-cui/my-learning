# ADR-0002：前端质量门禁采用「轻量档」

> **AI 向文档**：架构决策记录，人与 AI 共读；每条决策的「为什么」是重点。总入口见 [`../README.md`](../README.md)。

- **状态**：已接受（Accepted）
- **日期**：2026-11-06
- **决策人**：项目 owner（用户）
- **影响范围**：前端 lint / 格式化 / 单测 / CI 的严格程度

## 背景

阶段 1 发现前后端质量门禁严重不对称：后端有 ruff + pytest(23) + pre-commit + CI，前端**零 lint、零单测、CI 不覆盖**（见 `TECHNICAL_DEBT.md` T-02/T-03）。

调研推荐的「完整档」是：ESLint 10 flat + typescript-eslint（含 **type-aware 规则**）+ vue 插件 + Prettier + Vitest（含覆盖率门槛）+ Playwright（替换自研 E2E 脚本）+ 前端 CI job 全量阻断。

项目 owner 的判断：**完整档对单人维护的学习项目负担过重**，会让「加一个字段」变成「改三处配置」；但完全不设门禁又会持续产生新的前端债。

## 决策

前端质量门禁采用**轻量档**，只拦住"明显错误"，不追求"风格统一 + 全覆盖"。

| 能力 | 采用 | 不采用 | 原因 |
|---|---|---|---|
| ESLint | `eslint:recommended` + `plugin:vue/vue3-essential` + `typescript-eslint` 的 `recommended`（**非 type-aware**） | type-aware 规则集、`strict-type-checked` | type-aware 要配 `projectService`，慢且误报多；类型正确性由 `vue-tsc --noEmit` 兜底 |
| Prettier | 采用，配置极简（默认 + 100 列） | 进 CI 阻断 | 格式化是「保存时/需要时」的事，不该卡提交 |
| Vitest | 只覆盖 `src/api`、`src/utils` 等**纯逻辑** | 组件快照、覆盖率门槛 | 组件测试维护成本高、收益低；逻辑层才是 bug 源 |
| Playwright | **暂缓**，继续用 `scripts/acceptance.mjs`（18 项） | 现在替换 | 现有脚本能跑通；E2E 用例 < 30 条时自研脚本成本更低 |
| CI 前端 job | `pnpm build`（含 `vue-tsc`）+ `pnpm lint` | 覆盖率门槛、format check | 只挡「构建不过」和「明显写错」 |

**红线（这四条仍然阻断）**：
1. `pnpm build` 失败（含类型错误）。
2. ESLint 报 error 级问题（未定义变量、重复声明、无效指令等）。
3. 引入未声明依赖。
4. E2E 验收脚本从 18 项退化为通过项减少。

## 理由

1. **门禁的价值 = 拦住的 bug / 增加的摩擦**。type-aware lint 与覆盖率门槛在单人项目里摩擦 > 收益。
2. **类型检查已经兜住大部分低级错误**：`vue-tsc --noEmit` 本来就在 build 里。
3. **可持续**：能长期开着的门禁才是门禁；设了就跑不动、最后被注释掉的规则等于没有。

## 接受的成本

- 会有**风格漂移**（不同文件格式略有差异）——由 Prettier 手动执行收敛，不强制。
- **部分类型安全问题不会被 lint 捕获**（如 `any` 泛滥）——依靠后端契约 + review 兜底。
- 前端**没有回归网**（无单测覆盖组件）——靠 18 项 E2E + 人工验收。

## 升级触发条件

出现以下任一情况时，重新评估是否升到完整档：

- 前端代码超过 ~8000 行，或组件数 > 40。
- 出现「改一处、坏一片」且 E2E 没拦住的事故 ≥ 2 次。
- E2E 用例数 > 30（此时 Playwright 的 runner/trace 收益开始大于迁移成本）。
- 有第二个人参与前端开发（风格统一开始有协作价值）。

## 落地记录（2026-11-07）

| 组成 | 实际版本 / 位置 |
| --- | --- |
| ESLint | `eslint@10.14.0`（flat config，`frontend/eslint.config.js`） |
| 插件 | `@eslint/js@10.0.1`、`typescript-eslint@8.72.1`、`eslint-plugin-vue@10.12.0`（`flat/essential`）、`eslint-config-prettier@10.1.8`（放最后） |
| 其余 | `prettier@3.9.10` + `.prettierrc.json` / `.prettierignore`、`globals@17.14.0`（浏览器与 Node 全局） |
| 脚本 | `pnpm lint` / `lint:fix` / `format` / `format:check` |
| CI | `.github/workflows/ci.yml` 的 `frontend` job：`pnpm install --frozen-lockfile` → `pnpm build` → `pnpm lint`（Node 22 + pnpm 12.10.1） |

规则口径：`@eslint/js` recommended + `typescript-eslint` recommended + `vue` flat/essential，**未启用** type-aware 规则（不设 `projectService`）；仅额外调整两条——`@typescript-eslint/no-unused-vars` 允许 `_` 前缀、关闭 `vue/multi-word-component-names`（视图均已是多词名，规则无收益）。

首次接入的实际产出：存量代码只报出 2 个 error（`scripts/acceptance.mjs` 的未使用 `os` 导入与循环变量），修掉后全绿；另有 6 个文件存在格式漂移，已用 `pnpm format` 一次性收敛为独立提交，便于 review。

门禁有效性实测（break-glass）：临时写入未使用变量（`.ts` 与 `<script setup>` 各一处）+ 缺失 `v-for` key 的模板，`pnpm lint` 报 3 个 error 且退出码 1；删除临时文件后恢复 `exit=0`。

未做（按本 ADR 的「暂缓」）：Vitest 单测、Playwright、覆盖率门槛、Prettier 参与 CI。

### 修订记录（2026-11-09）

原表里「Vitest 只测 `src/api` 与 `src/utils`」的边界已随实践扩大——原因不是想加门槛，而是出现了**只有组件测试能拦**的错误（`storeToRefs` 解构丢状态导致主题格子全空，纯逻辑测试完全看不见）。本次只加能力，不放宽红线：

| 项 | 变化 | 取舍 |
| --- | --- | --- |
| 组件测试 | 引入 `@vue/test-utils@2.5.1` + `happy-dom@21.0.4` + `@pinia/testing@2.0.2`，新增 11 例（`ThemeCard` / `ModeSwitch` / `AppearancePanel`） | 默认环境仍是 `node`；组件测试按文件切 `happy-dom`，不影响纯逻辑测试速度（全量 50 例 ~1s） |
| 覆盖率 | 引入 `@vitest/coverage-v8@3.2.7`，`pnpm test:coverage` 出报告 | **仍不设门槛**，也不进 CI——`src/views` 覆盖率为 0 属预期，页面流程由 E2E 兜底 |
| 无障碍 | `eslint-plugin-vuejs-accessibility` recommended | 首次接入报出 3 个真实问题（label 未关联、会话项用 div 承载点击），已修；不引入运行时 a11y 测试框架 |
| 调试 | `vite-plugin-vue-devtools` | 仅开发期注入，`build` 产物不含 |
| 掉队项 | `@vitest/eslint-plugin@1.6.28` 要求 `typescript>=6`，本项目 TS 5.7 | 不装；等升 TS 6 时再补 |

Playwright 仍然暂缓：现有 `puppeteer-core` 验收脚本 + 组件测试已覆盖当前风险，引入第二套 E2E 框架只会增加维护面。
