<template>
  <div class="tracking-page">
    <!-- 页面头部 -->
    <PageHeader title="长期缺漏追踪" subtitle="知识图谱可视化，间隔重复复习，长效记忆" />

    <!-- 总览区 -->
    <section class="overview grid-3">
      <div class="card overview-card">
        <div class="overview-icon icon-mastery">
          <el-icon><TrendCharts /></el-icon>
        </div>
        <div class="overview-body">
          <div class="overview-label">整体掌握度</div>
          <div class="overview-value">{{ overview.mastery }}<span class="unit">%</span></div>
          <el-progress
            :percentage="overview.mastery"
            :stroke-width="8"
            :show-text="false"
            color="#6366f1"
            class="overview-progress"
          />
        </div>
      </div>

      <div class="card overview-card">
        <div class="overview-icon icon-review">
          <el-icon><Clock /></el-icon>
        </div>
        <div class="overview-body">
          <div class="overview-label">今日待复习</div>
          <div class="overview-value">{{ overview.todayReview }}<span class="unit">题</span></div>
          <el-button type="primary" size="small" round class="review-btn" @click="startReview">
            开始复习
          </el-button>
        </div>
      </div>

      <div class="card overview-card">
        <div class="overview-icon icon-streak">
          <el-icon><Calendar /></el-icon>
        </div>
        <div class="overview-body">
          <div class="overview-label">连续学习天数</div>
          <div class="overview-value">{{ overview.streakDays }}<span class="unit">天</span></div>
          <div class="overview-extra">坚持就是胜利，继续加油</div>
        </div>
      </div>
    </section>

    <!-- 知识图谱 -->
    <section class="card knowledge-card">
      <div class="card-header">
        <h2 class="card-title">知识图谱</h2>
        <span class="card-desc">12 个核心知识点的掌握程度</span>
      </div>
      <div class="knowledge-map">
        <span
          v-for="(node, index) in knowledgeMap"
          :key="index"
          class="knowledge-node"
          :class="`level-${node.level}`"
        >
          {{ node.name }}
          <em class="node-percent">{{ node.percent }}%</em>
        </span>
      </div>
      <div class="legend">
        <span class="legend-item"><i class="dot level-1"></i>掌握良好</span>
        <span class="legend-item"><i class="dot level-2"></i>基本掌握</span>
        <span class="legend-item"><i class="dot level-3"></i>待提升</span>
        <span class="legend-item"><i class="dot level-4"></i>薄弱</span>
      </div>
    </section>

    <!-- 底部双栏 -->
    <section class="grid-2">
      <!-- 间隔重复复习计划 -->
      <div class="card plan-card">
        <div class="card-header">
          <h2 class="card-title">间隔重复复习计划</h2>
          <span class="card-desc">基于艾宾浩斯遗忘曲线</span>
        </div>
        <el-timeline class="plan-timeline">
          <el-timeline-item
            v-for="(item, index) in reviewPlan"
            :key="index"
            :type="item.active ? 'primary' : 'info'"
            :hollow="!item.active"
            :timestamp="item.date"
            placement="top"
            size="large"
          >
            <div class="plan-node" :class="{ active: item.active }">
              <div class="plan-stage">{{ item.stage }}</div>
              <div class="plan-content">
                <span class="plan-count">{{ item.count }} 道题</span>
                <span class="plan-tag" v-if="item.active">进行中</span>
              </div>
            </div>
          </el-timeline-item>
        </el-timeline>
      </div>

      <!-- 学习活跃度热力图 -->
      <div class="card heatmap-card">
        <div class="card-header">
          <h2 class="card-title">学习活跃度</h2>
          <span class="card-desc">最近 14 天学习记录</span>
        </div>
        <div class="heatmap">
          <div
            v-for="(item, index) in heatMap"
            :key="index"
            class="heat-block"
            :class="`heat-${item.level}`"
            :title="`${item.date}：${item.count} 题`"
          >
            <span class="heat-count" v-if="item.count > 0">{{ item.count }}</span>
          </div>
        </div>
        <div class="heatmap-footer">
          <span class="heatmap-tip">少</span>
          <div class="heat-legend">
            <i class="heat-block heat-0"></i>
            <i class="heat-block heat-1"></i>
            <i class="heat-block heat-2"></i>
            <i class="heat-block heat-3"></i>
            <i class="heat-block heat-4"></i>
          </div>
          <span class="heatmap-tip">多</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { TrendCharts, Clock, Calendar } from '@element-plus/icons-vue'
import { trackingApi } from '@/api'
import { PageHeader } from '@/components'
import { useRequest } from '@/composables/useRequest'

// 总览数据（mock 初始展示）
const overview = ref({
  mastery: 68,
  todayReview: 7,
  streakDays: 23
})

// 知识图谱数据：level 1-4 分别对应 掌握良好/基本掌握/待提升/薄弱
const knowledgeMap = ref([
  { name: '函数与方程', level: 1, percent: 92 },
  { name: '导数应用', level: 2, percent: 78 },
  { name: '三角函数', level: 1, percent: 88 },
  { name: '数列求和', level: 3, percent: 58 },
  { name: '立体几何', level: 4, percent: 35 },
  { name: '解析几何', level: 3, percent: 52 },
  { name: '概率统计', level: 2, percent: 74 },
  { name: '不等式', level: 1, percent: 90 },
  { name: '向量运算', level: 2, percent: 71 },
  { name: '复数概念', level: 1, percent: 95 },
  { name: '排列组合', level: 4, percent: 40 },
  { name: '二项式定理', level: 3, percent: 55 }
])

// 间隔重复复习计划
const reviewPlan = ref([
  { stage: '今天', date: '今日复习', count: 7, active: true },
  { stage: '7 天后', date: '巩固强化', count: 12, active: false },
  { stage: '14 天后', date: '中期回顾', count: 9, active: false },
  { stage: '30 天后', date: '长效记忆', count: 6, active: false }
])

// 热力图数据：level 0-4，0 表示无数据
const heatMap = ref([
  { date: '7/5', count: 3, level: 2 },
  { date: '7/6', count: 5, level: 3 },
  { date: '7/7', count: 0, level: 0 },
  { date: '7/8', count: 8, level: 4 },
  { date: '7/9', count: 4, level: 2 },
  { date: '7/10', count: 6, level: 3 },
  { date: '7/11', count: 2, level: 1 },
  { date: '7/12', count: 7, level: 4 },
  { date: '7/13', count: 5, level: 3 },
  { date: '7/14', count: 3, level: 2 },
  { date: '7/15', count: 6, level: 3 },
  { date: '7/16', count: 9, level: 4 },
  { date: '7/17', count: 4, level: 2 },
  { date: '7/18', count: 7, level: 4 }
])

// 统一 API 请求封装（消除 try-catch 重复）
const { request } = useRequest()

const fetchAllTrackerData = async () => {
  await request(trackingApi.getTracker, {
    onSuccess: (data) => {
      // 掌握度
      if (data.mastery_levels) {
        const allPoints = [
          ...(data.mastery_levels.mastered || []),
          ...(data.mastery_levels.pending || []),
          ...(data.mastery_levels.weak || [])
        ]
        overview.value.mastery = Math.round(
          ((data.mastery_levels.mastered?.length || 0) / Math.max(allPoints.length, 1)) * 100
        ) || overview.value.mastery
      }

      // 知识图谱节点
      if (data.mastery_levels) {
        const all = [
          ...(data.mastery_levels.mastered || []).map(n => ({ name: n, level: 1, percent: 90 })),
          ...(data.mastery_levels.pending || []).map(n => ({ name: n, level: 2, percent: 65 })),
          ...(data.mastery_levels.weak || []).map(n => ({ name: n, level: 4, percent: 35 }))
        ]
        if (all.length) knowledgeMap.value = all
      }

      // 复习计划
      if (data.review_plan && data.review_plan.length) {
        reviewPlan.value = data.review_plan.map((item, i) => ({
          stage: `第${i + 1}次`,
          date: item.next_review || `${i * 7}天后`,
          count: 0,
          active: i === 0
        }))
      }
    },
    warnMsg: '获取追踪数据失败，使用 mock 数据'
  })
}

// 开始复习
const startReview = () => {
  ElMessage.success(`开始复习，共 ${overview.value.todayReview} 道题`)
}

onMounted(() => {
  fetchAllTrackerData()
})
</script>

<style lang="scss" scoped>
.tracking-page {
  padding: 24px;
  min-height: 100%;
  color: var(--text-color, #1f2937);

  // page-header now uses <PageHeader> component

  // 通用卡片：毛玻璃效果
  .card {
    background: var(--card-bg, rgba(255, 255, 255, 0.65));
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border: 1px solid var(--card-border, rgba(255, 255, 255, 0.4));
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 8px 24px rgba(31, 41, 55, 0.06);
    transition: transform 0.25s ease, box-shadow 0.25s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 12px 32px rgba(99, 102, 241, 0.12);
    }
  }

  .card-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 18px;

    .card-title {
      margin: 0;
      font-size: 17px;
      font-weight: 600;
      color: var(--title-color, #111827);
    }

    .card-desc {
      font-size: 12px;
      color: var(--text-secondary, #9ca3af);
    }
  }

  // 栅格布局
  .grid-3 {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
    margin-bottom: 18px;
  }

  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 18px;
  }

  // 总览卡片
  .overview-card {
    display: flex;
    align-items: center;
    gap: 16px;

    .overview-icon {
      width: 52px;
      height: 52px;
      border-radius: 14px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 24px;
      color: #fff;
      flex-shrink: 0;

      &.icon-mastery {
        background: linear-gradient(135deg, #6366f1, #8b5cf6);
      }
      &.icon-review {
        background: linear-gradient(135deg, #f59e0b, #f97316);
      }
      &.icon-streak {
        background: linear-gradient(135deg, #10b981, #06b6d4);
      }
    }

    .overview-body {
      flex: 1;
      min-width: 0;
    }

    .overview-label {
      font-size: 13px;
      color: var(--text-secondary, #6b7280);
      margin-bottom: 4px;
    }

    .overview-value {
      font-size: 28px;
      font-weight: 700;
      color: var(--title-color, #111827);
      line-height: 1.2;

      .unit {
        font-size: 14px;
        font-weight: 400;
        margin-left: 2px;
        color: var(--text-secondary, #9ca3af);
      }
    }

    .overview-progress {
      margin-top: 8px;
    }

    .overview-extra {
      margin-top: 6px;
      font-size: 12px;
      color: var(--text-secondary, #9ca3af);
    }

    .review-btn {
      margin-top: 8px;
    }
  }

  // 知识图谱
  .knowledge-card {
    margin-bottom: 18px;

    .knowledge-map {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
    }

    .knowledge-node {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 500;
      cursor: default;
      transition: transform 0.2s ease;

      &:hover {
        transform: translateY(-2px);
      }

      .node-percent {
        font-style: normal;
        font-size: 12px;
        opacity: 0.85;
      }

      // 1: 掌握良好 绿色
      &.level-1 {
        background: rgba(16, 185, 129, 0.15);
        color: #047857;
        border: 1px solid rgba(16, 185, 129, 0.35);
      }
      // 2: 基本掌握 蓝色
      &.level-2 {
        background: rgba(59, 130, 246, 0.15);
        color: #1d4ed8;
        border: 1px solid rgba(59, 130, 246, 0.35);
      }
      // 3: 待提升 橙色
      &.level-3 {
        background: rgba(249, 115, 22, 0.15);
        color: #c2410c;
        border: 1px solid rgba(249, 115, 22, 0.35);
      }
      // 4: 薄弱 红色
      &.level-4 {
        background: rgba(239, 68, 68, 0.15);
        color: #b91c1c;
        border: 1px solid rgba(239, 68, 68, 0.35);
      }
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 18px;
      margin-top: 18px;
      padding-top: 16px;
      border-top: 1px dashed var(--card-border, rgba(0, 0, 0, 0.08));

      .legend-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: var(--text-secondary, #6b7280);

        .dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          display: inline-block;

          &.level-1 {
            background: #10b981;
          }
          &.level-2 {
            background: #3b82f6;
          }
          &.level-3 {
            background: #f97316;
          }
          &.level-4 {
            background: #ef4444;
          }
        }
      }
    }
  }

  // 复习计划时间轴
  .plan-card {
    .plan-timeline {
      padding-left: 4px;

      :deep(.el-timeline-item__node--primary) {
        background-color: #6366f1;
        box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.2);
      }

      :deep(.el-timeline-item__timestamp) {
        color: var(--text-secondary, #9ca3af);
        font-size: 12px;
      }
    }

    .plan-node {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 8px 12px;
      border-radius: 10px;
      transition: background 0.2s ease;

      &.active {
        background: rgba(99, 102, 241, 0.08);
      }

      .plan-stage {
        font-size: 14px;
        font-weight: 600;
        color: var(--title-color, #111827);
      }

      .plan-content {
        display: flex;
        align-items: center;
        gap: 8px;

        .plan-count {
          font-size: 12px;
          color: var(--text-secondary, #6b7280);
        }

        .plan-tag {
          font-size: 11px;
          padding: 2px 8px;
          border-radius: 10px;
          background: rgba(99, 102, 241, 0.15);
          color: #6366f1;
        }
      }
    }
  }

  // 热力图
  .heatmap-card {
    .heatmap {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 8px;
      margin-bottom: 16px;
    }

    .heat-block {
      aspect-ratio: 1 / 1;
      border-radius: 6px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      font-weight: 600;
      color: rgba(255, 255, 255, 0.9);
      transition: transform 0.2s ease;

      &:hover {
        transform: scale(1.1);
      }

      // 0 级：无数据
      &.heat-0 {
        background: rgba(99, 102, 241, 0.06);
        color: transparent;
      }
      // 1-4 级：递增透明度
      &.heat-1 {
        background: rgba(99, 102, 241, 0.25);
      }
      &.heat-2 {
        background: rgba(99, 102, 241, 0.45);
      }
      &.heat-3 {
        background: rgba(99, 102, 241, 0.7);
      }
      &.heat-4 {
        background: rgba(99, 102, 241, 0.95);
      }
    }

    .heatmap-footer {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;

      .heatmap-tip {
        font-size: 12px;
        color: var(--text-secondary, #9ca3af);
      }

      .heat-legend {
        display: flex;
        gap: 4px;

        .heat-block {
          width: 14px;
          height: 14px;
          aspect-ratio: auto;
          border-radius: 3px;
        }
      }
    }
  }
}

// 响应式
@media (max-width: 1024px) {
  .tracking-page {
    .grid-3 {
      grid-template-columns: 1fr;
    }
    .grid-2 {
      grid-template-columns: 1fr;
    }
  }
}
</style>
