import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useChatStore } from '@/stores/chat'
import { createConversation, getConversation, deleteConversation } from '@/api/chat'
import {
  AgentHttpError,
  sendAgentStream,
  decideApprovalStream,
  listApprovals,
  getAgentSteps,
  type AgentStreamHandlers,
} from '@/api/agent'
import type { AgentRunSummary, ChatConversationDetail } from '@/types/api'

vi.mock('@/api/chat', () => ({
  createConversation: vi.fn(),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
  listConversations: vi.fn(),
  renameConversation: vi.fn(),
}))
vi.mock('@/api/agent', async (original) => ({
  AgentHttpError: (await original<typeof import('@/api/agent')>()).AgentHttpError,
  sendAgentStream: vi.fn(),
  decideApprovalStream: vi.fn(),
  listApprovals: vi.fn(),
  getAgentSteps: vi.fn(),
}))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: vi.fn() } }))
vi.mock('@/components/ui/messageBox', () => ({
  confirmDialog: vi.fn(async () => true),
  promptDialog: vi.fn(),
}))

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => {
    resolve = yes
    reject = no
  })
  return { promise, resolve, reject }
}
const run = (status: AgentRunSummary['status']): AgentRunSummary => ({
  id: 7,
  user_message_id: 11,
  assistant_message_id: status === 'completed' ? 12 : null,
  status,
  visible_step_count: 1,
})
const history = (status?: AgentRunSummary['status']): ChatConversationDetail => ({
  id: 1,
  title: '会话',
  agent_key: 'default',
  skill_slug: null,
  create_time: '',
  update_time: '',
  messages: status
    ? [
        { id: 11, conversation_id: 1, role: 'user', content: '问题', model: null, create_time: '' },
        ...(status === 'completed'
          ? [
              {
                id: 12,
                conversation_id: 1,
                role: 'assistant',
                content: '完成正文',
                model: null,
                create_time: '',
              },
            ]
          : []),
      ]
    : [],
  runs: status ? [run(status)] : [],
})
const approval = (id = 9) => ({
  id,
  run_id: 7,
  seq: 3,
  tool_name: 'rename_conversation',
  tool_args: {},
  status: 'pending' as const,
  note: '确认',
  create_time: '',
  decided_time: null,
})
const call = { type: 'tool_call' as const, seq: 2, tool: 'now', args: {} }
let handlers: AgentStreamHandlers
let stream: ReturnType<typeof deferred<void>>
beforeEach(() => {
  vi.resetAllMocks()
  setActivePinia(createPinia())
  stream = deferred<void>()
  vi.mocked(createConversation).mockResolvedValue({
    id: 1,
    title: '会话',
    agent_key: 'default',
    skill_slug: null,
    create_time: '',
    update_time: '',
  })
  vi.mocked(getConversation).mockResolvedValue(history())
  vi.mocked(getAgentSteps).mockResolvedValue([])
  vi.mocked(listApprovals).mockResolvedValue([approval()])
  vi.mocked(sendAgentStream).mockImplementation((_id, _text, callbacks) => {
    handlers = callbacks
    return stream.promise
  })
  vi.mocked(decideApprovalStream).mockImplementation((_id, _approval, _decision, callbacks) => {
    handlers = callbacks
    return stream.promise
  })
})
function start() {
  const chat = useChatStore()
  chat.activeId = 1
  const result = chat.send('问题')
  handlers.onEvent?.({ type: 'run_started', run_id: 7, conversation_id: 1, user_message_id: 11 })
  return { chat, result }
}
function finish() {
  const event = {
    type: 'run_finished' as const,
    run_id: 7,
    assistant_message_id: 12,
    content: '完成正文',
    model: null,
    steps: 3,
  }
  handlers.onEvent?.(event)
  handlers.onFinished(event)
  stream.resolve()
}

it('首次发送在建会话前锁定，并发创建复用同一请求', async () => {
  const creating = deferred<Awaited<ReturnType<typeof createConversation>>>()
  vi.mocked(createConversation).mockReturnValue(creating.promise)
  const chat = useChatStore()
  chat.composerText = '问题'
  const first = chat.send('问题')
  expect(chat.sending).toBe(true)
  expect(await chat.send('重复')).toBe(false)
  const ensured = chat.ensureConversation()
  expect(createConversation).toHaveBeenCalledTimes(1)
  creating.resolve({
    id: 1,
    title: '会话',
    agent_key: 'default',
    skill_slug: null,
    create_time: '',
    update_time: '',
  })
  await ensured
  await vi.waitFor(() => expect(sendAgentStream).toHaveBeenCalledTimes(1))
  const requestId = vi.mocked(sendAgentStream).mock.calls[0][8]
  expect(requestId).toMatch(/^[0-9a-f-]{36}$/)
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  finish()
  expect(await first).toBe(true)
  expect(chat.sending).toBe(false)
  expect(chat.messages.filter((message) => message.role === 'assistant')).toHaveLength(1)
})

it('创建失败保留草稿、释放锁，允许重新发送', async () => {
  vi.mocked(createConversation).mockRejectedValueOnce(new Error('创建失败'))
  const chat = useChatStore()
  chat.composerText = '保留草稿'
  expect(await chat.send('保留草稿')).toBe(false)
  expect(chat.composerText).toBe('保留草稿')
  expect(chat.sending).toBe(false)
  expect(chat.canSend).toBe(true)
  expect(chat.recoveryMessage).toContain('创建失败')
  expect(sendAgentStream).not.toHaveBeenCalled()
})

it.each(['reset', 'startNew'] as const)(
  '创建期间 %s 后不启动旧发送、不改变新页面',
  async (action) => {
    const creating = deferred<Awaited<ReturnType<typeof createConversation>>>()
    vi.mocked(createConversation).mockReturnValue(creating.promise)
    const chat = useChatStore()
    const pending = chat.send('问题')
    chat[action]()
    creating.resolve({
      id: 1,
      title: '旧会话',
      agent_key: 'default',
      skill_slug: null,
      create_time: '',
      update_time: '',
    })
    expect(await pending).toBe(false)
    expect(chat.activeId).toBeNull()
    expect(chat.conversations).toEqual([])
    expect(sendAgentStream).not.toHaveBeenCalled()
  },
)

it('断流时后端已完成，只查询恢复最终回复而不重新发送', async () => {
  const { chat, result } = start()
  handlers.onEvent?.({ type: 'assistant_delta', content: '半句' })
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  stream.reject(new Error('连接断开'))
  expect(await result).toBe(true)
  expect(chat.streamingText).toBe('')
  expect(chat.canSend).toBe(true)
  expect(chat.messages.at(-1)?.content).toBe('完成正文')
  expect(sendAgentStream).toHaveBeenCalledTimes(1)
})

it('断流后仍在运行或查询失败时锁住发送，重查终态后恢复', async () => {
  const { chat, result } = start()
  vi.mocked(getConversation).mockRejectedValueOnce(new Error('查询失败'))
  stream.reject(new Error('断流'))
  expect(await result).toBe(false)
  expect(chat.sending).toBe(false)
  expect(chat.canSend).toBe(false)
  expect(chat.recoveryMessage).toContain('查询失败')
  expect(await chat.send('重复')).toBe(false)
  vi.mocked(getConversation).mockResolvedValueOnce(history('running'))
  expect(await chat.recoverExecution()).toBe(false)
  expect(chat.canSend).toBe(false)
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  expect(await chat.recoverExecution()).toBe(true)
  expect(chat.canSend).toBe(true)
  expect(sendAgentStream).toHaveBeenCalledTimes(1)
})

it('开始事件丢失时不猜测运行关联、不自动重发', async () => {
  const chat = useChatStore()
  chat.activeId = 1
  const pending = chat.send('问题')
  stream.reject(new Error('断流'))
  expect(await pending).toBe(false)
  expect(chat.canSend).toBe(false)
  expect(chat.recoveryMessage).toContain('提交结果尚未确认')
  expect(await chat.recoverExecution()).toBe(false)
  vi.mocked(getConversation).mockResolvedValueOnce(history('running'))
  await chat.recoverExecution()
  vi.mocked(getConversation).mockResolvedValueOnce(history('completed'))
  await chat.recoverExecution()
  expect(chat.canSend).toBe(false)
  expect(chat.recoveryMessage).toContain('提交结果尚未确认')
  expect(sendAgentStream).toHaveBeenCalledTimes(1)
})

it('审批查询失败和空审批都不能当成已恢复，重查成功后才允许决定', async () => {
  const chat = useChatStore()
  vi.mocked(getConversation).mockResolvedValue(history('waiting_approval'))
  vi.mocked(listApprovals).mockRejectedValueOnce(new Error('审批不可用'))
  await chat.openConversation(1)
  expect(chat.canSend).toBe(false)
  expect(chat.recoveryMessage).toContain('审批不可用')
  expect(await chat.approveApproval()).toBe(false)
  vi.mocked(listApprovals).mockResolvedValueOnce([])
  expect(await chat.recoverExecution()).toBe(false)
  expect(chat.canSend).toBe(false)
  expect(await chat.recoverExecution()).toBe(true)
  expect(chat.pendingApproval?.approvalId).toBe(9)
  expect(chat.canSend).toBe(false)
})

it('审批续跑的步骤读取失败时不提交决定，步骤和错误仍可重试', async () => {
  const chat = useChatStore()
  vi.mocked(getConversation).mockResolvedValue(history('waiting_approval'))
  await chat.openConversation(1)
  vi.mocked(getAgentSteps).mockRejectedValueOnce(new Error('步骤读取失败'))
  expect(await chat.approveApproval()).toBe(false)
  expect(decideApprovalStream).not.toHaveBeenCalled()
  expect(chat.pendingApproval?.approvalId).toBe(9)
  expect(chat.replayDetails[7]?.status).toBe('error')
  expect(chat.feedItems.find((item) => item.kind === 'execution')).toMatchObject({
    approvalBlocked: true,
  })
  expect(chat.canSend).toBe(false)
})

it.each(['approve', 'reject'] as const)(
  '审批 %s 和再次审批共用同一运行，拒绝重复决定',
  async (decision) => {
    const chat = useChatStore()
    vi.mocked(getConversation).mockResolvedValue(history('waiting_approval'))
    await chat.openConversation(1)
    const first = chat.decideApproval(decision)
    expect(await chat.decideApproval(decision)).toBe(false)
    await vi.waitFor(() => expect(decideApprovalStream).toHaveBeenCalledTimes(1))
    const next = {
      type: 'approval_required' as const,
      run_id: 7,
      approval_id: 10,
      seq: 4,
      tool: 'rename_conversation',
      args: {},
      reason: '再次确认',
    }
    vi.mocked(listApprovals).mockResolvedValue([approval(10)])
    handlers.onEvent?.(next)
    handlers.onApproval?.(next)
    stream.resolve()
    expect(await first).toBe(true)
    expect(chat.pendingApproval?.approvalId).toBe(10)
    stream = deferred<void>()
    const second = chat.approveApproval()
    await vi.waitFor(() => expect(decideApprovalStream).toHaveBeenCalledTimes(2))
    vi.mocked(getConversation).mockResolvedValue(history('completed'))
    finish()
    expect(await second).toBe(true)
    expect(chat.pendingApproval).toBeNull()
    expect(chat.canSend).toBe(true)
  },
)

it('审批已提交但响应丢失时查询终态，不恢复旧审批卡', async () => {
  const chat = useChatStore()
  vi.mocked(getConversation).mockResolvedValue(history('waiting_approval'))
  await chat.openConversation(1)
  const deciding = chat.approveApproval()
  await vi.waitFor(() => expect(decideApprovalStream).toHaveBeenCalledTimes(1))
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  stream.reject(new Error('审批响应丢失'))
  expect(await deciding).toBe(true)
  expect(chat.pendingApproval).toBeNull()
  expect(decideApprovalStream).toHaveBeenCalledTimes(1)
})

it('重复步骤和重复终态不会重复保存，旧连接关闭后事件不再写入', async () => {
  const { chat, result } = start()
  handlers.onEvent?.(call)
  handlers.onEvent?.(call)
  expect(chat.agentSteps).toHaveLength(1)
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  finish()
  await result
  handlers.onEvent?.({
    type: 'tool_result',
    seq: 3,
    tool: 'now',
    content: '迟到',
    ok: true,
    duration_ms: 1,
  })
  expect(chat.agentSteps).toHaveLength(1)
  expect(chat.messages.filter((message) => message.id === 12)).toHaveLength(1)
})

it.each(['reset', 'delete'] as const)(
  '%s 后取消读取，迟到事件与历史响应不能污染新状态',
  async (action) => {
    const { chat, result } = start()
    const signal = vi.mocked(sendAgentStream).mock.calls[0][3]!
    if (action === 'reset') chat.reset()
    else {
      vi.mocked(deleteConversation).mockResolvedValue(undefined)
      await chat.remove({
        id: 1,
        title: '会话',
        message_count: 0,
        update_time: '',
        agent_key: 'default',
        skill_slug: null,
        create_time: '',
      })
    }
    expect(signal.aborted).toBe(true)
    finish()
    expect(await result).toBe(false)
    expect(chat.messages).toEqual([])
    expect(getConversation).not.toHaveBeenCalled()
  },
)

it('较旧历史响应不能覆盖正在接收的新运行', async () => {
  const stale = deferred<ChatConversationDetail>()
  vi.mocked(getConversation).mockReturnValueOnce(stale.promise)
  const chat = useChatStore()
  const opening = chat.openConversation(1)
  const pending = chat.send('问题')
  handlers.onEvent?.({ type: 'run_started', run_id: 7, conversation_id: 1, user_message_id: 11 })
  handlers.onEvent?.(call)
  stale.resolve(history())
  await opening
  expect(chat.agentSteps).toHaveLength(1)
  expect(chat.messages[0].id).toBe(11)
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  finish()
  await pending
})

it('明确的请求校验失败释放锁，显示错误并保留输入', async () => {
  vi.mocked(sendAgentStream).mockRejectedValueOnce(new AgentHttpError(422, '输入无效'))
  const chat = useChatStore()
  chat.activeId = 1
  chat.composerText = '保留'
  expect(await chat.send('保留')).toBe(false)
  expect(chat.canSend).toBe(true)
  expect(chat.recoveryMessage).toContain('输入无效')
  expect(chat.composerText).toBe('保留')
})

it('结束事件已确认时历史查询失败不会抹掉正式回复或把成功当断流', async () => {
  const { chat, result } = start()
  vi.mocked(getConversation).mockRejectedValueOnce(new Error('历史暂不可用'))
  finish()
  expect(await result).toBe(true)
  expect(chat.messages.at(-1)?.content).toBe('完成正文')
  expect(chat.canSend).toBe(true)
  expect(chat.recoveryMessage).toContain('历史暂不可用')
})

it('结束后的历史核对期间退出账号，旧响应不会恢复消息和列表', async () => {
  const { chat, result } = start()
  const snapshot = deferred<ChatConversationDetail>()
  vi.mocked(getConversation).mockReturnValueOnce(snapshot.promise)
  finish()
  await vi.waitFor(() => expect(getConversation).toHaveBeenCalledTimes(1))
  chat.reset()
  snapshot.resolve(history('completed'))
  expect(await result).toBe(false)
  expect(chat.messages).toEqual([])
  expect(chat.conversations).toEqual([])
})

it('较旧步骤响应不能覆盖刚完成的实时步骤', async () => {
  const { chat, result } = start()
  const stale = deferred<Awaited<ReturnType<typeof getAgentSteps>>>()
  vi.mocked(getAgentSteps).mockReturnValueOnce(stale.promise)
  const loading = chat.loadExecutionSteps(7)
  handlers.onEvent?.(call)
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  finish()
  await result
  stale.resolve([])
  await loading
  expect(chat.replayDetails[7]?.steps).toMatchObject([{ seq: 2, kind: 'tool_call' }])
  expect(chat.replayDetails[7]?.status).toBe('loaded')
})

it('首发已挂起后审批查询失败，不把空审批当作成功或解锁', async () => {
  const { chat, result } = start()
  vi.mocked(getConversation).mockResolvedValue(history('waiting_approval'))
  vi.mocked(listApprovals).mockRejectedValueOnce(new Error('审批查询失败'))
  handlers.onApproval?.({
    type: 'approval_required',
    run_id: 7,
    approval_id: 9,
    seq: 3,
    tool: 'rename_conversation',
    args: {},
    reason: '确认',
  })
  stream.resolve()
  expect(await result).toBe(false)
  expect(chat.canSend).toBe(false)
  expect(chat.recoveryMessage).toContain('审批查询失败')
  expect(await chat.approveApproval()).toBe(false)
})

it('审批请求被拒绝时重新查询原运行，不能将等待审批误标为失败解锁', async () => {
  const chat = useChatStore()
  vi.mocked(getConversation).mockResolvedValue(history('waiting_approval'))
  await chat.openConversation(1)
  vi.mocked(decideApprovalStream).mockRejectedValueOnce(new AgentHttpError(422, '决定无效'))
  expect(await chat.approveApproval()).toBe(false)
  expect(chat.pendingApproval?.approvalId).toBe(9)
  expect(chat.canSend).toBe(false)
  expect(chat.recoveryMessage).toContain('决定无效')
})

it('详情读取与审批预加载同时发生时只读一次步骤', async () => {
  const chat = useChatStore()
  vi.mocked(getConversation).mockResolvedValue(history('waiting_approval'))
  await chat.openConversation(1)
  const steps = deferred<Awaited<ReturnType<typeof getAgentSteps>>>()
  vi.mocked(getAgentSteps).mockReturnValueOnce(steps.promise)
  const loading = chat.loadExecutionSteps(7)
  const deciding = chat.approveApproval()
  expect(getAgentSteps).toHaveBeenCalledTimes(1)
  steps.resolve([])
  await loading
  await vi.waitFor(() => expect(decideApprovalStream).toHaveBeenCalledTimes(1))
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  finish()
  expect(await deciding).toBe(true)
})
