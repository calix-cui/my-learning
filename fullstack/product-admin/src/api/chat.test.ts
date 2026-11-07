import { beforeEach, describe, expect, it, vi } from 'vitest'

const { messageError } = vi.hoisted(() => ({ messageError: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { error: messageError } }))

import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
  sendMessage,
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
