// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import ChatView from './ChatView.vue'
import ChatComposer from '@/components/chat/ChatComposer.vue'
import ChatToolbar from '@/components/chat/ChatToolbar.vue'
import { useChatStore } from '@/stores/chat'
import { listSkills } from '@/api/skills'
import type { ChatSkillList } from '@/types/api'

vi.mock('@/api/skills', () => ({ listSkills: vi.fn(), mountSkill: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { success: vi.fn(), error: vi.fn() } }))
afterEach(() => vi.clearAllMocks())

function setup() {
  const pinia = createTestingPinia({ createSpy: vi.fn })
  const chat = useChatStore(pinia)
  chat.activeId = 1
  chat.agentMode = true
  chat.composerText = '整理会议'
  const wrapper = shallowMount(ChatView, {
    global: { plugins: [pinia], directives: { loading: () => {} } },
  })
  return { wrapper, chat }
}

it('未取得列表也保留手动挂载语义，用户可显式开启自动选择，普通回答不走 Agent', async () => {
  vi.mocked(listSkills).mockRejectedValue(new Error('离线'))
  const { wrapper, chat } = setup()
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
  const { wrapper, chat } = setup()
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
