<template>
  <div class="app">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <!-- Logo -->
      <div class="logo">
        <div class="logo-icon">
          <el-icon><Lightning /></el-icon>
        </div>
        <span class="logo-text">智学错题</span>
      </div>

      <!-- 导航菜单 -->
      <ul class="nav-list">
        <li
          v-for="item in menuItems"
          :key="item.path"
          class="nav-item"
          :class="{ active: currentPath === item.path }"
          @click="navigateTo(item.path)"
        >
          <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
          {{ item.title }}
        </li>
      </ul>

      <!-- 用户卡片 -->
      <div class="user-card" @click="navigateTo('/profile')">
        <div class="avatar">{{ userInitial }}</div>
        <div class="user-info">
          <div class="user-name">{{ userStore.userInfo?.nickname || '用户' }}</div>
          <div class="user-grade">{{ userStore.userInfo?.grade || '' }}</div>
        </div>
        <el-icon style="color: var(--ink-tertiary);"><ArrowRight /></el-icon>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>

    <!-- 移动端底部导航栏（≤768px 显示） -->
    <MobileNav class="mobile-only" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import {
  Upload, Reading, DataAnalysis, DocumentChecked, Timer, ArrowRight, List
} from '@element-plus/icons-vue'
import MobileNav from '@/components/MobileNav.vue'

// 闪电图标（自定义 SVG，因为 Element Plus 没有闪电）
const Lightning = {
  template: '<svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18"><path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z"/></svg>'
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const menuItems = [
  { path: '/upload', title: '作业上传', icon: Upload },
  { path: '/error-book', title: '错题本', icon: List },
  { path: '/knowledge', title: '知识强化', icon: Reading },
  { path: '/review', title: '学习复盘', icon: DataAnalysis },
  { path: '/assessment', title: '阶段评估', icon: DocumentChecked },
  { path: '/tracking', title: '长期追踪', icon: Timer }
]

const currentPath = computed(() => route.path)

const userInitial = computed(() => {
  const name = userStore.userInfo?.nickname || '用户'
  return name.charAt(0)
})

function navigateTo(path) {
  router.push(path)
}
</script>

<style scoped lang="scss">
.app {
  display: flex;
  min-height: 100vh;
}

/* 侧边栏 - 毛玻璃质感 */
.sidebar {
  width: 248px;
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border-right: 1px solid rgba(0, 0, 0, 0.04);
  box-shadow: 1px 0 24px rgba(0, 0, 0, 0.03);
  padding: 28px 16px;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
}

.logo {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 0 10px 22px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  margin-bottom: 18px;

  .logo-icon {
    width: 36px;
    height: 36px;
    background: var(--gradient-primary);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  }

  .logo-text {
    font-size: 16px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.01em;
  }
}

.nav-list {
  list-style: none;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  margin-bottom: 4px;
  color: var(--ink-secondary);
  font-size: 14px;
  font-weight: 500;
  outline: none;
  border: 1px solid transparent;

  &:hover {
    background: rgba(99, 102, 241, 0.06);
    color: var(--ink);
    transform: translateX(2px);
  }

  &.active {
    background: var(--gradient-primary);
    color: white;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3);
  }
}

.nav-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  border-radius: var(--radius-sm);
  margin-top: auto;
  border: 1px solid rgba(0, 0, 0, 0.04);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);

  &:hover {
    background: rgba(255, 255, 255, 0.85);
    box-shadow: var(--shadow-sm);
    transform: translateY(-1px);
  }
}

.avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--teal), var(--accent));
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 13px;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.3);
}

.user-info {
  flex: 1;
  min-width: 0;

  .user-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink);
  }

  .user-grade {
    font-size: 11px;
    color: var(--ink-tertiary);
  }
}

/* 主内容区 */
.main {
  flex: 1;
  margin-left: 248px;
  padding: 44px 52px;
  max-width: 1200px;
}

@media (max-width: 768px) {
  .sidebar {
    display: none;
  }
  .main {
    margin-left: 0;
    padding: 24px 20px 80px; /* 底部留出导航栏空间 */
  }
}
</style>
