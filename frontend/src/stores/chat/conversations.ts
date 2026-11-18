import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  createConversation,
  deleteConversation,
  listConversations,
  renameConversation,
} from '@/api/chat'
import { confirmDialog, promptDialog } from '@/components/ui/messageBox'
import type { ChatConversationListItem } from '@/types/api'
import { DRAFT_KEY, type ThreadState } from './threads'

export interface ConversationDeps {
  threads: ThreadState
  /** 删掉的正是当前会话时，页面要回到空白草稿 */
  onActiveRemoved(): void
}

/**
 * 会话列表与「当前打开的是哪个会话」。
 *
 * 只管列表行、打开状态和账号代次；消息、执行过程、分页都在别的模块。
 * `activeId` 为 null 表示草稿态：界面已经是一个空白会话，后端还没有记录。
 */
export function createConversations(deps: ConversationDeps) {
  const rows = ref<ChatConversationListItem[]>([])
  const activeId = ref<number | null>(null)
  const draft = ref(false)
  const loadingList = ref(false)
  /** 正在拉某个会话的消息（只影响当前会话的骨架屏） */
  const loadingMessages = ref(false)
  const activeConversation = computed(
    () => rows.value.find((item) => item.id === activeId.value) ?? null,
  )
  const activeTitle = computed(() => activeConversation.value?.title ?? '')

  /**
   * 账号代次：登录用户变了就加一，之前发出的响应全部作废。
   * 没有它，退出登录前发出的请求会在下一个账号里写数据。
   */
  let epoch = 0
  const currentEpoch = () => epoch
  const bumpEpoch = () => {
    epoch += 1
  }

  let loaded = false
  let inFlight: Promise<void> | null = null

  /** 列表里替换某条会话的本地状态，避免整表重拉 */
  function patch(id: number, next: Partial<ChatConversationListItem>) {
    rows.value = rows.value.map((item) => (item.id === id ? { ...item, ...next } : item))
  }

  /** 最近活动时间倒序：发完消息把会话顶到第一位 */
  function sortByRecent() {
    rows.value = [...rows.value].sort((a, b) => b.update_time.localeCompare(a.update_time))
  }

  async function load() {
    const requestEpoch = epoch
    loadingList.value = true
    try {
      const page = await listConversations()
      if (requestEpoch === epoch) rows.value = page.items
    } finally {
      if (requestEpoch === epoch) loadingList.value = false
    }
  }

  /**
   * 会话列表只拉一次。
   *
   * 侧栏和对话页都会在挂载时用到它，各自调用会造成两次请求；这里合并成同一个
   * Promise，谁先到谁发请求，后来者等结果。登出时 `reset()` 把标记清掉。
   */
  function ensureLoaded(): Promise<void> {
    if (loaded) return Promise.resolve()
    if (inFlight) return inFlight
    const requestEpoch = epoch
    inFlight = load()
      .then(() => {
        if (requestEpoch === epoch) loaded = true
      })
      .finally(() => {
        if (requestEpoch === epoch) inFlight = null
      })
    return inFlight
  }

  /** 草稿态发出第一条消息时才真正建会话；连点只落一次库，失败返回 null */
  async function ensureConversation(): Promise<number | null> {
    if (activeId.value !== null) return activeId.value
    const thread = deps.threads.threadOf(DRAFT_KEY)
    const existing = deps.threads.creations.get(thread)
    if (existing) return existing
    const requestEpoch = epoch
    const promise = (async () => {
      const created = await createConversation()
      if (requestEpoch !== epoch || deps.threads.threads.get(DRAFT_KEY) !== thread) return null
      rows.value = [{ ...created, message_count: 0 }, ...rows.value]
      deps.threads.moveThread(DRAFT_KEY, created.id)
      if (activeId.value === null) {
        activeId.value = created.id
        draft.value = false
      }
      return created.id
    })()
    deps.threads.creations.set(thread, promise)
    try {
      return await promise
    } finally {
      deps.threads.creations.delete(thread)
    }
  }

  async function rename(item: ChatConversationListItem) {
    const requestEpoch = epoch
    try {
      const value = await promptDialog({
        title: '重命名会话',
        confirmText: '保存',
        input: {
          label: '会话名称',
          value: item.title,
          placeholder: '给这个会话起个名字',
          validator: (next: string) => (next.trim() ? true : '名称不能只包含空白'),
        },
      })
      if (requestEpoch !== epoch) return
      const updated = await renameConversation(item.id, value)
      if (requestEpoch !== epoch) return
      patch(item.id, { title: updated.title })
      ElMessage.success('会话名称已更新')
    } catch {
      // 取消或接口失败（失败已由拦截器提示）
    }
  }

  async function remove(item: ChatConversationListItem) {
    const requestEpoch = epoch
    try {
      await confirmDialog({
        title: '删除后，该会话将不可恢复',
        description: '这个会话里的消息会一起删除。',
        confirmText: '删除该会话',
        danger: true,
      })
    } catch {
      return
    }
    if (requestEpoch !== epoch) return
    await deleteConversation(item.id)
    if (requestEpoch !== epoch) return
    ElMessage.success('删除成功')
    rows.value = rows.value.filter((row) => row.id !== item.id)
    deps.threads.detachThread(item.id)
    if (activeId.value === item.id) {
      // 删掉的正是当前会话：回到空白会话，而不是硬跳去别的会话
      deps.onActiveRemoved()
    }
  }

  /** 退出登录时清空，避免下一个账号看到上一个人的会话 */
  function resetAccount() {
    epoch += 1
    rows.value = []
    activeId.value = null
    draft.value = false
    loadingList.value = false
    loadingMessages.value = false
    loaded = false
    inFlight = null
  }

  return {
    rows,
    activeId,
    draft,
    loadingList,
    loadingMessages,
    activeConversation,
    activeTitle,
    currentEpoch,
    bumpEpoch,
    patch,
    sortByRecent,
    load,
    ensureLoaded,
    ensureConversation,
    rename,
    remove,
    resetAccount,
  }
}
