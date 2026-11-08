import { createRouter, createWebHistory } from 'vue-router'

// 对话页带着 markdown-it + DOMPurify（约 60KB gzip），按需加载
const ChatView = () => import('@/views/ChatView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // 商品 / 分类 / 概览页已归档（archive/product-admin/），现在应用只有对话
    { path: '/', redirect: '/chat' },
    {
      path: '/chat',
      name: 'chat',
      component: ChatView,
      meta: { title: '对话' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/chat' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} - My Agent` : 'My Agent'
})

export default router
