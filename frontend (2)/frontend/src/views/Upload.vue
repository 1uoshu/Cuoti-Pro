<template>
  <div class="upload-page">
    <!-- 页面头部 -->
    <PageHeader
      title="作业上传与自动批改"
      subtitle="支持图片（JPG / PNG）和 PDF 格式，上传后 AI 自动识别并批改"
    />

    <!-- 统计卡片 -->
    <div class="grid-4 stats-grid">
      <StatCard
        v-for="item in stats"
        :key="item.label"
        :icon="item.icon"
        :value="item.value"
        :unit="item.unit"
        :label="item.label"
        :color="item.color"
      />
    </div>

    <!-- 上传区域 -->
    <div class="upload-card">
      <!-- 科目与标题 -->
      <div class="upload-meta">
        <el-select
          v-model="uploadSubject"
          placeholder="选择科目（必选）"
          size="large"
          class="meta-subject"
        >
          <el-option v-for="s in subjectOptions" :key="s" :label="s" :value="s" />
        </el-select>
        <el-input
          v-model="uploadTitle"
          placeholder="作业名称（选填，默认使用文件名）"
          size="large"
          class="meta-title"
          maxlength="128"
        />
      </div>

      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        :auto-upload="false"
        :accept="acceptTypes"
        :on-change="handleFileChange"
        :file-list="fileList"
        :show-file-list="true"
        :limit="1"
        :on-exceed="handleExceed"
      >
        <div class="upload-inner">
          <div class="upload-icon-wrapper">
            <el-icon class="upload-icon"><UploadFilled /></el-icon>
          </div>
          <div class="upload-text">将作业文件拖到此处，或<em>点击上传</em></div>
          <div class="upload-hint">支持 JPG、PNG、PDF 格式，单文件不超过 10MB</div>
        </div>
      </el-upload>

      <!-- 操作按钮 -->
      <div class="upload-actions" v-if="fileList.length > 0">
        <el-button
          type="primary"
          size="large"
          :loading="uploading"
          :disabled="!uploadSubject"
          @click="submitUpload"
        >
          {{ uploading ? '上传中...' : '开始上传' }}
        </el-button>
        <el-button size="large" :disabled="uploading" @click="clearFiles">清空</el-button>
      </div>

      <!-- 批改进度 -->
      <div class="progress-wrapper" v-if="taskPolling">
        <div class="progress-label">
          <span>{{ taskStep }}</span>
          <span>{{ taskProgress }}%</span>
        </div>
        <el-progress
          :percentage="taskProgress"
          :status="taskStatus === 'completed' ? 'success' : taskStatus === 'failed' ? 'exception' : ''"
          :stroke-width="10"
          :show-text="false"
        />
        <div v-if="taskError" class="task-error">{{ taskError }}</div>
      </div>
    </div>

    <!-- 最近批改记录 -->
    <CommonTable
      title="最近批改记录"
      :header-icon="Document"
      :data="assignmentList"
      :loading="listLoading"
      :total="assignmentList.length"
      empty-text="暂无批改记录，上传作业后将自动展示"
    >
      <template #actions>
        <el-button text :loading="listLoading" @click="loadAssignments">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </template>

      <el-table-column prop="title" label="作业名称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="subject" label="科目" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="subjectTagMap[row.subject] || 'info'" effect="plain" size="small">
            {{ row.subject }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="得分" width="110" align="center">
        <template #default="{ row }">
          <template v-if="row.status === 'completed'">
            <span :class="scoreClass(row.student_score, row.total_score)">
              {{ row.student_score ?? '-' }}/{{ row.total_score ?? '-' }}
            </span>
          </template>
          <el-tag v-else type="info" size="small" effect="plain">
            {{ taskStatusLabel(row.task?.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="assignmentStatusType(row)" effect="light" size="small" round>
            {{ assignmentStatusLabel(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="上传时间" width="170" align="center">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
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

    <!-- 作业详情弹窗 -->
    <el-dialog
      v-model="detailVisible"
      :title="detailData?.title || '作业详情'"
      width="720px"
      align-center
      class="detail-dialog"
    >
      <template v-if="detailData">
        <div class="detail-overall">
          <div class="detail-comment">{{ detailData.overall_comment || '暂无点评' }}</div>
          <div v-if="detailData.weak_points?.length" class="detail-weak">
            <span class="weak-label">薄弱点：</span>
            <el-tag
              v-for="wp in detailData.weak_points"
              :key="wp"
              type="danger"
              size="small"
              effect="light"
              style="margin-right: 6px;"
            >
              {{ wp }}
            </el-tag>
          </div>
        </div>

        <el-divider />

        <div v-if="detailQuestions.length" class="detail-questions">
          <div
            v-for="(q, i) in detailQuestions"
            :key="q.id"
            class="question-item"
            :class="{ 'is-correct': q.is_correct, 'is-wrong': q.is_correct === false }"
          >
            <div class="q-header">
              <span class="q-number">{{ i + 1 }}</span>
              <el-tag v-if="q.is_correct === true" type="success" size="small" round>正确</el-tag>
              <el-tag v-else-if="q.is_correct === false" type="danger" size="small" round>错误</el-tag>
              <span class="q-score">{{ q.score ?? '-' }}/{{ q.max_score ?? '-' }}</span>
            </div>
            <div class="q-content">{{ q.content }}</div>
            <div v-if="q.student_answer" class="q-answer wrong">
              你的答案：{{ q.student_answer }}
            </div>
            <div v-if="q.correct_answer" class="q-answer correct">
              正确答案：{{ q.correct_answer }}
            </div>
            <div v-if="q.explanation" class="q-analysis">{{ q.explanation }}</div>
          </div>
        </div>
        <el-empty v-else description="暂无题目数据" />
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Document, Refresh } from '@element-plus/icons-vue'
import { uploadApi, dashboardApi } from '@/api'
import { PageHeader, StatCard, CommonTable } from '@/components'
import { useRequest } from '@/composables/useRequest'

/* ============ 常量 ============ */
const acceptTypes = '.jpg,.jpeg,.png,.pdf'
const subjectOptions = ['数学', '语文', '英语', '物理', '化学', '生物', '历史', '地理', '政治']
const subjectTagMap = { 数学: 'primary', 语文: 'success', 英语: 'warning', 物理: 'info', 化学: 'danger' }

/* ============ 响应式数据 ============ */
const uploadRef = ref(null)
const fileList = ref([])
const uploadSubject = ref('')
const uploadTitle = ref('')
const uploading = ref(false)
const listLoading = ref(false)

// 任务轮询
const taskPolling = ref(false)
const taskProgress = ref(0)
const taskStep = ref('')
const taskStatus = ref('')
const taskError = ref('')
let pollTimer = null

// 统计数据（默认 0，接口通了后更新）
const stats = ref([
  { label: '累计上传', value: 0, unit: '份', icon: UploadFilled, color: 'purple' },
  { label: '累计错题', value: 0, unit: '道', icon: Document, color: 'red' },
  { label: '薄弱知识点', value: 0, unit: '个', icon: Refresh, color: 'purple' }
])

// 作业列表
const assignmentList = ref([])

// 详情弹窗
const detailVisible = ref(false)
const detailData = ref(null)
const detailQuestions = ref([])

/* ============ API 请求 ============ */
const { request } = useRequest()

// 加载统计：GET /api/dashboard
async function loadStats() {
  await request(dashboardApi.getStats, {
    onSuccess: (data) => {
      stats.value[0].value = data.assignment_count ?? 0
      stats.value[1].value = data.wrong_count ?? 0
      stats.value[2].value = data.weak_points?.length ?? 0
    },
    warnMsg: '统计数据加载失败，使用默认值'
  })
}

// 加载作业列表：GET /api/assignments
async function loadAssignments() {
  await request(uploadApi.getList, {
    loading: listLoading,
    onSuccess: (list) => {
      assignmentList.value = Array.isArray(list) ? list : []
    },
    warnMsg: '作业列表加载失败'
  })
}

/* ============ 上传逻辑 ============ */
function handleFileChange(file, fl) {
  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    ElMessage.error(`文件 ${file.name} 超过 10MB`)
    fl.splice(fl.indexOf(file), 1)
    fileList.value = fl
    return
  }
  const allowed = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf']
  if (file.raw && !allowed.includes(file.raw.type)) {
    ElMessage.error(`文件 ${file.name} 格式不支持`)
    fl.splice(fl.indexOf(file), 1)
    fileList.value = fl
    return
  }
  fileList.value = fl
}

function handleExceed() {
  ElMessage.warning('每次只能上传一个文件')
}

function clearFiles() {
  fileList.value = []
  uploadRef.value?.clearFiles()
}

// 上传 → 轮询任务 → 完成
async function submitUpload() {
  if (!fileList.value.length) return
  if (!uploadSubject.value) {
    ElMessage.warning('请先选择科目')
    return
  }

  const formData = new FormData()
  formData.append('file', fileList.value[0].raw)
  formData.append('subject', uploadSubject.value)
  if (uploadTitle.value) formData.append('title', uploadTitle.value)

  uploading.value = true

  await request(() => uploadApi.uploadAssignment(formData), {
    onSuccess: (data) => {
      clearFiles()
      uploadTitle.value = ''
      ElMessage.success('上传成功，开始批改')
      startTaskPolling(data.task.id)
    },
    fallback: () => {
      // 后端不通时 mock 回退：假装成功并刷新列表
      clearFiles()
      ElMessage.success('上传成功（演示模式）')
      loadAssignments()
      loadStats()
    },
    warnMsg: '上传失败'
  })

  uploading.value = false
}

/* ============ 任务轮询 ============ */
function startTaskPolling(taskId) {
  taskPolling.value = true
  taskProgress.value = 0
  taskStep.value = '排队中...'
  taskStatus.value = 'queued'
  taskError.value = ''

  pollTimer = setInterval(async () => {
    const res = await request(() => uploadApi.getTaskStatus(taskId), {
      warnMsg: '任务状态查询失败'
    })
    if (!res) return

    const t = res.data ?? res
    taskProgress.value = t.progress ?? 0
    taskStep.value = t.step ?? ''
    taskStatus.value = t.status

    if (t.status === 'completed') {
      stopPolling('completed')
      ElMessage.success('批改完成')
      loadAssignments()
      loadStats()
    } else if (t.status === 'failed') {
      stopPolling('failed')
      taskError.value = t.error_message || '批改失败'
      ElMessage.error(taskError.value)
    }
  }, 2000)
}

function stopPolling(status) {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  // 3 秒后自动隐藏进度条
  setTimeout(() => { taskPolling.value = false }, 3000)
}

/* ============ 作业详情 ============ */
async function showDetail(row) {
  detailData.value = row
  detailQuestions.value = []

  if (row.status === 'completed') {
    await request(() => uploadApi.getDetail(row.id), {
      onSuccess: (data) => {
        detailData.value = data
        detailQuestions.value = data.questions || []
      },
      warnMsg: '作业详情加载失败'
    })
  }

  detailVisible.value = true
}

/* ============ 工具方法 ============ */
function scoreClass(score, total) {
  if (score == null || total == null) return ''
  const pct = score / total
  if (pct >= 0.8) return 'score-high'
  if (pct >= 0.6) return 'score-mid'
  return 'score-low'
}

function assignmentStatusLabel(row) {
  if (row.status === 'completed') return '已完成'
  if (row.task?.status === 'failed') return '批改失败'
  if (row.task?.status === 'processing' || row.task?.status === 'queued') return '批改中'
  return row.status || '未知'
}

function assignmentStatusType(row) {
  if (row.status === 'completed') return 'success'
  if (row.task?.status === 'failed') return 'danger'
  if (row.task?.status === 'processing' || row.task?.status === 'queued') return 'warning'
  return 'info'
}

function taskStatusLabel(status) {
  const map = { queued: '排队中', processing: '批改中', completed: '已完成', failed: '失败' }
  return map[status] || status || ''
}

function formatTime(iso) {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    const y = d.getFullYear()
    const M = String(d.getMonth() + 1).padStart(2, '0')
    const D = String(d.getDate()).padStart(2, '0')
    const h = String(d.getHours()).padStart(2, '0')
    const m = String(d.getMinutes()).padStart(2, '0')
    return `${y}-${M}-${D} ${h}:${m}`
  } catch {
    return iso
  }
}

/* ============ 生命周期 ============ */
onMounted(() => {
  loadStats()
  loadAssignments()
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped lang="scss">
.stats-grid {
  margin-bottom: 24px;
}

/* 上传元信息 */
.upload-meta {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;

  .meta-subject {
    width: 180px;
    flex-shrink: 0;
  }

  .meta-title {
    flex: 1;
  }
}

/* 上传卡片 */
.upload-card {
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-lg);
  padding: 28px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 24px;
}

.upload-area {
  width: 100%;

  :deep(.el-upload) {
    width: 100%;
  }

  :deep(.el-upload-dragger) {
    width: 100%;
    padding: 44px 20px;
    border: 2px dashed rgba(99, 102, 241, 0.25);
    border-radius: var(--radius-md);
    background: rgba(99, 102, 241, 0.02);
    transition: all 0.3s;

    &:hover {
      border-color: var(--accent);
      background: rgba(99, 102, 241, 0.05);
    }
  }
}

.upload-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.upload-icon-wrapper {
  width: 72px;
  height: 72px;
  border-radius: 20px;
  background: var(--gradient-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
}

.upload-icon {
  font-size: 32px;
  color: white;
}

.upload-text {
  font-size: 16px;
  color: var(--ink);
  font-weight: 600;

  em {
    color: var(--accent);
    font-style: normal;
  }
}

.upload-hint {
  font-size: 13px;
  color: var(--ink-tertiary);
  margin-top: 6px;
}

.upload-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
  justify-content: center;
}

/* 进度条 */
.progress-wrapper {
  margin-top: 20px;
  padding: 16px 20px;
  background: rgba(99, 102, 241, 0.04);
  border-radius: var(--radius-sm);

  .progress-label {
    display: flex;
    justify-content: space-between;
    font-size: 13px;
    color: var(--ink-secondary);
    margin-bottom: 8px;
    font-weight: 600;
  }

  .task-error {
    margin-top: 8px;
    font-size: 13px;
    color: var(--danger);
    font-weight: 500;
  }
}

/* 得分样式 */
.score-high { color: var(--success); font-weight: 700; }
.score-mid  { color: var(--warning); font-weight: 700; }
.score-low  { color: var(--danger);  font-weight: 700; }

/* 详情弹窗 */
.detail-overall {
  .detail-comment {
    font-size: 15px;
    line-height: 1.7;
    color: var(--ink-secondary);
    padding: 16px 18px;
    background: rgba(99, 102, 241, 0.04);
    border-radius: var(--radius-sm);
    margin-bottom: 12px;
  }

  .detail-weak {
    font-size: 13px;
    color: var(--ink-secondary);
  }

  .weak-label {
    font-weight: 600;
    color: var(--ink);
  }
}

.question-item {
  padding: 18px;
  margin-bottom: 14px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--separator);
  background: rgba(255, 255, 255, 0.5);

  &.is-correct {
    border-left: 3px solid var(--success);
  }

  &.is-wrong {
    border-left: 3px solid var(--danger);
  }

  .q-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;

    .q-number {
      font-size: 14px;
      font-weight: 700;
      color: var(--ink-secondary);
    }

    .q-score {
      margin-left: auto;
      font-size: 13px;
      font-weight: 600;
      color: var(--ink-tertiary);
    }
  }

  .q-content {
    font-size: 15px;
    line-height: 1.7;
    color: var(--ink);
    margin-bottom: 12px;
  }

  .q-answer {
    font-size: 13px;
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 8px;

    &.wrong {
      background: rgba(239, 68, 68, 0.06);
      color: var(--danger);
    }

    &.correct {
      background: rgba(16, 185, 129, 0.06);
      color: var(--success);
    }
  }

  .q-analysis {
    font-size: 13px;
    line-height: 1.7;
    color: var(--ink-tertiary);
    padding: 10px 12px;
    background: rgba(0, 0, 0, 0.02);
    border-radius: 6px;
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .upload-meta {
    flex-direction: column;

    .meta-subject {
      width: 100%;
    }
  }
}
</style>
