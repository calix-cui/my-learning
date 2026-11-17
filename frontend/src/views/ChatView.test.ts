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
import { useSkillsStore } from '@/stores/skills'
import { getAgentSteps, sendAgentStream, type AgentStreamHandlers } from '@/api/agent'
import { useSettingsStore } from '@/stores/settings'
import type { ChatConversationDetail } from '@/types/api'

vi.mock('@/api/chat', () => ({ getConversation: vi.fn() }))
vi.mock('@/api/agent', () => ({ getAgentSteps: vi.fn(), sendAgentStream: vi.fn() }))
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
      !(stream && name === 'send') &&
      !(replay && ['openConversation', 'loadExecutionSteps'].includes(name)),
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
          ? { MarkdownContent: false, ChatMessage: false, AgentTimeline: false }
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
  vi.mocked(sendAgentStream).mockImplementation((_id, _text, callbacks) => {
    handlers = callbacks
    return new Promise<void>((resolve) => {
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
  return { ...view, frames, paint, complete, handlers, delta, cancelFrame }
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
      runs: messageIds.map((messageId) => ({
        id: messageId + 100,
        user_message_id: messageId - 1,
        assistant_message_id: messageId,
        status: 'completed',
        visible_step_count: 1,
      })),
    }
  })
  vi.mocked(getAgentSteps).mockImplementation(async (runId) => [
    {
      seq: 2,
      kind: 'tool_result',
      tool_name: 'calculator',
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
  ])

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
    expect(timeline.element.previousElementSibling?.textContent).toContain(`助手回复 ${id}`)
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
  handlers.onEvent?.({ type: 'tool_call', seq: 2, tool: 'now', args: { timezone: 'UTC' } })
  await paint()
  expect(wrapper.find('.markdown-content').exists()).toBe(false)
  delta('**当前时间**')
  await paint()
  expect(wrapper.get('.markdown-content strong').text()).toBe('当前时间')
  await complete('**当前时间**')
  expect(wrapper.get('.chat__row--assistant strong').text()).toBe('当前时间')
  expect(wrapper.text()).not.toContain('中间说明')
  wrapper.unmount()
})
