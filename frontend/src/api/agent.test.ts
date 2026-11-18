import { afterEach, expect, it, vi } from 'vitest'
import { sendAgentStream, listApprovals, getAgentSteps } from './agent'

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
      {
        type: 'run_finished',
        run_id: 1,
        assistant_message_id: 2,
        content: '完成',
        steps: 4,
        model: null,
      },
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
    expect(fetchMock.mock.calls[0][0]).toBe('/api/conversations/1/messages/stream')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
      content: '整理会议',
      skill_mode: mode,
      skill_keys: [],
      execution: 'auto',
      reasoning_effort: 'none',
    })
    expect(onEvent.mock.calls.map(([event]) => event)).toEqual(events)
    expect(onFinished).toHaveBeenCalledExactlyOnceWith(events[2])
  },
)

it('流在结束事件之前关闭时报告中断', async () => {
  vi.stubGlobal(
    'fetch',
    vi
      .fn()
      .mockResolvedValue(new Response('data: {"type":"assistant_delta","content":"半句"}\n\n')),
  )
  await expect(sendAgentStream(1, '测试', { onFinished: vi.fn() })).rejects.toThrow('连接已中断')
})

it.each([listApprovals, getAgentSteps])('历史读取失败必须报错，不能返回空数组', async (load) => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 503 })))
  await expect(load(7)).rejects.toThrow()
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: 500, data: { items: [] } }))),
  )
  await expect(load(7)).rejects.toThrow()
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: 200, data: {} }))),
  )
  await expect(load(7)).rejects.toThrow('响应格式无效')
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: 200, data: { items: [] } }))),
  )
  await expect(load(7)).resolves.toEqual([])
})

it('传输层使用调用方持有的请求标识和取消信号', async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValue(
      new Response(
        'data: {"type":"run_finished","run_id":7,"assistant_message_id":12,"content":"完成","steps":1,"model":null}\n\n',
      ),
    )
  vi.stubGlobal('fetch', fetchMock)
  const controller = new AbortController()
  const requestId = '5fe99a6a-4c24-4a7e-8641-3fb53bd98c45'
  await sendAgentStream(
    1,
    '问题',
    { onFinished: vi.fn() },
    controller.signal,
    'auto',
    'none',
    [],
    undefined,
    requestId,
  )
  expect(JSON.parse(fetchMock.mock.calls[0][1].body).request_id).toBe(requestId)
  expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal)
})
