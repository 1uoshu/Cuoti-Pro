<template>
  <div class="wrong-questions-page">
    <div class="page-header">
      <h2>错题本</h2>
      <router-link to="/chat" class="back-link">
        ← 返回对话
      </router-link>
    </div>

    <div class="filters" v-if="!loading">
      <el-select v-model="subjectFilter" placeholder="全部学科" clearable @change="loadList" style="width: 140px">
        <el-option v-for="s in subjects" :key="s" :label="s" :value="s" />
      </el-select>
      <el-button @click="loadList" :loading="loading" size="small">刷新</el-button>
      <span class="count-hint">共 {{ list.length }} 道错题</span>
    </div>

    <el-table :data="list" v-loading="loading" stripe empty-text="暂无错题">
      <el-table-column prop="question.question_number" label="题号" width="80" />
      <el-table-column prop="question.content" label="题目内容" min-width="250" show-overflow-tooltip />
      <el-table-column prop="subject" label="学科" width="80" />
      <el-table-column prop="knowledge_point" label="知识点" width="140" />
      <el-table-column prop="wrong_reason" label="错因" width="180" show-overflow-tooltip />
      <el-table-column prop="wrong_count" label="错误次数" width="90" align="center" />
      <el-table-column prop="status" label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" align="center">
        <template #default="{ row }">
          <el-button size="small" type="primary" link @click="showDetail(row)">详情</el-button>
          <el-button
            v-if="row.status === 'active'"
            size="small"
            type="success"
            link
            @click="markReviewed(row)"
          >
            标记已复习
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="错题详情" width="640px">
      <template v-if="currentItem">
        <div class="detail-section">
          <h4>题目</h4>
          <p class="detail-text">{{ currentItem.question?.content }}</p>
        </div>
        <div class="detail-section">
          <h4>你的答案</h4>
          <p class="detail-text">{{ currentItem.question?.student_answer || '（无）' }}</p>
        </div>
        <div class="detail-section">
          <h4>正确答案</h4>
          <p class="detail-text">{{ currentItem.question?.correct_answer }}</p>
        </div>
        <div class="detail-section">
          <h4>解析</h4>
          <p class="detail-text">{{ currentItem.question?.explanation || '无' }}</p>
        </div>
        <div class="detail-section">
          <h4>判定置信度</h4>
          <p>{{ currentItem.question?.confidence ? (currentItem.question.confidence * 100).toFixed(0) + '%' : '未知' }}</p>
        </div>
        <div class="detail-section">
          <h4>归档时间</h4>
          <p>{{ currentItem.created_at || '未知' }}</p>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { wrongQuestionApi } from '@/api'

const list = ref([])
const loading = ref(false)
const subjectFilter = ref('')
const subjects = ref([])

const detailVisible = ref(false)
const currentItem = ref(null)

async function loadList() {
  loading.value = true
  try {
    const params = subjectFilter.value ? { subject: subjectFilter.value } : {}
    const res = await wrongQuestionApi.getList(params)
    const items = res.data || []
    list.value = Array.isArray(items) ? items : (items.items || [])
    subjects.value = [...new Set(list.value.map(i => i.subject).filter(Boolean))]
  } catch (e) {
    ElMessage.error('加载错题失败')
  } finally {
    loading.value = false
  }
}

async function showDetail(row) {
  try {
    const res = await wrongQuestionApi.getQuestion(row.id)
    currentItem.value = res.data
    detailVisible.value = true
  } catch (e) {
    ElMessage.error('加载详情失败')
  }
}

async function markReviewed(row) {
  try {
    await wrongQuestionApi.updateStatus(row.id, 'reviewed')
    ElMessage.success('已标记为已复习')
    loadList()
  } catch (e) {
    ElMessage.error('操作失败')
  }
}

function statusType(status) {
  return status === 'active' ? 'danger' : status === 'reviewed' ? 'warning' : 'info'
}

function statusLabel(status) {
  return status === 'active' ? '未复习' : status === 'reviewed' ? '已复习' : '已归档'
}

onMounted(loadList)
</script>

<style scoped>
.wrong-questions-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header h2 { margin: 0; }
.back-link { color: var(--el-color-primary); text-decoration: none; }
.filters {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.count-hint { color: #909399; font-size: 13px; }
.detail-section { margin-bottom: 12px; }
.detail-section h4 { margin: 0 0 4px; color: #606266; }
.detail-text { white-space: pre-wrap; color: #303133; line-height: 1.6; }
</style>
