/**
 * 401 的处理器注册表。
 *
 * 存在的理由：拦截器在 client.ts 里，而清理登录态要动 stores/session.ts，
 * 后者又依赖 api/auth.ts（它 import client）——直接互相 import 会成环。
 * 这里放一个最小回调位，由 session store 在模块初始化时注册。
 */

type Handler = () => void

let handler: Handler | null = null

export function onUnauthorized(next: Handler): void {
  handler = next
}

/** 通知所有监听者：当前会话已失效 */
export function emitUnauthorized(): void {
  handler?.()
}
