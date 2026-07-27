<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight, BookOpenCheck, ClipboardX, FileText } from 'lucide-vue-next'
import { api, errorMessage, request } from '../api'
import { useAuthStore } from '../stores/auth'
import type { Assignment, MasteryRecord } from '../types'

interface DashboardData {
  assignment_count: number
  wrong_count: number
  weak_points: Pick<MasteryRecord, 'subject' | 'knowledge_point' | 'mastery_score'>[]
}

const auth = useAuthStore()
const router = useRouter()
const loading = ref(true)
const error = ref('')
const dashboard = ref<DashboardData>({ assignment_count: 0, wrong_count: 0, weak_points: [] })
const assignments = ref<Assignment[]>([])
const pendingAssignments = computed(() => assignments.value.filter((item) => item.status === 'queued' || item.status === 'processing'))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [dashboardData, assignmentData] = await Promise.all([
      request<DashboardData>(api.get('/dashboard')),
      request<Assignment[]>(api.get('/assignments')),
    ])
    dashboard.value = dashboardData
    assignments.value = assignmentData
  } catch (loadError) {
    error.value = errorMessage(loadError)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="stack-lg">
    <div class="welcome-row">
      <div>
        <p class="page-context">{{ new Date().getHours() < 12 ? '上午好' : '下午好' }}</p>
        <h2>{{ auth.user?.nickname }}，从一处薄弱点开始巩固</h2>
      </div>
      <el-button plain @click="router.push('/practice')">开始针对练习 <ArrowRight :size="16" /></el-button>
    </div>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" />

    <div class="metric-grid" v-loading="loading">
      <article class="metric-card teal"><span class="metric-icon"><FileText :size="20" /></span><span>累计作业</span><strong>{{ dashboard.assignment_count }}</strong><small>份提交记录</small></article>
      <article class="metric-card rust"><span class="metric-icon"><ClipboardX :size="20" /></span><span>待巩固错题</span><strong>{{ dashboard.wrong_count }}</strong><small>道错题待回顾</small></article>
      <article class="metric-card blue"><span class="metric-icon"><BookOpenCheck :size="20" /></span><span>进行中批改</span><strong>{{ pendingAssignments.length }}</strong><small>份作业处理中</small></article>
    </div>

    <div class="content-grid two-column">
      <section class="panel">
        <div class="panel-heading"><div><p class="page-context">掌握度</p><h3>优先复习</h3></div><RouterLink to="/wrong-questions">查看错题本</RouterLink></div>
        <div v-if="dashboard.weak_points.length" class="mastery-list">
          <div v-for="point in dashboard.weak_points" :key="`${point.subject}-${point.knowledge_point}`" class="mastery-row">
            <div><strong>{{ point.knowledge_point }}</strong><small>{{ point.subject }}</small></div>
            <el-progress :percentage="point.mastery_score" :stroke-width="8" :show-text="false" color="var(--color-primary)" />
            <span>{{ point.mastery_score }}%</span>
          </div>
        </div>
        <el-empty v-else description="完成批改后，这里会展示薄弱知识点" :image-size="68" />
      </section>

      <section class="panel">
        <div class="panel-heading"><div><p class="page-context">最近作业</p><h3>批改进度</h3></div><RouterLink to="/assignments">全部作业</RouterLink></div>
        <div v-if="assignments.length" class="assignment-list">
          <button v-for="assignment in assignments.slice(0, 4)" :key="assignment.id" class="assignment-row" @click="router.push(`/assignments/${assignment.id}`)">
            <span class="file-tile">{{ assignment.subject.slice(0, 1) }}</span>
            <span class="assignment-copy"><strong>{{ assignment.title }}</strong><small>{{ new Date(assignment.created_at).toLocaleDateString('zh-CN') }}</small></span>
            <el-tag :type="assignment.status === 'completed' ? 'success' : assignment.status === 'failed' ? 'danger' : 'warning'" effect="plain">{{ assignment.status === 'completed' ? '已完成' : assignment.status === 'failed' ? '失败' : '处理中' }}</el-tag>
          </button>
        </div>
        <el-empty v-else description="还没有作业记录" :image-size="68"><el-button type="primary" @click="router.push('/assignments')">上传第一份作业</el-button></el-empty>
      </section>
    </div>
  </div>
</template>
