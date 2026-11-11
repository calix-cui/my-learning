# ADR-0009 · 每用户模型配置与密钥加密

- **状态**：已接受（2026-11-09）
- **相关**：[`../api.md`](../api.md) §4、[`../auth.md`](../auth.md)、[ADR-0006](0006-llm-client-and-chat-storage.md)、[ADR-0008](0008-auth-and-session.md)

## 背景

阶段 4 的模型配置只来自进程环境变量（`LLM_PROVIDER` / `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`）。这带来两个问题：

1. 用户换模型必须改 `.env` 再重启进程——设置页的「模型接入」无从谈起；
2. 一个进程只有一套配置，多个账号无法各用各的 key（Cloud 形态下就是「共用一把钥匙」）。

设置模块要落地「模型接入」分节，就必须把模型配置变成**用户级数据**，并且 API Key 不能明文落库。

## 决策

1. **新建 `user_settings` 表**，与 `users` 一对一（`user_id` 主键 + 外键 `ON DELETE CASCADE`）。字段只放设置项，不往 `users` 上加列。
2. **模型配置存在 `user_settings`**：`model_provider`（`fake` / `openai`）、`model_base_url`、`model_name`、`model_timeout_seconds`。
3. **API Key 用对称加密后存库**：`model_api_key_ciphertext`（Fernet，`cryptography` 库），主密钥来自进程环境变量 `APP_SECRET_KEY`；另存 `model_api_key_hint`（末 4 位）用于界面回显，**任何接口都不返回明文**。
4. **未配置 `APP_SECRET_KEY` 时禁止保存自定义 Key**：`PUT /api/settings/model` 返回 400「服务端未配置 APP_SECRET_KEY，无法保存自定义 Key」，其余字段仍可保存。这样本地开发不需要额外准备密钥，也不会悄悄降级成明文。
5. **解析顺序：用户配置 > 环境变量**。用户把 provider 设为 `fake` 时就是显式用假模型；没有用户配置时回落到环境变量那套（保持 CI 与本地零配置可用）。
6. **聊天链路改为依赖 `get_user_llm`**：`(db, user) -> LLMClient`，按用户配置构造；`get_llm()` 保留为「环境变量默认实现」，供测试与没有用户配置的场景使用。

## 代价

- 多了一个需要运维保管的密钥（`APP_SECRET_KEY`），**丢了就解不开已存的 Key**（只能让用户重填）。
- 每次请求都要读一次 `user_settings`；用 `@lru_cache` 之外的按请求查询，成本可忽略，但会多一条 SQL。
- 加密只保护「数据库被拖走」这一类风险；进程内存里的明文 Key 仍可能被 dump——这是所有「服务端代持密钥」方案的共同边界。

## 被否方案

| 方案 | 为什么不用 |
|---|---|
| 明文存 Key | 数据库泄露即泄露用户凭证；也违反 AGENTS.md §4「严禁提交/存储真实密钥」的精神 |
| 只读环境变量，不允许界面改 | 无法支撑设置页；多账号只能共用一把 key |
| 引入 KMS / Vault | 对个人项目是数量级的复杂度与成本，等上云且有合规要求再说 |
| 每个用户一把 Fernet 密钥 | 密钥本身又需要地方存，问题原地打转 |

## 复评触发

- 需要**密钥轮换或使用审计**（例如「上次用这把 key 是什么时候」）时，应换成 KMS/Secrets Manager 并在表里记 key 版本。
- 支持多 Agent 各自配模型时，模型配置应从 `user_settings` 迁到 `agents` 表，`user_settings` 只保留默认值。
- 若开放「共享模型额度」（一个团队共用一把 key），需要重新引入额度与归属模型，与本 ADR 的单用户假设冲突。

## 落地记录（2026-11-09）

| 项 | 结果 |
|---|---|
| 表 | `user_settings`（`user_id` unique + 5 个模型列），迁移 `7ccc172700f4`，`alembic check` 无漂移 |
| 加密 | `app/common/crypto.py`，Fernet(APP_SECRET_KEY)；库里存 `model_api_key_ciphertext`，接口只回 `api_key_hint` 末四位 |
| 解析顺序 | `app/llm/__init__.py` 的 `get_user_llm()`：有行用行，没有行回落环境变量；`resolve_llm(db, user_id)` 供非请求场景调用 |
| 接口 | `GET/PUT /api/settings/model`、`POST /api/settings/model/test`、`GET /api/settings/export`（见 api.md §4） |
| 验证 | 后端 148 例 / 94.22%；设置 E2E 13/13（含「测试连接」「导出可解析」「注销后无法登录」） |
| 代价兑现 | 每轮对话多一条 `user_settings` 查询（已用主键查，成本可忽略）；Key 丢失只能重填（无找回入口，界面已写明） |

## 追加（2026-11-10）：外观也进 `user_settings`

- 新增 `theme_id` / `theme_mode` 两列（都可空），接口 `GET|PUT /api/settings/appearance`。
- **`model_configured` 列**：外观与模型共用一行，所以「有行」不再代表「配过模型」；
  只有 `update_model_settings()` 会把该列置 `true`，读接口据此决定是否回落环境变量。
  （最初漏了这层，导致只改主题的新账号拿不到环境变量里的模型配置。）
- 优先级：账号 > `localStorage`；切换主题先写本机、再异步写账号，失败只影响跨设备同步。
