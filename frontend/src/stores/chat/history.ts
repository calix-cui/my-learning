import { reactive } from 'vue'

import { getConversation } from '@/api/chat'
import { getAgentSteps, listApprovals } from '@/api/agent'
import type { AgentRunSummary, ChatConversationDetail, ChatConversationListItem } from '@/types/api'
import { applySummary, createExecution, isTransferring, type Execution } from './execution'
import type { ChatThread, ThreadState } from './threads'

/** 一页历史的消息条数；分页游标由后端给，前端不自己算 */
export const HISTORY_PAGE_SIZE = 50

export interface HistoryDeps {
  threads: ThreadState
  patchConversation(id: number, patch: Partial<ChatConversationListItem>): void
}

/**
 * 所有「从服务端读回状态」的路径：历史页、执行详情、审批重查。
 *
 * 这里不持有当前会话（那属于 conversations），也不改发送状态机（那属于 execution）。
 * 每个函数都要求调用方传入 `(id, thread)`，靠这两者判断响应是否还属于那块界面。
 */
export function createHistory(deps: HistoryDeps) {
  const { threads } = deps

  function applyRunSummaries(thread: ChatThread, runs: AgentRunSummary[]) {
    for (const run of runs) {
      let execution = thread.executions.find((item) => item.runId === run.id)
      if (!execution) {
        execution = reactive(createExecution(`run:${run.id}`))
        thread.executions.push(execution)
      }
      applySummary(execution, run)
      if (run.status === 'running' || run.status === 'waiting_approval')
        thread.activeExecutionKey = execution.key
    }
  }

  function applyLatestHistory(id: number, thread: ChatThread, detail: ChatConversationDetail) {
    const firstId = detail.messages[0]?.id
    const older =
      detail.next_before_message_id && firstId !== undefined
        ? thread.messages.filter((message) => message.id > 0 && message.id < firstId)
        : []
    // 只有新页与已加载消息有交集，才保留已加载的旧页。
    const overlaps =
      firstId !== undefined && thread.messages.some((message) => message.id === firstId)
    applyRunSummaries(thread, detail.runs ?? [])
    const pendingMessages = thread.messages.filter(
      (message) =>
        message.id < 0 &&
        thread.executions.some(
          (execution) => execution.userMessageId === message.id && execution.status !== 'failed',
        ),
    )
    thread.messages = [...(overlaps ? older : []), ...detail.messages, ...pendingMessages]
    if (!overlaps || !older.length)
      thread.nextBeforeMessageId = detail.next_before_message_id ?? null
    thread.loaded = true
    deps.patchConversation(id, { title: detail.title })
  }

  /**
   * 读回一个会话的最新一页，并把每条执行的服务端状态、审批和步骤对齐。
   *
   * 断流后没有终态事件，这里的结论就是唯一的真相来源：服务端还在跑就锁发送，
   * 已经结束就解锁。所以它只读、不重发，也不猜测请求结果。
   */
  async function refreshThread(id: number, thread: ChatThread) {
    const revision = ++thread.historyRevision
    const valid = () => threads.threads.get(id) === thread && thread.historyRevision === revision
    const detail = await getConversation(id, { message_limit: HISTORY_PAGE_SIZE })
    if (!valid()) return
    applyLatestHistory(id, thread, detail)
    thread.historyError = null
    for (const execution of thread.executions) {
      if (!valid()) return
      if (execution.status === 'waiting_approval') {
        try {
          const approvals = await listApprovals(execution.runId!)
          if (!valid()) return
          const pending = approvals.find((item) => item.status === 'pending')
          if (!pending) throw new Error('待审批运行没有可用审批，请重新核对状态')
          execution.approval = {
            runId: pending.run_id,
            approvalId: pending.id,
            tool: pending.tool_name,
            args: pending.tool_args,
            reason: pending.note ?? '',
          }
          execution.transport = 'idle'
          execution.error = null
        } catch (error) {
          if (!valid()) return
          execution.transport = 'disconnected'
          execution.error = error instanceof Error ? error.message : '读取审批失败'
          throw error
        }
      } else if (execution.status === 'running' || execution.status === null) {
        execution.transport = 'disconnected'
        execution.error =
          execution.runId === null
            ? '连接已中断，提交结果尚未确认，请刷新页面核对，勿重复发送'
            : '执行尚未结束，连接已中断，请重新核对状态'
      } else {
        execution.transport = 'idle'
        execution.error =
          execution.status === 'failed'
            ? (execution.error ?? '执行失败，可重新发送')
            : execution.status === 'cancelled'
              ? '执行已取消'
              : null
        execution.preview = ''
      }
      if (
        execution.visibleStepCount > 0 &&
        execution.steps.length > 0 &&
        execution.detailStatus !== 'loaded'
      ) {
        try {
          await readSteps(id, thread, execution)
        } catch {
          /* 保留步骤，时间线显示读取失败和重试。 */
        }
        if (!valid()) return
      }
    }
  }

  async function loadOlderMessages(id: number, thread: ChatThread): Promise<boolean> {
    const before = thread.nextBeforeMessageId
    if (before === null || thread.loadingOlderMessages || thread.executions.some(isTransferring))
      return false

    const revision = thread.historyRevision
    thread.loadingOlderMessages = true
    try {
      const detail = await getConversation(id, {
        message_limit: HISTORY_PAGE_SIZE,
        before_message_id: before,
      })
      if (threads.threads.get(id) !== thread || thread.historyRevision !== revision) return false
      thread.messages = [...detail.messages, ...thread.messages]
      thread.nextBeforeMessageId = detail.next_before_message_id ?? null
      applyRunSummaries(thread, detail.runs ?? [])
      return true
    } catch (error) {
      if (threads.threads.get(id) === thread)
        thread.historyError = error instanceof Error ? error.message : '加载历史失败'
      return false
    } finally {
      thread.loadingOlderMessages = false
    }
  }

  /** 读一条执行的步骤；同一版本只发一次，迟到的响应按 revision 丢弃 */
  async function readSteps(id: number, thread: ChatThread, execution: Execution) {
    if (execution.runId === null || execution.detailStatus === 'loaded') return
    const revision = execution.revision
    const existing = threads.stepRequests.get(execution)
    if (existing?.revision === revision) return existing.promise
    execution.detailStatus = 'loading'
    const runId = execution.runId
    const promise = (async () => {
      try {
        const steps = await getAgentSteps(runId)
        if (threads.threads.get(id) !== thread || execution.revision !== revision) return
        execution.steps = [
          ...new Map([...execution.steps, ...steps].map((step) => [step.seq, step])).values(),
        ].sort((a, b) => a.seq - b.seq)
        execution.detailStatus = 'loaded'
      } catch (error) {
        if (threads.threads.get(id) === thread && execution.revision === revision)
          execution.detailStatus = 'error'
        throw error
      }
    })()
    threads.stepRequests.set(execution, { revision, promise })
    try {
      await promise
    } finally {
      if (threads.stepRequests.get(execution)?.promise === promise)
        threads.stepRequests.delete(execution)
    }
  }

  /** 时间线展开时的入口：失败由组件显示重试，这里只吞掉异常 */
  async function loadExecutionSteps(id: number, thread: ChatThread, runId: number) {
    const execution = thread.executions.find((item) => item.runId === runId)
    if (!execution || execution.detailStatus === 'loading') return
    try {
      await readSteps(id, thread, execution)
    } catch {
      /* 错误由时间线的重试入口显示。 */
    }
  }

  return { refreshThread, loadOlderMessages, readSteps, loadExecutionSteps }
}
