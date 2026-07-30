<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Back,
  Filter,
  Refresh,
  Reading,
  Search,
  Check,
  InfoFilled,
  DocumentCopy,
  Notebook,
  TrendCharts
} from '@element-plus/icons-vue'
import { wrongQuestionApi } from '../api'

const router = useRouter()
const wrongQuestions = ref([])
const selectedSubject = ref('')
const searchQuery = ref('')
const loading = ref(false)
const error = ref('')
const detailVisible = ref(false)
const currentItem = ref(null)
let loadSequence = 0

const defaultSubjects = ['数学', '语文', '英语', '物理', '化学']
const subjects = computed(() => {
  const values = new Set(defaultSubjects)
  wrongQuestions.value.forEach((item) => {
    if (item.subject) values.add(item.subject)
  })
  return [...values]
})

const filteredQuestions = computed(() => {
  let list = wrongQuestions.value
  if (selectedSubject.value) {
    list = list.filter((item) => item.subject === selectedSubject.value)
  }
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    list = list.filter((item) => {
      const text = [
        item.question?.content,
        item.knowledge_point,
        item.wrong_reason,
        item.question?.explanation
      ].filter(Boolean).join(' ').toLowerCase()
      return text.includes(q)
    })
  }
  return list
})

const stats = computed(() => {
  const list = filteredQuestions.value
  return {
    total: list.length,
    active: list.filter((i) => i.status === 'active').length,
    reviewed: list.filter((i) => i.status === 'reviewed').length,
    archived: list.filter((i) => i.status === 'archived' || !i.status).length
  }
})

const hasQuestions = computed(() => filteredQuestions.value.length > 0)

function questionText(item) {
  return item.question?.content?.trim() || '题目内容暂未识别'
}

function confidenceText(confidence) {
  if (confidence === null || !Number.isFinite(confidence)) return ''
  const normalized = confidence <= 1 ? confidence * 100 : confidence
  return `判定置信度 ${Math.round(Math.max(0, Math.min(100, normalized)))}%`
}

function confidenceWarning(item) {
  return item.question?.confidence_warning || (item.question?.needs_review ? '这道题的判定置信度偏低，请结合自己的推导和参考答案自行判断。' : '')
}

function answerText(value, fallback) {
  return value?.trim() || fallback
}

async function load() {
  const sequence = ++loadSequence
  loading.value = true
  error.value = ''
  try {
    const res = await wrongQuestionApi.getList(selectedSubject.value || undefined)
    if (sequence === loadSequence) {
      wrongQuestions.value = Array.isArray(res.data) ? res.data : []
    }
  } catch (loadError) {
    if (sequence === loadSequence) {
      error.value = loadError?.response?.data?.message || loadError?.message || '错题加载失败，请稍后重试'
      wrongQuestions.value = []
    }
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

function filterBySubject(subject) {
  selectedSubject.value = subject
  void load()
}

function startPractice(item) {
  if (!item.knowledge_point) {
    ElMessage.info('这道错题暂未关联知识点，请先在题目详情中查看')
    return
  }
  void router.push({
    name: 'practice',
    query: { subject: item.subject, knowledge_point: item.knowledge_point },
  })
}

function statusInfo(status) {
  if (status === 'active') return { label: '未复习', type: 'danger' }
  if (status === 'reviewed') return { label: '已复习', type: 'warning' }
  return { label: '已归档', type: 'info' }
}

async function showDetail(item) {
  try {
    const res = await wrongQuestionApi.getDetail(item.id)
    currentItem.value = res.data || item
    detailVisible.value = true
  } catch (e) {
    currentItem.value = item
    detailVisible.value = true
    console.warn('Failed to load detail:', e)
  }
}

async function markReviewed(item) {
  try {
    await wrongQuestionApi.updateStatus(item.id, 'reviewed')
    ElMessage.success('已标记为已复习')
    void load()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text || '').then(() => {
    ElMessage.success('已复制')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="wrong-questions-view">
    <!-- 简洁头部 -->
    <section class="page-header-bar">
      <div class="header-title">
        <div class="header-icon">
          <el-icon :size="22"><Notebook /></el-icon>
        </div>
        <div class="header-text">
          <h2>错题本</h2>
          <p>记录、复习、掌握每一个薄弱点</p>
        </div>
      </div>
      <el-button plain round @click="router.push('/chat')">
        <el-icon><Back /></el-icon>
        返回对话
      </el-button>
    </section>

    <!-- 统计卡片 -->
    <section class="stats-bar">
      <div class="stat-card total">
        <el-icon :size="20"><Notebook /></el-icon>
        <div class="stat-body">
          <span class="stat-value">{{ stats.total }}</span>
          <span class="stat-label">总错题</span>
        </div>
      </div>
      <div class="stat-card active">
        <el-icon :size="20"><TrendCharts /></el-icon>
        <div class="stat-body">
          <span class="stat-value">{{ stats.active }}</span>
          <span class="stat-label">未复习</span>
        </div>
      </div>
      <div class="stat-card reviewed">
        <el-icon :size="20"><Check /></el-icon>
        <div class="stat-body">
          <span class="stat-value">{{ stats.reviewed }}</span>
          <span class="stat-label">已复习</span>
        </div>
      </div>
      <div class="stat-card archived">
        <el-icon :size="20"><InfoFilled /></el-icon>
        <div class="stat-body">
          <span class="stat-value">{{ stats.archived }}</span>
          <span class="stat-label">已归档</span>
        </div>
      </div>
    </section>

    <!-- 筛选区 -->
    <section class="filter-panel" aria-label="错题筛选">
      <div class="filter-controls">
        <div class="filter-group subject-group">
          <el-select
            id="wrong-subject"
            v-model="selectedSubject"
            class="subject-select"
            aria-label="按学科筛选错题"
            @change="filterBySubject"
          >
            <el-option label="全部学科" value="" />
            <el-option v-for="subject in subjects" :key="subject" :label="subject" :value="subject" />
          </el-select>
        </div>
        <div class="filter-group search-group">
          <el-input
            v-model="searchQuery"
            placeholder="搜索题目内容、知识点、错因"
            :prefix-icon="Search"
            clearable
            class="search-input"
          />
        </div>
        <el-button class="refresh-button" plain :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
      <div class="result-count">共 {{ filteredQuestions.length }} 道错题</div>
    </section>

    <!-- 错误提示 -->
    <el-alert v-if="error" type="error" show-icon :closable="false" role="alert">
      <template #title>{{ error }}</template>
      <el-button class="alert-action" type="danger" plain size="small" @click="load">重试</el-button>
    </el-alert>

    <!-- 加载骨架 -->
    <section v-if="loading && wrongQuestions.length === 0" class="skeleton-list">
      <div v-for="n in 3" :key="n" class="skeleton-card">
        <div class="skeleton-header">
          <div class="skeleton-circle"></div>
          <div class="skeleton-lines">
            <div class="skeleton-line short"></div>
            <div class="skeleton-line"></div>
          </div>
        </div>
        <div class="skeleton-block"></div>
        <div class="skeleton-grid">
          <div class="skeleton-block"></div>
          <div class="skeleton-block"></div>
        </div>
      </div>
    </section>

    <!-- 错题列表 -->
    <section v-else-if="hasQuestions" class="wrong-question-list" aria-live="polite">
      <article v-for="item in filteredQuestions" :key="item.id" class="wrong-question-card">
        <header class="wrong-question-header">
          <div class="question-index">{{ item.question?.question_number || '—' }}</div>
          <div class="question-heading">
            <div class="tag-row">
              <el-tag :type="item.subject ? 'primary' : 'info'" effect="light" round size="small">
                {{ item.subject || '未分类' }}
              </el-tag>
              <el-tag v-if="item.knowledge_point" type="warning" effect="plain" round size="small">
                {{ item.knowledge_point }}
              </el-tag>
              <el-tag
                size="small"
                :type="statusInfo(item.status).type"
                effect="light"
                round
                class="status-tag"
              >
                {{ statusInfo(item.status).label }}
              </el-tag>
            </div>
            <h3>第 {{ item.question?.question_number || '—' }} 题</h3>
          </div>
          <div class="header-actions">
            <el-button type="primary" plain round size="small" @click="startPractice(item)">
              <el-icon><Reading /></el-icon>
              针对练习
            </el-button>
            <el-button type="default" plain round size="small" @click="showDetail(item)">
              详情
            </el-button>
          </div>
        </header>

        <div class="question-content" role="group" aria-label="题目内容">
          <p>{{ questionText(item) }}</p>
        </div>

        <div class="answer-grid">
          <div class="answer-block student-answer">
            <span class="answer-label">我的答案</span>
            <p>{{ answerText(item.question?.student_answer, '未记录答案') }}</p>
          </div>
          <div class="answer-block reference-answer">
            <span class="answer-label">参考答案</span>
            <p>{{ answerText(item.question?.correct_answer, '暂未提供参考答案') }}</p>
          </div>
        </div>

        <footer class="wrong-question-footer">
          <div class="wrong-reason">
            <span class="answer-label">错因记录</span>
            <p>{{ answerText(item.wrong_reason, item.question?.explanation || '暂未记录错因') }}</p>
          </div>
          <div v-if="confidenceText(item.question?.confidence ?? null)" class="confidence-line">
            <el-icon><InfoFilled /></el-icon>
            <span>{{ confidenceText(item.question?.confidence ?? null) }}</span>
          </div>
          <el-alert
            v-if="confidenceWarning(item)"
            class="confidence-warning"
            type="warning"
            :title="confidenceWarning(item)"
            :closable="false"
            show-icon
          />
        </footer>
      </article>
    </section>

    <!-- 空态 -->
    <section v-else class="empty-section">
      <el-empty description="暂无符合条件的错题" :image-size="96">
        <el-button v-if="selectedSubject || searchQuery" type="primary" plain round @click="selectedSubject = ''; searchQuery = ''; load()">
          查看全部错题
        </el-button>
        <el-button v-else type="primary" round @click="router.push('/chat')">
          返回对话
        </el-button>
      </el-empty>
    </section>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      title="错题详情"
      size="520px"
      direction="rtl"
      destroy-on-close
      class="detail-drawer"
    >
      <template v-if="currentItem">
        <div class="detail-content">
          <div class="detail-badge">第 {{ currentItem.question?.question_number || '—' }} 题</div>

          <div class="detail-section">
            <div class="detail-label">
              <span class="label-dot" style="background: var(--accent)"></span>
              题目
            </div>
            <div class="detail-box">
              <p>{{ questionText(currentItem) }}</p>
            </div>
          </div>

          <div class="detail-grid">
            <div class="detail-section">
              <div class="detail-label">
                <span class="label-dot" style="background: var(--danger)"></span>
                我的答案
              </div>
              <div class="detail-box error">
                <p>{{ answerText(currentItem.question?.student_answer, '未记录答案') }}</p>
              </div>
            </div>
            <div class="detail-section">
              <div class="detail-label">
                <span class="label-dot" style="background: var(--success)"></span>
                参考答案
              </div>
              <div class="detail-box success">
                <p>{{ answerText(currentItem.question?.correct_answer, '暂未提供参考答案') }}</p>
              </div>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-label">
              <span class="label-dot" style="background: var(--warning)"></span>
              错因 / 解析
            </div>
            <div class="detail-box">
              <p>{{ answerText(currentItem.wrong_reason, currentItem.question?.explanation || '暂未记录错因') }}</p>
            </div>
          </div>

          <div class="detail-meta">
            <div class="meta-item">
              <span class="meta-label">学科</span>
              <span class="meta-value">{{ currentItem.subject || '未分类' }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">知识点</span>
              <span class="meta-value">{{ currentItem.knowledge_point || '—' }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">状态</span>
              <el-tag size="small" :type="statusInfo(currentItem.status).type" effect="light" round>
                {{ statusInfo(currentItem.status).label }}
              </el-tag>
            </div>
            <div class="meta-item">
              <span class="meta-label">置信度</span>
              <span class="meta-value">{{ confidenceText(currentItem.question?.confidence ?? null) || '未知' }}</span>
            </div>
            <div class="meta-item">
              <span class="meta-label">归档时间</span>
              <span class="meta-value">{{ currentItem.created_at || '未知' }}</span>
            </div>
          </div>

          <el-alert
            v-if="confidenceWarning(currentItem)"
            class="confidence-warning"
            type="warning"
            :title="confidenceWarning(currentItem)"
            :closable="false"
            show-icon
          />
        </div>

        <div class="detail-footer">
          <el-button
            v-if="currentItem.status === 'active'"
            type="success"
            :icon="Check"
            round
            @click="markReviewed(currentItem); detailVisible = false"
          >
            标记已复习
          </el-button>
          <el-button type="primary" plain :icon="Reading" round @click="startPractice(currentItem)">
            针对练习
          </el-button>
          <el-button plain :icon="DocumentCopy" round @click="copyToClipboard(questionText(currentItem))">
            复制题目
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.wrong-questions-view {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}

/* 简洁头部 */
.page-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.header-title {
  display: flex;
  align-items: center;
  gap: 14px;
}
.header-icon {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: var(--gradient-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: var(--shadow-glow);
}
.header-text h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: -0.01em;
}
.header-text p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ink-secondary);
}

/* 统计卡片 */
.stats-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  background: var(--surface-solid);
  border: 1px solid var(--separator);
  border-radius: var(--radius-md);
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: var(--shadow-sm);
  transition: transform 0.2s;
}
.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}
.stat-card .el-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}
.stat-card.total .el-icon { background: var(--gradient-primary); }
.stat-card.active .el-icon { background: var(--gradient-warm); }
.stat-card.reviewed .el-icon { background: var(--gradient-success); }
.stat-card.archived .el-icon { background: var(--gradient-cool); }
.stat-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  line-height: 1;
}
.stat-label {
  font-size: 12px;
  color: var(--ink-tertiary);
}

/* 筛选面板 */
.filter-panel {
  background: var(--surface-solid);
  border-radius: var(--radius-md);
  padding: 16px 18px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--separator);
}
.filter-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.filter-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.subject-select {
  width: 150px;
}
.search-group {
  flex: 1;
  min-width: 220px;
}
.search-input :deep(.el-input__wrapper) {
  border-radius: 999px !important;
  padding-left: 14px;
}
.refresh-button {
  margin-left: auto;
}
.result-count {
  font-size: 12px;
  color: var(--ink-tertiary);
  margin-top: 10px;
}

/* 错题列表 */
.wrong-question-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wrong-question-card {
  background: var(--surface-solid);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow-sm);
  border: 1px solid var(--separator);
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.wrong-question-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

.wrong-question-header {
  display: flex;
  gap: 14px;
  margin-bottom: 16px;
  align-items: flex-start;
}
.question-index {
  flex-shrink: 0;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
  color: var(--accent);
  border: 1px solid var(--separator);
  border-radius: 12px;
  font-weight: 700;
  font-size: 16px;
}
.question-heading {
  flex: 1;
  min-width: 0;
}
.tag-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 6px;
  flex-wrap: wrap;
}
.status-tag {
  font-weight: 600;
}
.question-heading h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
}
.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.question-content {
  margin-bottom: 16px;
  padding: 16px;
  background: var(--bg);
  border-radius: 12px;
  border: 1px solid var(--separator);
}
.question-content p {
  margin: 0;
  line-height: 1.75;
  color: var(--ink);
  font-size: 14px;
}

.answer-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 16px;
}
.answer-block {
  padding: 12px;
  border-radius: 10px;
}
.student-answer {
  background: #fef2f2;
  border-left: 3px solid var(--danger);
}
.reference-answer {
  background: #f0fdf4;
  border-left: 3px solid var(--success);
}
.answer-label {
  display: block;
  font-weight: 600;
  font-size: 11px;
  margin-bottom: 6px;
  color: var(--ink-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.answer-block p {
  margin: 0;
  line-height: 1.6;
  color: var(--ink);
  word-break: break-word;
  font-size: 14px;
}

.wrong-question-footer {
  padding-top: 14px;
  border-top: 1px solid var(--separator);
}
.wrong-reason {
  margin-bottom: 10px;
}
.wrong-reason p {
  margin: 0;
  line-height: 1.6;
  color: var(--ink-secondary);
  font-size: 14px;
}
.confidence-line {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--ink-tertiary);
  margin-bottom: 8px;
}
.confidence-warning {
  margin-top: 8px;
}

/* 空态 */
.empty-section {
  padding: 60px 0;
  background: var(--surface-solid);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

/* 骨架屏 */
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.skeleton-card {
  background: var(--surface-solid);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow-sm);
}
.skeleton-header {
  display: flex;
  gap: 14px;
  margin-bottom: 16px;
  align-items: center;
}
.skeleton-circle {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.skeleton-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.skeleton-line {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
.skeleton-line.short {
  width: 40%;
}
.skeleton-block {
  height: 52px;
  border-radius: 10px;
  background: linear-gradient(90deg, #f3f4f6 25%, #e5e7eb 50%, #f3f4f6 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  margin-bottom: 10px;
}
.skeleton-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* 详情抽屉 */
.detail-drawer :deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 20px 24px;
  border-bottom: 1px solid var(--separator);
}
.detail-drawer :deep(.el-drawer__body) {
  padding: 0;
  display: flex;
  flex-direction: column;
}
.detail-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.detail-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 14px;
  background: var(--gradient-primary);
  color: white;
  border-radius: 999px;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 20px;
}
.detail-section {
  margin-bottom: 18px;
}
.detail-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink);
  margin-bottom: 8px;
}
.label-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.detail-box {
  padding: 14px;
  background: var(--bg);
  border-radius: 10px;
  border: 1px solid var(--separator);
}
.detail-box.error {
  background: #fef2f2;
  border-color: #fecaca;
}
.detail-box.success {
  background: #f0fdf4;
  border-color: #bbf7d0;
}
.detail-box p {
  margin: 0;
  line-height: 1.75;
  color: var(--ink);
  word-break: break-word;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.detail-meta {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  padding: 16px;
  background: var(--bg);
  border-radius: 12px;
  border: 1px solid var(--separator);
  margin-bottom: 16px;
}
.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.meta-label {
  font-size: 11px;
  color: var(--ink-tertiary);
  font-weight: 500;
}
.meta-value {
  font-size: 13px;
  color: var(--ink);
  font-weight: 500;
}
.detail-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--separator);
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  background: var(--surface-solid);
}

/* 移动端适配 */
@media (max-width: 768px) {
  .wrong-questions-view {
    padding: 16px;
  }
  .page-header-bar {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
  .stats-bar {
    grid-template-columns: repeat(2, 1fr);
  }
  .filter-controls {
    flex-direction: column;
    align-items: stretch;
  }
  .search-group,
  .subject-select,
  .refresh-button {
    width: 100%;
  }
  .refresh-button {
    margin-left: 0;
  }
  .answer-grid,
  .detail-grid,
  .detail-meta {
    grid-template-columns: 1fr;
  }
  .wrong-question-header {
    flex-direction: column;
    gap: 10px;
  }
  .header-actions {
    width: 100%;
  }
  .header-actions .el-button {
    flex: 1;
  }
}
</style>
