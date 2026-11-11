---
name: My Agent
description: 属于你一个人的 AI 助手。安静、可信、数据在你自己手里。
colors:
  canvas: "#faf8f4"
  surface: "#ffffff"
  sunken: "#f3f0ea"
  ink: "#1c1b18"
  muted: "#6b675e"
  faint: "#9a958a"
  line: "#e5e0d6"
  line-strong: "#d2ccbe"
  accent: "#1f4d46"
  accent-hover: "#173a35"
  accent-soft: "#e7efec"
  on-accent: "#ffffff"
  success: "#1a7f63"
  success-soft: "#e6f4f0"
  warn: "#a3651f"
  warn-soft: "#fbf1e4"
  danger: "#a6352b"
  danger-soft: "#fbeae7"
typography:
  display:
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  h1:
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-0.01em"
  h2:
    fontSize: "18px"
    fontWeight: 600
    lineHeight: 1.5
  h3:
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.6
  body:
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.75
    letterSpacing: "0.01em"
  caption:
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  mono:
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.6
rounded:
  sm: "8px"
  md: "12px"
  lg: "18px"
  xl: "26px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "6px"
  md: "10px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.md}"
    height: "40px"
    padding: "0 18px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "40px"
    padding: "0 16px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    height: "40px"
    padding: "0 12px"
  composer:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.xl}"
    padding: "14px 16px 12px"
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "24px"
  sidebar:
    backgroundColor: "{colors.canvas}"
    width: "264px"
---

# My Agent 设计规范

> 这份文档是**唯一**的视觉规则来源。做新页面、改组件、调颜色之前先读它；改完 UI 要把改动**回写**进来（见 §9）。

## 0. 怎么用

1. **写页面前**：读 §2–§5，把要用的颜色、字号、间距、圆角先定下来，再动 `<style>`。
2. **写样式时**：只用 `var(--ma-*)` 变量，不写死十六进制、不写魔法数字（有例外要在这里补一条规则）。
3. **交付前**：过一遍 §10 自查清单。
4. **改完 UI**：同一个提交里更新本文档——新增组件补 §5，改尺寸改对应表格。

三个必须记住的硬规则（详见 §8）：**不要随便加分割线**、**hover 用横向渐变**、**结构多用 div、嵌套 ≤4 层**。

## 1. 设计立场

1. **安静优先**：没有渐变背景、没有装饰插图、没有大面积色块。颜色只用来区分层级和标记状态。
2. **可信优先**：危险操作用暖红 + 说清后果 + 二次确认；失败就显示失败，不用绿色掩盖。
3. **一屏一件事**：对话页只做对话，设置页只做设置，登录页只做登录。内容永远比外壳显眼。

## 2. 配色

### 2.1 语义色 token（组件只准用这些名字）

CSS 变量一律是 `--ma-color-<token>`，值来自 `frontend/src/theme/themes/*.ts`。下表是默认主题**松林 · 浅色**的取值。

| Token | 变量 | 松林·浅色 | 用途 |
|---|---|---|---|
| `canvas` | `--ma-color-canvas` | `#faf8f4` | 页面底色（暖白纸） |
| `surface` | `--ma-color-surface` | `#ffffff` | 卡片、输入框、浮层、助手消息区 |
| `sunken` | `--ma-color-sunken` | `#f3f0ea` | 代码块、分组背景、次要区域 |
| `ink` | `--ma-color-ink` | `#1c1b18` | 正文、标题（不用纯黑） |
| `muted` | `--ma-color-muted` | `#6b675e` | 次要说明、时间戳、占位符 |
| `faint` | `--ma-color-faint` | `#9a958a` | 装饰性文字（分隔符、禁用态），不用于正文 |
| `line` | `--ma-color-line` | `#e5e0d6` | 极少数需要的 1px 线（见 §8.1） |
| `line-strong` | `--ma-color-line-strong` | `#d2ccbe` | hover 时的线、滚动条 |
| `accent` | `--ma-color-accent` | `#1f4d46` | **主色**：主按钮、选中态、用户气泡、焦点环 |
| `accent-hover` | `--ma-color-accent-hover` | `#173a35` | 主色按下 / 深一档 |
| `accent-soft` | `--ma-color-accent-soft` | `#e7efec` | 选中底色、用户气泡浅底 |
| `on-accent` | `--ma-color-on-accent` | `#ffffff` | 主色之上的文字 |
| `success` / `success-soft` | `--ma-color-success(-soft)` | `#1a7f63` / `#e6f4f0` | 成功、运行中 |
| `warn` / `warn-soft` | `--ma-color-warn(-soft)` | `#a3651f` / `#fbf1e4` | 待确认、待配置、预算接近上限 |
| `danger` / `danger-soft` | `--ma-color-danger(-soft)` | `#a6352b` / `#fbeae7` | 破坏性操作、错误 |

### 2.2 四套主题的主色

主题只换颜色，不换布局、字号、圆角。切换入口在设置 → 外观，深浅模式单独选（浅色 / 深色 / 跟随系统）。

| 主题 | id | 浅色主色 | 深色主色 | 浅色底色 | 深色底色 | 气质 |
|---|---|---|---|---|---|---|
| 松林（默认） | `pine` | `#1f4d46` | `#74c3ae` | `#faf8f4` | `#141715` | 暖白纸 + 深松绿，最安静 |
| 暖砂 | `sand` | `#8f4b2a` | `#d99272` | `#fbf6ec` | `#171310` | 米黄纸 + 陶土棕，暖 |
| 靛蓝 | `indigo` | `#2f3f86` | `#93a4ee` | `#f7f8fb` | `#101318` | 冷灰纸 + 深靛蓝，工具感 |
| 石墨 | `graphite` | `#3f4650` | `#b8bec9` | `#f7f7f8` | `#121213` | 几乎无色相，最不打扰 |

> 新增主题只需在 `frontend/src/theme/themes/` 加一个文件并注册；**任何组件都不许写死颜色**，否则换主题就破。

### 2.3 配色规则

1. **一屏最多两处强调色**：一个主按钮 + 一个选中态。第三处开始就变成仪表盘。
2. **状态不能只靠颜色**：成功/失败/待确认都要有文字，颜色只是加强。
3. **深浅两套必须同时给**：18 个 token 缺一个就会在深色下出现「透明洞」。
4. **正文对比度 ≥ 4.5:1**：`faint` 不能用来写正文或按钮文字。
5. **危险动作**用 `danger` 系，且必须配文案说明后果，禁止只把字变红。

## 3. 字体

### 3.1 字族

| 用途 | 字体栈 | 变量 |
|---|---|---|
| 正文 / UI / 标题 | `-apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif` | `--ma-font-sans` |
| 代码 / 数字标识 | `"SF Mono", ui-monospace, Menlo, Consolas, monospace` | `--ma-font-mono` |

**全站只有一个字族**（无衬线）。层级靠字号、字重、行高区分；不再引衬线体，也不用全大写做层级。

### 3.2 字号阶梯

| 层级 | 字号 | 字重 | 行高 | 字距 | 用在哪 |
|---|---|---|---|---|---|
| `display` | 28px | 600 | 1.3 | `-0.02em` | 登录/注册标题、空态大标题 |
| `h1` | 24px | 600 | 1.35 | `-0.01em` | 页面主标题（登录卡片标题、设置标题） |
| `h2` | 18px | 600 | 1.5 | 0 | 区块标题（「执行过程」、设置分组名） |
| `h3` | 15px | 600 | 1.6 | 0 | 列表项标题、字段组标题 |
| `body` | 15px | 400 | 1.75 | `0.01em` | 正文、消息、表单值、说明文字 |
| `body-strong` | 15px | 500 | 1.75 | `0.01em` | 按钮文字、会话标题、强调短语 |
| `caption` | 13px | 400 | 1.5 | `0.01em` | 时间戳、辅助说明、字数统计 |
| `micro` | 12px | 400 | 1.5 | 0 | 极次要标签（模型名、状态后缀） |
| `mono` | 13px | 400 | 1.6 | 0 | 代码块、工具参数、API Key 末四位 |

规则：

1. 一屏最多 **4 个字号层级**；同一层级内不要靠「12px vs 13px」制造差异，用颜色/字重。
2. 消息正文 15px/1.75；Markdown 渲染后的段落间距 12px，标题上下留 16/8px。
3. 数字列（时间、计数、用量）加 `font-variant-numeric: tabular-nums`（已有 `.tabular` 类）。
4. 中英混排保留 `0.01em` 字距；纯数字/代码不加。
5. 行宽上限 `--ma-reading-width`（720px），超过就换行，不拉满窗口。

## 4. 间距与布局

### 4.1 间距阶梯（8pt 为主，允许 6/10 做视觉微调）

| 变量 | 值 | 典型用途 |
|---|---|---|
| `--ma-space-xs` | 6px | 图标与文字、徽标内边距 |
| `--ma-space-sm` | 10px | 列表项内边距、标签与控件 |
| `--ma-space-md` | 16px | 卡片内边距、按钮组水平间距 |
| `--ma-space-lg` | 24px | 卡片之间、表单字段之间 |
| `--ma-space-xl` | 32px | 页面区块之间、页面上下留白 |
| 48px | — | 登录页顶部留白、空态上下呼吸 |

### 4.2 骨架尺寸

| 元素 | 尺寸 | 说明 |
|---|---|---|
| 侧边栏 | 264px | `--ma-sidebar-width`，底色 `canvas` |
| 内容区 | 1080px | `--ma-content-width`，超出居中 |
| 对话阅读列 | 720px | `--ma-reading-width`，消息与输入盒同宽 |
| 设置二级导航 | 208px | 悬浮窗内部的左栏 |
| 设置表单区 | 560px | 字段最大宽，右侧留白 |
| 设置悬浮窗 | `min(920px, 100%)` | 圆角 26，`--ma-shadow-float` |
| 登录卡片 | 400px | 距顶 12vh，垂直居中 |
| 输入盒 | 阅读列宽 | 圆角 26，最小高 48 |

### 4.3 场景间距

| 场景 | 间距 |
|---|---|
| 页面左右留白 | 32px（内容区 > 1200 时可到 40px） |
| 区块（section）之间 | 32px |
| 卡片之间 | 24px |
| 表单字段之间 | 24px（紧凑模式 16px） |
| 标签与控件之间 | 8px |
| 按钮之间 | 12px |
| 消息之间 | 28px（同一提问的步骤卡与回答之间 12px） |
| 侧栏顶部（品牌/新建按钮） | 18–20px 内边距 |

### 4.4 圆角

| 变量 | 值 | 用在哪 |
|---|---|---|
| `--ma-radius-sm` | 8px | 小标签、内嵌块、代码行内 |
| `--ma-radius-md` | 12px | **按钮、输入框、列表项、菜单项**（默认档） |
| `--ma-radius-lg` | 18px | 卡片、消息气泡、步骤卡 |
| `--ma-radius-xl` | 26px | 浮层/弹窗、对话输入盒、大容器 |
| `pill` | 999px | 状态胶囊、头像、圆形图标按钮、次要按钮 |

规则：同一层级里圆角不要混（卡片 18 里别嵌 26 的块）；嵌套时内层圆角 = 外层 − 内边距，最小 8。

### 4.5 断点

| 宽度 | 布局 |
|---|---|
| ≥1280px | 侧栏 + 内容区（+ 可选右栏） |
| 960–1279px | 侧栏可收起；内容区占满 |
| <960px | 单列；只保证「不横向滚动、能读能发」 |

## 5. 组件规范

### 5.1 按钮

| 类型 | 高度 | 圆角 | 底色 | 文字 | 用法 |
|---|---|---|---|---|---|
| 主按钮 | 40px | 12px | `accent` | `on-accent` | 每屏最多一个（发送、保存、批准执行） |
| 次按钮 | 40px | pill | `surface` + 10% 阴影 | `ink` | 取消、重命名、次要动作（`SoftButton`） |
| 描边按钮 | 32–36px | 12px | 透明 + 1px `line-strong` | `ink` | 表格行内、弹窗底部 |
| 文字按钮 | — | — | 透明 | `accent` | 行内操作（改名、查看全部） |
| 危险按钮 | 40px | 12px | `danger` | `on-accent` | 删除/注销，必须配二次确认 |
| 图标按钮 | 32–36px | pill | 透明 | `muted` | 工具栏、消息操作 |

状态：

- hover：横向渐变 `linear-gradient(90deg, ink 7%, ink 3%)`，用 `.u-tint` 实现 0.15s 淡入（§8.2）；实底按钮改为 `accent-hover`。
- active / 选中：加深一档（12% → 7%）。
- disabled：`opacity .45` + `cursor: not-allowed`，不做灰底变色。
- 主按钮内 padding `0 18px`，图标与文字 gap 6px，字号 14–15px / 500。

### 5.2 输入类

- 单行输入：高 40px，圆角 12，白底 `surface`，`padding 0 12px`，字号 15。
- 聚焦：1px `accent` 描边 + 3px `accent-soft` 外环（不用 `outline: none` 裸奔）。
- 错误：1px `danger` 描边，下方 8px 处 13px `danger` 说明原因。
- 多行输入盒（对话）：圆角 26，`padding 14px 16px 12px`，`--ma-shadow-soft`，聚焦升为 `--ma-shadow-float`；`textarea` 高度自适应 48–200px，不显示 resize 手柄。
- 开关 / 单选 / 下拉：统一 40px 行高，标签在左、控件在右，间距 16。
- **表单内的紧凑输入**（设置页的就地表单）：高 34，圆角 10，`canvas` 底、无边框，聚焦时才出现 1px `accent` 描边；字段标签 12px `muted`，与控件间距 6。

### 5.3 卡片与面板

- 圆角 18，`surface` 底，`padding 24`，**不加边框**，用 `--ma-shadow-soft` 或少一层底色区分。
- 悬浮面板/弹窗：圆角 26，`--ma-shadow-float`，遮罩 `rgb(0 0 0 / 28%)`。
- 卡片内部分组：用 24px 间距或 `sunken` 底块，**不画分割线**。

### 5.4 导航

- **侧边栏**：264px，底色 `canvas`（与内容区同色，不靠线分隔），内部 padding 18–20。
- **会话项**：高 44–48，圆角 12，padding `10px`；标题 14px/500 单行省略；hover 横向渐变；选中 `accent-soft` 底（不加左侧竖条）；右侧「…」按钮仅 hover/选中时出现。
- **设置二级导航**：208px，项高 40，圆角 12，padding `10px 12px`，14px；选中 `accent-soft` 底。
- **对话工具条**：内容区顶部一行，`padding 14px 32px 6px`，标题 16/600 单行省略，右侧模型胶囊 + 图标按钮；不加底边框，靠留白分隔。

### 5.5 菜单与弹窗

- 下拉菜单：`--ma-shadow-float` + 圆角 18，面板 padding 6，项高 40、圆角 12、字号 14，危险项文字 `danger`。
- 菜单必须能键盘操作（↑↓ 移动、Enter 选中、Esc 关闭），点击外部关闭。
- 确认弹窗：宽 `min(420px, 90vw)`，圆角 18，标题 18/600，正文 15/1.7，按钮右对齐，主按钮在最右。
- 遵循「浮层贴触发器、下方放不下就翻到上方」的定位规则。

### 5.6 消息与输入

- 用户消息：右对齐，`accent-soft` 底，`ink` 字，最大宽 78%，圆角 18（右下角可小一档 8）。
- 助手消息：左对齐，**不用气泡**，直接排在 `canvas` 上，15px/1.8；步骤卡与正文间距 12。
- 元信息（时间 · 模型名）：13px `muted`，在消息下方 6px。
- 输入盒：见 §5.2；下方一行是字数（13px `muted`）与发送按钮。

### 5.7 工具市场

市场页是「挑卡片接入」，不是表格也不是列表，所以卡片规格单独定：

- **网格**：`repeat(auto-fill, minmax(260px, 1fr))`，`gap 16`，`align-items: start`（卡片按内容高度，不强行拉齐等高）。
- **卡片**：`surface` 底 + `padding 18` + 圆角 18 + `0 1px 2px rgb(23 32 27 / 4%)`；已接入的卡片加 1px `accent-soft` 边，作为唯一的「已装」信号。
- **服务图标块**：48×48，圆角 14，`accent-soft` 底，图标 22px、颜色 `accent-ink`。
- **标签 chip**：11px，`padding 1px 8px`，圆角 999，`canvas` 底，`muted` 字；一张卡最多两个。
- **底栏**：第一行「状态胶囊 + 工具数」，第二行操作（开关 + 试连 + 移除）右对齐（`margin-left: auto`，`white-space: nowrap`）；操作按钮高 28、字号 12，文字按钮不带底色，危险操作用 `danger` 字。
- **筛选 chip 组**：高 30，`padding 0 14`，圆角 999，`canvas` 底；选中 `accent-soft` 底 + `accent-ink` 字。
- **就地展开的表单**（自定义接入、需要路径的条目）：`surface` 底 + 圆角 18 + `--ma-shadow-soft`，字段栅格 `repeat(auto-fit, minmax(200px, 1fr))`，整行字段 `grid-column: 1 / -1`，底部按钮右对齐。**不弹二级窗口**——设置本身已是浮层。
- **状态三态**：未连接（`canvas` + `muted`）、正常（`success-soft` + `success`）、失败（`danger` 12% 透明底 + `danger` 字）；失败时卡内补一行 12px 的原因，不用 tooltip 藏起来。
- **不重复信息**：卡片里不再重复 chip 已经说明过的事（例如「本地 / 远程」）。

### 5.8 技能

技能是「方法包」，界面上只有两处：对话工具条上的挂载入口、设置里的技能清单与表单。

- **工具条挂载胶囊**：高 24，`padding 3px 10px`，圆角 999，图标 14 + 文字 12，`max-width 120px` 省略号；未挂载时 `ink 6%` 底 + `muted` 字，挂上后 `accent-soft` 底 + `accent-ink` 字；草稿态（会话还没建）禁用，`opacity 0.6`。
- **技能清单项**：与工具市场卡片同源但更薄——`surface` 底 + `padding 14px 16px` + 圆角 16 + `0 1px 2px rgb(23 32 27 / 4%)`，行内左右分布（内容 / 操作）；标题 14/600，说明 12.5/1.7 `muted`。
- **来源标签**：内置用 `accent-soft` + `accent-ink`，自建用 `ink 6%` + `muted`；工具数同款灰 chip，不与来源标签抢色。
- **行内操作**：文字按钮（详情 / 编辑 / 删除），高 28、圆角 8，hover `ink 6%` 底；删除用 `danger` 字。内置技能不给编辑与删除入口，而不是点了再报错。
- **表单**：整块 `surface` + 圆角 18 + `--ma-shadow-soft`，字段纵向排列、间距 12；输入框与正文域 `canvas` 底、圆角 10，聚焦时换 `surface` 底 + 1px `accent` 边。正文域固定 8 行、`resize: none`。
- **工具白名单**：chip 多选，行内换行排列，选中 `accent-soft`；不选时显式写「不限制」，避免用户以为是漏配。

### 5.9 状态与辅助元素

- **状态胶囊**：`success-soft` + `success`、`warn-soft` + `warn`、`danger-soft` + `danger`；pill 圆角，padding `0 10px`，高 24，字号 12–13。
- **步骤 / 执行过程卡**：`surface` 底 + `--ma-shadow-soft`，圆角 18，标题 13/600 `muted`，每步一行（图标 + 文字 + 参数），参数用 `mono` 13。
- **审批卡**：`warn-soft` 边（1px 允许，属于状态提示）+ 圆角 18；参数用 `<pre>`（`sunken` 底、`mono` 13、圆角 8）。
- **空态**：居中，图标/虚线圈 44px，标题 20–28，说明 15 `muted`，一个主操作；最多 3 行文案。
- **图标**：20px 线性图标，线宽统一；不混用两套图标集，不自绘插画。

## 6. 交互与动效

1. **过渡时长**：hover 淡入 `0.15s`（`--ma-motion-hover`），浮层出现/关闭 `0.18s`，其余微调 `0.15–0.2s`；只过渡 `background-color` / `color` / `box-shadow` / `opacity`，**不直接过渡 `background-image`**（渐变不可动画，见 §8.2），不做位移放大。
2. **hover 用横向渐变**，不用整块纯色灰（见 §8.2）。
3. **焦点可见**：键盘焦点用 3px `accent-soft` 外环 + 1px `accent` 描边。
4. **加载**：流式回答显示「正在回复…」气泡 + 光标；按钮进 loading 态并禁用重复提交。
5. **禁止假成功**：不用乐观更新掩盖失败；失败必须回滚并给出可读文案。
6. **尊重 `prefers-reduced-motion`**：该系统偏好下取消非必要过渡。

## 7. 文案与无障碍

- 术语固定：**会话 / 消息 / 模型 / 设备 / 工具 / 审批**。不要混用「聊天记录」「机器人」「终端」。
- 按钮说动词（保存、批准执行、撤销设备）；错误说原因 + 下一步（「密码至少 8 位」「网络断开，已保留草稿」）。
- 不展示冗余文字：不写「点击这里」「如下所示」；一行能说清就不写两行。
- 所有可点元素：`role`/语义标签正确、可 Tab 到达、Enter/Space 可触发、有 `aria-label`（纯图标时）。
- 颜色不是唯一信息载体（见 §2.3）。

## 8. 三条硬规则

### 8.1 不要随便加分割线

1. 大板块里的小模块之间**不加线**，用 24/32px 间距；需要更强分组感时用底色差异或极淡阴影。
2. 按钮、输入框、卡片、菜单、弹窗用**阴影**表达边界，不用 1px 描边。
3. 只有三种情况允许线条：Markdown 表格/引用的排版线、输入框聚焦描边、极低对比度环境下的可访问性退化。
4. 列表项之间不用横线（靠行高 + hover 底色 + 圆角分组）；选中态只用底色。
5. 看到不必要的分割线，顺手删掉——它通常是「不敢用留白」的痕迹。

### 8.2 hover 用渐变，不用整块灰

1. 可点元素 hover 统一 `linear-gradient(90deg, ink 7%, ink 3%)`，方向固定从左到右。
2. `:active` 与选中态加深：`12% → 7%`。
3. 覆盖范围：按钮、图标按钮、列表项（会话/设备/设置导航）、菜单项、用户区。
4. 危险动作 hover 用 `danger 10% → 4%`。
5. 已是选中色时，hover 保持选中色，不再叠灰。
6. 不用 `background: #f5f5f5` 这类整块纯色 hover。

**实现方式（必须这样写）**：渐变属于 `background-image`，浏览器无法在 `none ↔ gradient` 之间插值，直接写 `transition: background` 会**瞬切**。所以统一用全局工具类 `.u-tint`：

```html
<div class="chat__item u-tint">…</div>      <!-- 默认 7% → 3% -->
<div class="devices__item u-tint u-tint--soft">…</div>   <!-- 6% → 2% -->
<button class="u-tint u-tint--danger">删除</button>       <!-- danger 10% → 4% -->
```

```css
/* 已封装在 src/styles/index.css，不要再自己写 */
.u-tint { position: relative; isolation: isolate; }
.u-tint::before {
  content: '';
  position: absolute;
  z-index: -1;            /* 压在文字下面、背景上面（靠 isolation 建立层叠上下文） */
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(90deg, color-mix(… 7%), color-mix(… 3%));
  opacity: 0;
  transition: opacity var(--ma-motion-hover) ease;
  pointer-events: none;
}
.u-tint:hover::before { opacity: 1; }
```

7. 选中/激活态要压制遮罩：`.xxx--active::before { opacity: 0 }`；按下态用更深的实底色，同样压制遮罩。
8. **禁止**再写 `:hover { background: linear-gradient(...) }`——那是这个 bug 的来源。

### 8.3 结构多用 div、少嵌套

1. 容器用 `div`，只有行内文字用 `span`；不为挂 class 多包一层。
2. 模板从根到叶子 ≤4 层，超过说明有可合并的包装层。
3. 不要用 `section`/`article` 撑门面；语义标签只在表达文档结构时用。
4. `div` 承担按钮行为时补 `role="button"` + `tabindex="0"` + Enter/Space 处理。
5. `Teleport`/`Transition`/`template v-for` 不计入层数。

## 9. 变更流程（每次 UI 改动都要走）

1. **动手前**：确认这次要用的组件在 §5 里有定义；没有就先补一条规范再实现。
2. **实现中**：只改 `var(--ma-*)` 与本文档定义的尺寸，不引入第三套圆角/间距/颜色。
3. **提交前**：
   - 若新增/修改了组件样式 → 改 §5 对应条目；
   - 若调整了间距/圆角/字号阶梯 → 改 §4 / §3 表格；
   - 若新增颜色语义 → 改 §2 与 `frontend/src/theme/types.ts`（两边必须同时加）。
4. **提交信息**里写清「改了什么视觉规则」，方便回溯。

## 10. 自查清单

- [ ] 颜色全部来自 `--ma-color-*`，没有新的十六进制值。
- [ ] 深浅两种模式都看过（切换主题 + 明暗都验）。
- [ ] 字号落在 §3.2 的 9 档里，没有 11px / 14.5px 这类野值。
- [ ] 间距落在 §4.1 阶梯里；区块 32、字段 24、标签 8。
- [ ] 圆角只用 8 / 12 / 18 / 26 / pill。
- [ ] 没有新加的分割线；边界用阴影或底色表达。
- [ ] hover/active 用的是渐变加深，不是整块灰。
- [ ] 主按钮一屏最多一个，危险动作有二次确认。
- [ ] 键盘能走完：Tab 顺序合理、Enter/Space 可用、Esc 能关浮层。
- [ ] 文案术语与 §7 一致，没有冗余提示。
- [ ] 本次改动已回写本文档。
