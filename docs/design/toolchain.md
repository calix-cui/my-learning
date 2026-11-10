# 设计工具链：impeccable + taste-skill

> 这份文档回答三个问题：设计规范是怎么产出的、以后改设计该跑哪条命令、为什么没用 `design-taste-frontend` 主导 App 界面。
> 规范正文在根目录 [`DESIGN.md`](../../DESIGN.md)，产品上下文在 [`PRODUCT.md`](../../PRODUCT.md)。

## 一句话结论

**App 界面用 `impeccable` 的 Operate 模式主导；`design-taste-frontend`（tasteskill）只借它的排版、间距、动效与文案细则，不用它做页面骨架。**

## 两个工具的实际差异（实测，不是听介绍）

| 维度 | `impeccable` v4.8.1 | `design-taste-frontend` 2.5.1 |
|---|---|---|
| 定位 | 设计工程：产品 UI、仪表盘、表单、空/错/载三态、可访问性 | 营销站/落地页生成器 |
| 四种模式 | `Persuade` / `Operate` / `Read` / `Experience`，本项目的 App 界面属 **Operate** | 单一取向：叙事 + 视觉冲击 |
| 硬约束 | 以「可用性优先」为判据，会给对照度、焦点态、目标尺寸的具体数字 | 九条铁律含「每屏一个 section」「hero 独占首屏」「每屏 60–80 词」「必须有真实照片」——套到后台会挤压信息密度 |
| 产物 | `PRODUCT.md`（产品上下文）+ `DESIGN.md`（token + 组件规格） | 页面级视觉方向，不含 token 体系 |
| 命令 | `init` / `document` / `shape` / `critique` / `audit` / `polish` / `harden` | 按页面生成 |

> **一条容易踩的坑**：官网 `tasteskill.dev/guide` 提到「App 屏幕走 `references/app-screens.md`」，
> 但本地 2.5.1 **没有这个文件**，上游 `skills/taste-skill/references/` 的 20 个文件里也没有（用 GitHub API 列过清单）。
> 也就是说这条路线目前只是文档预告，不能作为方案依据。

## 我们怎么用它（可复现流程）

```bash
# 0. 先看上下文：缺什么它自己会说
impeccable context
#   → NO_PRODUCT_MD / PRODUCT_INIT_REQUIRED：先去写 PRODUCT.md

# 1. 产品上下文（一次性，之后随功能演进更新）
#    走 reference/init.md 的访谈：平台、技术栈、用户、定位、运行场景、约束、品牌承诺
open ~/.agents/skills/impeccable/reference/init.md

# 2. 设计体系（一次性）
#    → 产出 DESIGN.md：YAML token + 组件规格 + do/don't
impeccable document

# 3. 单个界面成形 / 改版
impeccable shape        # 先定信息层级、布局、状态，再写代码

# 4. 评审与打磨（改完之后）
impeccable critique     # 结构化批评：层级、对比、密度、文案
impeccable audit        # 可访问性/一致性检查
impeccable polish       # 收尾：间距、对齐、微交互
impeccable harden       # 边界：空数据、超长文本、极窄视口
```

检测器命令行（收尾前跑）：`impeccable detect --json <改动的文件或目录>`，它会给可机读的问题清单；本机图片相关工具只有 `sips`（`imagemagick` 未装）。

## 仓库里该提交什么

| 文件 | 内容 | 为什么提交 |
|---|---|---|
| `PRODUCT.md` | 产品上下文（谁用、解决什么、硬约束） | 它是所有设计判断的前提，改需求要先改它 |
| `DESIGN.md` | token（颜色/字号/间距/圆角）+ 组件规格 + do/don't | 实现的唯一视觉事实来源 |
| `docs/design/mockups/*.html` | 5 张自包含静态稿（1440×900） | 评审与对齐用，不依赖构建 |
| `docs/design/README.md` | 设计索引、实现状态、截图与复现命令 | 人和 AI 的入口 |
| `docs/design/toolchain.md` | 本文档 | 让下一个人知道为什么这么选、怎么重跑 |

`.impeccable/`（工具的工作目录）目前**没有**纳入版本库：它存的是工具自己的缓存与检测快照，不是设计事实。若以后需要固定检测基线，再单独提交 `.impeccable/config.json`。

## 什么时候要重跑

- **新增页面**：先 `shape`，再写 `docs/design/mockups/` 的同款静态稿，最后实现。
- **改 token（配色/字号/间距）**：改 `DESIGN.md` 与 `frontend/src/theme/themes/*`，两处必须同步；主题系统的增改见 [`docs/design/README.md`](README.md#主题系统2026-11-09-落地)。
- **加组件**：先看 `DESIGN.md` 的「Components」节有没有覆盖；没有就补规范，再写 `frontend/src/components/`。
- **交付前**：`critique` + `audit` + `impeccable detect`，三者的问题都处理完再提。

## 不采用的方案

| 方案 | 否决理由 |
|---|---|
| 用 `design-taste-frontend` 主导全部页面 | 它的九条铁律（hero 独占首屏、每屏一 section、必须真实照片）与「后台信息密度优先」直接冲突 |
| 两套规范叠加使用 | 两者对「首屏该放多少信息」的判断相反，叠加只会让实现左右摇摆；官网自己也提醒不要叠多套重叠指令 |
| 只靠 `DESIGN.md` 不落静态稿 | 评审时没人愿意读 token 表；5 张 1440×900 静态稿是最低成本的共识载体 |
| 引入第二套 UI 库来「更像设计稿」 | Element Plus 已覆盖所需组件，第二套会让包体和样式冲突同时翻倍（见 `DESIGN.md` 的约束） |
