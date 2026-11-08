import axios, { type AxiosError, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

import type { ApiResponse } from '@/types/api'

/** 网络异常时的统一文案 */
const NETWORK_ERROR_MESSAGE = '网络异常，请确认后端已启动'

const client = axios.create({
  // 开发期由 Vite proxy 把 /api 转发到 http://127.0.0.1:8000
  baseURL: '/api',
  timeout: 10000,
})

/** 判断响应体是否为后端统一包裹结构 */
function isApiResponse(body: unknown): body is ApiResponse<unknown> {
  return typeof body === 'object' && body !== null && 'code' in body && 'message' in body
}

/** 从 422 校验失败的 data 中提取第一条字段错误，便于定位问题 */
function extractValidationDetail(data: unknown): string {
  if (!Array.isArray(data) || data.length === 0) {
    return ''
  }
  const first = data[0] as { loc?: unknown[]; msg?: string }
  const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : ''
  const reason = first.msg ?? ''
  if (!field && !reason) {
    return ''
  }
  return `${String(field)} ${reason}`.trim()
}

/** 把 HTTP 异常转换成可展示的中文提示 */
function resolveErrorMessage(error: AxiosError<unknown>): string {
  const response = error.response
  if (!response) {
    return NETWORK_ERROR_MESSAGE
  }
  const body = response.data
  if (isApiResponse(body)) {
    const message = body.message || '请求失败'
    if (body.code === 422) {
      const detail = extractValidationDetail(body.data)
      return detail ? `${message}：${detail}` : message
    }
    return message
  }
  if (response.status === 404) {
    return '请求的资源不存在'
  }
  if (response.status >= 500) {
    return '服务器内部错误，请稍后重试'
  }
  return `请求失败（HTTP ${response.status}）`
}

client.interceptors.response.use(
  (response: AxiosResponse<unknown>) => {
    const body = response.data
    // 非统一包裹结构（如根路径健康检查）原样返回，交给调用方处理
    if (!isApiResponse(body)) {
      return response
    }
    if (body.code !== 200) {
      // 业务失败也按 HTTP 200 返回的兜底分支，统一提示后端 message
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return response
  },
  (error: AxiosError<unknown>) => {
    const message = resolveErrorMessage(error)
    ElMessage.error(message)
    return Promise.reject(new Error(message))
  },
)

export default client
