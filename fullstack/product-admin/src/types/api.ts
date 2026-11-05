/**
 * 与后端接口一一对应的类型定义。
 * 字段命名严格遵循 FastAPI 的返回结构（snake_case）。
 */

/** 统一响应包裹结构 */
export interface ApiResponse<T> {
  /** 业务状态码，200 表示成功 */
  code: number
  /** 提示信息，失败时为中文原因 */
  message: string
  /** 业务数据 */
  data: T
}

/** 商品实体（详情接口返回，不含分类名称） */
export interface Product {
  id: number
  category_id: number
  name: string
  /** 价格由后端序列化为两位小数字符串，如 "3.50" */
  price: string
  stock: number
  shelf_status: boolean
  /** 创建时间，格式 yyyy-MM-dd HH:mm:ss */
  create_time: string
}

/** 商品列表项，比详情多一个分类名称 */
export interface ProductListItem extends Product {
  category_name: string
}

/** 分页响应 */
export interface ProductPage {
  items: ProductListItem[]
  total: number
  page: number
  page_size: number
}

/** 商品列表查询参数 */
export interface ProductQuery {
  page: number
  page_size: number
  keyword?: string
  category_id?: number
}

/** 新增商品请求体 */
export interface ProductCreatePayload {
  category_id: number
  name: string
  price: string
  stock: number
  shelf_status: boolean
}

/** 修改商品请求体，字段均可省略 */
export type ProductUpdatePayload = Partial<ProductCreatePayload>

/** 商品总数统计 */
export interface ProductCount {
  total: number
}

/** 分类实体 */
export interface Category {
  id: number
  name: string
  create_time: string
}

/** 分类商品数量统计 */
export interface CategoryStatistic {
  id: number
  name: string
  product_count: number
}

/** 新增 / 修改分类请求体 */
export interface CategoryPayload {
  name: string
}
