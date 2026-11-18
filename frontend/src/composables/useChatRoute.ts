import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export interface ChatRouteOptions {
  /** 当前会话 id；草稿态是 null */
  activeId: () => number | null
  /** 是否已经在草稿态。已经在草稿态就不要重复 startNew，否则会清掉刚打的字 */
  inDraft: () => boolean
  /** 正在发送：同一会话不打断它去重开一次 */
  sending: () => boolean
  open: (id: number) => void | Promise<void>
  startNew: () => void
}

/**
 * 会话地址与 Store 状态的双向同步。
 *
 * 两个方向：
 * - 地址 → 状态：`/chat/:id` 打开该会话，`/chat` 回到草稿态，非法 id 擦回 `/chat`；
 * - 状态 → 地址：首条消息建库后把草稿地址换成真实 id，当前会话被删除或打不开时退回 `/chat`。
 *
 * 都只认 `name === 'chat'`：设置浮层保留会话地址，在别的路由上不应该被改写。
 */
export function useChatRoute(options: ChatRouteOptions) {
  const route = useRoute()
  const router = useRouter()

  const blankAddress = () => ({ name: 'chat', params: { conversationId: '' } })

  // 地址 → 状态
  watch(
    () => route.params.conversationId,
    async (raw) => {
      if (route.name !== 'chat') return
      const param = Array.isArray(raw) ? raw[0] : raw
      if (!param) {
        // 已经在草稿态就别再 startNew：那会丢弃用户刚打的草稿
        if (options.activeId() !== null || !options.inDraft()) options.startNew()
        return
      }
      const id = Number(param)
      if (!Number.isSafeInteger(id) || id <= 0) {
        await router.replace(blankAddress())
        return
      }
      if (options.activeId() === id && options.sending()) return
      await options.open(id)
    },
    { immediate: true },
  )

  // 状态 → 地址。同步 flush：建会话成功后地址要立刻跟上，别留一帧空白地址
  watch(
    () => options.activeId(),
    (id, previousId) => {
      if (route.name !== 'chat') return
      const param = route.params.conversationId
      if (id !== null && !param && previousId === null) {
        void router.replace({ name: 'chat', params: { conversationId: id }, query: route.query })
      } else if (id === null && param === String(previousId)) {
        void router.replace({ ...blankAddress(), query: route.query })
      }
    },
    { flush: 'sync' },
  )
}
