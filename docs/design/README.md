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

## 与现有实现的差异（前端按此改造）

1. **配色**：Element Plus 主色从蓝改为 `--pine #1F4D46`；页面底色由 `#F5F7FA` 改为 `--canvas #FAF8F4`。
2. **侧边栏**：264px、`surface-sunken` 底、选中项用 `pine-soft` 底 + 3px 左竖条（不再整块反白）。
3. **对话**：消息列 720px 居中；用户气泡 `pine` 实底右对齐；助手气泡白底 1px 描边、无尾巴；时间戳 12px `ink-muted` 置于气泡外。
4. **输入区**：白底描边盒子 + 独立发送按钮（不再整条悬浮工具栏），字数计数在左下。
5. **新增设置页**：`/settings` 下六个分节，见 `docs/setting design.md`。
6. **字体**：登录/注册标题使用衬线（`Songti SC`），其余全部无衬线；正文 15px/1.75。

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

## 待确认

- 设置页是否保留「外观」（明暗主题会牵动整套 token 的暗色映射）。
- 「数据管理」里的导出格式（JSON / Markdown 二选一还是都给）。
- 是否要「关于」分节（版本与健康状态）。
