<template>
  <div class="error-book-page">
    <!-- 页面头部 -->
    <PageHeader title="错题本" subtitle="集中管理你的所有错题，针对性复习巩固" />

    <!-- 统计卡片 -->
    <section class="grid-4 stats-grid">
      <StatCard
        v-for="s in stats"
        :key="s.key"
        :icon="s.icon"
        :value="s.value"
        :unit="s.unit"
        :label="s.label"
        :color="s.color"
        size="small"
      />
    </section>

    <!-- 筛选栏 -->
    <section class="filter-bar">
      <el-select
        v-model="filters.subject"
        placeholder="全部科目"
        clearable
        class="filter-select"
        @change="onFilterChange"
      >
        <el-option
          v-for="item in subjectOptions"
          :key="item"
          :label="item"
          :value="item"
        />
      </el-select>

      <el-input
        v-model="filters.search"
        placeholder="搜索题目内容…"
        clearable
        class="filter-search"
        :prefix-icon="Search"
        @input="onSearchInput"
      />
    </section>

    <!-- 错题列表 -->
    <CommonTable
      title="错题列表"
      :header-icon="List"
      :data="errorList"
      :loading="tableLoading"
      :total="totalErrors"
      empty-text="暂无错题记录，继续保持！"
      :pagination="true"
      v-model:current-page="page"
      v-model:page-size="pageSize"
      @pagination-change="onPageChange"
    >
      <template #actions>
        <el-button text @click="refreshList">
          <el-icon><Refresh /></el-icon> 刷新
        </el-button>
      </template>

      <el-table-column prop="id" label="题号" width="85" align="center" />
      <el-table-column prop="subject" label="科目" width="85">
        <template #default="{ row }">
          <el-tag :type="subjectTagType(row.subject)" effect="plain" size="small">
            {{ row.subject }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="questionContent" label="题目" show-overflow-tooltip min-width="200" />
      <el-table-column prop="wrongReason" label="错因" width="110">
        <template #default="{ row }">
          <el-tag :type="wrongReasonTagType(row.wrongReason)" size="small" effect="light">
            {{ row.wrongReason || '其他' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="knowledgePoint" label="知识点" width="120">
        <template #default="{ row }">
          <el-tag type="info" size="small" effect="plain">{{ row.knowledgePoint }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="得分" width="85" align="center">
        <template #default="{ row }">
          <span :class="scoreClass(row.score, row.maxScore)">
            {{ row.score }}/{{ row.maxScore }}
          </span>
        </template>
      </el-table-column>
      <el-table-column prop="wrongCount" label="错误次数" width="90" align="center">
        <template #default="{ row }">
          <el-tag type="danger" size="small" effect="plain" round>{{ row.wrongCount }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" align="center" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" size="small" @click="showDetail(row)">
            详情
          </el-button>
        </template>
      </el-table-column>
    </CommonTable>

    <!-- 错题详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      :title="`错题详情 · #${detailData?.id}`"
      width="640px"
      align-center
      class="detail-dialog"
    >
      <template v-if="detailData">
        <div class="detail-section">
          <div class="detail-label">题目内容</div>
          <div class="detail-question">{{ detailData.questionContent }}</div>
        </div>

        <div class="detail-grid">
          <div class="detail-section">
            <div class="detail-label">你的答案</div>
            <div class="detail-answer wrong">
              <el-icon><Close /></el-icon>
              {{ detailData.studentAnswer || '未作答' }}
            </div>
          </div>
          <div class="detail-section">
            <div class="detail-label">正确答案</div>
            <div class="detail-answer correct">
              <el-icon><Check /></el-icon>
              {{ detailData.correctAnswer }}
            </div>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-label">解析</div>
          <div class="detail-analysis">{{ detailData.analysis }}</div>
        </div>

        <div class="detail-section" v-if="detailData.wrongReason">
          <div class="detail-label">错因分析</div>
          <div class="detail-analysis wrong-reason">{{ detailData.wrongReason }}</div>
        </div>

        <div class="detail-meta">
          <el-tag :type="subjectTagType(detailData.subject)" effect="plain" size="small">
            {{ detailData.subject }}
          </el-tag>
          <el-tag type="info" effect="plain" size="small">
            {{ detailData.knowledgePoint }}
          </el-tag>
          <el-tag type="warning" effect="plain" size="small">
            {{ detailData.score }}/{{ detailData.maxScore }} 分
          </el-tag>
          <el-tag type="danger" effect="plain" size="small">
            错误 {{ detailData.wrongCount }} 次
          </el-tag>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, List, Refresh, Close, Check } from '@element-plus/icons-vue'
import { errorBookApi, dashboardApi } from '@/api'
import { PageHeader, StatCard, CommonTable } from '@/components'
import { useRequest } from '@/composables/useRequest'

/* ============ 响应式状态 ============ */
const { request } = useRequest()

const stats = ref([
  { key: 'total', label: '累计错题', value: 0, unit: '题', icon: List, color: 'purple' },
  { key: 'weak', label: '薄弱知识点', value: 0, unit: '个', icon: List, color: 'red' }
])

const subjectOptions = ref([])
const filters = reactive({
  subject: '',
  search: ''
})

const errorList = ref([])
const totalErrors = ref(0)
const page = ref(1)
const pageSize = ref(10)
const tableLoading = ref(false)
let searchTimer = null

const detailVisible = ref(false)
const detailData = ref(null)

/* ========== 后端 → 前端字段映射 ========== */
function mapWrongItem(item) {
  const q = item.question || {}
  return {
    id: item.id,
    subject: item.subject || '',
    questionContent: q.content || '（无题目内容）',
    wrongReason: item.wrong_reason || '',
    knowledgePoint: item.knowledge_point || q.knowledge_point || '',
    score: q.score ?? 0,
    maxScore: q.max_score ?? 10,
    wrongCount: item.wrong_count ?? 1,
    status: item.status || 'unreviewed',
    studentAnswer: q.student_answer || '',
    correctAnswer: q.correct_answer || '',
    analysis: q.explanation || ''
  }
}

/* ============ 状态映射 ============ */
const SUBJECT_TAG_MAP = { 数学: 'primary', 物理: 'success', 英语: 'warning', 化学: 'danger', 语文: 'info' }
function subjectTagType(s) { return SUBJECT_TAG_MAP[s] || 'info' }

function wrongReasonTagType(reason) {
  const map = { '计算错误': 'danger', '概念不清': 'warning', '审题失误': 'info', '逻辑错误': 'danger', '粗心大意': 'warning' }
  return map[reason] || 'warning'
}

function scoreClass(score, total) {
  const pct = total > 0 ? score / total : 0
  if (pct >= 0.8) return 'score-high'
  if (pct >= 0.5) return 'score-mid'
  return 'score-low'
}

/* ============ 数据加载 ============ */
async function loadStats() {
  await request(dashboardApi.getStats, {
    onSuccess: (data) => {
      stats.value[0].value = data.wrong_count ?? 0
      stats.value[1].value = data.weak_points?.length ?? 0
    },
    warnMsg: '统计加载失败'
  })
}

async function loadList() {
  tableLoading.value = true

  const params = {}
  if (filters.subject) params.subject = filters.subject

  await request(() => errorBookApi.getList(params), {
    loading: tableLoading,
    onSuccess: (list) => {
      const arr = Array.isArray(list) ? list : []
      const mapped = arr.map(mapWrongItem)

      // 本地搜索过滤（后端只支持科目过滤）
      let filtered = mapped
      if (filters.search) {
        const q = filters.search.toLowerCase()
        filtered = mapped.filter(r => r.questionContent.toLowerCase().includes(q))
      }

      // 提取科目选项
      const subjects = [...new Set(mapped.map(r => r.subject).filter(Boolean))]
      if (subjects.length) subjectOptions.value = subjects.sort()

      totalErrors.value = filtered.length
      const start = (page.value - 1) * pageSize.value
      errorList.value = filtered.slice(start, start + pageSize.value)
    },
    warnMsg: '错题列表加载失败'
  })
}

/* ============ 交互逻辑 ============ */
function onFilterChange() {
  page.value = 1
  loadList()
}

function onSearchInput() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    loadList()
  }, 400)
}

function onPageChange() {
  loadList()
}

function refreshList() {
  loadStats()
  loadList()
}

function showDetail(row) {
  detailData.value = row
  detailVisible.value = true
}

/* ============ 初始化 ============ */
onMounted(() => {
  loadStats()
  loadList()
})
</script>

<style scoped lang="scss">
.error-book-page {
  padding: 8px 4px 40px;
}

.stats-grid {
  margin-bottom: 20px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filter-select {
  width: 150px;
}

.filter-search {
  width: 220px;
}

.score-high { color: var(--success); font-weight: 700; }
.score-mid  { color: var(--warning); font-weight: 700; }
.score-low  { color: var(--danger);  font-weight: 700; }

/* 详情弹窗 */
.detail-section {
  margin-bottom: 20px;
}

.detail-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-tertiary);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-question {
  font-size: 16px;
  line-height: 1.7;
  color: var(--ink);
  font-weight: 500;
  padding: 16px 18px;
  background: var(--accent-light);
  border-radius: var(--radius-sm);
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.detail-answer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  border-radius: var(--radius-sm);
  font-size: 15px;
  font-weight: 600;

  &.wrong {
    background: rgba(239, 68, 68, 0.08);
    color: var(--danger);
  }

  &.correct {
    background: rgba(16, 185, 129, 0.08);
    color: var(--success);
  }

  .el-icon { font-size: 18px; }
}

.detail-analysis {
  font-size: 14px;
  line-height: 1.8;
  color: var(--ink-secondary);
  padding: 16px 18px;
  background: rgba(0, 0, 0, 0.02);
  border: 1px solid var(--separator);
  border-radius: var(--radius-sm);

  &.wrong-reason {
    background: rgba(239, 68, 68, 0.04);
    border-color: rgba(239, 68, 68, 0.15);
  }
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 4px;
}
</style>
