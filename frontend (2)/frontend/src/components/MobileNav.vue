<template>
  <nav class="mobile-nav">
    <div
      v-for="item in navItems"
      :key="item.path"
      class="mobile-nav-item"
      :class="{ active: isActive(item.path) }"
      @click="navigate(item.path)"
    >
      <el-icon class="nav-item-icon">
        <component :is="item.icon" />
      </el-icon>
      <span class="nav-item-label">{{ item.label }}</span>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Upload, List, Reading, DataAnalysis, User } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const navItems = [
  { path: '/upload', label: '上传', icon: Upload },
  { path: '/error-book', label: '错题本', icon: List },
  { path: '/knowledge', label: '知识强化', icon: Reading },
  { path: '/review', label: '学习复盘', icon: DataAnalysis },
  { path: '/profile', label: '我的', icon: User }
]

function isActive(path) {
  // 根路径 '/' 重定向到 /upload，单独处理
  if (path === '/upload') {
    return route.path === '/' || route.path.startsWith(path)
  }
  return route.path.startsWith(path)
}

function navigate(path) {
  if (route.path !== path) {
    router.push(path)
  }
}
</script>

<style scoped lang="scss">
.mobile-nav {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 200;
  display: flex;
  align-items: stretch;
  height: 64px;
  padding-bottom: env(safe-area-inset-bottom, 0px);
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 -4px 24px rgba(0, 0, 0, 0.06);
}

.mobile-nav-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  cursor: pointer;
  transition: all 0.2s ease;
  -webkit-tap-highlight-color: transparent;
  color: var(--ink-tertiary);
  user-select: none;
  padding: 6px 0;

  .nav-item-icon {
    font-size: 22px;
    transition: color 0.2s ease;
  }

  .nav-item-label {
    font-size: 11px;
    font-weight: 500;
    transition: color 0.2s ease;
  }

  &:active {
    transform: scale(0.95);
  }

  &.active {
    color: var(--accent);

    .nav-item-icon {
      color: var(--accent);
    }

    .nav-item-label {
      font-weight: 600;
      color: var(--accent);
    }
  }
}
</style>
