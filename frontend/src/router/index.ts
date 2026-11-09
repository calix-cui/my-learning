import { createRouter, createWebHistory } from 'vue-router'

import { isLoggedIn, loadCurrentUser, session } from '@/stores/session'

// 对话页带着 markdown-it + DOMPurify（约 60KB gzip），按需加载
const ChatView = () => import('@/views/ChatView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const RegisterView = () => import('@/views/RegisterView.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { title: '登录', public: true },
    },
    {
      path: '/register',
      name: 'register',
      component: RegisterView,
      meta: { title: '注册', public: true },
    },
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

/**
 * 未登录只能进登录/注册页。
 *
 * 关键点：首次进入时 `session.loaded` 为 false，必须先问后端一次，
 * 否则刷新页面会把已登录用户踢回登录页。
 */
router.beforeEach(async (to) => {
  if (!session.loaded) {
    await loadCurrentUser()
  }

  const isPublic = to.meta.public === true

  if (!isLoggedIn() && !isPublic) {
    return { name: 'login', query: to.fullPath === '/' ? {} : { redirect: to.fullPath } }
  }

  // 已登录还去登录/注册页，直接送进对话
  if (isLoggedIn() && isPublic) {
    return { name: 'chat' }
  }

  return true
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} - My Agent` : 'My Agent'
})

export default router
