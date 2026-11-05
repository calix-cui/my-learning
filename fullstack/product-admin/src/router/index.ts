import { createRouter, createWebHistory } from 'vue-router'

import CategoryManage from '@/views/CategoryManage.vue'
import Dashboard from '@/views/Dashboard.vue'
import ProductList from '@/views/ProductList.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/products' },
    {
      path: '/products',
      name: 'products',
      component: ProductList,
      meta: { title: '商品管理' },
    },
    {
      path: '/categories',
      name: 'categories',
      component: CategoryManage,
      meta: { title: '分类管理' },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: Dashboard,
      meta: { title: '概览' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/products' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.afterEach((to) => {
  const title = to.meta.title as string | undefined
  document.title = title ? `${title} - 商品管理后台` : '商品管理后台'
})

export default router
