<template>
  <div class="review-page">
    <!-- 页面头部 -->
    <PageHeader title="多周期学习复盘" subtitle="回顾学习轨迹，发现进步与不足" gradient />

    <!-- 周期切换选项卡 -->
    <div class="period-tabs">
      <div
        v-for="item in periodOptions"
        :key="item.value"
        class="period-tab"
        :class="{ active: currentPeriod === item.value }"
        @click="switchPeriod(item.value)"
      >
        <el-icon class="period-tab-icon"><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </div>
    </div>

    <!-- 统计卡片 -->
    <section class="grid-4 stat-cards">
      <StatCard
        v-for="card in statCards"
        :key="card.key"
        :icon="card.icon"
        :value="card.value"
        :unit="card.unit"
        :label="card.label"
        :gradient="card.gradient"
        :trend="card.trend"
        :trend-type="card.trendType"
      />
    </section>

    <!-- 图表区 -->
    <section class="grid-2 chart-section">
      <!-- 错题数量趋势 -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <h3 class="chart-title">错题数量趋势</h3>
            <p class="chart-desc">最近 7 天错题数变化</p>
          </div>
          <el-tag type="danger" effect="light" round>最近 7 天</el-tag>
        </div>
        <div ref="trendChartRef" class="chart-container"></div>
      </div>

      <!-- 科目分布 -->
      <div class="chart-card">
        <div class="chart-header">
          <div>
            <h3 class="chart-title">各科目错题分布</h3>
            <p class="chart-desc">按学科统计错题占比</p>
          </div>
          <el-tag type="warning" effect="light" round>共 {{ totalSubjectErrors }} 题</el-tag>
        </div>
        <div class="subject-list">
          <div class="subject-item" v-for="subject in subjectDistribution" :key="subject.name">
            <div class="subject-head">
              <div class="subject-name">
                <span class="subject-dot" :style="{ background: subject.color }"></span>
                {{ subject.name }}
              </div>
              <div class="subject-count">{{ subject.count }} 题</div>
            </div>
            <el-progress
              :percentage="subject.percent"
              :color="subject.color"
              :stroke-width="10"
              :show-text="false"
              class="subject-progress"
            />
            <div class="subject-percent">{{ subject.percent }}%</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 错误类型分析 -->
    <section class="error-types-card">
      <div class="card-header">
        <div>
          <h3 class="card-title">错误类型分析</h3>
          <p class="card-desc">识别薄弱环节，针对性提升</p>
        </div>
        <el-tag type="info" effect="light" round>本周统计</el-tag>
      </div>
      <div class="grid-4 error-type-list">
        <div
          v-for="item in errorTypes"
          :key="item.type"
          class="error-type-item"
          :style="{ '--type-color': item.color }"
        >
          <div class="error-type-ring">
            <el-progress
              type="circle"
              :percentage="item.percent"
              :width="72"
              :stroke-width="7"
              :color="item.color"
            >
              <template #default>
                <span class="ring-text">{{ item.percent }}%</span>
              </template>
            </el-progress>
          </div>
          <div class="error-type-name">{{ item.type }}</div>
          <div class="error-type-count">{{ item.count }} 题</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Calendar,
  DataLine,
  PieChart,
  Histogram,
  TrendCharts,
  CircleCheck,
  Warning,
  Select
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { reviewApi } from '@/api'
import { PageHeader, StatCard } from '@/components'
import { useRequest } from '@/composables/useRequest'

// ===== 周期切换 =====
const periodOptions = [
  { value: 'daily', label: '日报', icon: Calendar },
  { value: 'weekly', label: '周报', icon: DataLine },
  { value: 'monthly', label: '月报', icon: Histogram },
  { value: 'semester', label: '学期', icon: PieChart }
]
const currentPeriod = ref('weekly')

// ===== Mock 数据 =====
const mockStats = {
  totalQuestions: 23,
  correctQuestions: 18,
  errorQuestions: 5,
  accuracy: 78
}

const mockTrend = {
  dates: ['7/12', '7/13', '7/14', '7/15', '7/16', '7/17', '7/18'],
  values: [4, 6, 3, 7, 5, 8, 5]
}

const mockSubjectDistribution = [
  { name: '数学', count: 12, percent: 44, color: '#6366f1' },
  { name: '物理', count: 8, percent: 30, color: '#8b5cf6' },
  { name: '英语', count: 5, percent: 19, color: '#06b6d4' },
  { name: '语文', count: 3, percent: 11, color: '#ec4899' }
]

const mockErrorTypes = [
  { type: '计算错误', percent: 40, count: 10, color: '#ef4444' },
  { type: '概念不清', percent: 25, count: 6, color: '#f59e0b' },
  { type: '逻辑错误', percent: 20, count: 5, color: '#8b5cf6' },
  { type: '审题失误', percent: 15, count: 4, color: '#06b6d4' }
]

// ===== 响应式数据 =====
const stats = reactive({ ...mockStats })
const trendData = reactive({ ...mockTrend })
const subjectDistribution = ref([...mockSubjectDistribution])
const errorTypes = ref([...mockErrorTypes])

const totalSubjectErrors = computed(() =>
  subjectDistribution.value.reduce((sum, item) => sum + item.count, 0)
)

// ===== 统计卡片配置 =====
const statCards = computed(() => [
  {
    key: 'total',
    label: '本周练习题数',
    value: stats.totalQuestions,
    unit: '题',
    icon: TrendCharts,
    gradient: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
    trend: '+12%',
    trendType: 'up',
    trendIcon: ArrowUp
  },
  {
    key: 'correct',
    label: '正确题数',
    value: stats.correctQuestions,
    unit: '题',
    icon: CircleCheck,
    gradient: 'linear-gradient(135deg, #10b981 0%, #34d399 100%)',
    trend: '+8%',
    trendType: 'up',
    trendIcon: ArrowUp
  },
  {
    key: 'error',
    label: '错题数',
    value: stats.errorQuestions,
    unit: '题',
    icon: Warning,
    gradient: 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
    trend: '-15%',
    trendType: 'down',
    trendIcon: ArrowDown
  },
  {
    key: 'accuracy',
    label: '正确率',
    value: stats.accuracy,
    unit: '%',
    icon: Select,
    gradient: 'linear-gradient(135deg, #06b6d4 0%, #6366f1 100%)',
    trend: '+5%',
    trendType: 'up',
    trendIcon: ArrowUp
  }
])

// ===== ECharts =====
const trendChartRef = ref(null)
let trendChart = null

function initTrendChart() {
  if (!trendChartRef.value) return
  trendChart = echarts.init(trendChartRef.value)
  updateTrendChart()
}

function updateTrendChart() {
  if (!trendChart) return
  const option = {
    grid: {
      top: 30,
      right: 20,
      bottom: 36,
      left: 40
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: 'rgba(99, 102, 241, 0.2)',
      borderWidth: 1,
      textStyle: { color: '#0a0a0f', fontSize: 13 },
      extraCssText: 'box-shadow: 0 8px 24px rgba(0,0,0,0.08); border-radius: 12px; padding: 10px 14px;',
      formatter: (params) => {
        const p = params[0]
        return `<div style="font-weight:600;margin-bottom:4px;">${p.axisValue}</div>
                <div style="color:#6366f1;">错题数：<b>${p.value}</b> 题</div>`
      }
    },
    xAxis: {
      type: 'category',
      data: trendData.dates,
      axisLine: { lineStyle: { color: 'rgba(0,0,0,0.08)' } },
      axisTick: { show: false },
      axisLabel: {
        color: '#9ca3af',
        fontSize: 12
      }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: 'rgba(0,0,0,0.04)', type: 'dashed' } },
      axisLabel: {
        color: '#9ca3af',
        fontSize: 12
      }
    },
    series: [
      {
        name: '错题数',
        type: 'bar',
        data: trendData.values,
        barWidth: '46%',
        itemStyle: {
          borderRadius: [8, 8, 8, 8],
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#8b5cf6' },
            { offset: 1, color: '#6366f1' }
          ])
        },
        emphasis: {
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: '#a78bfa' },
              { offset: 1, color: '#7c3aed' }
            ])
          }
        },
        label: {
          show: true,
          position: 'top',
          color: '#4b5563',
          fontSize: 12,
          fontWeight: 600
        }
      }
    ]
  }
  trendChart.setOption(option)
}

// ===== 数据获取 =====
const { request } = useRequest()

async function fetchReviewData(period) {
  const res = await request(() => reviewApi.getStats(period), {
    warnMsg: '[Review] 使用 mock 数据'
  })

  if (res?.stats) {
    Object.assign(stats, res.stats)
  }
  // 后端 report 字段包含完整报告文本
  if (typeof res?.report === 'string') {
    // 报告文本可用于扩展展示
  }
  // 数据不足时保留 mock 数据
}

// ===== 切换周期 =====
function switchPeriod(period) {
  if (currentPeriod.value === period) return
  currentPeriod.value = period
  ElMessage.success(`已切换到 ${periodOptions.find(p => p.value === period)?.label} 视图`)
  fetchReviewData(period)
}

// ===== 监听窗口尺寸 =====
function handleResize() {
  trendChart?.resize()
}

// ===== 生命周期 =====
onMounted(async () => {
  await nextTick()
  initTrendChart()
  window.addEventListener('resize', handleResize)
  // 异步获取真实数据，失败时保留 mock 数据
  fetchReviewData(currentPeriod.value)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  trendChart = null
})

// 监听图表数据变化
watch(trendData, () => {
  updateTrendChart()
}, { deep: true })
</script>

<style scoped lang="scss">
.review-page {
  padding: 8px 4px 40px;
}

/* ===== 周期切换选项卡 ===== */
.period-tabs {
  display: inline-flex;
  gap: 4px;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  padding: 5px;
  border-radius: var(--radius-sm);
  margin-bottom: 24px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow: var(--shadow-xs);

  .period-tab {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 9px 20px;
    border-radius: 9px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s ease;
    color: var(--ink-secondary);
    user-select: none;

    .period-tab-icon {
      font-size: 15px;
    }

    &:hover:not(.active) {
      background: rgba(99, 102, 241, 0.06);
      color: var(--accent);
    }

    &.active {
      background: var(--gradient-primary);
      color: #fff;
      box-shadow: 0 4px 14px rgba(99, 102, 241, 0.3);
    }
  }
}

/* ===== 统计卡片 ===== */
.stat-cards {
  margin-bottom: 24px;
}

/* ===== 图表区 ===== */
.chart-section {
  margin-bottom: 24px;
}

.chart-card {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-md);
  padding: 22px;
  box-shadow: var(--shadow-sm);
  transition: all 0.3s ease;

  &:hover {
    box-shadow: var(--shadow-md);
  }

  .chart-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 18px;
  }

  .chart-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.015em;
  }

  .chart-desc {
    font-size: 12px;
    color: var(--ink-tertiary);
    margin-top: 3px;
  }
}

.chart-container {
  width: 100%;
  height: 320px;
}

/* ===== 科目分布 ===== */
.subject-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 6px 4px 4px;
}

.subject-item {
  position: relative;

  .subject-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .subject-name {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
  }

  .subject-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    box-shadow: 0 0 0 3px rgba(0, 0, 0, 0.04);
  }

  .subject-count {
    font-size: 13px;
    color: var(--ink-secondary);
    font-weight: 600;
  }

  .subject-progress {
    width: 100%;
  }

  .subject-percent {
    position: absolute;
    right: 0;
    top: 28px;
    font-size: 12px;
    font-weight: 700;
    color: var(--ink-secondary);
  }

  :deep(.el-progress-bar__outer) {
    background: rgba(0, 0, 0, 0.05);
    border-radius: 999px;
  }

  :deep(.el-progress-bar__inner) {
    border-radius: 999px;
    transition: width 0.6s ease;
  }
}

/* ===== 错误类型分析 ===== */
.error-types-card {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-md);
  padding: 24px;
  box-shadow: var(--shadow-sm);

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 22px;
  }

  .card-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.015em;
  }

  .card-desc {
    font-size: 12px;
    color: var(--ink-tertiary);
    margin-top: 3px;
  }
}

.error-type-list {
  gap: 18px;
}

.error-type-item {
  text-align: center;
  padding: 18px 12px;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(0, 0, 0, 0.04);
  transition: all 0.25s ease;
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(135deg, var(--type-color, transparent) 0%, transparent 60%);
    opacity: 0.04;
    pointer-events: none;
  }

  &:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-md);
    background: rgba(255, 255, 255, 0.85);
  }

  .error-type-ring {
    display: flex;
    justify-content: center;
    margin-bottom: 12px;

    .ring-text {
      font-size: 15px;
      font-weight: 700;
      color: var(--ink);
    }
  }

  .error-type-name {
    font-size: 14px;
    font-weight: 600;
    color: var(--ink);
    margin-bottom: 2px;
  }

  .error-type-count {
    font-size: 12px;
    color: var(--ink-tertiary);
  }

  :deep(.el-progress-circle__track) {
    stroke: rgba(0, 0, 0, 0.05);
  }
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .period-tabs {
    width: 100%;
    justify-content: space-between;

    .period-tab {
      flex: 1;
      justify-content: center;
      padding: 9px 8px;
    }
  }

  .stat-card {
    padding: 18px;

    .stat-value {
      font-size: 26px;
    }
  }

  .chart-container {
    height: 260px;
  }
}
</style>
