import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import AppShell from '../components/AppShell.vue'
import AssignmentDetailView from '../views/AssignmentDetailView.vue'
import AssignmentsView from '../views/AssignmentsView.vue'
import DashboardView from '../views/DashboardView.vue'
import LoginView from '../views/LoginView.vue'
import PracticeView from '../views/PracticeView.vue'
import ProfileView from '../views/ProfileView.vue'
import WrongQuestionsView from '../views/WrongQuestionsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', name: 'dashboard', component: DashboardView },
        { path: 'assignments', name: 'assignments', component: AssignmentsView },
        { path: 'assignments/:id', name: 'assignment-detail', component: AssignmentDetailView, props: true },
        { path: 'wrong-questions', name: 'wrong-questions', component: WrongQuestionsView },
        { path: 'practice', name: 'practice', component: PracticeView },
        { path: 'profile', name: 'profile', component: ProfileView },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (!to.meta.public && !auth.isAuthenticated) return { name: 'login' }
  if (to.name === 'login' && auth.isAuthenticated) return { name: 'dashboard' }
  return true
})

export default router
