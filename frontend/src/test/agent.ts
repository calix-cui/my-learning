/**
 * Agent 接口的测试夹具。
 *
 * 运行摘要与步骤响应都是「字段只增不减」的契约，用例里逐个字段重写会让每加一个字段
 * 就要改十几处夹具，所以集中在这里给默认值，用例只写自己关心的部分。
 */

import type { AgentRunSummary, AgentStep, AgentStepsPage } from '@/types/api'

/** 一次运行的摘要：默认「已完成、没有 request_id、没有失败原因」 */
export function runSummary(
  overrides: Partial<AgentRunSummary> & Pick<AgentRunSummary, 'id'>,
): AgentRunSummary {
  return {
    user_message_id: null,
    assistant_message_id: null,
    status: 'completed',
    visible_step_count: 0,
    request_id: null,
    error_message: null,
    finished_time: null,
    ...overrides,
  }
}

/** 步骤接口的响应：步骤与运行状态一体返回 */
export function stepsPage(
  items: AgentStep[],
  overrides: Partial<AgentStepsPage> = {},
): AgentStepsPage {
  return {
    items,
    status: 'completed',
    visible_step_count: items.length,
    error_message: null,
    finished_time: null,
    ...overrides,
  }
}
