# ReAct-MCP

用 TypeScript 从零实现一个 **ReAct Agent + MCP 工具接入** 的学习子工程，用来把主仓库 `my-learning` 里的 Agent 概念（循环、工具、检索、审批）用最小代码走一遍。

它是仓库里的**独立工程**：不参与 `backend/`、`frontend/` 的构建、部署与验收，也不被主应用的测试扫描。

## 当前状态

只有工程骨架：`package.json`、`tsconfig.json`、`.env.example` 已就位，`src/` 下是待实现的占位文件（仅有文件头注释）。**还没有可运行代码**，实现顺序见「下一步」。

## 目录结构

| 路径 | 职责 | 状态 |
|---|---|---|
| `src/index.ts` | CLI 入口：读配置、建 Agent、跑一轮对话 | 待实现 |
| `src/Agent.ts` | ReAct 主循环：Thought → Action → Observation，含最大轮次与运行轨迹 | 待实现 |
| `src/ChatOpenAI.ts` | 模型客户端：走 OpenAI 兼容协议（`base_url` + `model`） | 待实现 |
| `src/MCPClient.ts` | MCP 客户端：启动 stdio server、`tools/list`、`tools/call` | 待实现 |
| `src/VectorStore.ts` | 向量存储：先内存实现，接口留出持久化 | 待实现 |
| `src/EmbeddingRetriever.ts` | 检索：把历史/文档切片后按相似度取回 | 待实现 |
| `src/utils.ts` | 日志、重试、JSON 解析等通用函数 | 待实现 |
| `output/` | 运行轨迹与中间结果（已忽略，不入库） | — |

## 环境要求

- Node.js >= 20（本机验证用 24）
- pnpm（主仓库统一用它；npm 亦可）

## 快速开始

```bash
cd ReAct-MCP
pnpm install            # 只装 typescript / tsx / prettier 等开发依赖
cp .env.example .env    # 填 OPENAI_API_KEY 等
pnpm type-check         # 目前 src 只有占位文件，可作为环境自检
pnpm dev                # 入口实现后才会真正跑起来
```

| 命令 | 作用 |
|---|---|
| `pnpm dev` | `tsx watch src/index.ts` |
| `pnpm start` | 跑一次 `src/index.ts` |
| `pnpm build` | `tsc` 编译到 `dist/` |
| `pnpm type-check` | 只做类型检查 |
| `pnpm format` / `format:check` | Prettier 格式化 / 校验 |

## 环境变量

见 [`.env.example`](.env.example)：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`、`EMBEDDING_MODEL`、`MCP_SERVERS`（JSON 数组，`command`/`args` 启动 stdio server）。`.env` 由根 `.gitignore` 忽略，**不要提交真实密钥**。

## 设计要点

1. **循环而不是编排**：模型在每轮决定「继续调用工具」还是「给最终答复」，代码只负责执行与回灌 observation。
2. **工具来自 MCP**：`tools/list` 的结果转换成统一的工具描述，执行时走 `tools/call`，不在本地硬编码工具实现。
3. **记忆分层**：短期记忆是消息列表；长期记忆用 `VectorStore` + `EmbeddingRetriever` 检索，先做内存版。
4. **模型可替换**：`ChatOpenAI` 只依赖 OpenAI 兼容协议，换本地模型/网关只改环境变量。
5. **轨迹留痕**：每轮 Thought/Action/Observation 写入 `output/`，便于对照主应用的运行记录（`docs/agent.md`）。

## 与主仓库的关系

- 主应用（FastAPI + Vue 3）见 [`backend/README.md`](../backend/README.md) 与 [`frontend/README.md`](../frontend/README.md)。
- 本子工程只做学习验证，不引入主应用依赖；主应用的前后端构建与 CI 不包含此目录。
- Agent 设计取舍参考 [`docs/agent.md`](../docs/agent.md) 与 [ADR-0010](../docs/adr/0010-agent-execution-loop.md)。

## 下一步

- [ ] `utils.ts`：日志、重试、模型输出解析
- [ ] `ChatOpenAI.ts`：流式 + tool_calls 支持
- [ ] `MCPClient.ts`：stdio 连接、工具发现与调用、异常清理
- [ ] `Agent.ts`：ReAct 循环、最大轮次、轨迹落盘
- [ ] `VectorStore.ts` / `EmbeddingRetriever.ts`：内存向量存储与 Top-K 检索
- [ ] `index.ts`：CLI 入口串起以上模块
- [ ] 补一个最小示例 MCP server 与端到端脚本
