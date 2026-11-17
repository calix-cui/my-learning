import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { useChatStore } from '@/stores/chat'
import type { AgentRunSummary, AgentStep, ChatMessage } from '@/types/api'

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
  getAgentSteps: vi.fn(async () => [] as AgentStep[]),
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
    agentHandlers = {}
    finishAgent = null
    for (const key of Object.keys(conversations)) delete conversations[Number(key)]
    conversations[2] = [msg(20, 2, 'user', '第二个会话的历史')]
  })

  it('切走后，旧会话的流式回包不会写进新会话', async () => {
    const chat = useChatStore()
    chat.activeId = 1
    const pending = chat.send('第一个会话的问题')

    // 服务端刚返回消息 ID 和一个分片，用户就点开了另一个会话。
    agentHandlers.onEvent?.({
      type: 'run_started',
      run_id: 7,
      conversation_id: 1,
      user_message_id: 11,
    })
    agentHandlers.onEvent?.({ type: 'assistant_delta', content: '半句' })
    await chat.openConversation(2)

    // 旧会话接着吐完（这一步以前会把内容塞进「当前会话」）
    agentHandlers.onEvent?.({ type: 'assistant_delta', content: '话' })
    const answer = msg(12, 1, 'assistant', '第一个会话的回答')
    agentHandlers.onFinished?.({
      type: 'run_finished',
      run_id: 7,
      assistant_message_id: 12,
      content: answer.content,
      model: null,
      steps: 2,
    })
    conversations[1] = [msg(11, 1, 'user', '第一个会话的问题'), answer]
    finishAgent?.()
    await pending

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
    finishAgent?.()
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

describe('chat store · 会话列表加载', () => {
  it('侧栏和对话页同时要列表时只发一次请求', async () => {
    const { listConversations } = await import('@/api/chat')
    const chat = useChatStore()

    await Promise.all([chat.ensureConversationsLoaded(), chat.ensureConversationsLoaded()])
    await chat.ensureConversationsLoaded()

    expect(vi.mocked(listConversations)).toHaveBeenCalledTimes(1)

    // 登出后标记要清掉，再进应用才会重新拉
    chat.reset()
    await chat.ensureConversationsLoaded()
    expect(vi.mocked(listConversations)).toHaveBeenCalledTimes(2)
  })
})

describe('chat store · 工具审批', () => {
  it('写工具挂起后给出待审批卡片，批准后落最终答复', async () => {
    const chat = useChatStore()
    await chat.loadConversations()
    chat.agentMode = true

    const sending = chat.send('把会话改名为周报')
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
      assistant_message_id: 22,
      content: '已经把会话改名为「周报」。',
      steps: 3,
      model: 'deepseek-chat',
    })
    finishAgent?.()
    await deciding

    expect(chat.pendingApproval).toBeNull()
    expect(chat.runsByMessage[22]?.[0].id).toBe(7)
    expect(chat.replayDetails[7]?.steps.at(-1)).toMatchObject({
      kind: 'tool_result',
      tool_name: 'rename_conversation',
      ok: true,
    })
  })
})

describe('chat store · Skill 时间线', () => {
  it('传递自动模式，隔离异步事件并回放已保存的 Skill 步骤', async () => {
    const { sendAgentStream, getAgentSteps } = await import('@/api/agent')
    const { getConversation } = await import('@/api/chat')
    setActivePinia(createPinia())
    const chat = useChatStore()
    chat.activeId = 1
    const sending = chat.send('整理会议', 'auto')
    expect(sendAgentStream).toHaveBeenLastCalledWith(
      1,
      '整理会议',
      expect.any(Object),
      undefined,
      'auto',
      'none',
      [],
      undefined,
    )
    await chat.openConversation(2)
    agentHandlers.onEvent?.({
      type: 'skill_loaded',
      seq: 2,
      skill_key: 'builtin:meeting',
      name: '会议纪要',
      source: 'builtin',
      version: 'v1',
    })
    agentHandlers.onEvent?.({
      type: 'skill_load_failed',
      seq: 3,
      skill_key: 'builtin:missing',
      error_code: 'unknown_skill',
      message: '技能不可用',
    })
    expect(chat.agentSteps).toEqual([])
    finishAgent?.()
    await sending
    await chat.openConversation(1)
    expect(chat.agentSteps).toMatchObject([
      { kind: 'skill_loaded', skill_name: '会议纪要', skill_version: 'v1' },
      { kind: 'skill_load_failed', content: '技能不可用' },
    ])
    agentHandlers.onEvent?.({
      type: 'skill_resource',
      seq: 4,
      skill_key: 'builtin:meeting',
      name: '会议纪要',
      path: 'references/checklist.md',
      ok: true,
      message: '已读取参考资料',
    })
    expect(chat.agentSteps.at(-1)).toMatchObject({
      kind: 'skill_resource',
      skill_name: '会议纪要',
      ok: true,
      tool_args: { path: 'references/checklist.md' },
    })
    const savedSteps = JSON.parse(JSON.stringify(chat.agentSteps))
    vi.mocked(getConversation).mockResolvedValueOnce({
      id: 1,
      title: '会话一',
      skill_slug: null,
      agent_key: 'default',
      create_time: '',
      update_time: '',
      messages: [msg(11, 1, 'assistant', '会议纪要')],
      runs: [completedRun(7, 10, 11, savedSteps.length)],
    })
    vi.mocked(getAgentSteps).mockResolvedValueOnce(savedSteps)
    setActivePinia(createPinia())
    const refreshed = useChatStore()
    await refreshed.openConversation(1)
    expect(refreshed.runsByMessage[11]?.[0].id).toBe(7)
    expect(refreshed.replayDetails[7]).toBeUndefined()
    await refreshed.loadExecutionSteps(7)
    expect(refreshed.replayDetails[7]?.steps).toEqual(savedSteps)
  })
})

function completedRun(
  id: number,
  userMessageId: number,
  assistantMessageId: number,
  visibleStepCount = 2,
): AgentRunSummary {
  return {
    id,
    user_message_id: userMessageId,
    assistant_message_id: assistantMessageId,
    status: 'completed',
    visible_step_count: visibleStepCount,
  }
}

it('刷新、切换会话和分页后分别从对应运行加载执行过程', async () => {
  const { getConversation } = await import('@/api/chat')
  const { getAgentSteps } = await import('@/api/agent')
  const first = completedRun(101, 9, 10)
  const second = completedRun(102, 19, 20)
  const older = completedRun(100, 1, 2)
  const other = completedRun(103, 29, 30)
  const conversation = {
    id: 1,
    title: '会话历史',
    skill_slug: null,
    agent_key: 'default',
    update_time: '',
    create_time: '',
  }
  const latestPage = {
    ...conversation,
    messages: [msg(10, 1, 'assistant', '第一次'), msg(20, 1, 'assistant', '第二次')],
    next_before_message_id: 10,
    runs: [second, first],
  }
  vi.mocked(getConversation).mockImplementation(async (id, page) => {
    if (id === 2) {
      return { ...conversation, id, messages: [msg(30, 2, 'assistant', '另外一条')], runs: [other] }
    }
    if (page?.before_message_id === 10) {
      return { ...conversation, messages: [msg(2, 1, 'assistant', '更早')], runs: [older] }
    }
    return latestPage
  })
  vi.mocked(getAgentSteps).mockImplementation(async (runId) => [
    {
      seq: 2,
      kind: 'tool_result',
      content: `结果 ${runId}`,
      tool_name: 'calculator',
      tool_args: null,
      skill_key: null,
      skill_name: null,
      skill_source: null,
      skill_version: null,
      ok: true,
      duration_ms: 0,
      create_time: '',
    },
  ])
  try {
    setActivePinia(createPinia())
    const chat = useChatStore()
    await chat.openConversation(1)
    expect(chat.runsByMessage).toEqual({ 10: [first], 20: [second] })
    expect(chat.replayDetails).toEqual({})
    await chat.loadExecutionSteps(101)
    await chat.loadExecutionSteps(102)
    expect(chat.replayDetails[101]?.steps[0].content).toBe('结果 101')
    expect(chat.replayDetails[102]?.steps[0].content).toBe('结果 102')

    expect(await chat.loadOlderMessages()).toBe(true)
    expect(chat.messages.map(({ id }) => id)).toEqual([2, 10, 20])
    expect(chat.runsByMessage[2]).toEqual([older])
    expect(chat.hasOlderMessages).toBe(false)
    await chat.openConversation(2)
    expect(chat.runsByMessage).toEqual({ 30: [other] })
    expect(chat.replayDetails).toEqual({})
    await chat.openConversation(1)
    expect(chat.messages.map(({ id }) => id)).toEqual([2, 10, 20])
    expect(chat.replayDetails[101]?.steps[0].content).toBe('结果 101')
  } finally {
    vi.mocked(getConversation).mockRestore()
    vi.mocked(getAgentSteps).mockRestore()
  }
})

it('本条 Skill 选择随草稿发送，成功后清除，下一次提问不自动继承', async () => {
  setActivePinia(createPinia())
  const chat = useChatStore()
  chat.selectedSkillKey = 'user:guide'
  const pending = chat.send('第一条', 'manual', 'none', 'catalog1')
  await vi.waitFor(() => expect(chat.sending).toBe(true))
  const { sendAgentStream } = await import('@/api/agent')
  expect(sendAgentStream).toHaveBeenLastCalledWith(
    1,
    '第一条',
    expect.any(Object),
    undefined,
    'manual',
    'none',
    ['user:guide'],
    'catalog1',
  )
  agentHandlers.onEvent?.({
    type: 'run_started',
    run_id: 10,
    conversation_id: 1,
    user_message_id: 50,
  })
  agentHandlers.onFinished?.({
    type: 'run_finished',
    run_id: 10,
    assistant_message_id: 51,
    content: '已处理',
    steps: 2,
    model: null,
  })
  finishAgent?.()
  expect(await pending).toBe(true)
  expect(chat.selectedSkillKey).toBeNull()
  const next = chat.send('第二条')
  expect(sendAgentStream).toHaveBeenLastCalledWith(
    1,
    '第二条',
    expect.any(Object),
    undefined,
    'auto',
    'none',
    [],
    undefined,
  )
  finishAgent?.()
  await next
})
