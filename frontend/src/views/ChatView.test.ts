// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createTestingPinia } from '@pinia/testing'
import ChatView from './ChatView.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatToolbar from '@/components/chat/ChatToolbar.vue'
import appRouter from '@/router'
import { useChatStore } from '@/stores/chat'
import { listSkills } from '@/api/skills'
import type { ChatSkillList } from '@/types/api'

vi.mock('@/api/skills', () => ({ listSkills: vi.fn(), mountSkill: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: vi.fn() } }))
afterEach(() => vi.clearAllMocks())

async function setup(path = '/chat/1') {
  const pinia = createTestingPinia({ createSpy: vi.fn })
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
    global: { plugins: [pinia, router], directives: { loading: () => {} } },
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
