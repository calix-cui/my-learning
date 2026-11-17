// @vitest-environment happy-dom
import { expect, it, vi, afterEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from './App.vue'
import { useSettingsStore } from '@/stores/settings'
import { useSessionStore } from '@/stores/session'
import { rescanSkills } from '@/api/skills'

vi.mock('@/api/skills', () => ({ rescanSkills: vi.fn() }))
afterEach(() => vi.clearAllMocks())

async function setup(loggedIn = false) {
  const pinia = createTestingPinia({
    createSpy: vi.fn,
    stubActions: (name) => !['initialize', 'scan', 'reset'].includes(name),
  })
  const session = useSessionStore(pinia)
  vi.mocked(useSettingsStore(pinia).load).mockResolvedValue(null)
  if (loggedIn) session.user = { id: 1 } as NonNullable<typeof session.user>
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', component: { template: '<div />' }, meta: { public: true } },
      { path: '/chat/:id?', component: { template: '<div />' } },
    ],
  })
  await router.push(loggedIn ? '/chat/1' : '/login')
  const wrapper = shallowMount(App, { global: { plugins: [pinia, router] } })
  return { session, router, wrapper }
}

it('登录及刷新各获取一次 Skill，切换会话和退出不再发目录请求', async () => {
  vi.mocked(rescanSkills).mockResolvedValue({ items: [], version: 'v1', legacy_count: 0 })
  const { session, router, wrapper } = await setup()
  await flushPromises()
  expect(rescanSkills).not.toHaveBeenCalled()
  session.user = { id: 1 } as NonNullable<typeof session.user>
  await flushPromises()
  expect(rescanSkills).toHaveBeenCalledTimes(1)
  await router.push('/chat/1')
  await router.push('/chat/2')
  await flushPromises()
  expect(rescanSkills).toHaveBeenCalledTimes(1)
  wrapper.unmount()

  const refreshed = await setup(true)
  await flushPromises()
  expect(rescanSkills).toHaveBeenCalledTimes(2)
  refreshed.session.user = null
  await flushPromises()
  expect(rescanSkills).toHaveBeenCalledTimes(2)
  refreshed.wrapper.unmount()
})
