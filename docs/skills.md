# Skill 本地目录与按需加载

Skill 提供工作流程和参考资料。聊天中默认允许模型根据元数据按需加载，用户也可以通过工具条为下一条消息显式选择一个 Skill。工具准入与审批继续由账号工具设置和 Policy 执行。

## 安装位置

| 来源 | 默认位置或配置 | 可见范围 |
| --- | --- | --- |
| 应用内置 | `backend/app/skills/<目录>/SKILL.md` | 所有已登录账号 |
| 管理员共享 | `SKILL_SHARED_DIRS` 指定的目录数组 | 当前部署全部账号 |
| 用户私有 | `backend/data/skills/<账号ID>/<目录>/SKILL.md` | 对应账号 |

`SKILL_USER_ROOT` 可以覆盖用户私有根目录。账号 ID 可从 `GET /api/auth/me` 获取。目录指后端进程可访问的文件系统。容器部署可将宿主机目录只读挂载，再通过环境变量指定容器内路径。前端显示来源键，服务端目录绝对路径保留在服务端。

例如设置 `SKILL_SHARED_DIRS=["/srv/my-agent/skills/shared"]` 后安装如下目录。

```text
/srv/my-agent/skills/shared/
└── summarize/
    ├── SKILL.md
    └── references/
        └── checklist.md
```

```markdown
---
name: summarize
description: 用户需要按固定结构整理材料时使用。
---

先读 references/checklist.md，按检查项整理用户提供的材料。
```

下载后把完整包放到对应根目录，在「设置 → Skill」点击「重新扫描」。当前只扫描每个根目录下的一层包目录。内置、共享与私有来源分别生成 `builtin:`、`shared-0:`、`user:` 等键，跨来源的同名项可分别选择。

## 发现与加载时机

1. 登录成功或页面刷新后，App 按账号 ID 初始化 Skill Store，调用一次 `POST /api/skills/catalog/rescan`。
2. 切换、新建或直接访问会话只读 Store 缓存。
3. 进入「设置 → Skill」重新扫描，可查看只读清单并按需读取说明。页面内可再次点击「重新扫描」。
4. 服务端将名称、描述、来源、版本与包路径清单存入 `user_settings.skill_catalog`，不同请求和应用进程共享同一账号快照。运行期间复用快照，按需读取具体包。
5. 用户选择的 Skill 键随本条消息提交，成功提交后清除本次选择。关闭自动选择后，仍可显式使用 Skill。新聊天请求忽略旧的会话挂载字段。
6. 模型先看到有限的 Skill 元数据，通过 `__runtime_request_skill_load` 请求正文。已加载项按运行去重，需要参考资料时通过 `__runtime_read_skill_resource` 读取。
7. 每次运行固定目录版本、加载正文与已读资源，审批恢复使用原快照。扫描到的新版本对后续运行生效。扫描后又被修改或删除的包返回加载失败。

## 文件与上下文限制

- `SKILL.md` 必须包含 YAML frontmatter 的文本 `name` 和 `description`，正文必填。可省略 `slug`，默认取包目录名。
- 文件最大 64 KiB，名称最多 64 字符，描述最多 1024 字符，正文最多 12000 字符。
- 账号目录最多保留 100 项。每个根目录最多检查 256 个直接子项，最多配置 8 个共享根。单次运行最多向模型提供 50 项目录、加载 3 个 Skill，指令总量最多 12000 字符。
- `tools` 可列出推荐的工具名称。第三方 `allowed-tools` 字段只作为不参与授权的文件元数据。文件内容始终作为受约束的工作指引。
- 正文和资源读取拒绝路径穿越、符号链接及管道等特殊文件。参考文本只开放 `references/` 与 `assets/` 下现有允许类型，单文件 16 KiB。
- 包中的脚本留在文件系统中，当前 Loader 仅提供文本读取。
- 扫描失败时界面保留旧目录并提示重试。目录配置发生变化时，需要重新扫描后再发送。
- 退出或切换账号会清除前端目录状态，迟到的旧账号响应会被丢弃。

## 旧数据过渡

设置页根据当前账号的旧记录数量提供「导出旧 Skill」，下载包含 `<slug>/SKILL.md` 的 ZIP。解压到账号私有目录后重新扫描。已有同名目录时，先由用户核对文件内容再合并。

旧数据库记录、旧版 CRUD 与会话挂载 API 暂留作兼容，写接口标记弃用。现行聊天的目录只来自文件系统。已有旧运行继续根据原版本快照回放。数据库中的旧名称和说明保持其历史内容。

## 源码与测试

| 责任 | 代码 |
| --- | --- |
| 账号认证后的初始化 | [App.vue](../frontend/src/App.vue)、[Skill Store](../frontend/src/stores/skills.ts) |
| 本条消息选择与提交 | [ChatView.vue](../frontend/src/views/ChatView.vue)、[ChatToolbar.vue](../frontend/src/components/chat/ChatToolbar.vue)、[Chat Store](../frontend/src/stores/chat.ts) |
| 只读设置 | [SkillsPanel.vue](../frontend/src/components/settings/SkillsPanel.vue) |
| 目录、重扫、说明、旧数据导出 API | [api/skills.py](../backend/app/api/skills.py) |
| 账号快照和根目录作用域 | [skill_catalog_service.py](../backend/app/services/skill_catalog_service.py) |
| 元数据、版本与安全文件访问 | [filesystem.py](../backend/app/skills/providers/filesystem.py)、[loader.py](../backend/app/skills/loader.py)、[resources.py](../backend/app/skills/resources.py) |
| 加载、指令注入、资源快照、审批恢复 | [executor.py](../backend/app/agent/executor.py) |
| 后端回归 | [test_local_skill_catalog.py](../backend/tests/test_local_skill_catalog.py)、[test_skill_resources.py](../backend/tests/test_skill_resources.py) |
| 前端回归 | [App.test.ts](../frontend/src/App.test.ts)、[skills.test.ts](../frontend/src/stores/skills.test.ts)、[SkillsPanel.test.ts](../frontend/src/components/settings/SkillsPanel.test.ts)、[ChatView.test.ts](../frontend/src/views/ChatView.test.ts) |
| 浏览器验收 | [skills-acceptance.mjs](../frontend/scripts/skills-acceptance.mjs)，通过 `pnpm acceptance:skills` 执行 |

本轮使用 CodeGraph MCP 的 `codegraph_explore` 核对了 App、页面选择、目录服务、Provider、Registry 与 Runtime 的调用关系。接口契约见 [API](api.md#66-skill-apiskills)，决策见 [ADR-0014](adr/0014-local-skill-catalog-and-message-selection.md)。
