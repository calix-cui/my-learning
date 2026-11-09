/**
 * 全局测试环境补丁（只在 happy-dom 环境生效）。
 *
 * `vitest.config.ts` 的默认环境是 node——纯逻辑（api / stores / themes）用 node 跑最快；
 * 组件测试在文件顶部写 `// @vitest-environment happy-dom` 切到 DOM 环境，本文件负责补齐
 * happy-dom 没实现、但组件会调用到的浏览器 API，避免每个测试自己 stub 一遍。
 */

if (typeof window !== 'undefined') {
  // 主题 store 用它监听系统深浅色；happy-dom 默认没有实现
  if (typeof window.matchMedia !== 'function') {
    window.matchMedia = ((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia
  }

  // Element Plus 的下拉/弹层用这两个观察器做定位
  class NoopObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return []
    }
  }
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = NoopObserver as unknown as typeof ResizeObserver
  }
  if (typeof globalThis.IntersectionObserver === 'undefined') {
    globalThis.IntersectionObserver = NoopObserver as unknown as typeof IntersectionObserver
  }

  // 聊天页滚动到底部会调用 scrollTo；happy-dom 的 Element 没有实现
  if (typeof Element !== 'undefined' && !Element.prototype.scrollTo) {
    Element.prototype.scrollTo = () => {}
  }
}
