import 'axios'

declare module 'axios' {
  interface AxiosRequestConfig {
    /** 该请求返回 401 时不要整页跳登录（用于启动时的登录态探测） */
    skipAuthRedirect?: boolean
  }
}
