import client from './client'

import type {
  ApiResponse,
  Product,
  ProductCount,
  ProductCreatePayload,
  ProductListItem,
  ProductPage,
  ProductQuery,
  ProductUpdatePayload,
} from '@/types/api'

/** 分页查询商品，keyword 为空时不传，category_id 为空表示全部分类 */
export async function listProducts(query: ProductQuery): Promise<ProductPage> {
  const params: Record<string, string | number> = {
    page: query.page,
    page_size: query.page_size,
  }
  if (query.keyword) {
    params.keyword = query.keyword
  }
  if (query.category_id) {
    params.category_id = query.category_id
  }
  const { data } = await client.get<ApiResponse<ProductPage>>('/products', { params })
  return data.data
}

/** 统计全部商品数量 */
export async function countProducts(): Promise<ProductCount> {
  const { data } = await client.get<ApiResponse<ProductCount>>('/products/count')
  return data.data
}

/** 查询商品详情（不含 category_name） */
export async function getProduct(id: number): Promise<Product> {
  const { data } = await client.get<ApiResponse<Product>>(`/products/${id}`)
  return data.data
}

/** 新增商品 */
export async function createProduct(payload: ProductCreatePayload): Promise<Product> {
  const { data } = await client.post<ApiResponse<Product>>('/products', payload)
  return data.data
}

/** 局部修改商品 */
export async function updateProduct(id: number, payload: ProductUpdatePayload): Promise<Product> {
  const { data } = await client.patch<ApiResponse<Product>>(`/products/${id}`, payload)
  return data.data
}

/** 删除商品 */
export async function deleteProduct(id: number): Promise<void> {
  await client.delete<ApiResponse<null>>(`/products/${id}`)
}

/** 供列表页复用的类型导出，避免调用方重复从 types 引入 */
export type { ProductListItem }
