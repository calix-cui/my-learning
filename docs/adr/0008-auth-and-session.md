# ADR-0008 个人助手的账号体系：服务端会话 + 行级归属隔离

- 状态：已接受（2026-11-09 用户确认）
- 日期：2026-11-09
- 相关：[docs/auth.md](../auth.md)、[ADR-0006](0006-llm-client-and-chat-storage.md)、[ADR-0007](0007-archive-product-module.md)

## 背景

My Agent 目前没有任何用户概念：`conversations` / `messages` 全局可见，任何拿到地址的人都能读写所有会话，也看不到「这条会话是谁的」。产品方向是**个人助手**（一人一号，不做工作空间），所以需要一个最小但正确的账号体系：注册、登录、鉴权、数据隔离，并且给将来的多设备、多 Agent、API Token 留出位置。

调研过个人助手类 Agent（ChatGPT / Claude / Gemini / dots / Muse）的共同做法：账号是唯一隔离维度；记忆与对话分开存；凭证单独托管；会话级状态与用户级状态分清。据此确定本版范围。

## 决策

1. **服务端会话 + HttpOnly Cookie**（`my_agent_session`），数据库 `sessions` 只存令牌的 SHA-256 摘要，有效期 30 天滑动续期。
2. **自研 `app/auth/` 轻量模块**（约 300 行），不引入 `fastapi-users`。
3. **密码用 Argon2id**（`argon2-cffi` 默认参数）。
4. **`conversations.user_id` 非空外键**；service 层签名强制 `user_id`，越权返回 404 而非 403。
5. **默认拒绝**：除注册/登录/健康检查外，所有 `/api/*` 路由都挂 `Depends(get_current_user)`。
6. v1 不做邮箱验证、找回密码邮件、第三方登录、MFA、API Token 签发（表结构与扩展路径在 docs/auth.md §10 说明）。
7. 已确认的口径：邮箱作登录标识；注册默认开放、`ALLOW_REGISTRATION=false` 可关；会话 30 天滑动续期；密码 8–72 位不强制字符种类；首个账号由 `python -m app.create_admin` 创建。

## 代价

- **多一张会话表 + 每次请求一次查库**（一次主键索引查询，忽略不计；换来撤销即时生效）。
- **CSRF 面**：Cookie 自动携带，理论上存在 CSRF；靠 `SameSite=lax` + 只接受 `application/json` + 无 `GET` 写操作收敛。若将来需要跨站嵌入，再补 CSRF token。
- **自研即自负**：没有社区在帮我们修洞，所以密码哈希、令牌生成、比较都用标准库/成熟库，并配越权测试。
- **迁移不可逆**：`conversations` 旧数据（已确认不保留）在迁移里直接清空，`downgrade` 后表结构回来但数据不会。

## 被否方案

| 方案 | 否掉的原因 |
|---|---|
| JWT 放 localStorage | XSS 直接拿到长期令牌；撤销要额外黑名单 |
| JWT 短效 + refresh Cookie | 前端要处理并发刷新、续期失败，复杂度换来的收益在单页同源场景不明显 |
| `fastapi-users` | 自带路由的响应格式与本项目 `Response{code,message,data}` 不一致，adapter/UserManager 都要改；我们只需要 6 个接口 |
| OAuth-only（只第三方登录） | 自建个人项目不该依赖外部 IdP；也不解决「本机无外网时无法登录」 |
| 在 `messages` 表冗余 `user_id` | 与 conversations 的归属重复，出问题时反而要向两处对齐；用会话级隔离 + 服务层过滤已足够 |
| 现在就把 API Token / 第三方登录做掉 | 当前无调用方；提前做等于把未验证的假设固化进表结构 |

## 复评触发

- 需要把 Agent 作为服务被脚本或桌面端调用 → 加 `api_tokens`，`get_current_user` 增加 Bearer 分支。
- 需要邀请/审核才能注册 → 加 `invites` 或注册开关。
- 单账号会话数超过几千或需要跨区部署 → 才考虑 Redis 存会话。
- 需要团队协作 → 这不是本 ADR 的扩展点，要新开 ADR 讨论 workspace 模型。
