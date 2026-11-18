import { reactive } from 'vue'

import type { ChatMessage } from '@/types/api'
import type { Execution } from './execution'

/** 草稿态的伪会话键：界面已经在「一个会话」里，但后端还没有记录 */
export const DRAFT_KEY = 0

/**
 * 一个会话自己的运行时状态。
 *
 * 关键点：**会话之间不能共享可变状态**。之前 messages / streamingText 是 store 上的
 * 单例，切换会话只是把它们换成另一份数据，而正在跑的流仍然往同一份里写，
 * 于是「上一个会话的回答」就落到新会话里了。现在按会话隔离，流只写自己那一份。
 */
export interface ChatThread {
  messages: ChatMessage[]
  executions: Execution[]
  activeExecutionKey: string | null
  nextBeforeMessageId: number | null
  loadingOlderMessages: boolean
  historyRevision: number
  historyError: string | null
  selectedSkillKey: string | null
  draftText: string
  loaded: boolean
}

export function emptyThread(): ChatThread {
  return {
    messages: [],
    executions: [],
    activeExecutionKey: null,
    nextBeforeMessageId: null,
    loadingOlderMessages: false,
    historyRevision: 0,
    historyError: null,
    selectedSkillKey: null,
    draftText: '',
    loaded: false,
  }
}

export function currentExecution(thread: ChatThread) {
  return thread.executions.find((execution) => execution.key === thread.activeExecutionKey)
}

/**
 * 所有会话的运行时状态，以及几张按实例索引的旁表。
 *
 * 这里只负责「谁存在、怎么释放」，不读接口、不知道当前打开的是哪个会话。
 */
export interface ThreadState {
  threads: Map<number, ChatThread>
  /** 每条执行的取消句柄：删除会话、退出登录时中断在途请求 */
  controllers: Map<Execution, AbortController>
  /** 步骤详情请求去重：同一条执行同一版只发一次 */
  stepRequests: WeakMap<Execution, { revision: number; promise: Promise<void> }>
  /** 建会话请求去重：连点发送只落一次库 */
  creations: WeakMap<ChatThread, Promise<number | null>>
  threadOf(key: number): ChatThread
  moveThread(from: number, to: number): void
  disposeThread(thread: ChatThread): void
  detachThread(key: number): ChatThread | undefined
  clearThreads(): void
}

export function createThreadState(): ThreadState {
  const threads = reactive(new Map<number, ChatThread>())
  const controllers = new Map<Execution, AbortController>()
  const stepRequests = new WeakMap<Execution, { revision: number; promise: Promise<void> }>()
  const creations = new WeakMap<ChatThread, Promise<number | null>>()

  function threadOf(key: number): ChatThread {
    const existing = threads.get(key)
    if (existing) return existing
    threads.set(key, emptyThread())
    // 必须把 reactive 代理取回来：直接改原始对象不会触发视图更新
    return threads.get(key)!
  }

  function moveThread(from: number, to: number) {
    const thread = threads.get(from)
    if (!thread) return
    threads.set(to, thread)
    threads.delete(from)
  }

  /** 中断这个会话所有在途请求，并让已发出的响应作废 */
  function disposeThread(thread: ChatThread) {
    for (const execution of thread.executions) {
      controllers.get(execution)?.abort()
      controllers.delete(execution)
    }
    thread.historyRevision++
  }

  function detachThread(key: number) {
    const thread = threads.get(key)
    if (thread) disposeThread(thread)
    threads.delete(key)
    return thread
  }

  function clearThreads() {
    for (const thread of threads.values()) disposeThread(thread)
    threads.clear()
  }

  return {
    threads,
    controllers,
    stepRequests,
    creations,
    threadOf,
    moveThread,
    disposeThread,
    detachThread,
    clearThreads,
  }
}
