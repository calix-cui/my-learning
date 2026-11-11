# 设计稿（My Agent）

> **设计系统以根目录 [`DESIGN.md`](../../DESIGN.md) 为唯一来源**：配色、字体、间距、圆角、组件规则、硬约束都在那里，本文不重复。

本目录放两样东西：`mockups/*.html`（2026-11-09 那版的高保真稿，**历史**）和「怎么出截图」的说明。工具链与复现流程见 [`toolchain.md`](toolchain.md)。

## 1. 历史稿与现状的差异（别照着 HTML 写代码）

那版稿已完成历史使命：11-10 ~ 11-11 又迭代了三轮。要照着做新页面，看 `DESIGN.md` §5 和现有组件，不要回到 HTML。

| 设计稿当年 | 现在 |
|---|---|
| 助手消息是白底描边的气泡 | 助手消息**没有气泡**，直接排在画布上（`ChatMessage.vue`） |
| 用户气泡是 `accent` 实底白字 | 改成 `accent-soft` 浅底 + `ink` 字 |
| 设置是独立页面 `/settings` | 改成**悬浮窗**（`SettingsDialog.vue`），`/settings` 重定向到 `/chat?settings=1` |
| 侧栏 `sunken` 底 + 选中项 3px 竖条 | 侧栏与内容区同为 `canvas` 底，选中只靠 `accent-soft` 底色 |
| 输入区描边盒 + 方形发送按钮 | 圆角 26 的阴影盒 + 圆形发送按钮 + 「深度回答」开关 |
| 应用级顶栏 | 内容区工具条：标题 + 模型胶囊 + 分享 |

历史稿清单：

| # | 页面 | 稿 | 截图 |
|---|---|---|---|
| 01 | 登录 | [01-login.html](mockups/01-login.html) | [design-01-login.png](../images/design-01-login.png) |
| 02 | 注册 | [02-register.html](mockups/02-register.html) | [design-02-register.png](../images/design-02-register.png) |
| 03 | 对话 | [03-chat.html](mockups/03-chat.html) | [design-03-chat.png](../images/design-03-chat.png) |
| 04 | 设置 · 概览 | [04-settings.html](mockups/04-settings.html) | [design-04-settings.png](../images/design-04-settings.png) |
| 05 | 设置 · 模型接入 | [05-settings-model.html](mockups/05-settings-model.html) | [design-05-settings-model.png](../images/design-05-settings-model.png) |

## 2. 现状截图（以这个为准）

都在 [`docs/images/`](../images/)，1440×900 @2x。

| 场景 | 截图 |
|---|---|
| 登录 / 注册 | `ui-01-login.png`、`ui-02-register.png` |
| 对话（消息态 / 空态 / 草稿） | `ui-07-chat.png`、`ui-06-chat-empty.png`、`ui-12-new-chat-draft.png` |
| 查询与菜单（会话项菜单、自绘确认框） | `ui-10-thread-menu.png`、`ui-11-message-box.png` |
| 设置悬浮窗（浅色 / 深色） | `ui-09-settings-dialog.png`、`ui-05-settings-dark.png` |
| 设置 · 工具治理 | `ui-13-tools-settings.png` |
| 审批卡片（写工具挂起） | `ui-14-approval.png` |
| 设置 · 工具市场（卡片网格 / 已接入态） | `ui-15-tool-market.png`、`ui-16-tool-market-installed.png` |
| 对话 · MCP 工具审批（待确认 / 批准后时间线） | `ui-17-mcp-approval.png`、`ui-18-mcp-approved.png` |
| 设置 · 技能（内置只读 / 自建可改） | `ui-19-skills.png` |
| 对话 · 工具条上的技能胶囊 | `ui-20-skill-mounted.png` |
| 主题回归基线（浅 / 深 / 暖砂） | `theme-settings-light.png`、`theme-settings-dark.png`、`theme-settings-sand.png`、`theme-chat-dark.png` |
| Agent 执行时间线 | `agent-timeline.png` |

## 3. 主题的存储与优先级

- 本机 `localStorage`（键 `my-agent.theme`）：**先读它再绘制**，保证首屏不闪。
- 账号设置（`user_settings.theme_id` / `theme_mode`，见 [`api.md`](../api.md) §4.5）：**登录后拉一次**。
- 优先级：**账号 > 本机**。账号存过就以账号为准（换设备自动生效）；账号为空则把本机这套写上去。
- 切换主题：本地立即生效（不等网络），随后异步写回账号；写失败只影响跨设备同步。

新增主题只需在 `frontend/src/theme/themes/` 加一个文件并注册；18 个语义色缺一个，`apply.test.ts` 的「每个主题都给全」用例会直接红灯。

## 4. 怎么预览与出图

```bash
# 直接打开历史稿
open docs/design/mockups/03-chat.html

# 出历史稿截图（1440×900 @2x）
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --no-sandbox --disable-gpu --hide-scrollbars \
  --user-data-dir=/tmp/cp-shot --window-size=1440,900 --force-device-scale-factor=2 \
  --screenshot=docs/images/design-03-chat.png \
  "file://$PWD/docs/design/mockups/03-chat.html"
```

现状截图由 `frontend/scripts/*-acceptance.mjs` 顺手产出（`.acceptance/*.png`），挑需要的拷进 `docs/images/`。
