import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

const { messageError, messageWarning, assign } = vi.hoisted(() => ({
  messageError: vi.fn(),
  messageWarning: vi.fn(),
  assign: vi.fn(),
}))

vi.mock('element-plus', () => ({
  ElMessage: { error: messageError, warning: messageWarning },
}))

import { emitUnauthorized, onUnauthorized } from './unauthorized'
import client from './client'

function respondWith(body: unknown, status = 200) {
  client.defaults.adapter = async (config) => makeResponse(config, body, status)
}

function makeResponse(
  config: InternalAxiosRequestConfig,
  data: unknown,
  status: number,
): AxiosResponse {
  return { data, status, statusText: String(status), headers: {}, config }
}

function failWith(status: number, body?: unknown) {
  client.defaults.adapter = async (config) => {
    throw new AxiosError(
      '请求失败',
      'ERR_BAD_RESPONSE',
      config,
      undefined,
      makeResponse(config, body, status),
    )
  }
}

describe('api/unauthorized 与 401 处理', () => {
  let handled: ReturnType<typeof vi.fn>

  beforeEach(() => {
    messageError.mockClear()
    messageWarning.mockClear()
    assign.mockClear()
    handled = vi.fn()
    onUnauthorized(handled)
    // 拦截器用 window.location.assign 做整页跳转，jsdom/node 下替换掉
    vi.stubGlobal('window', { location: { pathname: '/chat', search: '', assign } })
  })

  it('emitUnauthorized 会通知已注册的处理器', () => {
    emitUnauthorized()

    expect(handled).toHaveBeenCalledTimes(1)
  })

  it('HTTP 401 时清登录态并跳登录页（不弹 error 提示）', async () => {
    failWith(401, { code: 401, message: '请先登录', data: null })

    await expect(client.get('/conversations')).rejects.toThrow('请先登录')

    expect(handled).toHaveBeenCalledTimes(1)
    expect(messageWarning).toHaveBeenCalledWith('登录已过期，请重新登录')
    expect(assign).toHaveBeenCalledWith('/login')
    expect(messageError).not.toHaveBeenCalled()
  })

  it('已在登录页时不重复跳转', async () => {
    vi.stubGlobal('window', { location: { pathname: '/login', search: '', assign } })
    failWith(401, { code: 401, message: '请先登录', data: null })

    await expect(client.get('/conversations')).rejects.toThrow('请先登录')

    expect(assign).not.toHaveBeenCalled()
  })

  it('业务包裹里的 code=401 也按未登录处理', async () => {
    respondWith({ code: 401, message: '请先登录', data: null }, 200)

    await expect(client.get('/conversations')).rejects.toThrow('请先登录')

    expect(handled).toHaveBeenCalledTimes(1)
    expect(messageError).not.toHaveBeenCalled()
  })
})
