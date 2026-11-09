import axios, { type AxiosError, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'

import { emitUnauthorized } from '@/api/unauthorized'
import type { ApiResponse } from '@/types/api'

/** 网络异常时的统一文案 */
const NETWORK_ERROR_MESSAGE = '网络异常，请确认后端已启动'

const client = axios.create({
  // 开发期由 Vite proxy 把 /api 转发到 http://127.0.0.1:8000
  baseURL: '/api',
  timeout: 10000,
})

/**
 * 401 只处理一次：同一时刻多个请求失败时，避免弹一串提示、跳多次路由。
 *
 * 例外：请求方可以用 `skipAuthRedirect: true` 关掉跳转——`/auth/me` 是启动时的
 * 登录态探测，未登录返回 401 属于正常结果，不能因此触发整页跳转（会丢掉 redirect 参数）。
 */
let redirecting = false

/**
 * 未登录/会话过期：清本地状态并把人送回登录页。
 *
 * 用 window.location.assign 而不是 router.push——拦截器不在组件里，
 * 拿不到 router 实例；整页跳转也顺便清掉组件里的残留状态。
 */
function handleUnauthorized(skipRedirect = false) {
  emitUnauthorized()
  // 单测跑在 node 环境（没有 window）；探测类请求也不需要跳转
  if (skipRedirect || typeof window === 'undefined') {
    return
  }
  const { pathname, search } = window.location
  if (redirecting || pathname.startsWith('/login')) {
    return
  }
  const redirect =
    pathname === '/' || pathname === '/chat'
      ? ''
      : `?redirect=${encodeURIComponent(pathname + search)}`
  ElMessage.warning('登录已过期，请重新登录')
  redirecting = true
  window.location.assign(`/login${redirect}`)
}

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
    if (body.code === 401) {
      handleUnauthorized(response.config.skipAuthRedirect === true)
      return Promise.reject(new Error(body.message || '请先登录'))
    }
    if (body.code !== 200) {
      // 业务失败也按 HTTP 200 返回的兜底分支，统一提示后端 message
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message || '请求失败'))
    }
    return response
  },
  (error: AxiosError<unknown>) => {
    // 后端用 HTTP 401 表示未登录，这里不要当成普通错误弹提示
    if (error.response?.status === 401) {
      handleUnauthorized(error.config?.skipAuthRedirect === true)
      const body = error.response.data as { message?: string } | undefined
      return Promise.reject(new Error(body?.message || '请先登录'))
    }
    const message = resolveErrorMessage(error)
    ElMessage.error(message)
    return Promise.reject(new Error(message))
  },
)

export default client
