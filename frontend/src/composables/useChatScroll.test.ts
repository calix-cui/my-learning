// @vitest-environment happy-dom
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, ref } from 'vue'
import { afterEach, expect, it, vi } from 'vitest'

import { useChatScroll } from './useChatScroll'

/** 用可控的 rAF 与几何尺寸搭一个最小宿主，验证组合式函数自己的行为 */
async function harness() {
  const frames = new Map<number, FrameRequestCallback>()
  let frameId = 0
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    frames.set(++frameId, callback)
    return frameId
  })
  const cancelFrame = vi.fn((id: number) => frames.delete(id))
  vi.stubGlobal('cancelAnimationFrame', cancelFrame)

  const conversationId = ref<number | null>(1)
  const streamingText = ref('')
  const lastMessageId = ref<number | undefined>(undefined)
  const stepCount = ref(0)

  let api!: ReturnType<typeof useChatScroll>
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useChatScroll({
          conversationId: () => conversationId.value,
          streamingText: () => streamingText.value,
          lastMessageId: () => lastMessageId.value,
          stepCount: () => stepCount.value,
        })
        return () => h('div', { ref: api.scroller, class: 'scroll' }, api.preview.value)
      },
    }),
  )

  await nextTick() // 等 post watcher 把 scroll 监听装上
  const el = () => wrapper.get('.scroll').element as HTMLElement
  let height = 1000
  Object.defineProperty(el(), 'scrollHeight', { configurable: true, get: () => height })
  Object.defineProperty(el(), 'clientHeight', { configurable: true, get: () => 400 })

  async function paint() {
    const callbacks = [...frames.values()]
    frames.clear()
    callbacks.forEach((callback) => callback(0))
    await flushPromises()
    await nextTick()
  }

  function scrollTo(top: number) {
    el().scrollTop = top
    el().dispatchEvent(new Event('scroll'))
  }

  return {
    wrapper,
    api,
    el,
    frames,
    cancelFrame,
    paint,
    scrollTo,
    setHeight: (value: number) => {
      height = value
    },
    streamingText,
    conversationId,
    lastMessageId,
    stepCount,
  }
}

afterEach(() => vi.unstubAllGlobals())

it('同一帧只提交一次最新文本，并在 DOM 更新后滚到底部', async () => {
  const kit = await harness()
  kit.streamingText.value = '第一段'
  kit.streamingText.value = '第一段第二段'
  await nextTick()
  expect(kit.frames.size).toBe(1)

  await kit.paint()
  expect(kit.api.preview.value).toBe('第一段第二段')
  expect(kit.el().scrollTop).toBe(1000)
  kit.wrapper.unmount()
})

it('用户向上翻历史时不再被拽回底部，滚回底部后恢复跟随', async () => {
  const kit = await harness()
  kit.scrollTo(300) // 1000 - 300 - 400 = 300，远超阈值
  expect(kit.api.following.value).toBe(false)

  kit.streamingText.value = '新内容'
  await nextTick()
  await kit.paint()
  expect(kit.el().scrollTop).toBe(300)

  kit.scrollTo(600) // 正好在底部
  expect(kit.api.following.value).toBe(true)
  kit.streamingText.value = '再来一段'
  await nextTick()
  await kit.paint()
  expect(kit.el().scrollTop).toBe(1000)
  kit.wrapper.unmount()
})

it('自己发消息时无条件贴回底部', async () => {
  const kit = await harness()
  kit.scrollTo(0)
  expect(kit.api.following.value).toBe(false)
  kit.api.follow()
  await kit.paint()
  expect(kit.api.following.value).toBe(true)
  expect(kit.el().scrollTop).toBe(1000)
  kit.wrapper.unmount()
})

it('切换会话时取消待渲染帧、清空预览并重新贴底', async () => {
  const kit = await harness()
  kit.streamingText.value = '旧会话正文'
  await nextTick()
  expect(kit.frames.size).toBe(1)

  kit.conversationId.value = 2
  expect(kit.cancelFrame).toHaveBeenCalled()
  expect(kit.api.preview.value).toBe('')
  expect(kit.api.following.value).toBe(true)
  kit.wrapper.unmount()
})

it('帧属于别的会话时丢弃，不拿旧文本去滚新会话', async () => {
  const kit = await harness()
  kit.streamingText.value = '旧会话正文'
  await nextTick()
  const callbacks = [...kit.frames.values()]
  kit.frames.clear()
  kit.conversationId.value = 2
  kit.streamingText.value = ''
  kit.el().scrollTop = 0
  callbacks.forEach((callback) => callback(0))
  await flushPromises()
  await nextTick()
  expect(kit.api.preview.value).toBe('')
  expect(kit.el().scrollTop).toBe(0)
  kit.wrapper.unmount()
})

it('加载更早的消息时把新增高度补进 scrollTop，正在读的那行不动', async () => {
  const kit = await harness()
  kit.el().scrollTop = 500
  let resolved = false
  const task = vi.fn(async () => {
    kit.setHeight(1600) // 上面插进了 600px 的内容
    resolved = true
    return true
  })

  await kit.api.keepAnchor(task)
  expect(resolved).toBe(true)
  expect(task).toHaveBeenCalledTimes(1)
  expect(kit.el().scrollTop).toBe(500 + 600)
  kit.wrapper.unmount()
})

it('加载失败或会话已经切走时不改滚动位置', async () => {
  const kit = await harness()
  kit.el().scrollTop = 500
  expect(await kit.api.keepAnchor(async () => false)).toBe(false)
  expect(kit.el().scrollTop).toBe(500)

  kit.conversationId.value = 2
  kit.el().scrollTop = 500
  const moved = await kit.api.keepAnchor(async () => {
    kit.conversationId.value = 3
    kit.setHeight(1600)
    return true
  })
  expect(moved).toBe(false)
  expect(kit.el().scrollTop).toBe(500)
  kit.wrapper.unmount()
})

it('卸载后取消待渲染帧，不再写入预览', async () => {
  const kit = await harness()
  kit.streamingText.value = '还没画的正文'
  await nextTick()
  expect(kit.frames.size).toBe(1)

  kit.wrapper.unmount()
  expect(kit.cancelFrame).toHaveBeenCalled()
  expect(kit.frames.size).toBe(0)

  kit.api.schedule()
  expect(kit.frames.size).toBe(0)
})
