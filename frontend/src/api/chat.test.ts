import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const { messageError } = vi.hoisted(() => ({ messageError: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { error: messageError } }))

import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
  sendMessage,
  sendMessageStream,
} from './chat'
import client from './client'

function mockSuccess(data: unknown) {
  const calls: Array<{ method?: string; url?: string; body?: unknown; params?: unknown }> = []
  client.defaults.adapter = async (config) => {
    calls.push({
      method: config.method,
      url: config.url,
      body: config.data ? JSON.parse(String(config.data)) : undefined,
      params: config.params,
    })
    return {
      data: { code: 200, message: '请求成功', data },
      status: 200,
      statusText: '200',
      headers: {},
      config,
    }
  }
  return calls
}

describe('api/chat', () => {
  beforeEach(() => {
    messageError.mockClear()
  })

  it('新建会话：不传标题时发空对象', async () => {
    const calls = mockSuccess({ id: 1, title: '新会话' })

    const created = await createConversation()

    expect(calls[0]).toMatchObject({ method: 'post', url: '/conversations', body: {} })
    expect(created.id).toBe(1)
  })

  it('新建会话：传了标题就带上', async () => {
    const calls = mockSuccess({ id: 2, title: '定价讨论' })

    await createConversation('定价讨论')

    expect(calls[0].body).toEqual({ title: '定价讨论' })
  })

  it('会话列表带分页参数', async () => {
    const calls = mockSuccess({ items: [], total: 0, page: 2, page_size: 20 })

    const page = await listConversations(2, 20)

    expect(calls[0].url).toBe('/conversations')
    expect(calls[0].params).toEqual({ page: 2, page_size: 20 })
    expect(page.page).toBe(2)
  })

  it('会话详情、重命名、删除走对应路径与方法', async () => {
    const calls = mockSuccess({ id: 7, title: '改名', messages: [] })

    await getConversation(7)
    await renameConversation(7, '改名')
    await deleteConversation(7)

    expect(calls[0]).toMatchObject({ method: 'get', url: '/conversations/7' })
    expect(calls[1]).toMatchObject({ method: 'patch', url: '/conversations/7' })
    expect(calls[1].body).toEqual({ title: '改名' })
    expect(calls[2]).toMatchObject({ method: 'delete', url: '/conversations/7' })
  })

  it('发送消息：POST 到 /messages 且超时放宽到 35s', async () => {
    const calls = mockSuccess({
      user_message: { id: 1, content: '你好' },
      assistant_message: { id: 2, content: '收到' },
    })
    let timeout: number | undefined
    client.defaults.adapter = async (config) => {
      calls.push({ method: config.method, url: config.url, body: JSON.parse(String(config.data)) })
      timeout = config.timeout
      return {
        data: {
          code: 200,
          message: '请求成功',
          data: {
            user_message: { id: 1, content: '你好' },
            assistant_message: { id: 2, content: '收到' },
          },
        },
        status: 200,
        statusText: '200',
        headers: {},
        config,
      }
    }

    const exchange = await sendMessage(7, '你好')

    expect(calls[0]).toMatchObject({
      method: 'post',
      url: '/conversations/7/messages',
      body: { content: '你好' },
    })
    expect(timeout).toBe(35000)
    expect(exchange.assistant_message.content).toBe('收到')
  })

  it('业务失败时抛出后端 message 并提示', async () => {
    client.defaults.adapter = async (config) => ({
      data: { code: 502, message: '模型服务不可用', data: null },
      status: 200,
      statusText: '200',
      headers: {},
      config,
    })

    await expect(sendMessage(7, '你好')).rejects.toThrow('模型服务不可用')
    expect(messageError).toHaveBeenCalledWith('模型服务不可用')
  })
})

describe('api/chat 流式', () => {
  function mockSse(chunks: string[]) {
    const encoder = new TextEncoder()
    let index = 0
    const stream = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (index < chunks.length) {
          controller.enqueue(encoder.encode(chunks[index]))
          index += 1
        } else {
          controller.close()
        }
      },
    })
    const fetchMock = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit): Promise<Response> =>
        new Response(stream, {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' },
        }),
    )
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('按帧解析 meta / delta / done，半帧会缓存到下一块', async () => {
    const fetchMock = mockSse([
      'data: {"type":"meta","user_message":{"id":9,"role":"user"}}\n\n' +
        'data: {"type":"delta","content":"你"}\n\n',
      // 故意把一帧劈成两半，验证缓冲区拼接
      'data: {"type":"delta","content":"好"',
      '}\n\ndata: {"type":"done","conversation_id":3,"conversation_title":"你好","message_count":2,' +
        '"assistant_message":{"id":10,"role":"assistant","content":"你好"}}\n\n',
    ])
    const deltas: string[] = []
    let metaId = 0
    let doneTitle = ''

    await sendMessageStream(3, '你好', {
      onMeta: (message) => {
        metaId = message.id
      },
      onDelta: (text) => deltas.push(text),
      onDone: (event) => {
        doneTitle = event.conversation_title
      },
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({ content: '你好' })
    expect(metaId).toBe(9)
    expect(deltas.join('')).toBe('你好')
    expect(doneTitle).toBe('你好')
  })

  it('校验失败返回普通 JSON 时抛后端 message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ code: 400, message: '消息内容不能只包含空白' }), {
            status: 400,
            headers: { 'Content-Type': 'application/json' },
          }),
      ),
    )

    await expect(
      sendMessageStream(3, '   ', { onDelta: vi.fn(), onDone: vi.fn() }),
    ).rejects.toThrow('消息内容不能只包含空白')
  })

  it('收到 error 事件时抛错并保留已收到的文本', async () => {
    mockSse([
      'data: {"type":"delta","content":"半句"}\n\n',
      'data: {"type":"error","code":502,"message":"模型服务不可用"}\n\n',
    ])
    const deltas: string[] = []

    await expect(
      sendMessageStream(3, '你好', {
        onDelta: (text) => deltas.push(text),
        onDone: vi.fn(),
      }),
    ).rejects.toThrow('模型服务不可用')
    expect(deltas.join('')).toBe('半句')
  })
})
