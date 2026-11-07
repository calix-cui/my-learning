import { beforeEach, describe, expect, it, vi } from 'vitest'

const { messageError } = vi.hoisted(() => ({ messageError: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { error: messageError } }))

import client from './client'
import {
  countProducts,
  createProduct,
  deleteProduct,
  getProduct,
  listProducts,
  updateProduct,
} from './products'

/** 记录最后一次请求的 method/url/params/data，并按统一包裹结构返回 data */
function mockSuccess(data: unknown) {
  const calls: Array<{ method?: string; url?: string; params?: unknown; body?: unknown }> = []
  client.defaults.adapter = async (config) => {
    calls.push({
      method: config.method,
      url: config.url,
      params: config.params,
      body: config.data ? JSON.parse(String(config.data)) : undefined,
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

describe('api/products', () => {
  beforeEach(() => {
    messageError.mockClear()
  })

  it('分页查询只传有值的筛选条件', async () => {
    const calls = mockSuccess({ items: [], total: 0, page: 1, page_size: 10 })

    await listProducts({ page: 1, page_size: 10, keyword: '', category_id: undefined })

    expect(calls[0].method).toBe('get')
    expect(calls[0].url).toBe('/products')
    expect(calls[0].params).toEqual({ page: 1, page_size: 10 })
  })

  it('关键词与分类都传时一并带上', async () => {
    const calls = mockSuccess({ items: [], total: 0, page: 2, page_size: 5 })

    await listProducts({ page: 2, page_size: 5, keyword: '可乐', category_id: 3 })

    expect(calls[0].params).toEqual({ page: 2, page_size: 5, keyword: '可乐', category_id: 3 })
  })

  it('查询结果取出统一包裹里的 data', async () => {
    mockSuccess({ items: [], total: 7, page: 1, page_size: 10 })

    await expect(listProducts({ page: 1, page_size: 10 })).resolves.toEqual({
      items: [],
      total: 7,
      page: 1,
      page_size: 10,
    })
  })

  it('统计数量走 /products/count', async () => {
    const calls = mockSuccess({ total: 12 })

    await expect(countProducts()).resolves.toEqual({ total: 12 })
    expect(calls[0].url).toBe('/products/count')
  })

  it('详情、更新、删除使用对应的路径与方法', async () => {
    const calls = mockSuccess({ id: 1, name: '可乐' })

    await getProduct(1)
    await updateProduct(1, { stock: 5 })
    await deleteProduct(1)

    expect(calls.map((call) => `${call.method} ${call.url}`)).toEqual([
      'get /products/1',
      'patch /products/1',
      'delete /products/1',
    ])
    expect(calls[1].body).toEqual({ stock: 5 })
  })

  it('新增商品把表单原样提交', async () => {
    const calls = mockSuccess({ id: 9 })
    const payload = { category_id: 3, name: '可乐', price: '3.50', stock: 10, shelf_status: true }

    await createProduct(payload)

    expect(calls[0].method).toBe('post')
    expect(calls[0].url).toBe('/products')
    expect(calls[0].body).toEqual(payload)
  })
})
