import { beforeEach, describe, expect, it, vi } from 'vitest'

const { messageError } = vi.hoisted(() => ({ messageError: vi.fn() }))
vi.mock('element-plus', () => ({ ElMessage: { error: messageError } }))

import {
  createCategory,
  deleteCategory,
  categoryStatistics,
  listCategories,
  updateCategory,
} from './categories'
import client from './client'

function mockSuccess(data: unknown) {
  const calls: Array<{ method?: string; url?: string; body?: unknown }> = []
  client.defaults.adapter = async (config) => {
    calls.push({
      method: config.method,
      url: config.url,
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

describe('api/categories', () => {
  beforeEach(() => {
    messageError.mockClear()
  })

  it('分类列表取 data 数组', async () => {
    mockSuccess([{ id: 1, name: '饮料' }])

    await expect(listCategories()).resolves.toEqual([{ id: 1, name: '饮料' }])
  })

  it('统计接口走 /categories/statistics 并保留 0 商品分类', async () => {
    const calls = mockSuccess([{ id: 1, name: '空分类', product_count: 0 }])

    const stats = await categoryStatistics()

    expect(calls[0].url).toBe('/categories/statistics')
    expect(stats[0].product_count).toBe(0)
  })

  it('新增、改名、删除使用对应的路径与方法', async () => {
    const calls = mockSuccess({ id: 2, name: '零食' })

    await createCategory({ name: '零食' })
    await updateCategory(2, { name: '坚果' })
    await deleteCategory(2)

    expect(calls.map((call) => `${call.method} ${call.url}`)).toEqual([
      'post /categories',
      'patch /categories/2',
      'delete /categories/2',
    ])
    expect(calls[1].body).toEqual({ name: '坚果' })
  })
})
