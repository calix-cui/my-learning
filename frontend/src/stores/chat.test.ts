import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useChatStore } from '@/stores/chat'
import type { ChatMessage } from '@/types/api'

/** 被测试拿在手里的流控制器：由它决定什么时候吐 delta / done */
let streamHandlers: {
  onMeta?: (m: ChatMessage) => void
  onDelta?: (d: string) => void
  onDone?: (e: unknown) => void
} = {}

/** 由测试决定什么时候结束这次 SSE */
let finishStream: (() => void) | null = null

const conversations: Record<number, ChatMessage[]> = {}

vi.mock('@/api/chat', () => ({
  listConversations: vi.fn(async () => ({ items: [], total: 0, page: 1, page_size: 50 })),
  createConversation: vi.fn(async () => ({
    id: 1,
    title: '新会话',
    agent_key: 'default',
    update_time: '2026-11-11 10:00:00',
    create_time: '2026-11-11 10:00:00',
  })),
  getConversation: vi.fn(async (id: number) => ({
    id,
    title: id === 1 ? '会话一' : '会话二',
    agent_key: 'default',
    update_time: '2026-11-11 10:00:00',
    create_time: '2026-11-11 10:00:00',
    messages: conversations[id] ?? [],
  })),
  renameConversation: vi.fn(),
  deleteConversation: vi.fn(),
  // 手动控制何时结束：这样才能模拟「流还没跑完就切走」
  sendMessageStream: vi.fn(
    (_id: number, _text: string, handlers: typeof streamHandlers) =>
      new Promise<void>((resolve) => {
        streamHandlers = handlers
        finishStream = resolve
      }),
  ),
}))

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

vi.mock('@/components/ui/messageBox', () => ({
  confirmDialog: vi.fn(async () => true),
  promptDialog: vi.fn(async () => '新标题'),
}))

let agentHandlers: {
  onEvent?: (event: unknown) => void
  onFinished?: (event: unknown) => void
  onApproval?: (event: unknown) => void
} = {}

let finishAgent: (() => void) | null = null

vi.mock('@/api/agent', () => ({
  listAgentRuns: vi.fn(async () => ({ items: [] })),
  listApprovals: vi.fn(async () => []),
  // 写操作会挂起：先吐 approval_required，再由测试决定批准后怎么走
  sendAgentStream: vi.fn(
    (_id: number, _text: string, handlers: typeof agentHandlers) =>
      new Promise<void>((resolve) => {
        agentHandlers = handlers
        finishAgent = resolve
      }),
  ),
  decideApprovalStream: vi.fn(
    (_runId: number, _approvalId: number, _decision: string, handlers: typeof agentHandlers) =>
      new Promise<void>((resolve) => {
        agentHandlers = handlers
        finishAgent = resolve
      }),
  ),
}))

function msg(
  id: number,
  conversationId: number,
  role: 'user' | 'assistant',
  content: string,
): ChatMessage {
  return {
    id,
    conversation_id: conversationId,
    role,
    content,
    model: null,
    create_time: '2026-11-11 10:00:00',
  }
}

describe('chat store：会话状态按会话隔离', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    streamHandlers = {}
    finishStream = null
    for (const key of Object.keys(conversations)) delete conversations[Number(key)]
    conversations[2] = [msg(20, 2, 'user', '第二个会话的历史')]
  })

  it('切走后，旧会话的流式回包不会写进新会话', async () => {
    const chat = useChatStore()
    chat.activeId = 1
    const pending = chat.send('第一个会话的问题')

    // 服务端刚回 meta + 一个 delta，用户就点开了另一个会话
    streamHandlers.onMeta?.(msg(11, 1, 'user', '第一个会话的问题'))
    streamHandlers.onDelta?.('半句')
    await chat.openConversation(2)

    // 旧会话接着吐完（这一步以前会把内容塞进「当前会话」）
    streamHandlers.onDelta?.('话')
    const answer = msg(12, 1, 'assistant', '第一个会话的回答')
    streamHandlers.onDone?.({
      assistant_message: answer,
      conversation_title: '第一个会话的问题',
      message_count: 2,
    })
    finishStream?.()
    await pending
    // 服务端把它落库了；下一次打开会话时从服务端读到
    conversations[1] = [msg(11, 1, 'user', '第一个会话的问题'), answer]

    // 新会话的内容不受影响
    expect(chat.messages.map((m) => m.content)).toEqual(['第二个会话的历史'])
    // 旧会话自己的数据留在了它那一份里
    await chat.openConversation(1)
    expect(chat.messages.map((m) => m.content)).toEqual(['第一个会话的问题', '第一个会话的回答'])
  })

  it('每个会话的发送状态互相独立', async () => {
    const chat = useChatStore()
    chat.activeId = 1
    const pending = chat.send('问题')
    expect(chat.sending).toBe(true)
    await chat.openConversation(2)
    // 切到会话二：二没在发，所以按钮可用
    expect(chat.sending).toBe(false)
    expect(chat.isBusy(1)).toBe(true)
    finishStream?.()
    await pending
    expect(chat.isBusy(1)).toBe(false)
  })

  it('输入框草稿也按会话隔离：切走再切回来文字还在', async () => {
    const chat = useChatStore()
    chat.activeId = 1
    chat.composerText = '会话一写了一半'
    await chat.openConversation(2)
    expect(chat.composerText).toBe('')
    chat.composerText = '会话二的草稿'
    await chat.openConversation(1)
    expect(chat.composerText).toBe('会话一写了一半')
  })

  it('删掉当前会话回到草稿态，并清掉它的缓存', async () => {
    const chat = useChatStore()
    chat.activeId = 1
    conversations[1] = [msg(11, 1, 'user', '旧内容')]
    await chat.openConversation(1)
    await chat.remove({
      id: 1,
      title: '会话一',
      message_count: 1,
      update_time: '2026-11-11 10:00:00',
    } as never)
    expect(chat.activeId).toBeNull()
    expect(chat.draft).toBe(true)
    expect(chat.messages).toEqual([])
  })
})

describe('chat store · 工具审批', () => {
  it('写工具挂起后给出待审批卡片，批准后落最终答复', async () => {
    const chat = useChatStore()
    await chat.loadConversations()
    chat.agentMode = true

    const sending = chat.sendWithAgent('把会话改名为周报')
    await vi.waitFor(() => expect(agentHandlers.onEvent).toBeTruthy())

    // 服务端先回一个 tool_call，再挂起等审批
    agentHandlers.onEvent?.({
      type: 'tool_call',
      seq: 1,
      tool: 'rename_conversation',
      args: { title: '周报' },
    })
    agentHandlers.onEvent?.({
      type: 'approval_required',
      run_id: 7,
      approval_id: 9,
      seq: 2,
      tool: 'rename_conversation',
      args: { title: '周报' },
      reason: '写操作需要确认',
    })
    agentHandlers.onApproval?.({
      type: 'approval_required',
      run_id: 7,
      approval_id: 9,
      seq: 2,
      tool: 'rename_conversation',
      args: { title: '周报' },
      reason: '写操作需要确认',
    })
    finishAgent?.()
    await sending

    expect(chat.pendingApproval).toMatchObject({
      runId: 7,
      approvalId: 9,
      tool: 'rename_conversation',
      reason: '写操作需要确认',
    })
    expect(chat.agentRunning).toBe(false)

    // 批准：服务端接着跑完这次运行
    const deciding = chat.approveApproval()
    await vi.waitFor(() => expect(agentHandlers.onEvent).toBeTruthy())
    agentHandlers.onEvent?.({
      type: 'tool_result',
      seq: 3,
      tool: 'rename_conversation',
      ok: true,
      content: '已改名为周报',
      duration_ms: 8,
    })
    agentHandlers.onFinished?.({
      type: 'run_finished',
      run_id: 7,
      content: '已经把会话改名为「周报」。',
      steps: 3,
      model: 'deepseek-chat',
    })
    finishAgent?.()
    await deciding

    expect(chat.pendingApproval).toBeNull()
    // 收尾会重新拉一次会话详情覆盖消息，所以这里看时间线：工具真的执行了
    expect(chat.agentSteps.at(-1)).toMatchObject({
      kind: 'tool_result',
      tool_name: 'rename_conversation',
      ok: true,
    })
  })
})
