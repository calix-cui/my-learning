import type { AgentStreamEvent } from '@/api/agent'
import { VISIBLE_STEP_KINDS, type Execution } from './execution'

/** 正文分片只随当前连接追加；持久步骤以 seq 去重，发送与审批共用。 */
export function applyExecutionEvent(execution: Execution, event: AgentStreamEvent) {
  if (
    execution.status === 'completed' ||
    execution.status === 'failed' ||
    execution.status === 'cancelled'
  )
    return
  if ('seq' in event && execution.steps.some((step) => step.seq === event.seq)) return
  const base = {
    seq: 0,
    content: null,
    tool_name: null,
    call_id: null,
    tool_args: null,
    skill_key: null,
    skill_name: null,
    skill_source: null,
    skill_version: null,
    ok: null,
    duration_ms: null,
    create_time: new Date().toISOString(),
  }
  if (event.type === 'run_snapshot') {
    // 订阅到的第一帧：先把服务端已经生成的部分画出来，再跟后面的实时分片
    execution.status = event.status
    execution.preview = event.draft_content ?? ''
    if (event.error_message) execution.error = event.error_message
  } else if (event.type === 'assistant_delta') {
    execution.preview += event.content
  } else if (event.type === 'assistant_preview_reset') {
    execution.preview = ''
  } else if (event.type === 'tool_call') {
    execution.steps = [
      ...execution.steps,
      {
        ...base,
        seq: event.seq,
        kind: 'tool_call',
        tool_name: event.tool,
        call_id: event.call_id,
        tool_args: event.args,
      },
    ]
  } else if (event.type === 'tool_result') {
    execution.steps = [
      ...execution.steps,
      {
        ...base,
        seq: event.seq,
        kind: 'tool_result',
        tool_name: event.tool,
        call_id: event.call_id,
        content: event.content,
        ok: event.ok,
        duration_ms: event.duration_ms,
      },
    ]
  } else if (event.type === 'assistant_text') {
    execution.steps = [
      ...execution.steps,
      { ...base, seq: event.seq, kind: 'assistant_text', content: event.content },
    ]
  } else if (event.type === 'skill_loaded') {
    execution.steps = [
      ...execution.steps,
      {
        ...base,
        seq: event.seq,
        kind: 'skill_loaded',
        skill_key: event.skill_key,
        skill_name: event.name,
        skill_source: event.source,
        skill_version: event.version,
      },
    ]
  } else if (event.type === 'skill_load_failed') {
    execution.steps = [
      ...execution.steps,
      {
        ...base,
        seq: event.seq,
        kind: 'skill_load_failed',
        skill_key: event.skill_key,
        content: event.message,
      },
    ]
  } else if (event.type === 'skill_resource') {
    execution.steps = [
      ...execution.steps,
      {
        ...base,
        seq: event.seq,
        kind: 'skill_resource',
        skill_key: event.skill_key,
        skill_name: event.name,
        tool_args: { skill_key: event.skill_key, path: event.path },
        ok: event.ok,
        content: event.message,
      },
    ]
  }
  if ('seq' in event && execution.steps.some((step) => step.seq === event.seq)) {
    execution.detailStatus = 'loaded'
    execution.visibleStepCount = execution.steps.filter((step) =>
      VISIBLE_STEP_KINDS.has(step.kind),
    ).length
  }
  execution.revision++
}
