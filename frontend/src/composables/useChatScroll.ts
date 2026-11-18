import { nextTick, onBeforeUnmount, ref, watch } from 'vue'

export interface ChatScrollOptions {
  /** 当前会话 id：切换会话时丢弃旧会话的待渲染文本，并重新贴到底部 */
  conversationId: () => number | null
  /** 累计的流式正文；同一帧内只取最后一次 */
  streamingText: () => string
  /** 最后一条消息的 id：新消息到达时跟随 */
  lastMessageId: () => number | undefined
  /** 已到达的执行步骤数：步骤逐个出现时跟随 */
  stepCount: () => number
}

/** 离底部这么近就算「还在跟着最新内容」；再远就认为用户在翻历史 */
const STICK_THRESHOLD = 80

/**
 * 消息区的滚动、帧合并与分页锚点。
 *
 * 三件事分开记：
 * - `preview`：按帧提交给模板的流式正文，避免每个分片都触发一次 Markdown 渲染；
 * - `following`：用户是否还停在底部。只有跟着的时候才自动滚，翻历史时不许被拽回去；
 * - `keepAnchor`：往上翻页时把新增高度补进 scrollTop，让正在看的那一行留在原位。
 */
export function useChatScroll(options: ChatScrollOptions) {
  const scroller = ref<HTMLElement | null>(null)
  const preview = ref('')
  const following = ref(true)

  let frame: number | null = null
  let unmounting = false

  function distanceToBottom(el: HTMLElement) {
    return el.scrollHeight - el.scrollTop - el.clientHeight
  }

  function onScroll() {
    const el = scroller.value
    if (el) following.value = distanceToBottom(el) <= STICK_THRESHOLD
  }

  /** 同一帧只提交最新累计文本，等 Markdown 进入 DOM 后再读滚动高度 */
  function schedule() {
    if (unmounting || frame !== null) return
    // 记下这一帧是替哪个会话排的：帧真正执行时可能已经切走了
    const scheduledFor = options.conversationId()
    frame = requestAnimationFrame(() => {
      frame = null
      if (options.conversationId() !== scheduledFor) return
      preview.value = options.streamingText()
      void nextTick(() => {
        if (options.conversationId() !== scheduledFor) return
        if (following.value) {
          const el = scroller.value
          if (el) el.scrollTop = el.scrollHeight
        }
      })
    })
  }

  function cancel() {
    if (frame === null) return
    cancelAnimationFrame(frame)
    frame = null
  }

  /** 自己发消息、审批有结果：无条件贴回底部并立即提交一帧 */
  function follow() {
    following.value = true
    schedule()
  }

  /**
   * 包一次「往上加载」：先记下高度与位置，插进更早的消息后把差值补回 scrollTop。
   * 没有补这一步，翻页会把正在阅读的内容顶走。
   */
  async function keepAnchor(task: () => Promise<boolean>) {
    const el = scroller.value
    if (!el) return false
    const conversationId = options.conversationId()
    const height = el.scrollHeight
    const top = el.scrollTop
    const loaded = await task()
    if (!loaded) return false
    await nextTick()
    // 切会话或换了元素：这次加载已经不作数，别把新会话的位置改掉
    const stillHere = scroller.value === el && options.conversationId() === conversationId
    if (stillHere) el.scrollTop = top + el.scrollHeight - height
    return stillHere
  }

  // 切换会话：旧的待渲染文本作废，新会话从底部开始看
  watch(
    () => options.conversationId(),
    () => {
      cancel()
      preview.value = ''
      following.value = true
      schedule()
    },
    { flush: 'sync' },
  )

  watch(
    () => options.streamingText(),
    (text) => {
      if (!text) preview.value = ''
      schedule()
    },
    { immediate: true },
  )
  watch(() => options.lastMessageId(), () => schedule())
  watch(() => options.stepCount(), () => schedule())

  // 模板 ref 在挂载后才赋值；换元素时把监听挪过去（卸载时一并摘掉）
  watch(
    scroller,
    (el, previous) => {
      previous?.removeEventListener('scroll', onScroll)
      el?.addEventListener('scroll', onScroll, { passive: true })
    },
    { flush: 'post' },
  )

  onBeforeUnmount(() => {
    unmounting = true
    cancel()
    scroller.value?.removeEventListener('scroll', onScroll)
  })

  return { scroller, preview, following, schedule, follow, keepAnchor, onScroll }
}
