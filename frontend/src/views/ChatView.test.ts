// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createTestingPinia } from '@pinia/testing'
import ChatView from './ChatView.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatToolbar from '@/components/chat/ChatToolbar.vue'
import appRouter from '@/router'
import { useChatStore } from '@/stores/chat'
import MarkdownContent from '@/components/chat/MarkdownContent.vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import { getConversation } from '@/api/chat'
import { rescanSkills } from '@/api/skills'
import { runSummary, stepsPage } from '@/test/agent'
import { useSkillsStore } from '@/stores/skills'
import {
  getAgentSteps,
  listApprovals,
  sendAgentStream,
  type AgentStreamHandlers,
} from '@/api/agent'
import { useSettingsStore } from '@/stores/settings'
import type { ChatConversationDetail } from '@/types/api'

vi.mock('@/api/chat', () => ({ getConversation: vi.fn() }))
vi.mock('@/api/agent', async (importOriginal) => ({
  AgentHttpError: (await importOriginal<typeof import('@/api/agent')>()).AgentHttpError,
  getAgentSteps: vi.fn(),
  listApprovals: vi.fn(),
  sendAgentStream: vi.fn(),
}))
vi.mock('@/api/skills', () => ({ rescanSkills: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: vi.fn() } }))
afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

async function setup(path = '/chat/1', stream = false, replay = false) {
  const pinia = createTestingPinia({
    createSpy: vi.fn,
    stubActions: (name) =>
      !(stream && ['send', 'recoverExecution'].includes(name)) &&
      !(replay && ['openConversation', 'loadExecutionSteps', 'loadOlderMessages'].includes(name)),
  })
  const chat = useChatStore(pinia)
  const settings = useSettingsStore(pinia)
  const skills = useSkillsStore(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: appRouter.options.routes,
  })
  await router.push(path)
  await router.isReady()
  if (!replay) {
    vi.mocked(chat.openConversation).mockImplementation(async (id) => {
      chat.activeId = id
      chat.draft = false
    })
  }
  vi.mocked(chat.startNew).mockImplementation(() => {
    chat.activeId = null
    chat.draft = true
  })
  chat.agentMode = true
  chat.composerText = '整理会议'
  const wrapper = shallowMount(ChatView, {
    global: {
      plugins: [pinia, router],
      directives: { loading: () => {} },
      stubs:
        stream || replay
          ? {
              ChatMessageList: false,
              ChatExecutionItem: false,
              MarkdownContent: false,
              ChatMessage: false,
              AgentTimeline: false,
            }
          : {},
    },
  })
  return { wrapper, chat, router, settings, skills }
}

it('深度回答只改变推理强度，普通聊天和 Skill 使用同一发送链路', async () => {
  const { wrapper, chat, settings } = await setup()
  settings.model = {
    provider: 'openai',
    base_url: null,
    model: 'deepseek-chat',
    timeout_seconds: 30,
    has_api_key: true,
    api_key_hint: null,
    can_store_api_key: true,
    inherited_from_env: true,
    update_time: null,
    supports_reasoning_effort: true,
  }
  await flushPromises()
  const composer = wrapper.findComponent(ChatComposer)
  composer.vm.$emit('send')
  await flushPromises()
  expect(chat.send).toHaveBeenLastCalledWith('整理会议', 'auto', 'high', undefined)

  composer.vm.$emit('toggle-auto-skills')
  chat.agentMode = false
  composer.vm.$emit('send')
  await flushPromises()
  expect(chat.send).toHaveBeenLastCalledWith('整理会议', 'manual', 'none', undefined)

  chat.agentMode = true
  settings.model.supports_reasoning_effort = false
  composer.vm.$emit('send')
  await flushPromises()
  expect(chat.send).toHaveBeenLastCalledWith('整理会议', 'manual', 'none', undefined)
  wrapper.unmount()
})

it('切换会话只读取账号 Skill 缓存，本条消息可以显式选择且支持草稿', async () => {
  const { wrapper, chat, router, skills } = await setup('/chat')
  skills.items = [
    {
      key: 'user:guide',
      slug: 'guide',
      name: '本地指引',
      description: '用途',
      version: 'v1',
      source: 'local',
      trust: 'untrusted',
      tools: [],
      icon: 'sparkle',
    },
  ]
  skills.version = 'catalog1'
  await flushPromises()
  expect(wrapper.findComponent(ChatToolbar).props('skillDisabled')).toBe(false)
  wrapper.findComponent(ChatToolbar).vm.$emit('selectSkill', 'user:guide')
  await flushPromises()
  expect(chat.selectedSkillKey).toBe('user:guide')
  wrapper.findComponent(ChatComposer).vm.$emit('send')
  await flushPromises()
  expect(chat.send).toHaveBeenCalledWith('整理会议', 'auto', 'none', 'catalog1')
  await router.push('/chat/2')
  await flushPromises()
  expect(skills.items[0]?.key).toBe('user:guide')
  expect(rescanSkills).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('直接访问会话、切换路由及回到空白页时按 URL 加载', async () => {
  const { wrapper, chat, router } = await setup('/chat/123')
  await flushPromises()
  expect(chat.openConversation).toHaveBeenLastCalledWith(123)

  await router.push('/chat/456')
  await flushPromises()
  expect(chat.openConversation).toHaveBeenLastCalledWith(456)

  router.back()
  await flushPromises()
  expect(chat.activeId).toBe(123)
  await router.push('/chat')
  await flushPromises()
  expect(chat.activeId).toBeNull()
  expect(chat.openConversation).toHaveBeenCalledTimes(3)
  wrapper.unmount()
})

it('首条消息创建会话后立即更新地址，删除当前会话后返回空白页', async () => {
  const { wrapper, chat, router } = await setup('/chat')
  expect(chat.openConversation).not.toHaveBeenCalled()
  chat.activeId = 789
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/chat/789')
  chat.startNew()
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/chat')
  wrapper.unmount()
})

it('会话找不到时回到空白地址', async () => {
  const { wrapper, chat, router } = await setup('/chat')
  vi.mocked(chat.openConversation).mockImplementationOnce(async (id) => {
    chat.activeId = id
    chat.startNew()
  })
  await router.push('/chat/999')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/chat')
  wrapper.unmount()
})

async function setupStream() {
  const frames = new Map<number, FrameRequestCallback>()
  let frameId = 0
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    frames.set(++frameId, callback)
    return frameId
  })
  const cancelFrame = vi.fn((id: number) => frames.delete(id))
  vi.stubGlobal('cancelAnimationFrame', cancelFrame)
  let handlers!: AgentStreamHandlers
  let finish!: () => void
  let fail!: (error: Error) => void
  vi.mocked(sendAgentStream).mockImplementation((_id, _text, callbacks) => {
    handlers = callbacks
    return new Promise<void>((resolve, reject) => {
      fail = reject
      finish = resolve
    })
  })
  vi.mocked(getConversation).mockRejectedValueOnce(new Error('详情暂不可用'))
  const view = await setup('/chat/1', true)
  const sending = view.chat.send('测试 Markdown')
  await nextTick()

  async function paint() {
    const callbacks = [...frames.values()]
    frames.clear()
    callbacks.forEach((callback) => callback(0))
    await flushPromises()
  }

  async function complete(content: string) {
    handlers.onFinished({
      type: 'run_finished',
      run_id: 41,
      assistant_message_id: 2,
      content,
      steps: 2,
      model: null,
    })
    finish()
    await sending
    await flushPromises()
  }

  const delta = (content: string) => handlers.onEvent?.({ type: 'assistant_delta', content })
  const disconnect = async () => {
    fail(new Error('连接断开'))
    await sending
    await flushPromises()
  }
  return { ...view, frames, paint, complete, handlers, delta, cancelFrame, disconnect }
}

it('密集分片按帧渲染，滚动读取更新后的 DOM，完成时显示正式消息', async () => {
  const { wrapper, frames, paint, complete, delta } = await setupStream()
  const scroller = wrapper.get('.chat__scroll').element as HTMLElement
  const measureScroll = vi.fn(() => (scroller.querySelector('strong') ? 200 : 100))
  Object.defineProperty(scroller, 'scrollHeight', { get: measureScroll })

  delta('## 标题\n\n- **')
  await nextTick()
  expect(wrapper.findComponent(MarkdownContent).exists()).toBe(false)
  delta('分片内容**')
  await nextTick()
  expect(frames.size).toBe(1)
  expect(measureScroll).not.toHaveBeenCalled()

  await paint()
  expect(wrapper.get('.markdown-content').text()).toContain('标题')
  expect(wrapper.find('.chat__row--assistant').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('正在输入')
  expect(wrapper.get('li strong').text()).toBe('分片内容')
  expect(measureScroll).toHaveBeenCalledTimes(1)
  expect(scroller.scrollTop).toBe(200)

  delta('\n\n```txt\n尾部')
  await nextTick()
  await complete('## 标题\n\n- **分片内容**\n\n```txt\n尾部\n```')
  expect(wrapper.findAllComponents(MarkdownContent)).toHaveLength(1)
  expect(wrapper.findComponent(ChatMessage).exists()).toBe(true)
  expect(wrapper.get('pre code').text()).toBe('尾部')
  expect(wrapper.text()).not.toContain('正在输入')
  expect(wrapper.find('details.timeline').exists()).toBe(false)
  wrapper.unmount()
  expect(frames.size).toBe(0)
})

it('切换会话时取消待渲染帧，迟到的分片只在返回原会话时显示', async () => {
  const { wrapper, router, frames, paint, complete, delta, cancelFrame } = await setupStream()
  delta('## 原会话')
  await paint()
  expect(wrapper.get('.markdown-content').text()).toBe('原会话')

  delta('\n\n**待渲染**')
  await nextTick()
  const oldFrame = [...frames.keys()][0]
  await router.push('/chat/2')
  await flushPromises()
  expect(cancelFrame).toHaveBeenCalledWith(oldFrame)
  expect(wrapper.findComponent(MarkdownContent).exists()).toBe(false)

  delta('\n\n- 迟到的分片')
  await paint()
  expect(wrapper.findComponent(MarkdownContent).exists()).toBe(false)

  await router.push('/chat/1')
  await paint()
  expect(wrapper.get('li').text()).toBe('迟到的分片')
  await complete('## 原会话\n\n**待渲染**\n\n- 迟到的分片')
  wrapper.unmount()
})

it('直达或刷新后从每条助手回复打开对应详情，切换会话不混用结果', async () => {
  vi.mocked(getConversation).mockImplementation(async (id): Promise<ChatConversationDetail> => {
    const messageIds = id === 1 ? [12, 14] : [22]
    return {
      id,
      title: '对话',
      agent_key: 'default',
      skill_slug: null,
      create_time: '',
      update_time: '',
      messages: messageIds.map((messageId) => ({
        id: messageId,
        conversation_id: id,
        role: 'assistant',
        content: `助手回复 ${messageId}`,
        model: null,
        create_time: '',
      })),
      runs: messageIds.map((messageId) =>
        runSummary({
          id: messageId + 100,
          user_message_id: messageId - 1,
          assistant_message_id: messageId,
          visible_step_count: 1,
        }),
      ),
    }
  })
  vi.mocked(getAgentSteps).mockImplementation(async (runId) =>
    stepsPage([
      {
        seq: 2,
        kind: 'tool_result',
        tool_name: 'calculator',
        call_id: null,
        tool_args: { expression: String(runId) },
        content: `工具结果 ${runId}`,
        ok: true,
        duration_ms: 0,
        create_time: '',
        skill_key: null,
        skill_name: null,
        skill_source: null,
        skill_version: null,
      },
    ]),
  )

  const initial = await setup('/chat/1', false, true)
  await flushPromises()
  expect(initial.wrapper.findAll('details.timeline')).toHaveLength(2)
  initial.wrapper.unmount()

  // 新 Store 模拟浏览器刷新，详情只在打开对应入口时请求。
  const { wrapper, router } = await setup('/chat/1', false, true)
  await flushPromises()
  expect(getAgentSteps).not.toHaveBeenCalled()
  const timelines = wrapper.findAll<HTMLDetailsElement>('details.timeline')
  for (const [index, id] of [12, 14].entries()) {
    const timeline = timelines[index]
    expect(timeline.element.nextElementSibling?.textContent).toContain(`助手回复 ${id}`)
    timeline.element.open = true
    await timeline.trigger('toggle')
    await flushPromises()
    const detail = timeline.find('details.timeline__entry')
    expect(detail.text()).toContain(`工具结果 ${id + 100}`)
    expect(detail.text()).toContain(`"expression": "${id + 100}"`)
  }

  await router.push('/chat/2')
  await flushPromises()
  expect(wrapper.findAll('details.timeline')).toHaveLength(1)
  expect(wrapper.text()).not.toContain('工具结果 112')
  await router.push('/chat/1')
  await flushPromises()
  expect(wrapper.findAll('details.timeline')).toHaveLength(2)
  expect(wrapper.text()).toContain('工具结果 114')
  expect(getAgentSteps).toHaveBeenCalledTimes(2)
  wrapper.unmount()
})

it('模型开始调用工具时清除该轮临时文本，随后流式展示正式答复', async () => {
  const { wrapper, handlers, delta, paint, complete } = await setupStream()
  delta('中间说明')
  await paint()
  expect(wrapper.get('.markdown-content').text()).toBe('中间说明')
  handlers.onEvent?.({ type: 'assistant_preview_reset' })
  handlers.onEvent?.({ type: 'tool_call', seq: 2, tool: 'now', args: { timezone: 'UTC' }, call_id: null })
  await paint()
  expect(wrapper.find('.markdown-content').exists()).toBe(false)
  delta('**当前时间**')
  await paint()
  expect(wrapper.get('.markdown-content strong').text()).toBe('当前时间')
  expect(wrapper.get('details.timeline').element.previousElementSibling?.textContent).toContain(
    '测试 Markdown',
  )
  expect(wrapper.get('details.timeline').element.nextElementSibling?.textContent).toContain(
    '当前时间',
  )
  await complete('**当前时间**')
  expect(wrapper.get('.chat__row--assistant strong').text()).toBe('当前时间')
  expect(wrapper.findAll('details.timeline')).toHaveLength(1)
  expect(wrapper.get('details.timeline').element.nextElementSibling).toBe(
    wrapper.get('.chat__row--assistant').element,
  )
  expect(wrapper.text()).not.toContain('中间说明')
  wrapper.unmount()
})

it('分页只有助手消息时过程仍在正文前，补入用户消息后不重复', async () => {
  const user = {
    id: 11,
    conversation_id: 1,
    role: 'user',
    content: '用户问题',
    model: null,
    create_time: '',
  }
  const assistant = { ...user, id: 12, role: 'assistant', content: '助手回复' }
  const run = runSummary({
    id: 41,
    user_message_id: 11,
    assistant_message_id: 12,
    visible_step_count: 1,
  })
  vi.mocked(getConversation).mockImplementation(async (_id, options) => ({
    id: 1,
    title: '分页',
    agent_key: 'default',
    skill_slug: null,
    create_time: '',
    update_time: '',
    messages: options?.before_message_id ? [user] : [assistant],
    runs: options?.before_message_id ? [] : [run],
    next_before_message_id: options?.before_message_id ? null : 12,
  }))
  const { wrapper } = await setup('/chat/1', false, true)
  await flushPromises()
  expect(wrapper.get('details.timeline').element.nextElementSibling?.textContent).toContain(
    '助手回复',
  )
  const loadMore = wrapper.findAll('button').find((button) => button.text() === '加载更早消息')!
  await loadMore.trigger('click')
  await flushPromises()
  expect(getConversation).toHaveBeenLastCalledWith(1, { message_limit: 50, before_message_id: 12 })
  expect(wrapper.findAll('details.timeline')).toHaveLength(1)
  expect(wrapper.get('details.timeline').element.previousElementSibling?.textContent).toContain(
    '用户问题',
  )
  expect(wrapper.get('details.timeline').element.nextElementSibling?.textContent).toContain(
    '助手回复',
  )
  wrapper.unmount()
})

it('历史里的失败运行把服务端原因显示在原来该有回复的位置', async () => {
  vi.mocked(getConversation).mockResolvedValue({
    id: 1,
    title: '重启前留下的运行',
    agent_key: 'default',
    skill_slug: null,
    create_time: '',
    update_time: '',
    messages: [
      { id: 11, conversation_id: 1, role: 'user', content: '用户问题', model: null, create_time: '' },
    ],
    runs: [
      runSummary({
        id: 32,
        user_message_id: 11,
        assistant_message_id: null,
        status: 'failed',
        error_message: '服务重启，这次运行已中断',
      }),
    ],
  })
  const { wrapper } = await setup('/chat/1', false, true)
  await flushPromises()

  // 失败原因属于「那一条运行」，写在原来该出现回复的位置，而不是全局横幅
  expect(wrapper.get('.chat__execution-error').text()).toContain('服务重启，这次运行已中断')
  expect(wrapper.find('.chat__recovery').exists()).toBe(false)
  expect(wrapper.findComponent(ChatComposer).props('disabled')).toBe(false)
  wrapper.unmount()
})

it.each(['failed', 'cancelled', 'waiting_approval'] as const)(
  '没有助手消息的 %s 运行保持在用户消息之后',
  async (status) => {
    vi.mocked(getConversation).mockResolvedValue({
      id: 1,
      title: '未完成',
      agent_key: 'default',
      skill_slug: null,
      create_time: '',
      update_time: '',
      messages: [
        {
          id: 11,
          conversation_id: 1,
          role: 'user',
          content: '用户问题',
          model: null,
          create_time: '',
        },
      ],
      runs: [
        runSummary({
          id: 41,
          user_message_id: 11,
          assistant_message_id: null,
          status,
          visible_step_count: 1,
        }),
      ],
    })
    vi.mocked(listApprovals).mockResolvedValue([
      {
        id: 9,
        run_id: 41,
        seq: 2,
        tool_name: 'rename_conversation',
        tool_args: {},
        status: 'pending',
        note: '需要确认',
        decided_time: null,
        create_time: '',
      },
    ])
    const { wrapper } = await setup('/chat/1', false, true)
    await flushPromises()
    expect(wrapper.findAll('details.timeline')).toHaveLength(1)
    expect(wrapper.get('details.timeline').element.previousElementSibling?.textContent).toContain(
      '用户问题',
    )
    expect(wrapper.find('.chat__row--assistant').exists()).toBe(false)
    if (status === 'waiting_approval') {
      expect(wrapper.get('details.timeline').element.nextElementSibling?.tagName).toBe(
        'APPROVAL-CARD-STUB',
      )
    }
    wrapper.unmount()
  },
)

it('临时消息转正式 ID、完成及历史核对后保留两层展开，正文只显示一次', async () => {
  const { wrapper, handlers, delta, paint, complete, chat } = await setupStream()
  const execution = wrapper.findComponent({ name: 'ChatExecutionItem' }).vm.$
  handlers.onEvent?.({ type: 'run_started', run_id: 41, conversation_id: 1, user_message_id: 11 })
  handlers.onEvent?.({ type: 'tool_call', seq: 2, tool: 'now', args: { timezone: 'UTC' }, call_id: null })
  await paint()
  expect(wrapper.findComponent({ name: 'ChatExecutionItem' }).vm.$).toBe(execution)
  const timeline = wrapper.get<HTMLDetailsElement>('details.timeline')
  const entry = wrapper.get<HTMLDetailsElement>('details.timeline__entry')
  timeline.element.open = true
  entry.element.open = true
  await timeline.trigger('toggle')
  await entry.trigger('toggle')
  handlers.onEvent?.({
    type: 'tool_result',
    call_id: null,
    seq: 3,
    tool: 'now',
    ok: true,
    content: '结果',
    duration_ms: 1,
  })
  delta('唯一的正文')
  await paint()
  expect(wrapper.findAll('.chat__bubble--streaming')).toHaveLength(1)

  // 完成后的真实历史查询使用相同运行；较旧分页可能只包含助手消息。
  vi.mocked(getConversation)
    .mockReset()
    .mockResolvedValue({
      id: 1,
      title: '对话',
      agent_key: 'default',
      skill_slug: null,
      create_time: '',
      update_time: '',
      messages: [
        {
          id: 2,
          conversation_id: 1,
          role: 'assistant',
          content: '唯一的正文',
          model: null,
          create_time: '',
        },
      ],
      runs: [
        runSummary({
          id: 41,
          user_message_id: 11,
          assistant_message_id: 2,
          visible_step_count: 2,
        }),
      ],
    })
  await complete('唯一的正文')
  await paint()
  expect(chat.sending).toBe(false)
  expect(chat.feedItems.some((item) => item.kind === 'execution' && item.running)).toBe(false)
  expect(wrapper.findComponent({ name: 'ChatExecutionItem' }).vm.$).toBe(execution)
  expect(wrapper.get('details.timeline').element).toBe(timeline.element)
  expect(wrapper.get('details.timeline__entry').element).toBe(entry.element)
  expect(timeline.element.open).toBe(true)
  expect(entry.element.open).toBe(true)
  expect(wrapper.findAll('.chat__row--assistant')).toHaveLength(1)
  expect(wrapper.find('.chat__bubble--streaming').exists()).toBe(false)
  expect(wrapper.text().match(/唯一的正文/g)).toHaveLength(1)
  expect(getAgentSteps).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('断流后显示核对入口并禁止重发，查询完成后恢复正文和发送', async () => {
  const { wrapper, handlers, disconnect, chat } = await setupStream()
  handlers.onEvent?.({ type: 'run_started', run_id: 41, conversation_id: 1, user_message_id: 11 })
  await disconnect()
  expect(wrapper.get('.chat__recovery').text()).toContain('详情暂不可用')
  expect(wrapper.findComponent(ChatComposer).props('disabled')).toBe(true)
  vi.mocked(getConversation).mockResolvedValueOnce({
    id: 1,
    title: '对话',
    agent_key: 'default',
    skill_slug: null,
    create_time: '',
    update_time: '',
    messages: [
      {
        id: 12,
        conversation_id: 1,
        role: 'assistant',
        content: '恢复的正文',
        model: null,
        create_time: '',
      },
    ],
    runs: [
      runSummary({ id: 41, user_message_id: 11, assistant_message_id: 12, visible_step_count: 0 }),
    ],
  })
  await wrapper.get('.chat__recovery button').trigger('click')
  await flushPromises()
  expect(wrapper.find('.chat__recovery').exists()).toBe(false)
  expect(wrapper.get('.chat__row--assistant').text()).toContain('恢复的正文')
  expect(chat.canSend).toBe(true)
  expect(wrapper.findComponent(ChatComposer).props('disabled')).toBe(false)
  expect(sendAgentStream).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})

it('输入区的停止按钮交给商店去终止这次运行', async () => {
  const { wrapper, chat } = await setup('/chat/1')
  wrapper.findComponent(ChatComposer).vm.$emit('stop')
  await nextTick()
  expect(chat.stopExecution).toHaveBeenCalled()
  wrapper.unmount()
})

it('恢复提示位于消息区与输入区之间，可以收起但不改变状态', async () => {
  const { wrapper, handlers, disconnect, chat } = await setupStream()
  handlers.onEvent?.({ type: 'run_started', run_id: 41, conversation_id: 1, user_message_id: 11 })
  await disconnect()
  const nodes = [...wrapper.element.children].map((el) => el.className)
  const scrollAt = nodes.findIndex((name) => name.includes('chat__scroll'))
  const recoveryAt = nodes.findIndex((name) => name.includes('chat__recovery'))
  expect(scrollAt).toBeGreaterThanOrEqual(0)
  // 提示紧挨在消息区之后、输入区之前：靠 flex 挤压消息区高度，而不是浮在页面上
  expect(recoveryAt).toBe(scrollAt + 1)
  expect(nodes).toHaveLength(recoveryAt + 2)
  expect(wrapper.element.lastElementChild).toBe(wrapper.findComponent(ChatComposer).element)

  await wrapper.get('[aria-label="收起提示"]').trigger('click')
  expect(wrapper.find('.chat__recovery').exists()).toBe(false)
  // 收起只是不再占地方：提示来源没变，发送仍然锁着
  expect(chat.recoveryMessage).toContain('详情暂不可用')
  expect(chat.canSend).toBe(false)
  expect(wrapper.findComponent(ChatComposer).props('disabled')).toBe(true)
  wrapper.unmount()
})
