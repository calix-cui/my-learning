import client from './client'

import type { ApiResponse, Category, CategoryPayload, CategoryStatistic } from '@/types/api'

/** 查询全部分类（后端按 ID 倒序返回） */
export async function listCategories(): Promise<Category[]> {
  const { data } = await client.get<ApiResponse<Category[]>>('/categories')
  return data.data
}

/** 新增分类 */
export async function createCategory(payload: CategoryPayload): Promise<Category> {
  const { data } = await client.post<ApiResponse<Category>>('/categories', payload)
  return data.data
}

/** 修改分类名称 */
export async function updateCategory(id: number, payload: CategoryPayload): Promise<Category> {
  const { data } = await client.patch<ApiResponse<Category>>(`/categories/${id}`, payload)
  return data.data
}

/** 删除分类，分类下有商品时后端返回 409 */
export async function deleteCategory(id: number): Promise<void> {
  await client.delete<ApiResponse<null>>(`/categories/${id}`)
}

/** 分类商品数量统计（含商品数为 0 的分类） */
export async function categoryStatistics(): Promise<CategoryStatistic[]> {
  const { data } = await client.get<ApiResponse<CategoryStatistic[]>>('/categories/statistics')
  return data.data
}
