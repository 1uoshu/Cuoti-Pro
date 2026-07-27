import { createRouter, createWebHistory } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录注册', requiresAuth: false }
  },
  {
    path: '/chat',
    name: 'Chat',
    component: () => import('@/views/ChatView.vue'),
    meta: { title: '对话', requiresAuth: true }
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/chat'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 全局前置守卫：检查登录状态
router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - 智学错题` : '智学错题'
  
  const userStore = useUserStore()
  const isLoggedIn = userStore.isLoggedIn

  if (to.meta.requiresAuth && !isLoggedIn) {
    next('/login')
  } else if (to.path === '/login' && isLoggedIn) {
    next('/chat')
  } else if (to.meta.requiresAdmin && userStore.userInfo?.role !== 'admin') {
    ElMessage.error('仅管理员可访问')
    next('/')
  } else {
    next()
  }
})

export default router
