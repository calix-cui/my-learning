// @vitest-environment happy-dom
import { afterEach, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { useChatRoute } from './useChatRoute'

const Blank = defineComponent({ render: () => h('div') })

interface HarnessState {
  activeId: number | null
  inDraft: boolean
  sending: boolean
}

async function harness(path = '/chat', options: { loose?: boolean } = {}) {
  const state = reactive<HarnessState>({ activeId: null, inDraft: false, sending: false })
  const open = vi.fn(async (id: number) => {
    state.activeId = id
    state.inDraft = false
  })
  const startNew = vi.fn(() => {
    state.activeId = null
    state.inDraft = true
  })
  const router: Router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        // 真实路由用 [1-9]\d* 收窄参数；loose 用来验证「万一放开了」时的兜底分支
        path: options.loose ? '/chat/:conversationId?' : '/chat/:conversationId([1-9]\\d*)?',
        name: 'chat',
        component: Blank,
      },
      { path: '/settings', name: 'settings', component: Blank },
    ],
  })
  const Host = defineComponent({
    setup() {
      useChatRoute({
        activeId: () => state.activeId,
        inDraft: () => state.inDraft,
        sending: () => state.sending,
        open,
        startNew,
      })
      return () => h('div')
    },
  })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(Host, { global: { plugins: [router] } })
  await flushPromises()
  return { state, open, startNew, router, wrapper }
}

afterEach(() => {
  vi.clearAllMocks()
})

it('没有会话参数的地址进入草稿态', async () => {
  const { state, open, startNew } = await harness('/chat')
  expect(startNew).toHaveBeenCalledTimes(1)
  expect(open).not.toHaveBeenCalled()
  expect(state.activeId).toBeNull()
})

it('已经在草稿态时不重复清空，保留用户刚打的字', async () => {
  const { state, startNew, router } = await harness('/chat')
  state.inDraft = true
  state.activeId = null
  await router.push('/chat?x=1')
  await flushPromises()
  expect(startNew).toHaveBeenCalledTimes(1)
})

it('深链打开指定会话', async () => {
  const { state, open, router } = await harness('/chat')
  await router.push('/chat/7')
  await flushPromises()
  expect(open).toHaveBeenCalledWith(7)
  expect(state.activeId).toBe(7)
})

it('正在发送时访问同一会话不打断它重开一次', async () => {
  const { state, open, router } = await harness('/chat/7')
  open.mockClear()
  state.activeId = 7
  state.sending = true
  await router.push('/chat/7')
  await flushPromises()
  expect(open).not.toHaveBeenCalled()
})

it('非法会话 id 不打开会话，擦回空白地址', async () => {
  const { open, router } = await harness('/chat/7', { loose: true })
  open.mockClear()
  await router.push('/chat/0')
  await flushPromises()
  expect(open).not.toHaveBeenCalled()
  expect(router.currentRoute.value.path).toBe('/chat')
})

it('首条消息建库后把草稿地址换成真实 id，并保留查询参数', async () => {
  const { state, router } = await harness('/chat?settings=1')
  state.activeId = 12
  await nextTick()
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/chat/12')
  expect(router.currentRoute.value.query.settings).toBe('1')
})

it('当前会话被删除后回到空白地址，并保留查询参数', async () => {
  const { state, router } = await harness('/chat/3')
  state.activeId = null
  await nextTick()
  await flushPromises()
  expect(router.currentRoute.value.path).toBe('/chat')
  expect(router.currentRoute.value.query).toEqual({})
})

it('不在对话路由上不改写地址', async () => {
  const { state, startNew, router } = await harness('/settings')
  startNew.mockClear()
  state.activeId = 5
  await nextTick()
  await flushPromises()
  expect(startNew).not.toHaveBeenCalled()
  expect(router.currentRoute.value.path).toBe('/settings')
})
