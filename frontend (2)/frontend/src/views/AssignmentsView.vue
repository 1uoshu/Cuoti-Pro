<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type UploadFile, type UploadInstance } from 'element-plus'
import { FileImage, UploadCloud } from 'lucide-vue-next'
import { api, errorMessage, request } from '../api'
import type { Assignment, Task } from '../types'

const router = useRouter()
const assignments = ref<Assignment[]>([])
const loading = ref(false)
const uploading = ref(false)
const uploadOpen = ref(false)
const file = ref<File | null>(null)
const form = ref({ subject: '数学', title: '' })
const uploadRef = ref<UploadInstance>()
const polling = new Map<string, number>()

const processingCount = computed(() => assignments.value.filter((item) => ['queued', 'processing'].includes(item.status)).length)

async function load() {
  loading.value = true
  try {
    assignments.value = await request<Assignment[]>(api.get('/assignments'))
    assignments.value.forEach((item) => {
      if (item.task && ['queued', 'processing'].includes(item.task.status)) watchTask(item.id, item.task.id)
    })
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

function watchTask(assignmentId: number, taskId: string) {
  if (polling.has(taskId)) return
  const timer = window.setInterval(async () => {
    try {
      const task = await request<Task>(api.get(`/tasks/${taskId}`))
      const assignment = assignments.value.find((item) => item.id === assignmentId)
      if (assignment) {
        assignment.task = task
        assignment.status = task.status
      }
      if (['completed', 'failed'].includes(task.status)) {
        window.clearInterval(timer)
        polling.delete(taskId)
        await load()
      }
    } catch (error) {
      window.clearInterval(timer)
      polling.delete(taskId)
      ElMessage.error(errorMessage(error, '无法获取批改进度'))
    }
  }, 2000)
  polling.set(taskId, timer)
}

function validateFile(candidate: File) {
  const extension = candidate.name.split('.').pop()?.toLowerCase()
  if (!extension || !['jpg', 'jpeg', 'png', 'pdf'].includes(extension)) {
    ElMessage.error('只支持 JPG、JPEG、PNG 和 PDF 文件')
    return false
  }
  if (candidate.size > 10 * 1024 * 1024) {
    ElMessage.error('文件不能超过 10MB')
    return false
  }
  return true
}

function onFileChange(uploadFile: UploadFile) {
  const candidate = uploadFile.raw
  if (!candidate || !validateFile(candidate)) {
    file.value = null
    uploadRef.value?.clearFiles()
    return
  }
  file.value = candidate
}

function clearSelectedFile() {
  file.value = null
}

async function submitUpload() {
  if (!file.value) {
    ElMessage.warning('请选择作业文件')
    return
  }
  if (!validateFile(file.value)) return
  uploading.value = true
  try {
    const data = new FormData()
    data.append('file', file.value)
    data.append('subject', form.value.subject)
    if (form.value.title) data.append('title', form.value.title)
    const result = await request<{ assignment_id: number; task: Task }>(api.post('/assignments', data))
    ElMessage.success('作业已提交，正在开始批改')
    uploadOpen.value = false
    file.value = null
    uploadRef.value?.clearFiles()
    form.value.title = ''
    await load()
    watchTask(result.assignment_id, result.task.id)
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    uploading.value = false
  }
}

function statusLabel(status: Assignment['status']) {
  return { queued: '等待处理', processing: '批改中', completed: '已完成', failed: '批改失败' }[status]
}

onMounted(load)
onBeforeUnmount(() => polling.forEach((timer) => window.clearInterval(timer)))
</script>

<template>
  <div class="stack-lg">
    <section class="upload-banner">
      <div><p class="page-context">作业批改</p><h2>上传一份作业，开始定位问题</h2><p>支持手写或打印的 JPG、PNG、PDF，系统将异步识别并给出每题批改结果。</p></div>
      <el-button type="primary" :icon="UploadCloud" @click="uploadOpen = true">上传作业</el-button>
    </section>

    <section class="panel">
      <div class="panel-heading"><div><p class="page-context">作业记录</p><h3>全部提交</h3></div><el-tag v-if="processingCount" type="warning" effect="plain">{{ processingCount }} 份处理中</el-tag></div>
      <div class="desktop-record-table"><el-table v-loading="loading" :data="assignments" empty-text="还没有作业记录">
        <el-table-column label="作业" min-width="250">
          <template #default="{ row }"><button class="table-title" @click="router.push(`/assignments/${row.id}`)"><span class="file-tile">{{ row.subject.slice(0, 1) }}</span><span><strong>{{ row.title }}</strong><small>{{ row.subject }} · {{ new Date(row.created_at).toLocaleString('zh-CN') }}</small></span></button></template>
        </el-table-column>
        <el-table-column label="批改状态" min-width="220">
          <template #default="{ row }"><div v-if="row.task && ['queued','processing'].includes(row.status)" class="task-progress"><el-progress :percentage="row.task.progress" :stroke-width="7" :show-text="false" /><small>{{ row.task.step }} {{ row.task.progress }}%</small></div><el-tag v-else :type="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'danger' : 'info'" effect="plain">{{ statusLabel(row.status) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="得分" width="120"><template #default="{ row }">{{ row.student_score === null ? '—' : `${row.student_score}/${row.total_score}` }}</template></el-table-column>
        <el-table-column label="操作" width="100"><template #default="{ row }"><el-button text type="primary" @click="router.push(`/assignments/${row.id}`)">查看</el-button></template></el-table-column>
      </el-table></div>
      <div v-loading="loading" class="mobile-record-list">
        <button v-for="assignment in assignments" :key="assignment.id" class="assignment-mobile-row" @click="router.push(`/assignments/${assignment.id}`)">
          <span class="file-tile">{{ assignment.subject.slice(0, 1) }}</span>
          <span class="assignment-copy"><strong>{{ assignment.title }}</strong><small>{{ assignment.subject }} · {{ new Date(assignment.created_at).toLocaleDateString('zh-CN') }}</small></span>
          <span class="mobile-record-status"><el-tag :type="assignment.status === 'completed' ? 'success' : assignment.status === 'failed' ? 'danger' : 'warning'" effect="plain">{{ statusLabel(assignment.status) }}</el-tag><small>{{ assignment.student_score === null ? '—' : `${assignment.student_score}/${assignment.total_score}` }}</small></span>
        </button>
        <el-empty v-if="!loading && !assignments.length" description="还没有作业记录" :image-size="60" />
      </div>
    </section>

    <el-dialog v-model="uploadOpen" title="上传作业" width="min(520px, calc(100vw - 32px))" :close-on-click-modal="!uploading">
      <el-form label-position="top">
        <el-form-item label="学科"><el-select v-model="form.subject" class="full-width"><el-option label="数学" value="数学" /><el-option label="语文" value="语文" /><el-option label="英语" value="英语" /><el-option label="物理" value="物理" /><el-option label="化学" value="化学" /></el-select></el-form-item>
        <el-form-item label="作业名称（可选）"><el-input v-model="form.title" maxlength="128" placeholder="默认使用文件名" /></el-form-item>
        <el-form-item label="作业文件"><el-upload ref="uploadRef" drag :auto-upload="false" :show-file-list="true" :limit="1" accept=".jpg,.jpeg,.png,.pdf" :on-change="onFileChange" :on-remove="clearSelectedFile"><FileImage :size="30" /><div class="el-upload__text">拖入文件，或 <em>点击选择</em></div><template #tip><div class="el-upload__tip">JPG、PNG 或 PDF，最大 10MB，PDF 最多 10 页</div></template></el-upload></el-form-item>
      </el-form>
      <template #footer><el-button @click="uploadOpen = false">取消</el-button><el-button type="primary" :loading="uploading" @click="submitUpload">提交并批改</el-button></template>
    </el-dialog>
  </div>
</template>
