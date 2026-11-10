---
name: My Agent
description: 属于你一个人的 AI 助手：安静、可信、数据在你自己手里的对话应用。
colors:
  canvas: "#FAF8F4"
  surface: "#FFFFFF"
  surface-sunken: "#F3F0EA"
  ink: "#1C1B18"
  ink-muted: "#6B675E"
  ink-faint: "#9A958A"
  line: "#E5E0D6"
  line-strong: "#D2CCBE"
  pine: "#1F4D46"
  pine-deep: "#173A35"
  pine-soft: "#E7EFEC"
  amber: "#B4722A"
  amber-soft: "#FBF1E4"
  danger: "#A6352B"
  danger-soft: "#FBEAE7"
typography:
  display:
    fontFamily: '"Songti SC", "Noto Serif SC", Georgia, serif'
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.01em"
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0em"
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.75
    letterSpacing: "0.01em"
  small:
    fontFamily: '-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0.01em"
  mono:
    fontFamily: '"SF Mono", ui-monospace, Menlo, Consolas, monospace'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "0em"
rounded:
  sm: "6px"
  md: "10px"
  lg: "14px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.pine}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "0 18px"
    height: "40px"
  button-primary-hover:
    backgroundColor: "{colors.pine-deep}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 14px"
    height: "36px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "0 12px"
    height: "40px"
  sidebar:
    backgroundColor: "{colors.surface-sunken}"
    textColor: "{colors.ink}"
    width: "264px"
  bubble-user:
    backgroundColor: "{colors.pine}"
    textColor: "#FFFFFF"
    rounded: "{rounded.lg}"
    padding: "12px 16px"
  bubble-assistant:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "16px 20px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "20px 24px"
---

## Overview

My Agent 是一个**个人** AI 助手。界面要让人放松：暖白纸面、墨色文字、一个深松绿作为唯一强调色。视觉主语永远是**内容**（对话与设置项），外壳尽量退到背景里。

三条设计立场：

1. **安静优先**：没有渐变、没有装饰性插图、没有大面积色块。颜色只用来区分层级和标示状态。
2. **可信优先**：危险操作（清空、注销、撤销设备）用暖红并配二次确认；成功用松绿，失败用暖红，绝不用「绿色对勾」掩盖失败。
3. **一屏一件事**：对话页只做对话，设置页只做设置，登录页只做登录。

## Colors

| Token | 值 | 用途 |
|---|---|---|
| `canvas` | `#FAF8F4` | 页面底色（暖白纸），比纯白柔和，长时间阅读不刺眼 |
| `surface` | `#FFFFFF` | 卡片、输入框、助手气泡 |
| `surface-sunken` | `#F3F0EA` | 侧边栏、代码块底、分组背景 |
| `ink` | `#1C1B18` | 正文，不用纯黑 |
| `ink-muted` | `#6B675E` | 次要说明、时间戳、占位符 |
| `ink-faint` | `#9A958A` | 只用于非必要装饰文字（分隔符、禁用态） |
| `line` | `#E5E0D6` | 1px 分隔线、卡片描边 |
| `pine` / `pine-deep` / `pine-soft` | `#1F4D46` / `#173A35` / `#E7EFEC` | 主操作、选中态、用户气泡、焦点环 |
| `amber` / `amber-soft` | `#B4722A` / `#FBF1E4` | 提醒（未保存、待配置、用量接近上限） |
| `danger` / `danger-soft` | `#A6352B` / `#FBEAE7` | 破坏性操作、错误信息 |

规则：

- 强调色每屏**最多出现两处**（一个主按钮 + 一个选中态）。多了就退化成仪表盘。
- 正文不用 `ink-faint`，对比度不足 4.5:1。
- 状态不只靠颜色：上架/下架、成功/失败都要有文字，颜色只是强化。

## Typography

- **显示级**（登录页标题、空态大标题）用衬线 `Songti SC / Georgia`，28px/1.3，字距 +0.01em。整站只有登录页与空态使用衬线，其余一律无衬线。
- **正文** 15px / 1.75：中文长段落最舒服的行高；对话气泡、设置项说明都用这一档。
- **小字** 13px / 1.5：时间戳、字段说明、按钮内次要文案。
- **等宽** 13px：代码块、API Key 末四位、版本号。
- 中文与英文/数字混排时保留 `0.01em` 字距，避免挤在一起。
- 数字列（用量、时间）用 `font-variant-numeric: tabular-nums` 对齐。

## Layout

- 外壳：左侧栏 **264px**（`surface-sunken`，1px 右边线）+ 主区（`canvas`），主区最大内容宽 **1080px**，超出居中留白。
- 对话页：消息列最大宽 **720px** 居中；用户气泡右对齐、助手气泡左对齐且无气泡尾巴。
- 登录/注册：单列卡片 **400px**，垂直居中偏上（距顶部 12vh），背景只用 `canvas`。
- 设置页：左侧二级导航 **200px**（模型 / 账号 / 设备 / 外观 / 数据 / 关于）+ 右侧表单区，表单最大宽 **560px**。
- 间距节奏用 8pt：`4 / 8 / 16 / 24 / 32 / 48`。区块之间 32，字段之间 24，标签与控件之间 8。
- 断点：`≥1280` 三栏（侧栏 + 内容 + 可选的上下文栏）；`960–1279` 隐藏侧栏改用顶部下拉；`<960` 单列，移动端只保证「不横向滚动、能读能发」。

## Elevation & Depth

- 只有两级：`canvas` 上的 `surface` 卡片（1px `line` 描边 + `0 1px 2px rgba(28,27,24,.04)`）与浮层（弹窗、下拉，`0 8px 24px rgba(28,27,24,.10)`）。
- 不用大阴影堆叠，不用玻璃拟态。
- 焦点态用 3px `pine-soft` 外环 + 1px `pine` 内描边，替代 `outline: none`。

## Shapes

- 圆角：输入框与按钮 6px，卡片 10px，气泡 14px，状态点与头像用 pill。
- 描边一律 1px，颜色 `line`；hover 提到 `line-strong`。
- 图标用 Element Plus 线性图标，20px，线宽随组件；不自绘插画。

## Components

- **按钮**：主按钮深松绿实底（40px 高）；次按钮白底 1px 描边；文字按钮只用于行内操（撤销、重命名）。同一行最多一个主按钮。
- **输入框**：40px 高，白底，聚焦时描边变 `pine` + 外环；错误态描边 `danger` 并在下方 8px 处给 13px 红字说明原因。
- **侧边栏会话项**：两行——标题（15px，最多 1 行省略）+ 元信息（13px `ink-muted`，「N 条 · 时间」）。选中态底色 `pine-soft` + 左侧 3px `pine` 竖条，不用整块反白。
- **消息气泡**：用户气泡右对齐（`pine` 底白字，最多 80% 宽）；助手气泡左对齐（白底、1px 描边），支持 Markdown 的 h1–h4、列表、代码块（`surface-sunken` 底 + 等宽 13px）、表格、引用。
- **状态胶囊**：`pine-soft` 底 + `pine` 字（成功/在线）、`amber-soft` + `amber`（待配置）、`danger-soft` + `danger`（失败）。前后各 6px 内边距，圆角 pill。
- **空态**：居中、最多 3 行文案（一句标题 + 一句解释 + 一个主操作），不放大插图。
- **危险区**（设置页底部）：`danger-soft` 底卡片，写明「删除后无法恢复」，操作按钮为红色描边按钮，点击后弹二次确认，需输入会话数量或账号邮箱才能确认。

## 结构约定：多用 div、少嵌套（2026-11-11 修订）

1. **容器用 `div`，只有行内文字用 `span`**；不要为了挂一个 class 而多包一层。
2. 组件模板从根到叶子**不超过 4 层**；超过就说明有可合并的包装层。
3. 布局容器不要用 `section`/`article` 这类语义标签「撑门面」——语义标签只在表达文档结构时使用。
4. 需要 `div` 承担按钮行为时，补 `role="button"` + `tabindex="0"` + Enter/Space 键盘处理。
5. `Teleport`、`Transition`、`template v-for` 等框架必需结构不计入层数。

## 交互反馈：hover 用渐变，不用整块灰（2026-11-11 修订）

悬停反馈是「有质感」和「像 Bootstrap 默认样式」的分界线。统一规则：

1. **凡是可点的东西，hover 都用横向渐变**：`linear-gradient(90deg, ink 7%, ink 3%)`（`ink` 即 `--ma-color-ink`）。方向固定从左到右，不要有的从上到下。
2. **按下（`:active`）加深一档**：`12% → 7%`；选中态（`is-active`）与按下同档。
3. **覆盖范围**：按钮、图标按钮、列表项（会话项、设备项、设置导航）、菜单项、用户区。项目里已经这样实现，新增交互元素照抄。
4. **危险动作**用红色渐变：`danger 10% → 4%`，不要只改文字颜色。
5. **选中态优先**：元素已经是选中色时，hover 保持选中色，不要再叠一层灰（否则看起来像被取消选中）。
6. **不用整块纯色 hover**（`background: #f5f5f5` 这类）——它会让界面显得廉价，也让深浅色主题下更难调。
7. **过渡时间 150ms**、只过渡 `background` 与 `color`，不做位移、放大、阴影跳动。

## 边界规则：不要轻易加分割线（2026-11-11 修订）

这条是硬规则，评审时按它执行：

1. **大板块里的小模块之间不加分割线**。默认用间距（24 / 32px）分隔；需要更强的分组感时，用底色差异或一层很淡的阴影，而不是画线。
2. **按钮、输入框、卡片、菜单、弹窗**这些「有体积」的组件用**阴影**表达边界与抬升，不用 1px 描边（`--ma-shadow-soft` / `--ma-shadow-float`）。
3. 只在三种情况下允许线条：
   - **内容语义本身需要**：Markdown 的表格、引用块（阅读区里的排版元素，不是布局切分）。
   - **状态提示**：输入框聚焦时的 1px 强调色描边 + 3px 外环。
   - **可访问性**：`prefers-contrast` 或极低对比度屏幕上，阴影不足以区分时，可退化为一层 `--ma-color-line-soft`。
4. 列表项之间**不用横线**：靠行高、hover 底色与圆角分组表达；选中态只用底色（不加左侧竖条）。
5. 已经存在但不再必要的分割线，看到就顺手删掉——它通常是「不敢用留白」的痕迹。

## Do's and Don'ts

- ✅ 一屏只有一个主按钮；❌ 同一行并排两个实底按钮。
- ✅ hover 用 7%→3% 的横向渐变；❌ 用整块纯色灰、位移或放大做悬停反馈。
- ✅ 用留白与层级（字号 / 字重 / 底色 / 阴影）分隔区块；❌ 用分割线或彩色背景块切分。
- ✅ 长内容（对话、代码）保持 720px 阅读宽；❌ 把文本拉满 1440px。
- ✅ 危险操作用暖红 + 文案说清后果；❌ 用灰色小字弱化「删除全部」。
- ✅ 加载中显示骨架或「正在回复…」；❌ 用乐观更新假装成功。
- ✅ 中文术语固定：会话 / 消息 / 模型 / 设备；❌ 混用「聊天记录」「机器人」「终端」。
