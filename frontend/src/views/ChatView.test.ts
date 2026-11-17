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
import { sendMessageStream, type ChatStreamHandlers } from '@/api/chat'
import { listSkills } from '@/api/skills'
import type { ChatSkillList } from '@/types/api'

vi.mock('@/api/chat', () => ({ sendMessageStream: vi.fn() }))
vi.mock('@/api/skills', () => ({ listSkills: vi.fn(), mountSkill: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: vi.fn() } }))
afterEach(() => {
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

async function setup(path = '/chat/1', stream = false) {
  const pinia = createTestingPinia({
    createSpy: vi.fn,
    stubActions: (name) => !stream || name !== 'send',
  })
  const chat = useChatStore(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: appRouter.options.routes,
  })
  await router.push(path)
  await router.isReady()
  vi.mocked(chat.openConversation).mockImplementation(async (id) => {
    chat.activeId = id
    chat.draft = false
  })
  vi.mocked(chat.loadAgentRuns).mockResolvedValue(undefined)
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
      stubs: stream ? { MarkdownContent: false, ChatMessage: false } : {},
    },
  })
  return { wrapper, chat, router }
}

it('未取得列表也保留手动挂载语义，用户可显式开启自动选择，普通回答不走 Agent', async () => {
  vi.mocked(listSkills).mockRejectedValue(new Error('离线'))
  const { wrapper, chat } = await setup()
  await flushPromises()
  const composer = wrapper.findComponent(ChatComposer)
  composer.vm.$emit('send')
  await flushPromises()
  expect(chat.sendWithAgent).toHaveBeenLastCalledWith('整理会议', 'manual')
  composer.vm.$emit('toggle-auto-skills')
  await flushPromises()
  composer.vm.$emit('send')
  await flushPromises()
  expect(chat.sendWithAgent).toHaveBeenLastCalledWith('整理会议', 'auto')
  chat.agentMode = false
  composer.vm.$emit('send')
  await flushPromises()
  expect(chat.send).toHaveBeenCalledWith('整理会议')
  wrapper.unmount()
})

it('旧会话的延迟响应不能覆盖新会话技能', async () => {
  let resolveOld!: (value: ChatSkillList) => void
  vi.mocked(listSkills).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        resolveOld = resolve
      }),
  )
  vi.mocked(listSkills).mockResolvedValue({ items: [], mounted: null })
  const { wrapper, chat } = await setup()
  await flushPromises()
  chat.activeId = 2
  await flushPromises()
  resolveOld({
    mounted: 'old',
    items: [
      {
        slug: 'old',
        name: '旧会话技能',
        description: '',
        tools: [],
        tool_count: 0,
        icon: '',
        source: 'builtin',
        skill_id: null,
        mounted: true,
      },
    ],
  })
  await flushPromises()
  expect(wrapper.findComponent(ChatToolbar).props('skillName')).toBe('')
  wrapper.unmount()
})

it('直接访问会话、切换路由及回到空白页时按 URL 加载', async () => {
  vi.mocked(listSkills).mockResolvedValue({ items: [], mounted: null })
  const { wrapper, chat, router } = await setup('/chat/123')
  await flushPromises()
  expect(chat.openConversation).toHaveBeenLastCalledWith(123)
  expect(chat.loadAgentRuns).toHaveBeenLastCalledWith(123)

  await router.push('/chat/456')
  await flushPromises()
  expect(chat.openConversation).toHaveBeenLastCalledWith(456)
  expect(chat.loadAgentRuns).toHaveBeenLastCalledWith(456)

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
  vi.mocked(listSkills).mockResolvedValue({ items: [], mounted: null })
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
  vi.mocked(listSkills).mockResolvedValue({ items: [], mounted: null })
  const { wrapper, chat, router } = await setup('/chat')
  vi.mocked(chat.openConversation).mockImplementationOnce(async (id) => {
    chat.activeId = id
    chat.startNew()
  })
  await router.push('/chat/999')
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/chat')
  expect(chat.loadAgentRuns).not.toHaveBeenCalled()
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
  let handlers!: ChatStreamHandlers
  let finish!: () => void
  vi.mocked(sendMessageStream).mockImplementation((_id, _text, callbacks) => {
    handlers = callbacks
    return new Promise<void>((resolve) => {
      finish = resolve
    })
  })
  vi.mocked(listSkills).mockResolvedValue({ items: [], mounted: null })
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
    handlers.onDone({
      type: 'done',
      conversation_id: 1,
      conversation_title: '测试 Markdown',
      message_count: 2,
      assistant_message: {
        id: 2,
        conversation_id: 1,
        role: 'assistant',
        content,
        model: null,
        create_time: '',
      },
    })
    finish()
    await sending
    await flushPromises()
  }

  return { ...view, frames, paint, complete, handlers, cancelFrame }
}

it('密集分片按帧渲染，滚动读取更新后的 DOM，完成时显示正式消息', async () => {
  const { wrapper, frames, paint, complete, handlers } = await setupStream()
  const scroller = wrapper.get('.chat__scroll').element as HTMLElement
  const measureScroll = vi.fn(() => (scroller.querySelector('strong') ? 200 : 100))
  Object.defineProperty(scroller, 'scrollHeight', { get: measureScroll })

  handlers.onDelta('## 标题\n\n- **')
  await nextTick()
  expect(wrapper.findComponent(MarkdownContent).exists()).toBe(false)
  handlers.onDelta('分片内容**')
  await nextTick()
  expect(frames.size).toBe(1)
  expect(measureScroll).not.toHaveBeenCalled()

  await paint()
  expect(wrapper.get('.markdown-content').text()).toContain('标题')
  expect(wrapper.get('li strong').text()).toBe('分片内容')
  expect(measureScroll).toHaveBeenCalledTimes(1)
  expect(scroller.scrollTop).toBe(200)

  handlers.onDelta('\n\n```txt\n尾部')
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
  const { wrapper, router, frames, paint, complete, handlers, cancelFrame } = await setupStream()
  handlers.onDelta('## 原会话')
  await paint()
  expect(wrapper.get('.markdown-content').text()).toBe('原会话')

  handlers.onDelta('\n\n**待渲染**')
  await nextTick()
  const oldFrame = [...frames.keys()][0]
  await router.push('/chat/2')
  await flushPromises()
  expect(cancelFrame).toHaveBeenCalledWith(oldFrame)
  expect(wrapper.findComponent(MarkdownContent).exists()).toBe(false)

  handlers.onDelta('\n\n- 迟到的分片')
  await paint()
  expect(wrapper.findComponent(MarkdownContent).exists()).toBe(false)

  await router.push('/chat/1')
  await paint()
  expect(wrapper.get('li').text()).toBe('迟到的分片')
  await complete('## 原会话\n\n**待渲染**\n\n- 迟到的分片')
  wrapper.unmount()
})
