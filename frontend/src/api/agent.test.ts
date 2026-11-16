import { afterEach, expect, it, vi } from 'vitest'
import { sendAgentStream } from './agent'

afterEach(() => vi.unstubAllGlobals())

it.each(['off', 'manual', 'auto'] as const)(
  '发送 %s 模式并解析跨数据块的 Skill 事件',
  async (mode) => {
    const events = [
      {
        type: 'skill_loaded',
        seq: 2,
        skill_key: 'builtin:meeting',
        name: '会议纪要',
        source: 'builtin',
        version: 'v1',
      },
      {
        type: 'skill_load_failed',
        seq: 3,
        skill_key: 'missing',
        error_code: 'unknown_skill',
        message: '技能不可用',
      },
      { type: 'run_finished', run_id: 1, content: '完成', steps: 4, model: null },
    ]
    const bytes = new TextEncoder().encode(
      events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join(''),
    )
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            for (const byte of bytes) controller.enqueue(new Uint8Array([byte]))
            controller.close()
          },
        }),
      ),
    )
    vi.stubGlobal('fetch', fetchMock)
    const onEvent = vi.fn()
    const onFinished = vi.fn()
    await sendAgentStream(1, '整理会议', { onEvent, onFinished }, undefined, mode)
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      content: '整理会议',
      skill_mode: mode,
    })
    expect(onEvent.mock.calls.map(([event]) => event)).toEqual(events)
    expect(onFinished).toHaveBeenCalledExactlyOnceWith(events[2])
  },
)
