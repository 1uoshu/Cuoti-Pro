<template>
  <div
    class="stat-card"
    :class="[sizeClass, { 'is-clickable': !!to || !!$attrs.onClick }]"
  >
    <!-- 图标区 -->
    <div v-if="icon" class="stat-icon" :style="iconStyle">
      <el-icon><component :is="icon" /></el-icon>
    </div>

    <!-- 数值区 -->
    <div class="stat-body">
      <div class="stat-value">
        {{ value }}<span v-if="unit" class="stat-unit">{{ unit }}</span>
      </div>
      <div class="stat-label">{{ label }}</div>
    </div>

    <!-- 趋势指示器（可选） -->
    <div v-if="trend" class="stat-trend" :class="trendType">
      <el-icon><component :is="trendIcon" /></el-icon>
      <span>{{ trend }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ArrowUp, ArrowDown } from '@element-plus/icons-vue'

const props = defineProps({
  /** 图标组件引用（如 TrendCharts） */
  icon: { type: [Object, Function], default: null },
  /** 主数值 */
  value: { type: [String, Number], required: true },
  /** 数值单位 */
  unit: { type: String, default: '' },
  /** 标签文本 */
  label: { type: String, required: true },
  /** 图标背景渐变。传则覆盖 color */
  gradient: { type: String, default: '' },
  /** 快捷颜色名（gradient 为空时生效） */
  color: { type: String, default: 'primary' },
  /** 卡片尺寸 */
  size: { type: String, default: 'default', validator: v => ['small', 'default', 'large'].includes(v) },
  /** 趋势文本（如 "+12%"） */
  trend: { type: String, default: '' },
  /** 趋势方向 */
  trendType: { type: String, default: 'up', validator: v => ['up', 'down'].includes(v) }
})

const COLOR_MAP = {
  primary: { bg: 'rgba(99, 102, 241, 0.12)', icon: '#6366f1', bar: 'var(--gradient-primary)' },
  green:   { bg: 'rgba(16, 185, 129, 0.12)', icon: '#10b981', bar: 'var(--gradient-success)' },
  red:     { bg: 'rgba(239, 68, 68, 0.12)',  icon: '#ef4444',  bar: 'var(--gradient-warm)' },
  purple:  { bg: 'rgba(139, 92, 246, 0.12)', icon: '#8b5cf6',  bar: 'linear-gradient(135deg, #8b5cf6, #a78bfa)' },
  orange:  { bg: 'rgba(245, 158, 11, 0.12)', icon: '#f59e0b',  bar: 'linear-gradient(135deg, #f59e0b, #f97316)' },
  teal:    { bg: 'rgba(6, 182, 212, 0.12)',  icon: '#06b6d4',  bar: 'linear-gradient(135deg, #06b6d4, #6366f1)' }
}

const sizeClass = computed(() => `stat-${props.size}`)

const iconStyle = computed(() => {
  if (props.gradient) {
    return { background: props.gradient, color: '#fff' }
  }
  const m = COLOR_MAP[props.color] || COLOR_MAP.primary
  return { background: m.bg, color: m.icon }
})

const trendIcon = computed(() => props.trendType === 'up' ? ArrowUp : ArrowDown)
</script>

<style scoped lang="scss">
.stat-card {
  position: relative;
  background: var(--surface);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-md);
  padding: 22px 24px;
  box-shadow: var(--shadow-sm);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--gradient-primary);
    opacity: 0.85;
  }

  &:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
  }

  &.is-clickable {
    cursor: pointer;
  }

  /* ---- 尺寸变体 ---- */
  &.stat-small {
    padding: 16px 18px;
    .stat-icon { width: 38px; height: 38px; font-size: 17px; }
    .stat-value { font-size: 24px; }
  }

  &.stat-large {
    padding: 28px 30px;
    .stat-icon { width: 56px; height: 56px; font-size: 26px; }
    .stat-value { font-size: 36px; }
  }
}

/* ---- 图标 ---- */
.stat-icon {
  width: 46px;
  height: 46px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
  margin-bottom: 16px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
}

/* ---- 数值 ---- */
.stat-body {
  min-width: 0;
}

.stat-value {
  font-size: 30px;
  font-weight: 700;
  letter-spacing: -0.025em;
  line-height: 1.1;
  color: var(--ink);
}

.stat-unit {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-tertiary);
  margin-left: 3px;
}

.stat-label {
  font-size: 13px;
  color: var(--ink-secondary);
  margin-top: 4px;
}

/* ---- 趋势 ---- */
.stat-trend {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 12px;
  font-weight: 600;
  padding: 3px 8px;
  border-radius: 999px;
  margin-top: 12px;
  align-self: flex-start;

  &.up {
    color: var(--success);
    background: rgba(16, 185, 129, 0.1);
  }

  &.down {
    color: var(--danger);
    background: rgba(239, 68, 68, 0.1);
  }
}
</style>
