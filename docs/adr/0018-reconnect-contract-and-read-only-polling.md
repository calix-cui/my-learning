# ADR-0018 断线核对契约：按 request_id 认领、只读续查、不做真续跑

- 状态：已接受
- 日期：2026-11-18
- 关联：[ADR-0016](0016-chat-execution-state-and-recovery.md)（断流后的执行状态）、[ADR-0017](0017-chat-store-module-boundaries.md)（Store 边界）

## 背景

ADR-0016 把断流处理定成「不猜、只读核对」，但当时的契约回答不了两个具体问题：

1. **这条消息到底发出去了吗**：如果连 `run_started` 都没收到，前端手里只有一个自己生成的 `request_id`，历史页也没有任何东西可查。旧实现只能说「结果未知，请刷新核对」，然后靠用户自己数消息。
2. **为什么没有答复**：运行摘要里没有 `error_message`，服务端已经算出来的「运行被中断」「模型没有给出答复」「连续工具失败」等原因传不到界面，前端只能显示自己编的通用文案。

此外，判断「还在跑吗」和「有没有新步骤」在旧契约下要两个请求、且每次拉全量步骤，断流时轮询成本高。

## 决定

### 1. 摘要补齐三项，只读不改写

`GET /api/conversations/{id}` 返回的 `runs[]` 增加 `request_id`、`error_message`、`finished_time`。这三项都是既有列（`agent_runs.request_id`、`error_message`、`finished_time`），只是没透出，所以本决定不含迁移。

`request_id` 的列与唯一约束 `uq_agent_runs_request` 早在 `models/agent_run.py` 就存在，重复提交的 409 也早已按它去重，本决定只是把同一个标识暴露给前端做**读取侧**的认领。

### 2. 两个只读入口

- `GET /api/agent/runs/{run_id}`：单点查运行详情（含全部步骤），与分页无关。历史页分页可能不含这次运行，审批卡片因此可能复原不出来，单点查解决这个问题。
- `GET /api/conversations/{id}/agent/runs?request_id=<uuid>`：按 `request_id` 认领。**查不到返回 404「这次提交还没有落库，可以重新发送」**——这是唯一可以据此放心重发的信号。

### 3. 步骤接口带运行状态，支持增量

`GET /api/agent/runs/{run_id}/steps?since_seq=N` 的响应从数组改成对象：`items`（只含 `seq > N` 的可见步骤）+ `status` / `visible_step_count` / `error_message` / `finished_time`。一次请求同时回答「还在跑吗」和「有新步骤吗」，没有新步骤时响应体很小。前端继续读 `data.items`，改动局限在类型与状态读取。

### 4. 前端只读续查，不重发

断流后点「重新核对状态」时：

- 知道 `run_id`：直接查历史与步骤，和 ADR-0016 相同。
- 只知 `request_id`：先按 `request_id` 认领；认领到就采用它的运行号再核对，认领不到（404）就明确提示「没有落库，可以重新发送」并解锁。
- 认领到的运行仍是 `running`：按 1.5 秒、最多 20 次轮询增量步骤，跑到终态再刷新一次正文。轮询**不 await**——核对按钮不该替用户等满 30 秒，后台轮询失败也只是停在断开态。
- 服务端已在认领时报告失败：`error_message` 直接进恢复提示，不再显示前端编的通用文案。

### 5. 不做「真续跑」

不提供 `POST /api/agent/runs/{id}/resume` 让断开的运行接着生成。理由：

- 运行与请求线程是同一件事：`executor.py` 的 `_finish_interrupted_run` 在连接断开时就把 run 置为失败（`_fail(db, run, "运行被中断")`），`tests/test_agent_executor.py` 已锁定这个行为。
- `resume_run` 只服务审批检查点：它依赖 `run.approval_context` 恢复工具调用，不是一个通用的「从最后一条消息继续」入口。
- 真要续跑就得把执行从请求线程里拿出来（后台任务 + 消费者 + 取消），并把已经花掉的 token 再花一遍，属于另一次执行模型改造。

因此「断线后自动接着生成」记入技术债（T-29），等执行模型改造时一起做。

## 后果

- 断线后能准确回答「发出去了吗、为什么没答复」，409 变得可解释，重发不再靠猜。
- 失败文案统一来自服务端，前端不再维护一套平行的原因表。
- 每次核对最多多一次 `request_id` 查询；轮询是增量读，代价随步骤数而非总字数增长。
- 契约多了一个 404 语义（「还没落库」），前端必须把它和「运行不存在」区分开：同为 404，文案由服务端给出，前端只展示不判断。
- 步骤接口的响应结构变化对旧调用方是破坏性的，但当时只有本站前端在读 `data.items`，属于可控范围内的一次性调整。

## 验证

- 后端 `tests/test_agent_api.py` 13 → 18 项：运行详情字段与失败原因、越权 404、按 `request_id` 查到/查不到、增量步骤与 `visible_step_count` 不变。
- 前端 `stores/chat/execution.test.ts` 新增：按 `request_id` 认领后不重发、404 时提示可重发并保留草稿、运行中轮询到终态才恢复正文（增量参数为 `since_seq`）。
- 浏览器验收 `pnpm acceptance:recovery` 12 → 20 项：新增「连 `run_started` 都没收到」的场景——历史页此刻什么都没有，只能靠 `request_id` 认领，且全程只有一次 POST。
- 真实模型联调（真实 DeepSeek + 真实 MySQL，2026-11-18）：`backend/scripts/check_reconnect_live.py` 20 项全过（断流被记成失败、失败原因来自服务端、按 `request_id` 认领、404 文案、详情、增量读、完整流式跑通）；`frontend/scripts/chat-live-acceptance.mjs` 14 项全过（真实 Chrome 里发消息→刷新断流→恢复提示→核对后显示「运行被中断」且不重发）。
- **联调发现并修掉一个真 bug**：断流时请求依赖已关闭 Session，生成器 `finally` 里的 `_finish_interrupted_run` 读 `run.status` 抛 `DetachedInstanceError` 并被静默吞掉，收尾被跳过，运行永久停在 `running`（同一会话再发消息被 409 锁死）。修复：`LoopState` 记 `run_id`，收尾失败时回落到独立 Session 的 `_mark_interrupted(run_id)`。单测 `test_stream_closed_after_session_teardown_still_marks_failed` 锁定；未打补丁时该用例报 `ObjectDereferencedError`。
- 实测：后端全量 356 passed（失败项均为沙箱起不了 MCP echo 子进程）；前端 144 项（23 文件）、ESLint、`vue-tsc`、生产构建通过；三组浏览器验收 20 / 10 / 11 项全通过。

## 2026-11-19 补充：手动联调暴露的三处问题

真实模型手动联调（用户自己操作）又发现三种「核对也无解」的情况，逐条补上：

1. **进程重启留下的运行**。运行只存在于服务进程的请求线程里；进程一重启（改代码热重载、容器重启），`running` 行就再没人推进，会话被永久挡住。现在服务启动时把仍是 `running` 的运行标成失败（`executor.remove_stale_runs()`，文案「服务重启，这次运行已中断」），`waiting_approval` 不动——那是活着但暂停。**已知假设：单进程部署**，多 worker 要改成按进程心跳判断（记技术债）。
2. **轮询跑满仍不终态**。只读轮询 20 次（约 30 秒）后服务端还报 `running` 时，界面给出「不再等待」：只把本地判定改成失败并解锁发送，不发请求、不动服务端。服务端真跑完时下一次读历史照常显示正文——这条路径不追求「猜对」，只保证会话不会永久锁死。
3. **上游把错误写进 SSE 帧**。DeepSeek 等上游在 HTTP 200 的流里返回 `{"error": {...}}` 时，原来只会得到「模型返回格式无法解析」，看不出是模型不支持工具调用还是额度用尽。现在识别这种帧并把上游原话（截断 120 字）作为 502 文案，同时记 warning 日志；`_stream_tool_round` 的宽泛 `except ValueError` 也不会再吞掉这类业务错误（`BusinessError` 继承 `ValueError`）。
