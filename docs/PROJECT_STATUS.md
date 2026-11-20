# 项目状态

> 一页纸：**现在在哪、下一步做什么、有什么坑**。每次任务开始前读它，结束后更新它（AGENTS.md §7）。
> 最近更新：2026-11-20 · ReAct-MCP 骨架落地 + 分支归并到 main

- **ReAct-MCP 骨架 + 分支收尾（2026-11-20）**：新增独立学习子工程 [`ReAct-MCP/`](../ReAct-MCP/README.md)（Node ≥ 20 + TypeScript，用 `tsx` 直跑）：`package.json` 提供 `dev`/`start`/`build`/`type-check`/`format`，`tsconfig.json` 用 NodeNext + strict，`README.md` 写清目录职责、命令、环境变量、设计要点与下一步，`.env.example` 记录模型与 `MCP_SERVERS`（`.env` 仍被根 `.gitignore` 忽略）。`src/` 下 7 个文件只有头注释，**还没有实现**，不参与主应用构建。验证：`pnpm install`、`type-check`、`format:check`、`build`、`start` 均通过（只自检工具链，没有可运行逻辑）。同一轮把 `docs/agent-trace-map.{md,html}` 提交；`codex/skill-tool-system`（领先 66 个提交）快进合并进 `main` 并推送，本地与远端的其它分支全部删除（`backup-before-split` 的 3 个独有提交只留在本地 reflog，原 tip `71cde74`；两个 `dsh-*` 分支连同 `.agents/worktrees/dsh-88d7f25b-c093` 一并清掉）。

- **新增 [Agent 全链路追踪图](agent-trace-map.md)（2026-11-20）**：把「入口 → prepare_run → RunHub → _run_loop → LLM → ToolUse → Skill → 审批恢复」整理成断点表，并配 [交互版思维导图](agent-trace-map.html)。行号基准为主工作树 `codex/skill-tool-system @ 13b5701`；`.agents/worktrees/dsh-*` 的旧快照不可用于对照。本次只新增两份文档，未改代码、未跑测试。

- **清理收尾（2026-11-19 晚）**：开发库只剩真实账号一个（`@example.com` 的联调/验收账号及其会话 35、消息 80、run 49 全部删除，删前备份在 `/tmp/dbbackup/before-purge.sql`），没有停在 `running`/`waiting_approval` 的僵尸运行；清理用现成的 `backend/scripts/cleanup_demo_accounts.py --yes`（先写了个同类脚本，发现重复后删掉）。前端删掉三处无人引用：`Execution.gaveUp`、`getAgentRun()`、`missingColorKeys()`。随后按同一原则下线了旧版数据库 Skill：删掉 `DatabaseSkillProvider`、`skills` 表（迁移 `d39c4a07e1f2`）、`/api/skills` 的列表/详情/写接口与 `/skills/legacy/export`、`skill_service` 的 CRUD、前端的旧版导出面板与 `legacy_count`；技能只剩本地目录一种来源。

- **执行与连接解耦已完成（ADR-0019）**：以前「运行」和「请求线程」是同一件事——关标签页、刷新、断网都会让 `executor.py` 收尾时 `_fail`，正在生成的回答直接消失，用户只能重发、token 白花。现在执行搬到后台线程（`backend/app/agent/hub.py` 的 `run_hub`），用自己的 Session 跑，跟连接无关：正文按快照写进 `agent_runs.draft_content`（攒 200 字或 0.5 秒一次），SSE 降级成纯读取（`GET /api/agent/runs/{id}/stream?since_seq=`，先发 `run_snapshot` 再跟实时，每 15 秒注释心跳 `: ping`），断连不再等于取消——只有 `POST /runs/{id}/stop` 才停，已生成正文落成正常助手消息、`stop_reason=user_cancelled`，正文下方给「您终止了此次会话」与「重新生成」（删旧回答、用同一条提问重跑）；无人订阅满 10 分钟自行停止（`stop_reason=abandoned`）。前端发送仍是「创建 + 订阅」，但打开会话时若服务端还在跑就直接挂回（`attachRunning`），刷新后正文接着长出来。**不做**跨进程：运行注册表在进程内存里，部署需 `--workers 1`，记技术债 T-30；T-29（断线不能续跑）随本次改造关闭。决策见 [ADR-0019](adr/0019-execution-decoupled-from-connection.md) 与 [api.md §6.2.2–6.2.3](api.md)。验证：后端 `test_run_hub.py` 13 项、`test_agent_api.py` 24 项、`test_settings_api.py` 26 项全过、Ruff 通过；全量 **399 passed + 19 xfailed（exit 0）**——跑不过的 MCP 用例已登记进 `tests/known-failures.txt`，新失败会被单独标红，不再被环境噪声盖住。前端全量 **153 项（23 文件）**、ESLint、`vue-tsc`、生产构建通过；真实模型联调（真 Chrome + 真后端 8000 + 真 DeepSeek）`pnpm acceptance:live` **30 项全过**——刷新后回答继续生成且完整、全程只提交 1 次；点停止才终止且保留已生成正文；重新生成删旧回答只调一次接口；写操作弹审批卡片、批准后真的改名成功，且 `tool_call`/`tool_result` 的 `call_id` 一致。联调中修掉三个真实缺陷：`openConversation` 只读历史不自订阅，刷新后仍停在「请重新核对状态」（`attachRunning`）；审批交回用户后连接仍算「传输中」，卡片显示「执行中…」且点不动（`runExecution` 在交接后保持 idle）；首屏几次设置读写并发「建行」撞唯一索引报「数据库操作失败」（`_get_or_create` 撞键后回滚重查）。本机 MySQL 已升级至 `b0fc5a19fd76`。

- **第五步已完成（断线核对契约）**：运行摘要补 `request_id` / `error_message` / `finished_time`，新增 `GET /api/agent/runs/{run_id}` 单点详情与 `GET /api/conversations/{id}/agent/runs?request_id=` 认领查询（查不到返回 404「这次提交还没有落库，可以重新发送」），步骤接口支持 `since_seq` 增量并带回 `status` / `visible_step_count` / `error_message` / `finished_time`。前端据此在断流后先认领再核对：知道运行号就按运行号查，只知道 `request_id` 就按它认领，认领到的运行仍在跑时每 1.5 秒轮询增量、最多 20 次，跑到终态才刷新正文；轮询不重发、不阻塞按钮。失败文案改为透出服务端原因（「运行被中断」「模型没有给出答复」等）。当时**不做**真续跑（运行与请求线程同体，另记技术债 T-29）——这一条已被下方 ADR-0019 的改造取代。决策见 [ADR-0018](adr/0018-reconnect-contract-and-read-only-polling.md) 与 [api.md §6.2.1](api.md)。验证：后端 `test_agent_api.py` 13 → 18 项全过、Ruff 通过，全量 356 passed（10 项失败均为沙箱起不了 MCP echo 子进程）；前端全量 **144 项（23 文件）**、ESLint、`vue-tsc --noEmit`、生产构建通过；浏览器验收 `acceptance:recovery` 12 → 20 项、`acceptance:scroll` 10 项、`acceptance:route` 11 项全通过（新增「连 run_started 都没收到」场景，历史页此刻为空，只能靠 `request_id` 认领，全程只 1 次 POST）。真实模型联调（2026-11-18，真实 DeepSeek + 真实 MySQL）：API 级 `backend/scripts/check_reconnect_live.py` 20 项、浏览器级 `pnpm acceptance:live` 14 项全过；并修掉联调暴露的真 bug——断流时请求 Session 已关闭，收尾逻辑抛 `DetachedInstanceError` 被静默吞掉，运行永久停在 `running`（同一会话再发消息被 409 锁死），改为回落到独立 Session 收尾（`executor.py` 的 `_mark_interrupted`，单测锁定）。手动联调又补三处：服务启动时清理上一进程留下的 `running` 运行（`remove_stale_runs`，单进程假设记 T-30）；轮询跑满仍不终态时给「不再等待」（只改本地判定、不动服务端）；上游把错误写进 SSE 帧时把真实原因作为 502 文案透出（不再一律「格式无法解析」）。前端 145 项、后端 356 passed。

- **第四步已完成（收拢历史与页面职责）**：`stores/chat.ts` 835 → 475 行，只保留组合根职责（选择当前会话、串发送与审批、派生视图值）。新增 `stores/chat/threads.ts`（`threads` Map、取消句柄、请求去重、释放）、`stores/chat/conversations.ts`（列表行、`activeId`/`draft`、账号代次、创建/改名/删除）、`stores/chat/history.ts`（历史页合并、刷新对齐、分页、步骤与审批重查），用 `createX(deps)` 工厂接线，读函数显式接收 `(id, thread)`，不各建 Pinia store；对外接口名与数量不变。页面层再拆出两个组合式函数：`composables/useChatScroll.ts`（帧合并、贴底跟随、翻页锚点、卸载清理，并补上「用户上滚阅读时不被拽回底部」，阈值 80px）与 `composables/useChatRoute.ts`（`/chat/:id` 与草稿态双向同步、建库后改写地址、删除或打不开时退回 `/chat`，只在对话路由上改写，设置浮层不吃会话地址）。`ChatView.vue` 315 → 233 行，只剩 Skill 参数与提交参数。决策见 [ADR-0017](adr/0017-chat-store-module-boundaries.md) 与 [chat.md §9](chat.md#9-聊天状态与展示一条时间线2026-11-18--11-19)。验证：前端全量 **142 项（23 文件）**、ESLint、`vue-tsc --noEmit`、生产构建通过；浏览器验收 `acceptance:recovery` 12 项、`acceptance:scroll` 10 项、`acceptance:route` 11 项（深链、刷新、侧栏切换、后退/前进、设置浮层共存、非数字路径回落）在真实 Chrome 里全通过。（第五步补了断线核对契约，第六步把执行与连接解耦，见下方 ADR-0019 条目。）

- **第三步已完成（统一执行状态与断流恢复）**：每个 Execution 成为步骤、预览、审批与运行状态的唯一可写来源（`stores/chat/execution.ts`），事件归并到 `stores/chat/events.ts`。创建前锁定草稿并复用创建请求；断流后只读历史核对、不自动重发；等待审批时读取当前待决定项；历史/审批/步骤读取失败保留错误与重试入口；迟到结果按账号代次与会话实例失效。本轮补上此前缺的浏览器验收：新增 `frontend/scripts/chat-recovery-acceptance.mjs`（`pnpm acceptance:recovery`，12 项断言，模拟 API/SSE）。验收中发现并修复「核对确认消息已落库后草稿仍留在输入框、同一句话会被再发一遍」，并补单测（去掉修复该用例失败）。前端全量 **126 项（21 文件）**、ESLint、类型检查、生产构建通过。同步 chat.md §9.6、ADR-0016 验证段、DESIGN §5.9、前端 README 与 toolchain 测试清单。随后清理了三个只剩测试引用的派生出口（`runsByMessage` / `replayDetails` / `activeUserMessageId`，`stores/chat.ts` 874 → 835 行），断言改为读展示项，前端 126 项仍全通过。未进行真实模型或完整应用 E2E 验收；未修改后端。

- **第二步已完成，按要求停止**：新增纯展示投影 `stores/chat/feed.ts`、`ChatMessageList.vue` 和 `ChatExecutionItem.vue`。页面读取统一展示项；Store 仅增加展示标识与运行的映射，不改执行状态机。临时用户消息转正式 ID、运行完成及历史核对时复用执行组件和两层详情节点，正文只渲染一次；支持分页缺少用户消息、普通历史消息、多运行排序及会话隔离。前端全量 **98 项（20 文件）**、ESLint、类型检查、构建和改动 Vue/TS 格式检查通过。独立 Chrome 加载实际页面与 Store，使用模拟 API/SSE 实际点击两层展开，验证完成后节点和展开态不变、只有一份正文、刷新位置正确，无页面运行错误，并检查截图。未进行真实模型或完整应用 E2E 验收。同步 DESIGN、前端 README、chat 方案和 ADR-0015；未修改后端、未开始第三步及后续重构。

- **第一步已完成，按要求停止**：ChatView 保持用户消息在过程前、助手正文在过程后；运行结束和刷新后不再把过程放到正文下方，未修改 Store、后端或开始后续重构。更新页面回归测试与 DESIGN.md、chat.md。新增/调整的位置断言修复前出现 3 项失败，修复后页面 13 项、前端全量 93 项（19 个文件）通过，ESLint、类型检查、生产构建、改动 Vue/TS 格式及 diff 空白检查通过。覆盖分页仅含助手消息、补入用户消息不重复、失败/取消/待审批位置、零调用隐藏入口。独立 Chrome 页面加载实际 ChatView 和 Store，以模拟 API/SSE 验证运行→完成→刷新的位置并检查默认配色截图，无页面运行错误；未进行真实模型、完整应用 E2E 或全主题验收。下一步保持待指示。

- [聊天状态与展示](chat.md#9-聊天状态与展示一条时间线2026-11-18--11-19)已重排成一条时间线（2026-11-18 → 11-19），记录六步的「触发问题 → 决定 → 落地 → 验收 → 后来被什么改写」，并把已被推翻或没采纳的方案集中列在 9.3：断线即失败、「只读续查」轮询、「不再等待」、`run_finished` 扩展、`tool_call_id` 关联等都已明确标注现状。

- 调整四套主题的 `textHover`：浅色模式使用 `#1f1f1f` 近黑色，深色模式保留 `#f5f5f5` 近白色，默认 `text` 浅灰保持不变。首屏浅色兜底、类型注释和 DESIGN.md 同步更新。按用户要求仅修改，未运行测试、构建或浏览器验收。

- 按用户澄清补齐 `--ma-color-text`（`#a3a3a3` 浅灰）与 `--ma-color-text-hover`（`#f5f5f5` 近白），四套主题的明暗模式统一使用这对颜色；文字交互类与执行过程默认文字已接入。后续纯样式修改只修改并汇报，不运行测试、构建或浏览器验收；本次未执行这些检查。同步更新视觉规范与前端说明。

- 已新增主题语义色 `textHover`（`--ma-color-text-hover`）与通用 `u-text-action`，接入四套主题的浅色、深色及首屏兜底。执行过程展开、重试和加载更早消息默认灰色，悬停或键盘聚焦提高对比度，禁用不强调，减少动态效果时关闭过渡。保留已有字号、折叠和消息运行接口设计。前端 89 项测试、ESLint、类型检查、生产构建及相关格式检查通过；本机 Chrome 使用实际主题与样式验证八套配色、悬停、键盘聚焦、禁用和减少动态效果，并检查截图。同步更新 DESIGN.md 与前端 README。本步完成后停止。

- 已按用户要求移除 `legacyRuns` / `legacy_runs` 查询、状态、类型和页面入口。迁移 `b72e80d193ac` 清理两个消息关联均为空的已结束运行及其步骤、审批；本机实际删除 5 条运行、14 条步骤，73 条消息及其余运行保持不变，数据库结构无漂移。新增 3 项迁移边界测试，验证关联记录、进行中、待审批及消息保留；后端全量 370 项（覆盖率 92.40%）、前端 89 项、Ruff、ESLint、类型检查和生产构建通过。本步完成，等待下一步指示。

- 本地改动整理提交：按后端实现与测试、前端交互与测试、项目文档分组，提交信息统一使用中文。提交前复验后端全量测试（覆盖率 92.40%）、前端 89 项测试、Ruff、ESLint、类型检查和生产构建通过。

- 已完成 [重设计第三步](skills.md)。网页统一使用 Skill，本地目录按账号保存元数据快照，登录或刷新初始化一次，切换会话零目录查询。设置只读并支持重扫、说明和旧数据库 Skill 导出。单条消息可显式选择，默认支持模型按需加载。后端 367 项（覆盖率 92.40%）、前端 89 项测试，Ruff、ESLint、格式检查及构建通过。本机 MySQL 已升级至 `a638c170ef92`，结构无漂移。Chrome 已用真实 DeepSeek 验证显式选择与新安装本地 Skill 的按需加载，并检查明暗主题。按要求在本步停止。
- 已完成 [对话执行、Tool 与 Skill 重设计](conversation-tool-skill-redesign.md) 第二步。聊天页统一走自动工具循环，深度回答独立调整推理强度。工具市场新增 Exa，搜索查询在审批后发送，来源随回复保存。Chrome 使用真实 DeepSeek 验证了当前时间和审批后的 Exa 搜索，刷新可回放两次执行。浏览器回归 10 项通过。本机 MySQL 已升级至 `52f9b8c781ad`，`alembic check` 无漂移。后端 353 项测试、前端 83 项测试、构建及静态检查通过。
- 已完成 [对话执行、Tool 与 Skill 重设计](conversation-tool-skill-redesign.md) 第一步。新运行关联用户及助手消息，工具步骤按消息回放。会话刷新、切换和翻页有覆盖。当时以会话级兼容旧执行记录，现已按用户要求移除该兼容分支。本机 MySQL 已升级至 `ae69f7e9c341`，`alembic check` 无漂移。后端 344 项测试，前端 81 项测试，构建、类型检查、ESLint 和 Ruff 均通过。Chrome 使用模拟模型验收。
- 已精简深度回答时间线：无调用时以浅色文字和依次跳动的三个点显示思考，有调用时可展开过程与单条参数、结果。流式区域仅显示 Markdown 正文。前端 79 项测试、构建和 ESLint 通过；Chrome 用模拟 Agent 事件验证两层展开和键盘操作，真实模型验收未运行。
- 调试日志交付复验通过：后端全量 340 项（覆盖率 92.33%），前端 78 项，构建和静态检查通过。摘要测试显式隔离本机正文开关；生产前端产物无开发日志标记。
- 已在模型适配层记录每次同步、流式与工具轮次，按 `exchange_id` 配对请求、返回、错误或取消。开发环境可用 `LLM_LOG_PAYLOADS=true` 查看消息、工具定义和回复正文，默认摘要，生产环境禁用。后端 122 项相关测试及 Ruff 通过。
- 已补齐 Tool、MCP 和 Skill 管理与运行链路的开发日志，覆盖浏览器请求/响应、技能挂载、后端目录发现/加载、MCP 连接与远端执行。后端 125 项相关测试和前端 78 项测试通过，生产前端产物未发现日志标记。
- 已补齐前端开发日志：页面发送、普通 SSE、会话消息更新、Agent 时间线和 Markdown 渲染。前端 78 项测试、构建、ESLint 通过，生产产物未发现调试日志标记。用法见[前端 README](../frontend/README.md#浏览器调试日志)。
- 新增开发环境 Function Calling、Agent 调度与模型上下文日志。后端按 `APP_ENV=development` 输出摘要，浏览器通过 Vite 开发模式显示 SSE 事件。后端 130 项相关测试和前端 78 项测试通过，生产环境静默行为与前端生产产物已核对。用法见[后端 README](../backend/README.md#开发环境链路日志)。
- 已实现流式 Markdown。流式预览与正式助手消息共用 `MarkdownContent`，按动画帧合并累计文本，正文更新后滚动。切换会话取消待渲染帧，完成事件交接正式消息。新增分片与会话切换测试，前端 78 项测试、构建、类型检查及 ESLint 通过。
- 已为 Function Calling 主链路补充中文注释，覆盖前端入口、工具装配、模型请求与解析、策略审批、参数校验、Skill 控制动作与结果回传。阅读入口见[源码研读指南](code-reading-guide.md)第 5、6 节。
- 已将会话地址绑定到当前数字主键。`/chat` 打开空白草稿，`/chat/:conversationId` 支持直接访问、刷新和浏览器历史。首次发送建库后更新地址，删除当前会话或无法打开时返回空白页，设置浮层保留会话地址。新增 3 项前端路由测试，前端共 76 项通过，构建、类型检查、ESLint 与格式检查通过。
- 新增[源码研读指南](code-reading-guide.md)，串起登录、会话、两类消息链路、Tool/Skill、审批和展示，并在文档导航中提供入口。
- 已整理并保存 [Python Agent 开发面试问答](../面经&八股/Python%20Agent%20开发面试问答.md)。通过 CodeGraph 核对模型客户端、深度回答、工具审批与 SSE 链路，并用 HTTPX 模拟请求验证补全示例。
- 已补充 [Python 面试题与 Agent 岗位面经](../面经&八股/纯%20python/八股.md)，按 9 个技术模块整理 33 道题，保留公开面经和岗位来源。两个 Python 示例均已本地执行验证。

## 第三步涉及文件（2026-11-18）

- 目录、作用域和 API新增 [skill_catalog_service.py](../backend/app/services/skill_catalog_service.py) 与 [目录快照迁移](../backend/migrations/versions/20261117_a638c170ef92_local_skill_catalog.py)。调整 `backend/app/api/{skills,agent,chat}.py`、`schemas/{skill,chat}.py`、`models/user_settings.py`、`config.py` 和 `backend/.env.example`。
- 文件读取和运行调整 `backend/app/skills/{loader,registry,resources}.py`、`providers/filesystem.py` 与 `agent/executor.py`，复用原加载、资源安全检查和执行快照。
- 网页新增 [Skill Store](../frontend/src/stores/skills.ts)，调整 `App.vue`、`api/{skills,agent}.ts`、`stores/chat.ts`、`types/api.ts`、`views/{ChatView,SettingsView}.vue`、`components/chat/{ChatToolbar,ChatComposer,AgentTimeline}.vue` 与 [只读设置](../frontend/src/components/settings/SkillsPanel.vue)。
- 测试新增 `backend/tests/test_local_skill_catalog.py`、`frontend/src/App.test.ts`、`stores/skills.test.ts` 和 `components/settings/SkillsPanel.test.ts`。调整 `backend/tests/test_skills.py`、`frontend/src/{stores/chat,views/ChatView,api/agent}.test.ts`、`components/chat/SkillInteraction.test.ts`，重写 `frontend/scripts/skills-acceptance.mjs`。
- 文档同步 `DESIGN.md`、后端环境示例、前后端 README、API、Skill、研读指南、重设计方案及 ADR。新增 [ADR-0014](adr/0014-local-skill-catalog-and-message-selection.md)，`.gitignore` 排除本地安装目录。

## 本地交付核对（2026-11-16）

- 本地 MySQL 已从 `a1b2c3d4e5f6` 升级到 `9d3e5f7a1b20`：审批指纹、Skill 快照两条迁移已应用，并补充第三条仅同步字段注释的迁移；`alembic check` 报告无漂移。未备份本地库，遵循此前用户指示。
- 本机后端 `/healthz`、`/readyz` 和前端首页均返回 200；新建验收账号下 `/api/settings/model`、`/api/settings/appearance`、`/api/conversations` 均成功。
- **真实模型验收未通过**：当前默认 DeepSeek 返回「模型服务余额不足」，自动模式在模型调用阶段产生 SSE error；手动/关闭场景未继续执行。临时账号及其运行记录已自动清理。新增可复用 `backend/scripts/skill_runtime_acceptance.py`，待可用模型凭据或余额恢复后重跑；不将模拟模型测试等同于真实模型验收。
- 本轮按用户要求在 `codex/skill-tool-system` 整理本地提交：后端能力、前端交互、迁移与验收、架构与状态文档四部分。提交前复跑后端 333 项（覆盖率 92.20%）、前端 73 项测试，构建/类型检查/ESLint/Ruff 均通过；新增文件检查未发现密钥或环境配置文件。未推送远程。
- 后续按「一个完整功能 + 对应测试」推进；每步交付后等待确认。下方 11-14 过程记录中的“迁移尚未应用”是历史状态，以本节为准。

## 本轮接手核对（2026-11-14）

- **本步完成：Skill 文本资源安全读取 + 对应测试**。新增 `app/skills/resources.py`，Provider/Registry 提供有限文本读取，Runtime 控制动作只读已加载技能清单；拒绝路径穿越、符号链接、管道、二进制和超限内容，首次读取固定快照，审批恢复及重复读取复用；同批普通工具延后重新规划。新增 `skill_resource` SSE/历史步骤与前端状态，会议纪要新增参考检查清单。后端全量 **333 passed / 92.20%**，前端 **73 passed**，构建/类型检查/ESLint、后端 Ruff 通过。本步新增后端 24 个用例，扩展前端 Store/组件用例；未新增依赖、表或迁移。限制：Windows 不支持当前安全读取方式时拒绝访问，自建数据库 Skill 无文件资源；未读资源以首次读取内容为准。下一功能建议完成本地数据库升级与实际 Skill 对话闭环验收，等待用户确认。

- **本步完成：Skill 选择与执行过程的前端功能闭环**。修复切换会话时技能列表响应乱序；手动模式由后端读取挂载状态，避免列表请求失败误发 off；发送期间锁定模式与挂载入口，阻止重复发送。时间线显示可读来源，不显示内部版本哈希。新增页面与组件测试 4 项，前端总计 73 项通过，构建/类型检查/ESLint/格式检查通过；同步 DESIGN.md。验证基于组件 DOM 与模拟接口，未进行真实模型端到端或深浅主题浏览器视觉验收，本地数据库迁移仍待应用。下一功能建议完成 Skill 文本资源安全读取及对应测试（阶段 4），等待用户确认。

- **本步完成：前端 Skill 数据链路验证**。通过 CodeGraph `codegraph_explore` 核对页面 → Store → SSE 请求和时间线映射；新增 4 项测试，覆盖 off/manual/auto 请求参数、逐字节 SSE 分片（含中文）、成功/失败事件会话隔离与历史步骤回放。前端 69 项测试、构建（含类型检查）、ESLint 通过；仅格式化 Store 调用，无业务行为调整。既有测试仍输出 localhost:3000 连接受限日志，构建仍有混合导入提示；不等同真实服务联调通过。本步未执行浏览器视觉/E2E 验收或数据库迁移。下一小步建议补页面交互与时间线组件验收，等待确认。

- **最小步交付约定**：后续每步完成一个完整功能及对应测试，不把单独测试拆成一步；汇报后等待用户确认再进入下一功能，除非用户明确要求连续完成。
- **本步完成：阶段 3 后端回归修正**。修复 Skill 加载失败时步骤计数晚于事务提交的问题，并增加下一轮模型调用前重读数据库的断言；修正自动加载测试，将 Runtime 加载控制动作与普通执行工具区分。执行器、Skill、Agent API、MCP Agent、Agent 模型共 64 项测试通过，改动文件 Ruff 检查和格式检查通过。本步未验收前端、未应用数据库迁移，阶段 3 整体验收仍未完成。下一小步建议核对前端模式传递与 Skill SSE 时间线并运行前端检查，等待用户确认。

- Skill 与 Tool System 架构方案已获确认，按文档阶段计划执行。阶段 1 已完成执行安全边界，阶段 2 已完成 Skill Registry/Loader（内置文件与用户数据库两来源、元数据发现、按需正文加载）；阶段 3–4 的 Runtime/SSE/资源读取已实现并通过自动化验证，本地迁移与真实服务联调待验收。详见 [Skill 与 Tool 架构方案](agent-skill-tool-architecture.md)。

- 已完成 Tools、MCP 工具市场和 Skill 的设计评估。44 项相关后端测试通过。后续优先处理 MCP 的接入权限与审批策略，并核对试连和实际运行的凭据传递。应用内 Skill 目前采用自定义格式和手动挂载。

- 本地 MySQL 在本轮改造前已对齐到 `a1b2c3d4e5f6`；本轮新增的审批指纹迁移 `71c2a847d901` 与 Skill 快照迁移 `8c1a4d7e2f90` 尚未应用到数据库。当前只新增迁移文件，没有对本地库执行写操作；本地运行新代码前需完成迁移并验收。

已完成文档梳理与 CodeGraph SSE 静态追踪，基线 `d28d15a`，当前仍包含 Agent、MCP 和技能。交付见 [接手说明](PROJECT_HANDOFF.md)。本轮未复跑运行验收，以下历史阶段记录和测试数字待后续校准。下一步建议验证 SSE 断流与提交边界。

已更新 [AGENTS.md](../AGENTS.md) 的工程目录入口和 CodeGraph 使用规则。用 CodeGraph MCP 验证了普通 SSE 的前端调用示例，文档变更通过 `git diff --check`。

## 1. 现在在哪

**按 [`playbooks/05-development-plan-and-mvp-tasks.md`](playbooks/05-development-plan-and-mvp-tasks.md) 的 11 阶段计划：阶段 1–7 的基础交付已完成**（阶段 4.5「账号体系」作为前置补强也已落地）。本轮在既有 Skill/MCP 交付上落实已确认的架构演进：安全阶段 1 与 Skill Registry/Loader 阶段 2 已完成，Runtime/SSE 阶段 3 与资源读取阶段 4 已通过代码和自动化验证，尚待本地迁移与联调。

阶段口径只以该文件为准。此前本文件里出现的「阶段 2 = MCP client / Agent PoC / Electron 骨架」是我自行归纳的临时说法（源自 `archive/REUSE_CANDIDATES.md` 的「MCP 建议尽早」与 ADR-0001 的 Electron 结论），**与 11 阶段计划无对应关系，已废弃**，勿再引用。

已经有一个能跑、能测、能部署的最小闭环：

- 后端 FastAPI（账号 9 + 对话 7 + 设置 4 + **Agent 2** + 运维 3 个操作；会话与消息按用户隔离落库，每个账号可自带模型配置）
- **阶段 5 的 Agent 循环**：原生工具调用（`calculator` / `now` / `search_conversations` / `rename_conversation`）、最多 8 步、过程落 `agent_runs` / `agent_steps`、SSE 逐步推送
- **阶段 6 的工具治理**：`ToolMeta`/`ToolLevel`/`ToolPolicy`（参数规则、日预算）+ `agent_approvals` 审批（写/外网工具挂起等确认，单 run ≤5 次、同工具被拒 ≤2 次）
- **阶段 7 的 MCP 工具市场**：内置 7 条清单 + 自定义接入，`stdio`/`http` 两种传输，连接池（工具清单 5 分钟、空闲 15 分钟回收），MCP 工具一律 `EXTERNAL` + 审批
- **阶段 7 的技能包**：内置 3 个（代码审查 / 会议纪要 / 决策简报）+ 账号自建，挂到会话后作为 system 消息注入本次运行；工具白名单只做减法，不提权
- 前端 Vue 3：登录/注册页 + 聊天界面（会话列表 + 消息区 + SSE 逐字渲染 + Markdown + 「深度回答」开关与执行时间线），未登录只能进登录/注册；13 项账号 + 10 项对话 + **10 项 Agent** E2E 全过
- 数据库迁移（Alembic）、依赖锁定（uv / pnpm）、质量门禁（ruff / ESLint / pytest / Vitest / CI）、容器化（Docker Compose）

> 商品 / 分类 / 概览页与对应后端接口已于 2026-11-08 整体归档到 `archive/product-admin/`（`git mv`，历史保留），应用层不再暴露这些路由。

## 2. 已完成

| 日期 | 交付 | 证据 |
|---|---|---|
| 11-14 | **Skill/Tool 架构演进阶段 1：执行安全边界**：审批决定原子写入，恢复时核对待执行步骤、工具定义指纹并重新检查 Policy；MCP 工具 Schema 做本地检查，忽略远端只读提示的授权效力；运行与试连共用解密凭据解析；未知状态超时终止后续循环。针对性测试 40 项通过；迁移尚未应用到本地库 | [Skill 与 Tool 架构方案](agent-skill-tool-architecture.md) §12；`backend/tests/test_agent_executor.py`、`test_agent_policy.py`、`test_mcp_source.py` |
| 11-14 | **Skill/Tool 架构演进阶段 2：Skill Registry/Loader**：以请求级 Registry 聚合内置文件与用户数据库 Provider，发现只返回元数据，按稳定 key 加载正文；内置优先、来源隔离、坏文件隔离和内容版本校验。24 项 Skill 测试通过 | [Skill 与 Tool 架构方案](agent-skill-tool-architecture.md) §12；`backend/app/skills/`、`backend/tests/test_skills.py` |
| 11-11 | **阶段 7：技能包（T1–T6）**：`app/skills/`（`SKILL.md` frontmatter 解析 + 3 个内置技能）、`skills` 表与迁移 `a1b2c3d4e5f6`、`conversations.skill_slug`、`build_system_prompt()` 注入 + `ToolRegistry.only()` 收窄、5 个接口 + `PUT /api/conversations/{id}/skill`、设置页「技能」节与工具条技能胶囊、`acceptance:skills` 7 项；后端 296 例 / 93.36% | [skills.md](skills.md)、[ADR-0013](adr/0013-skills-as-method-packages.md)、[api.md](api.md) §6.6；截图 `docs/images/ui-19-skills.png`、`ui-20-skill-mounted.png` |
| 11-11 | **阶段 7：MCP 客户端与工具市场（T1–T7）**：官方 `mcp==2.3.0` + 线程内监督协程的同步门面、`mcp_servers` 表与迁移 `4f9edca19113`、内置 7 条市场清单、连接池与 `mcp__<slug>__<tool>` 装配（`EXTERNAL` 一律审批）、6 个接口、工具市场页（筛选 / 自定义接入 / 试连 / 启停 / 移除 / 工具清单）、`acceptance:mcp` 11 项、`mcp__*` 审批联调 3 例；后端 274 例 / 93.21%，前端 64 例 | [mcp.md](mcp.md)、[ADR-0012](adr/0012-mcp-client-uses-official-sdk.md)、[api.md](api.md) §6.5；截图 `docs/images/ui-15-tool-market.png`、`ui-16-tool-market-installed.png` |
| 11-11 | **文档与代码精简**：删掉 3 份过程报告、`docs/setting design.md`、`docs/plan/TASKS.md`（共 976 行）；`TECHNICAL_DEBT.md` 只留当前未解决的 10 条；清空开发库 112 个演示账号（新增 `backend/scripts/cleanup_demo_accounts.py` + `make clean-demo`）；`:root` 兜底 token 与 `theme/pine.ts` 对齐 | [docs/README.md](README.md) §5 维护规则、[DESIGN.md](../DESIGN.md)、[TECHNICAL_DEBT.md](TECHNICAL_DEBT.md) |
| 11-11 | **`DESIGN.md` 重写为设计规范**：配色 18 个语义 token + 四套主题主色、字体 3 字族 9 档字号、间距与骨架尺寸、组件（按钮 6 型 / 卡片 / 导航 / 菜单 / 消息 / 状态）与三条硬规则、§9 变更流程、§10 自查清单；`AGENTS.md` §2.5 规定「UI 改动必须遵循并更新 DESIGN.md」 | [DESIGN.md](../DESIGN.md)、[design/README.md](design/README.md) |
| 11-11 | **阶段 6：工具生态与权限治理（T1–T7）**：`ToolMeta`/`ToolLevel`/`ToolRegistry` + `ToolPolicy`（参数规则、日预算）、`agent_approvals` 四态审批与迁移 `2c0c6e7b3613`、执行器挂起与 `resume_run` 重放、写工具 `rename_conversation`、6 个接口、前端 `ApprovalCard` 与设置页「工具」节、`acceptance:tools` 9 项；后端 230 例 / 93.37%，前端 64 例 | [tools.md](tools.md)、[ADR-0011](adr/0011-tool-permissions-and-approvals.md)、[api.md](api.md) §6.4 |
| 11-10 | **阶段 5：Agent 执行循环 + Tool Calling（T1–T7）**：模型层原生 `tools`/`tool_calls`（Fake 剧本可重放）、两表 `agent_runs`/`agent_steps`、只读工具层与注册表、执行器（8 步 / 2s 工具超时 / 连续 3 次失败中止 / 断流回滚）、`POST /agent/stream` + `GET /agent/runs`、前端「深度回答」开关与执行时间线（刷新可回放）；后端 204 例 / 93.22%，前端 59 例，Agent E2E 10 项 | [agent.md](agent.md)、[ADR-0010](adr/0010-agent-execution-loop.md)、[api.md](api.md) §6；截图 `docs/images/agent-timeline.png` |
| 11-10 | **主题随账号同步（T-FE-03 收尾）**：`user_settings` 加 `theme_id` / `theme_mode` + `GET|PUT /api/settings/appearance`；登录后账号优先、切换时本地先生效再异步写回；顺带用 `model_configured` 列修掉「只存主题被当成配过模型」的问题 | [ADR-0009](adr/0009-per-user-model-settings.md)、[api.md](api.md) §4.5；后端 159 例 / 94.42%，前端 59 例，设置 E2E 15 项 |
| 11-09 | **设置模块（T-FE-02）**：模型接入（Key Fernet 加密存 `user_settings`、界面只显示末四位、可测试连接）/ 账号资料（改显示名、改密码踢其他设备）/ 登录设备（撤销）/ 外观 / 数据管理（导出 JSON·Markdown、注销账号）；聊天按账号取模型，未配置回落环境变量 | [ADR-0009](adr/0009-per-user-model-settings.md)、[api.md](api.md) §3.8–3.9、§4；后端 148 例 / 94.22%，前端 54 例，设置 E2E 13 项 |
| 11-09 | **前端按 `DESIGN.md` 重构全部页面**：外壳（264 侧栏 + 48 顶栏 + 1080 内容区）、对话（720 阅读列 + 气泡 + 输入盒）、登录/注册（400 卡片 + 衬线标题 + logo）、设置（200 导航 + 560 表单）；会话状态提升到 `stores/chat.ts`；`styles/index.css` 收敛为 token 兜底 + reset + Element Plus 映射；接入 logo/favicon/manifest | `DESIGN.md`、[design/README.md](design/README.md)、截图 `docs/images/ui-0*.png`；前端 50 例、E2E 13+10 全过 |
| 11-09 | **账号体系**：注册/登录/登出/我的设备/改密 + 服务端会话（HttpOnly Cookie，库里存 SHA-256）+ Argon2id + `conversations.user_id` 数据隔离（越权一律 404）+ 前端登录守卫与 401 统一跳转；后端 123 例 / 93.37%，前端 50 例（含组件 11），账号 E2E 13 项 | [auth.md](auth.md)、[ADR-0008](adr/0008-auth-and-session.md)、[api.md](api.md) §3 |
| 11-08 | **改名为 My Agent 并归档商品模块**：`product-admin` → `my-agent`（包名/标题/Compose 项目名/数据库名），商品·分类·概览的前后端代码与需求/设计/验收文档整体迁到 `archive/product-admin/`，新增迁移 `17fe0c7d2cb5` 删除 `products`/`categories` 两表；前后端只保留对话链路 | `archive/product-admin/README.md`、[ADR-0007](adr/0007-archive-product-module.md) |
| 11-08 | **接入真实模型**：DeepSeek（OpenAI 兼容）跑通本地与容器；修 `NO_PROXY=[::1]` 导致 `httpx.InvalidURL` 启动崩溃、补 402 余额不足映射、测试强制 fake 隔离 | [backend/README.md](../backend/README.md)「接入真实模型」、[api.md](api.md) §4.6 |
| 11-08 | **开发体验**：`scripts/dev.sh` 一条命令起前后端（都带热更新）；README 写明「日常开发用本地、容器只做交付验证」；对话页助手消息支持 Markdown 渲染（`markdown-it` + `DOMPurify`，路由级懒加载） | `frontend/src/utils/markdown.ts`、[chat.md](chat.md) §6、[toolchain.md](toolchain.md) |
| 11-08 | **目录扁平化**：`python/fastapi-demo/` → `backend/`、`fullstack/product-admin/` → `frontend/`（`git mv` 保留历史），同步 CI 路径、Compose 上下文、pre-commit 正则、`.vscode`、全部文档与角色卡；E2E 复跑 18/18 + 10/10 | 提交见 `git log` |
| 11-08 | **阶段 4 对话功能**：会话/消息落库 + 模型抽象（fake/openai）+ 会话 CRUD + 同步与 SSE 两种发消息 + `/chat` 页面；后端 120 例 / 87.87%，前端 26 例，E2E 10 项 | [chat.md](chat.md)、[api.md](api.md) §4、[ADR-0006](adr/0006-llm-client-and-chat-storage.md) |
| 11-07 | **名称空白校验统一**：分类改名、商品改名与新增同规则（先 strip 再判空，纯空白 400），补 5 个用例 | T-22 已解决（相关接口已归档） |
| 11-07 | **文档治理四批 + 终检**：39 份文档全量审查（22 条事实陈旧、11 处职责重叠、6 处缺失），四批重构 + 终检（过程报告已随 2026-11-11 精简删除，git 历史可查） | 本次提交 |
| 11-07 | **测试基线**：后端 55 例 + 覆盖率门槛 80%（实测 85.38%），前端 Vitest 17 例 | [ADR-0005](adr/0005-testing-baseline.md) |
| 11-07 | **容器化**：多阶段镜像 + Compose（db/backend/frontend/可选 Caddy）+ `/healthz` `/readyz` | [ADR-0004](adr/0004-deployment-docker-compose.md)、[deploy.md](deploy.md) |
| 11-07 | **uv 统一依赖**：`pyproject.toml` 唯一来源 + `uv.lock`，CI 用 `uv sync --frozen` | `a09763d` |
| 11-07 | **前端轻量门禁**：ESLint 10 + Prettier + CI 前端 job | [ADR-0002](adr/0002-frontend-quality-gate-lite.md) |
| 11-07 | **Alembic 接管 schema**：首个 revision `2a89b3237f54` | [ADR-0003](adr/0003-database-migrations-alembic.md) |
| 11-06 | **商品管理网站 v1**：需求 → 设计 → 前后端 → 18 项验收（模块已于 11-08 归档） | [交付说明（归档）](../archive/product-admin/docs/delivery.md) |
| 11-05 | 后端工程化：ruff / pytest / pre-commit / CI / Makefile | `backend/README.md` |

## 3. 下一步

### 3.1 阶段对照表（严格按 11 阶段计划）

| # | 阶段 | 状态 | 证据 / 缺口 |
|---|---|---|---|
| 1 | AI 开发基建 | ✅ | `AGENTS.md`、`agents/`、`.agents/skills/`、`adr/`、`playbooks/` |
| 2 | 前后端项目骨架 | ✅ | `backend/`、`frontend/` |
| 3 | 基础 API 和数据库 | ✅ | 对话 7 个操作 + 3 个探针、Alembic 迁移、MySQL（商品/分类接口已归档） |
| 4 | **LLM 接入与基础对话** | ✅ | [chat.md](chat.md)：T1 表结构 / T2 模型抽象 / T3 会话 CRUD / T4 同步发消息 / T4b SSE 流式 / T5 `/chat` 页面 / T6 文档；已接 DeepSeek 实测 |
| 4.5 | 账号体系（补强） | ✅ | [auth.md](auth.md)：users/sessions 两表 + Argon2id + 服务端会话 + 用户级数据隔离 + 登录页/守卫 |
| 5 | **Agent 基础执行循环 + Tool Calling** | ✅ | [agent.md](agent.md) + [ADR-0010](adr/0010-agent-execution-loop.md)：T1 原生工具调用 / T2 两表 / T3 工具层 / T4 执行器 / T5 流式接口 / T6 前端时间线 / T7 文档与 E2E；后端 204 例 / 93.22%，Agent E2E 10 项 |
| 6 | **工具生态与权限治理** | ✅ | [tools.md](tools.md) + [ADR-0011](adr/0011-tool-permissions-and-approvals.md)：注册表（`ToolSource`）、三级权限、审批暂停/恢复、工具设置与统计接口、前端审批卡片与「工具」节；后端 230 例 / 93.37%，前端 64 例，`acceptance:tools` 9 项 |
| 7 | Skill 和 MCP | ✅（基础交付）/ 演进实施中 | MCP 工具市场与 Skill 包已交付；当前按 [Skill 与 Tool 架构方案](agent-skill-tool-architecture.md) 补齐渐进式加载和运行边界 |
| 8 | RAG 和 Memory | ⬜ | 依赖 7 |
| 9 | Agent 应用功能完善 | ⬜ | 依赖 8 |
| 10 | 桌面端集成 | ⬜ | 按 [ADR-0001](adr/0001-desktop-shell-electron.md)（Electron + PyInstaller onedir） |
| 11 | 部署、测试和发布 | ⚠️ 部分 | 容器化 ✅、测试基线 ✅、CI ✅；**发布流程（版本号/镜像归档/回滚）未做** |

### 3.2 阶段 5 的形状（已落地，设计见 [`agent.md`](agent.md)）

四种主流运行架构（单 agent 工具循环 / 图状状态机 / SDK Runner / 多 agent 编排）里**只实现第一种**：
模型 ↔ 工具往返，没有 `tool_calls` 即收尾。护栏固定为最大 8 步、单工具 2s、连续 3 次同类失败中止。
状态落 `agent_runs` + `agent_steps` 两张表，前端时间线可回放；工具 v1 只有 `calculator` / `now` / `search_conversations`，全部只读。
不引 LangGraph / OpenAI Agents SDK / CrewAI，理由与被否方案见 [ADR-0010](adr/0010-agent-execution-loop.md)。

**为什么不是「直接用 ReAct」**：ReAct 是提示词范式（Action 是自由文本，靠正则解析），原生工具调用是它的生产级实现——
动作变成结构化 JSON、参数由 pydantic 校验、错误用 `ok:false` 回灌、终止由 `tool_calls` 是否为空判定。对照表见 [agent.md](agent.md) §2.1。

**执行进度**：T1 模型层 ✅（`chat_with_tools` + Fake 剧本）；T2 两表 ✅（`d8812afe7ea7`）；T3 工具层 ✅（3 个只读工具 + 注册表）；T4 执行器 ✅（`executor.py`，事件流见 api.md §6.1）；T5 接口 ✅（`POST /agent/stream`、`GET /agent/runs`）；T6 前端 ✅（「深度回答」开关 + 执行时间线，刷新回放）；T7 文档与 E2E ✅（`pnpm acceptance:agent` 10 项）。

### 3.2b 阶段 4 的接入方式（已定，设计见 [`chat.md`](chat.md)）

**执行进度**：T1 数据模型 + 迁移 ✅（revision `b1b54e93e0ca`，`conversations` / `messages` 两表已建，`alembic check` 无漂移）；T2 模型抽象层 ✅（`FakeLLM` 默认 + `OpenAICompatibleClient`，`httpx.MockTransport` 覆盖 4 类错误映射）；T3 会话 CRUD ✅（5 个端点，[api.md](api.md) §4）；T4 发消息 ✅（`POST /{id}/messages`，同事务写两条消息、失败整体回滚、首条消息自动命名、上下文最近 20 条 + system，见 api.md §4.6；后端 104 例 / 覆盖率 87.59%）；T5 前端 `/chat` ✅（会话列表 + 消息区 + 输入框，Enter 发送、自动命名、刷新保留、重命名/删除，前端 26 例）；T4b 流式 ✅（`POST /{id}/messages/stream`，SSE 事件 meta/delta/done/error，先校验后开流、流结束才提交、断开即回滚，见 api.md §4.7；后端 120 例 / 覆盖率 87.87%；`pnpm acceptance:chat` 10 项 E2E 全过）；T6 文档 ✅

1. **先 C 打底**：定义 `LLMClient` 协议 + 一个返回固定文本的 `FakeLLM`，在没有 API key 的情况下把「请求 → 流式输出 → 错误处理 → 测试」整条链路立起来，可独立验证。
2. **随后接 A**：用 OpenAI 兼容 API（`base_url` + `api_key`，走 `.env`），把 `FakeLLM` 换成真实现，其余代码不动。

不做 B（本地 Ollama）作为主线：需要拉数 GB 模型，且与「应用层 Agent」目标无关；如后续要离线演示再作为可选实现接入。

### 3.3 进入阶段 4 前要满足的门槛

| 门槛 | 判定标准 | 现状 |
|---|---|---|
| 文档可信 | `docs/` 无已知过期事实 | ✅ 2026-11-11（精简掉 3 份过程报告与 2 份过期设计稿，见本次提交） |
| 基线可跑 | `make check` ≥80%、`pnpm lint && pnpm test && pnpm build` 全过 | ✅ 2026-11-09（后端 123 passed / 93.37%、前端 50 passed） |
| 存储明确 | 对话数据存哪（新表 or 不落库）、是否需要会话 ID | ✅ 已定：`conversations` / `messages` 两表落库（[ADR-0006](adr/0006-llm-client-and-chat-storage.md)） |

剩余技术债见 [`TECHNICAL_DEBT.md`](TECHNICAL_DEBT.md)：P0/P1 已清空，剩下以 P2 为主（日志规范 T-23、Element Plus 体积 T-21）。

## 4. 关键决策

完整理由见 [`adr/`](adr/README.md)，这里只列「选了 A 不选 B」的结论：

| 决策 | 选择 | 一句话理由 |
|---|---|---|
| 后端框架 | FastAPI + SQLAlchemy 2.0 + MySQL | 类型友好、OpenAPI 自动生成 |
| 后端分层 | api / schemas / services / models / common | 控制器不写 SQL，业务可单测 |
| 前端 | Vue 3 + TS + Vite + Element Plus | 与设计稿还原度高、组件齐 |
| 通信 | REST + 统一响应 `{code,message,data}` | 简单，任意客户端可消费 |
| 鉴权 | 服务端会话 + HttpOnly Cookie + Argon2id，自研 `app/auth/` | 能即时踢下线、不把 token 暴露给 JS；不引 fastapi-users 以免为单人项目加一层抽象（ADR-0008） |
| 数据库迁移 | Alembic | 结构变更要能复现与回滚（ADR-0003） |
| 依赖管理 | uv（后端）+ pnpm（前端） | 锁定完整依赖树，CI 可复现 |
| 质量门禁 | 后端严（ruff+pytest+80% 覆盖）、前端轻（ESLint recommended + Vitest 纯逻辑） | 单人项目，摩擦要小于收益（ADR-0002） |
| 部署 | Docker Compose（db/backend/frontend/可选 Caddy） | 一条命令起全套（ADR-0004） |
| 桌面端外壳 | Electron + PyInstaller `--onedir` | 复用 Node 工具链，拉起本地后端最省事（ADR-0001） |
| Agent 框架 | **未决策**（MCP Python SDK 先 client，OpenAI Agents SDK 先 PoC） | 需求未定，先走最小可验证路径 |

## 5. 已知问题

按优先级见 [`TECHNICAL_DEBT.md`](TECHNICAL_DEBT.md)（当前 10 条，P0 已清空）。最该处理的五条：

1. **T-11** — E2E 直接打开发库，跑一次就留一批演示账号；临时用 `make clean-demo` 收尾（根治要独立测试库）
2. **T-04** — 后端测试用内存 SQLite，MySQL 专有行为（外键级联、排序规则、并发可见性）没有自动化覆盖
3. **T-06** — 统一响应的 `data: Any` 让 OpenAPI 里没有具体结构，前端只能手写类型
4. **T-17** — CORS 写死 localhost 且 `allow_methods=["*"]`，上真实域名要改代码
5. **T-23** — 后端日志无统一配置、无 request id，排障只能靠 uvicorn 默认输出

## 6. 阻塞与环境限制

无硬阻塞。以下是环境级限制，会在特定任务变成阻塞：

- **Docker**：本机 CLI 无 compose 插件、daemon 默认未运行；本轮用 colima（`HOME=/tmp/home`）验证过容器化，日常部署需自行启动 Docker Desktop/colima
- **gh 凭据**：`~/.gitconfig` 已配 `gh auth git-credential`，但 token 缺 `workflow` scope 时需要设备授权（见 T-13）

## 7. 仓库状态

- 目录结构：`backend/`（后端）、`frontend/`（前端）、`docs/`（文档）、`deploy/`（Caddy）；`agent/`、`desktop/` 为后续阶段预留
- 最近提交：见 `git log --oneline -5`
- CI：只改 `docs/` 的提交不会触发 CI（`ci.yml` 的 `paths` 只含 `backend/**`、`frontend/**`、自身）
- 文档：`docs/` 下 38 份 markdown（人读 / AI 向两层，规则见 `docs/README.md` §3）；全仓相对链接 0 失效
- 测试基线：后端 231 passed / 93.39%；前端 64 passed；E2E 五套（chat 10 / agent 10 / auth 13 / settings 15 / tools 9）
- 容器验证：三容器 healthy，`http://localhost:8080` 首页、`/chat`、`/api/conversations`、`/healthz`、`/readyz` 均 200
