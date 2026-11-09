# 设计稿（My Agent）

> 设计系统 **以根目录 [`DESIGN.md`](../../DESIGN.md) 为唯一来源**（token、排版、布局、组件规则都在那里）。
> 本目录只放**可点开的高保真稿**：`mockups/*.html`（自包含，无外部依赖）+ `docs/images/design-*.png` 截图。

## 为什么不用旧的那套

旧设计（`archive/product-admin/docs/design/`）是商品管理后台的，页面已归档下线；当前应用只有对话、登录、注册、设置四类页面，按 2026-11-09 的裁决**从零重建，不参考旧实现**。

## 设计立场（一句话版）

暖白纸面 + 墨色文字 + 深松绿单一强调色；一屏一件事；危险操作必须说清后果；不做装饰性动效。

## 页面清单

| # | 页面 | 路由 | 稿 | 截图 |
|---|---|---|---|---|
| 01 | 登录 | `/login` | [01-login.html](mockups/01-login.html) | [design-01-login.png](../images/design-01-login.png) |
| 02 | 注册 | `/register` | [02-register.html](mockups/02-register.html) | [design-02-register.png](../images/design-02-register.png) |
| 03 | 对话 | `/chat` | [03-chat.html](mockups/03-chat.html) | [design-03-chat.png](../images/design-03-chat.png) |
| 04 | 设置 · 概览 | `/settings` | [04-settings.html](mockups/04-settings.html) | [design-04-settings.png](../images/design-04-settings.png) |
| 05 | 设置 · 模型接入 | `/settings/model` | [05-settings-model.html](mockups/05-settings-model.html) | [design-05-settings-model.png](../images/design-05-settings-model.png) |

设置其余分节（账号资料 / 登录设备 / 外观 / 数据管理）共用 04 与 05 的版式：左侧二级导航 + 右侧单列卡片，不重复出稿。

## 实现状态（T-FE-01，2026-11-09 完成）

设计稿已按 1:1 落进代码，逐条对照：

| 设计点 | 实现位置 |
|---|---|
| 配色改为 `--ma-*` 语义 token，主色深松绿 | `frontend/src/theme/` + `frontend/src/styles/index.css` |
| 侧栏 264px、`sunken` 底、选中项 `accent-soft` + 3px 左竖条 | `frontend/src/App.vue`、`components/chat/ThreadList.vue` |
| 对话阅读列 720px 居中、用户气泡实底右对齐、助手气泡白底描边、时间在气泡外 | `views/ChatView.vue`、`components/chat/ChatMessage.vue` |
| 输入区白底描边盒 + 独立发送按钮 + 左下计数 | `components/chat/ChatComposer.vue` |
| 设置页 200px 二级导航 + 560px 表单 | `views/SettingsView.vue` |
| 登录/注册 400px 卡片、衬线标题、距顶 12vh | `styles/index.css` 的 `.auth*`、`views/LoginView.vue`、`views/RegisterView.vue` |
| 品牌资产（logo / favicon / manifest） | `frontend/public/*`、`frontend/index.html`（源图在仓库根 `images/`） |

实体截图见下方「实现截图」，与 `design-*.png` 同尺寸（1440×900 @2x），可直接叠对比。

## 怎么预览

```bash
# 直接双击打开，或：
open docs/design/mockups/03-chat.html
```

截图重出（1440×900，2x）：

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
  --user-data-dir=/tmp/cp-shot --window-size=1440,900 --force-device-scale-factor=2 \
  --screenshot=docs/images/design-03-chat.png \
  "file://$PWD/docs/design/mockups/03-chat.html"
```

## 已定口径

- 设置页保留「外观」（明暗主题牵动整套 token 的暗色映射，已实现）。
- 「数据管理」的导出：**JSON 与 Markdown 都给**（T-FE-02 实现时落）。
- **不做**「关于」分节（2026-11-09 裁决）。

## 主题系统（2026-11-09 落地）

主题是**运行时可切**的：`:root` 上挂一层 `--ma-*` 语义变量，组件只引用这层；换主题 = 重写这批变量，不重渲染组件、不换 CSS 文件。

| 位置 | 作用 |
|---|---|
| `frontend/src/theme/types.ts` | `ThemeColors` 的 18 个语义色 + `ThemeDefinition`（一套主题必须同时给 light / dark） |
| `frontend/src/theme/themes/*.ts` | 每套主题一个文件：松林（默认）/ 暖砂 / 靛蓝 / 石墨 |
| `frontend/src/theme/themes/index.ts` | 注册表：数组顺序即设置页展示顺序，第一个是默认 |
| `frontend/src/theme/apply.ts` | `buildThemeVars()` 编译 CSS 变量；`buildElementPlusVars()` 用 `color-mix` 把 accent 派生成 Element Plus 的 6 档主色，**不需要为每个主题手写色阶** |
| `frontend/src/stores/theme.ts` | Pinia setup store：`themeId` + `mode(light/dark/system)` + `systemDark`，写 `localStorage['my-agent.theme']`，监听 `prefers-color-scheme`；`main.ts` 里 `app.use(createPinia())` 之后、挂载之前调 `initTheme()` 防闪白 |
| `frontend/src/styles/index.css` | 兼容层：旧的 `--pa-*` 全部指向 `--ma-*`，老页面不用改就跟着换肤 |

**新增一套主题（只改两处）**：

```ts
// 1) frontend/src/theme/themes/sakura.ts
export const sakuraTheme: ThemeDefinition = {
  id: 'sakura',
  name: '樱',
  description: '一句话描述这锅配色适合什么时候用。',
  light: { canvas: '#…', surface: '#…', /* 18 个键都不能少 */ },
  dark: { /* 同上 */ },
}

// 2) frontend/src/theme/themes/index.ts
export const themes = [pineTheme, sandTheme, indigoTheme, graphiteTheme, sakuraTheme]
```

漏任何一个色键，`src/theme/apply.test.ts` 的「每个主题都给全」用例会直接红灯，不会等到界面上出现透明洞。

### 截图

| 浅色 · 松林 | 深色 · 松林 |
|---|---|
| ![浅色](../images/theme-settings-light.png) | ![深色](../images/theme-settings-dark.png) |

## 实现截图（1440×900 @2x，2026-11-09）

| # | 页面 | 截图 |
|---|---|---|
| 01 | 登录 | [ui-01-login.png](../images/ui-01-login.png) |
| 02 | 注册 | [ui-02-register.png](../images/ui-02-register.png) |
| 03 | 对话（真实模型回答） | [ui-03-chat.png](../images/ui-03-chat.png) |
| 04 | 设置 · 外观（浅色） | [ui-04-settings.png](../images/ui-04-settings.png) |
| 05 | 设置 · 外观（深色） | [ui-05-settings-dark.png](../images/ui-05-settings-dark.png) |

重出命令（需要后端 8000 与 dev 5173 在跑）：

```bash
cd frontend && node .shots-light.mjs /tmp/ui-shots   # 临时脚本，出浅色四张
```

> `theme-*.png` 是主题系统落地时的专项截图（含暖砂与深色对话页），保留作主题回归基线。
