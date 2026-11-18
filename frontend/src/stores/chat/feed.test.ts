import { describe, expect, it } from 'vitest'
import { buildChatFeed } from './feed'
import { applySummary, createExecution } from './execution'
import type { AgentRunSummary, ChatMessage } from '@/types/api'
import { runSummary } from '@/test/agent'

const message = (id: number, role: string): ChatMessage => ({
  id,
  role,
  conversation_id: 1,
  content: `消息 ${id}`,
  model: null,
  create_time: '',
})
const run = (id: number, user: number, assistant: number | null): AgentRunSummary =>
  runSummary({
    id,
    user_message_id: user,
    assistant_message_id: assistant,
    status: assistant ? 'completed' : 'failed',
    visible_step_count: 1,
  })
const execution = (summary: AgentRunSummary) => {
  const value = createExecution(`run:${summary.id}`)
  applySummary(value, summary)
  return value
}
const source = () => ({
  messages: [message(1, 'user'), message(2, 'assistant')],
  executions: [execution(run(41, 1, 2))],
})

describe('聊天消息流投影', () => {
  it('已关联正文只归执行项，未关联的普通历史消息照常输出', () => {
    const input = source()
    input.messages.push(message(3, 'assistant'))
    const feed = buildChatFeed(input, 1)
    expect(feed.map((item) => item.kind)).toEqual(['message', 'execution', 'message'])
    expect(feed.map((item) => item.message?.id)).toEqual([1, 2, 3])
    expect(input.messages).toHaveLength(3)
  })

  it('同一输入的多个运行按运行 ID 排序，无助手的运行也不丢失', () => {
    const input = source()
    input.messages = [message(1, 'user')]
    input.executions = [execution(run(43, 1, null)), execution(run(41, 1, null))]
    expect(buildChatFeed(input, 1).map((item) => item.key)).toEqual([
      '1:message:1',
      '1:run:41',
      '1:run:43',
    ])
  })

  it('实时运行覆盖相同历史摘要，临时 ID、真实 ID 和完成保持同一 key', () => {
    const input = source()
    input.messages = [message(-1, 'user')]
    const value = createExecution('local:1')
    value.userMessageId = -1
    value.transport = 'streaming'
    input.executions = [value]
    const pending = buildChatFeed(input, 1)[1].key
    input.messages = [message(1, 'user')]
    applySummary(value, { ...run(41, 1, null), status: 'waiting_approval' })
    const live = buildChatFeed(input, 1)
    expect(live).toHaveLength(2)
    expect(live[1].key).toBe(pending)
    applySummary(value, run(41, 1, 2))
    value.transport = 'idle'
    input.messages.push(message(2, 'assistant'))
    const completed = buildChatFeed(input, 1)
    expect(completed).toHaveLength(2)
    expect(completed[1].key).toBe(pending)
    expect(completed[1].message?.id).toBe(2)
    expect(buildChatFeed(input, 2)[1].key).not.toBe(pending)
  })

  it('分页补入用户消息时执行项 key 不变，不显示其他页的已完成运行', () => {
    const input = source()
    input.messages = [message(2, 'assistant')]
    input.executions.push(execution(run(43, 3, 4)))
    expect(buildChatFeed(input, 1).map((item) => item.key)).toEqual(['1:run:41'])
    input.messages.unshift(message(1, 'user'))
    expect(buildChatFeed(input, 1).map((item) => item.key)).toEqual(['1:message:1', '1:run:41'])
  })
})
