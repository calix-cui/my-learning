import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// vi.mock 会被提升到 import 之前执行，工厂里引用外部变量必须用 vi.hoisted 声明
const { messageError } = vi.hoisted(() => ({ messageError: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { error: messageError } }))

import client from './client'

/** 让请求直接返回给定响应体，不经过网络 */
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

/** 让请求以 AxiosError 失败，模拟网络层/HTTP 层错误 */
function failWith(status: number | undefined, body?: unknown) {
  client.defaults.adapter = async (config) => {
    const response = status === undefined ? undefined : makeResponse(config, body, status)
    throw new AxiosError('请求失败', 'ERR_BAD_RESPONSE', config, undefined, response)
  }
}

describe('api/client 响应拦截器', () => {
  beforeEach(() => {
    messageError.mockClear()
  })

  it('统一包裹且 code=200 时正常返回响应', async () => {
    respondWith({ code: 200, message: '请求成功', data: { id: 1 } })

    const response = await client.get('/products/1')

    expect(response.data).toEqual({ code: 200, message: '请求成功', data: { id: 1 } })
    expect(messageError).not.toHaveBeenCalled()
  })

  it('业务失败（HTTP 200 但 code≠200）时提示后端 message 并 reject', async () => {
    respondWith({ code: 409, message: '分类名称已存在', data: null })

    await expect(client.post('/categories', { name: '饮料' })).rejects.toThrow('分类名称已存在')
    expect(messageError).toHaveBeenCalledWith('分类名称已存在')
  })

  it('非统一包裹结构的响应原样返回', async () => {
    respondWith({ status: 'ok' })

    const response = await client.get('/healthz')

    expect(response.data).toEqual({ status: 'ok' })
    expect(messageError).not.toHaveBeenCalled()
  })

  it('422 校验失败时把第一条字段错误拼进提示', async () => {
    // 422 由 axios 按 HTTP 状态判为失败，走错误分支而不是响应分支
    failWith(422, {
      code: 422,
      message: '请求参数校验失败',
      data: [{ loc: ['body', 'price'], msg: '价格最多 2 位小数' }],
    })

    await expect(client.post('/products', {})).rejects.toThrow(
      '请求参数校验失败：price 价格最多 2 位小数',
    )
  })

  it('网络不可达时给出统一网络提示', async () => {
    failWith(undefined)

    await expect(client.get('/products')).rejects.toThrow('网络异常，请确认后端已启动')
    expect(messageError).toHaveBeenCalledWith('网络异常，请确认后端已启动')
  })

  it('HTTP 500 且响应体不是统一包裹时提示服务器错误', async () => {
    failWith(500, 'Internal Server Error')

    await expect(client.get('/products')).rejects.toThrow('服务器内部错误，请稍后重试')
  })

  it('HTTP 404 且响应体不是统一包裹时提示资源不存在', async () => {
    failWith(404, 'Not Found')

    await expect(client.get('/missing')).rejects.toThrow('请求的资源不存在')
  })

  it('HTTP 错误带统一包裹时优先用后端 message', async () => {
    failWith(409, { code: 409, message: '分类下有其他商品，不能删除分类', data: null })

    await expect(client.delete('/categories/1')).rejects.toThrow('分类下有其他商品，不能删除分类')
  })
})
