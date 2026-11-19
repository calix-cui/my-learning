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
  findRunByRequestId,
  subscribeAgentRun,
  stopAgentRun,
  regenerateAgentRun,
  type AgentStreamHandlers,
} from '@/api/agent'
import type { AgentRunSummary, AgentStep, ChatConversationDetail } from '@/types/api'
import { runSummary, stepsPage } from '@/test/agent'

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
  findRunByRequestId: vi.fn(),
  subscribeAgentRun: vi.fn(),
  stopAgentRun: vi.fn(),
  regenerateAgentRun: vi.fn(),
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
/** 按 request_id 查到的那次运行：比摘要多带会话、步骤等字段 */
const runDetail = (status: AgentRunSummary['status'], requestId = 'req-1') => ({
  id: 7,
  conversation_id: 1,
  user_message_id: 11,
  assistant_message_id: status === 'completed' ? 12 : null,
  status,
  step_count: 0,
  model: null,
  request_id: requestId,
  started_time: '',
  finished_time: null,
  error_message: null,
  steps: [] as AgentStep[],
})

const run = (status: AgentRunSummary['status']): AgentRunSummary =>
  runSummary({
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
  call_id: null,
  tool_args: {},
  status: 'pending' as const,
  note: '确认',
  create_time: '',
  decided_time: null,
})
const call = { type: 'tool_call' as const, seq: 2, tool: 'now', args: {}, call_id: 'c1' }
let handlers: AgentStreamHandlers
let stream: ReturnType<typeof deferred<void>>
/** 挂回运行（订阅）用的那条连接：每次订阅新开一条 */
let live: ReturnType<typeof deferred<void>>
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
  vi.mocked(getAgentSteps).mockResolvedValue(stepsPage([]))
  vi.mocked(listApprovals).mockResolvedValue([approval()])
  vi.mocked(sendAgentStream).mockImplementation((_id, _text, callbacks) => {
    handlers = callbacks
    return stream.promise
  })
  vi.mocked(subscribeAgentRun).mockImplementation((_id, callbacks) => {
    handlers = callbacks
    live = deferred<void>()
    return live.promise
  })
  vi.mocked(stopAgentRun).mockResolvedValue(undefined)
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
  vi.mocked(findRunByRequestId).mockResolvedValue(runDetail('running'))
  vi.mocked(getConversation).mockRejectedValueOnce(new Error('查询失败'))
  stream.reject(new Error('断流'))
  expect(await result).toBe(false)
  expect(chat.sending).toBe(false)
  expect(chat.canSend).toBe(false)
  expect(chat.recoveryMessage).toContain('查询失败')
  expect(await chat.send('重复')).toBe(false)
  vi.mocked(getConversation).mockResolvedValueOnce(history('running'))
  expect(await chat.recoverExecution()).toBe(true)
  // 挂回的是同一次运行：仍在接收，所以还发不出去
  expect(chat.canSend).toBe(false)
  expect(subscribeAgentRun).toHaveBeenCalledWith(7, expect.anything(), expect.anything())

  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  const ending = {
    type: 'run_finished' as const,
    run_id: 7,
    assistant_message_id: 12,
    content: '完成正文',
    model: null,
    steps: 1,
  }
  handlers.onEvent?.(ending)
  handlers.onFinished(ending)
  live.resolve()
  await vi.waitFor(() => expect(chat.canSend).toBe(true))
  expect(chat.messages.at(-1)?.content).toBe('完成正文')
  // 全程只有最初那一次提交
  expect(sendAgentStream).toHaveBeenCalledTimes(1)
})

it('开始事件丢失时用 request_id 认领这次提交，不重发', async () => {
  const chat = useChatStore()
  chat.activeId = 1
  const pending = chat.send('问题')
  stream.reject(new Error('断流'))
  expect(await pending).toBe(false)
  // 还没认领到运行之前，只能说「结果不确定」，不能猜
  expect(chat.canSend).toBe(false)
  expect(chat.recoveryMessage).toContain('提交结果尚未确认')

  vi.mocked(findRunByRequestId).mockResolvedValue(runDetail('completed'))
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  expect(await chat.recoverExecution()).toBe(true)
  expect(chat.canSend).toBe(true)
  expect(chat.messages.at(-1)?.content).toBe('完成正文')
  // 认领靠 request_id 查询，没有第二次提交
  expect(sendAgentStream).toHaveBeenCalledTimes(1)
  expect(findRunByRequestId).toHaveBeenCalledWith(1, expect.any(String))
})

it('request_id 查不到时告诉用户没落库、可以重发', async () => {
  const chat = useChatStore()
  chat.activeId = 1
  chat.composerText = '问题'
  const pending = chat.send('问题')
  stream.reject(new Error('断流'))
  expect(await pending).toBe(false)

  vi.mocked(findRunByRequestId).mockResolvedValue(null)
  expect(await chat.recoverExecution()).toBe(false)
  // 没落库就是可以安全重发：解锁并把草稿留着
  expect(chat.canSend).toBe(true)
  expect(chat.composerText).toBe('问题')
  expect(chat.recoveryMessage).toContain('没有落库，可以重新发送')
  expect(sendAgentStream).toHaveBeenCalledTimes(1)
})

it('核对到消息已落库后清空草稿，避免同一句话再发一遍', async () => {
  const chat = useChatStore()
  chat.activeId = 1
  chat.composerText = '问题'
  const result = chat.send('问题')
  handlers.onEvent?.({ type: 'run_started', run_id: 7, conversation_id: 1, user_message_id: 11 })
  vi.mocked(getConversation).mockResolvedValueOnce(history('running'))
  stream.reject(new Error('断流'))
  expect(await result).toBe(false)
  expect(chat.composerText).toBe('问题')
  expect(chat.canSend).toBe(false)
  vi.mocked(getConversation).mockResolvedValue(history('running'))
  await chat.recoverExecution()
  expect(chat.composerText).toBe('')
  expect(chat.messages.filter((message) => message.role === 'user')).toHaveLength(1)
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
  expect(chat.feedItems.find((item) => item.kind === 'execution')).toMatchObject({
    approvalBlocked: true,
    loadStatus: 'error',
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

it('首发撞上审批：核对期间卡片不能显示「执行中…」，否则点了没反应', async () => {
  const chat = useChatStore()
  chat.activeId = 1
  const pending = chat.send('改名')
  const refresh = deferred<ChatConversationDetail>()
  vi.mocked(getConversation).mockReturnValue(refresh.promise)
  const ask = {
    type: 'approval_required' as const,
    run_id: 7,
    approval_id: 9,
    seq: 3,
    tool: 'rename_conversation',
    args: { title: '改名' },
    reason: '写操作',
    call_id: 'c1',
  }
  handlers.onEvent?.(ask)
  handlers.onApproval?.(ask)
  stream.resolve()
  // 卡片这时已经渲染出来了，但核对还没回来
  await vi.waitFor(() => expect(getConversation).toHaveBeenCalled())
  expect(chat.pendingApproval?.approvalId).toBe(9)
  expect(chat.sending).toBe(false)

  refresh.resolve(history('waiting_approval'))
  expect(await pending).toBe(true)
  expect(chat.sending).toBe(false)

  stream = deferred<void>()
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  const decided = chat.approveApproval()
  await vi.waitFor(() => expect(decideApprovalStream).toHaveBeenCalledTimes(1))
  stream.resolve()
  expect(await decided).toBe(true)
})

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
    call_id: null,
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
  stale.resolve(stepsPage([]))
  await loading
  const finished = chat.feedItems.find((item) => item.kind === 'execution')
  if (finished?.kind !== 'execution') throw new Error('运行 7 没有进入消息流')
  expect(finished.steps).toMatchObject([{ seq: 2, kind: 'tool_call' }])
  expect(finished.loadStatus).toBe('loaded')
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
  steps.resolve(stepsPage([]))
  await loading
  await vi.waitFor(() => expect(decideApprovalStream).toHaveBeenCalledTimes(1))
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  finish()
  expect(await deciding).toBe(true)
})

it('断线后挂回运行的流：先看快照里已生成的正文，再跟实时分片', async () => {
  const chat = useChatStore()
  chat.activeId = 1
  const pending = chat.send('问题')
  handlers.onEvent?.({ type: 'assistant_delta', content: '前半句' })
  stream.reject(new Error('断流'))
  expect(await pending).toBe(false)
  expect(chat.canSend).toBe(false)

  vi.mocked(findRunByRequestId).mockResolvedValue(runDetail('running'))
  vi.mocked(getConversation).mockResolvedValue(history('running'))
  await chat.recoverExecution()

  // 订阅到的是「已经在跑的那次运行」，不是又发一遍
  expect(sendAgentStream).toHaveBeenCalledTimes(1)
  expect(subscribeAgentRun).toHaveBeenCalledWith(7, expect.anything(), expect.anything())
  expect(chat.sending).toBe(true)

  handlers.onEvent?.({
    type: 'run_snapshot',
    run_id: 7,
    conversation_id: 1,
    status: 'running',
    draft_content: '前半句，服务端已经收下',
    visible_step_count: 0,
    error_message: null,
    stop_reason: null,
    finished_time: null,
  })
  expect(chat.feedItems.at(-1)?.kind).toBe('execution')

  handlers.onEvent?.({ type: 'assistant_delta', content: '，后半句' })
  vi.mocked(getConversation).mockResolvedValue(history('completed'))
  const ending = {
    type: 'run_finished' as const,
    run_id: 7,
    assistant_message_id: 12,
    content: '完成正文',
    model: null,
    steps: 1,
  }
  handlers.onEvent?.(ending)
  handlers.onFinished(ending)
  live.resolve()
  await vi.waitFor(() => expect(chat.canSend).toBe(true))
  expect(chat.messages.at(-1)?.content).toBe('完成正文')
  expect(sendAgentStream).toHaveBeenCalledTimes(1)
})

it('终止：调服务端的终止接口，再把已生成的部分读回来', async () => {
  const chat = useChatStore()
  const { result } = start()
  expect(await chat.stopExecution()).toBe(true)
  expect(stopAgentRun).toHaveBeenCalledWith(7)

  // 服务端把正文落成消息、状态记成 cancelled，并关掉这条连接：
  // 这不是断线，发送要解锁，也不该留恢复提示
  vi.mocked(getConversation).mockResolvedValue(history('cancelled'))
  stream.resolve()
  await vi.waitFor(() => expect(chat.canSend).toBe(true))
  expect(chat.recoveryMessage).toBeNull()
  expect(
    chat.feedItems.some((item) => item.kind === 'execution' && item.cancelled === true),
  ).toBe(true)
  await result
})

it('终止之后清掉已经发出去的草稿，避免同一句话再发一遍', async () => {
  const chat = useChatStore()
  const { result } = start()
  // 点发送时那句话还留在输入框里（正常收尾成功才清）
  chat.composerText = '问题'
  vi.mocked(getConversation).mockResolvedValue(history('cancelled'))
  expect(await chat.stopExecution()).toBe(true)
  expect(chat.composerText).toBe('')
  stream.resolve()
  await result
})

it('重新生成：删掉旧的运行项，用同一条提问开一次新运行', async () => {
  const chat = useChatStore()
  const { result: first } = start()
  stream.reject(new Error('断流'))
  expect(await first).toBe(false)
  vi.mocked(getConversation).mockResolvedValue(history('cancelled'))
  await chat.recoverExecution()

  const again = deferred<void>()
  vi.mocked(regenerateAgentRun).mockImplementation((_id, callbacks) => {
    handlers = callbacks
    return again.promise
  })
  const regenerating = chat.regenerate(7)
  expect(regenerateAgentRun).toHaveBeenCalledWith(7, expect.anything(), expect.anything())
  handlers.onEvent?.({ type: 'run_started', run_id: 8, conversation_id: 1, user_message_id: 21 })
  handlers.onEvent?.({
    type: 'run_finished',
    run_id: 8,
    assistant_message_id: 22,
    content: '新的答案',
    model: null,
    steps: 1,
  })
  handlers.onFinished?.({
    type: 'run_finished',
    run_id: 8,
    assistant_message_id: 22,
    content: '新的答案',
    model: null,
    steps: 1,
  })
  // 新运行跑完后服务端的历史：问题只有一条，答案是新的
  vi.mocked(getConversation).mockResolvedValue({
    ...history('completed'),
    messages: [
      { id: 21, conversation_id: 1, role: 'user', content: '问题', model: null, create_time: '' },
      {
        id: 22,
        conversation_id: 1,
        role: 'assistant',
        content: '新的答案',
        model: null,
        create_time: '',
      },
    ],
    runs: [
      runSummary({
        id: 8,
        user_message_id: 21,
        assistant_message_id: 22,
        status: 'completed',
        visible_step_count: 0,
      }),
    ],
  })
  again.resolve()
  expect(await regenerating).toBe(true)
  // 新运行结束时已经写进历史：旧答案被替换成新答案，问题只出现一次
  expect(chat.messages.at(-1)?.content).toBe('新的答案')
  expect(chat.messages.filter((message) => message.role === 'user')).toHaveLength(1)
})
