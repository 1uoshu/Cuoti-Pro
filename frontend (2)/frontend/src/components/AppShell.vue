<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  CircleUserRound,
  ClipboardCheck,
  FileUp,
  LayoutDashboard,
  LogOut,
  NotebookPen,
} from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navigation = [
  { label: '学习概览', to: '/', icon: LayoutDashboard },
  { label: '作业批改', to: '/assignments', icon: FileUp },
  { label: '错题本', to: '/wrong-questions', icon: NotebookPen },
  { label: '针对练习', to: '/practice', icon: ClipboardCheck },
  { label: '个人资料', to: '/profile', icon: CircleUserRound },
]

const pageTitle = computed(() => {
  if (route.path.startsWith('/assignments/')) return '作业详情'
  return navigation.find((item) => item.to === route.path)?.label || '学习记录'
})

async function signOut() {
  await auth.logout()
  await router.replace('/login')
}
</script>

<template>
  <div class="app-shell">
    <a class="skip-link" href="#main-content">跳到主要内容</a>
    <aside class="sidebar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">知</span>
        <span>知错学习</span>
      </RouterLink>

      <nav aria-label="主导航">
        <RouterLink v-for="item in navigation" :key="item.to" :to="item.to" class="nav-link">
          <component :is="item.icon" :size="18" stroke-width="2" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-user">
        <span class="avatar">{{ auth.user?.nickname.slice(0, 1) || '学' }}</span>
        <span class="user-copy">
          <strong>{{ auth.user?.nickname }}</strong>
          <small>{{ auth.user?.grade || '学习者' }}</small>
        </span>
        <el-tooltip content="退出登录" placement="right">
          <el-button class="icon-button" text circle aria-label="退出登录" @click="signOut">
            <LogOut :size="18" />
          </el-button>
        </el-tooltip>
      </div>
    </aside>

    <main id="main-content" class="workspace" tabindex="-1">
      <header class="topbar">
        <div>
          <p class="page-context">学习中心</p>
          <h1>{{ pageTitle }}</h1>
        </div>
        <el-button type="primary" :icon="FileUp" @click="router.push('/assignments')">上传作业</el-button>
      </header>
      <section class="page-content">
        <RouterView />
      </section>
    </main>
  </div>
</template>
