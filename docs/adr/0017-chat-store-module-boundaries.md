# ADR-0017 聊天 Store 的模块边界

- 日期：2026-11-18
- 状态：已接受
- 延续：[ADR-0016](0016-chat-execution-state-and-recovery.md)

## 背景

第三步结束时，`frontend/src/stores/chat.ts` 仍是 874 行的单个 Pinia setup store，闭包里同时装着：会话列表与当前 id、账号代次、每个会话的运行时状态 `threads` Map、历史分页与刷新对齐、步骤详情读取、发送与审批的状态机接线，以及约四十个对外派生值。分页逻辑想单独测，就得先把整个 store 挂起来再 mock 三类接口。

## 决定

按「谁拥有状态」拆成三个模块，`chat.ts` 只做组合根：

| 模块 | 拥有 | 不碰 |
| --- | --- | --- |
| `chat/threads.ts` | `ChatThread` 与 `threads` Map、取消句柄 `controllers`、步骤请求去重 `stepRequests`、建会话去重 `creations`、`threadOf`/`moveThread`/`disposeThread` | 接口、当前打开哪个会话 |
| `chat/conversations.ts` | 列表行、`activeId`、`draft`、`loadingList`/`loadingMessages`、账号代次、`patch`/`sortByRecent`、拉列表、建会话、改名、删除 | 消息与执行状态 |
| `chat/history.ts` | 所有读路径：历史页合并、刷新对齐、分页、步骤详情与审批重查 | 当前是哪个会话 |
| `chat.ts` | 选择当前会话（`openConversation`/`startNew`）、串发送与审批、派生视图值、`reset` | 具体存储与请求细节 |

模块用工厂函数 `createX(deps)` 注入依赖，不各自建 Pinia store。`history` 只拿到 `threads` 与 `patchConversation`（回写会话标题），`conversations` 只拿到 `threads` 与 `onActiveRemoved`（删掉当前会话时回到草稿态）。读函数一律显式接收 `(id, thread)`，模块内部不读「当前会话」。

## 理由

- **依赖方向单一**：`conversations` 建会话时要把草稿线程搬到新 id，`history` 刷新时要回写标题——两者互相需要对方的能力。工厂注入让 `chat.ts → 三个模块 → threads` 单向，没有 import 环，也不需要延迟 import 解环。
- **可以在不挂 store 的情况下测**：分页、去重、释放都能直接构造模块验证；现有 store 级测试仍走 `setActivePinia`，不重写。
- **工厂而非组合式函数**：`useChatScroll` 一类要绑定组件生命周期与 DOM，属于另一类问题（见下）；模块本身不依赖组件实例，用普通闭包最直白。
- **不新增对外字段**：拆完 store 返回的接口名与数量不变，`ChatView` 无需改动。

## 取舍

行数从 835 增到 990（475 + 195 + 199 + 121），多一层间接；改状态前要先判断它属于哪个模块；`ensureConversation` 仍然横跨 `conversations` 与 `threads`（建会话后搬线程），是这组边界上最不干净的一处。为此付出的代价被认为小于「一个 800 行闭包里所有东西都能改所有东西」。

## 不做

- 路由（`useChatRoute`）当时仍在 `ChatView`：绑定组件生命周期和 URL，收益要到页面层才能兑现。随后它与滚动一起被提取成 `composables/useChatScroll.ts` / `composables/useChatRoute.ts`（见文末补充）。
- 不把 `feed.ts` / `execution.ts` / `events.ts` 再拆（第三步已就位），也不换响应式方案——仍是 `reactive Map` 加 `WeakMap` 旁表。
- 不为拆而拆地新建 Pinia store：多实例、跨 store 循环依赖都会立刻反噬。

## 验证

`pnpm test` 126 项（21 文件）、`pnpm lint`、`vue-tsc --noEmit`、`pnpm build` 全通过；`pnpm acceptance:recovery` 12 项在真实 Chrome 里仍全通过（模拟断流 → 核对 → 恢复）。

## 补充（2026-11-18）

滚动与帧合并随后从 `ChatView.vue` 提取到 `composables/useChatScroll.ts`，地址同步再提取到 `composables/useChatRoute.ts`（`ChatView.vue` 315 → 233 行，只剩 Skill 参数与提交参数）。两者都不属于 Store：DOM 测量、`requestAnimationFrame`、模板 ref 与 `useRoute`/`useRouter` 都只能在组件 setup 里取，放进模块工厂要么多带一套路由依赖，要么把 URL 概念泄进 Store。

两个方向的同步都带 `name === 'chat'` 守卫（地址 → `openConversation`/`startNew`，状态 → `router.replace`）：离开对话页时（登录页、退出过程中的地址变更）不该被地址逻辑写回对话地址。设置浮层只在对话地址上加 `?settings=1`，`name` 不变，所以会话 id 自然保留（浏览器验收第 9 项）。滚动策略（切会话无条件贴底、流式只跟随仍在底部的用户、翻页补偿高度）属于局部且易改的展示规则，记录在 [`docs/chat.md`](../chat.md) §9，不为它单独开 ADR。

验证：`pnpm test` 142 项（23 文件）、`pnpm acceptance:scroll` 10 项、`pnpm acceptance:route` 11 项、`pnpm acceptance:recovery` 12 项。
