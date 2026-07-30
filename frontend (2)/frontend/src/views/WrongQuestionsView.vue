<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { wrongQuestionApi } from '../api'

const router = useRouter()
const wrongQuestions = ref([])
const selectedSubject = ref('')
const loading = ref(false)
const error = ref('')
let loadSequence = 0

const defaultSubjects = ['数学', '语文', '英语', '物理', '化学']
const subjects = computed(() => {
  const values = new Set(defaultSubjects)
  wrongQuestions.value.forEach((item) => {
    if (item.subject) values.add(item.subject)
  })
  return [...values]
})

const hasQuestions = computed(() => wrongQuestions.value.length > 0)

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

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="stack-lg wrong-questions-view">
    <section class="page-intro">
      <div>
        <p class="page-context">错题归档</p>
        <h2>把做错的题，变成下一次掌握</h2>
        <p class="muted">按学科筛选薄弱点，回看原题、答案和错因。Agent 的低置信度判断会明确标注，最终请以你的推导为准。</p>
      </div>
      <div style="display: flex; gap: 12px;">
        <el-button type="default" plain @click="router.push('/chat')">
          <el-icon><Back /></el-icon>
          返回对话
        </el-button>
      </div>
    </section>

    <section class="panel filter-panel" aria-label="错题筛选">
      <div class="filter-heading">
        <div class="filter-title">
          <el-icon><Filter /></el-icon>
          <strong>筛选错题</strong>
        </div>
        <span class="muted">{{ selectedSubject || '全部学科' }} · {{ wrongQuestions.length }} 道</span>
      </div>
      <div class="filter-controls">
        <label class="filter-label" for="wrong-subject">学科</label>
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
        <el-button class="refresh-button" plain :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </section>

    <el-alert v-if="error" type="error" show-icon :closable="false" role="alert">
      <template #title>{{ error }}</template>
      <el-button class="alert-action" type="danger" plain size="small" @click="load">重试</el-button>
    </el-alert>

    <section v-loading="loading" class="wrong-question-list" aria-live="polite">
      <article v-for="item in wrongQuestions" :key="item.id" class="wrong-question-card">
        <header class="wrong-question-header">
          <div class="question-index">{{ item.question?.question_number || '—' }}</div>
          <div class="question-heading">
            <div class="tag-row">
              <el-tag type="primary" effect="light">{{ item.subject || '未分类' }}</el-tag>
              <el-tag v-if="item.knowledge_point" type="warning" effect="plain">{{ item.knowledge_point }}</el-tag>
              <span class="wrong-count">错 {{ item.wrong_count || 0 }} 次</span>
            </div>
            <h3>第 {{ item.question?.question_number || '—' }} 题</h3>
          </div>
          <el-button class="practice-button" type="primary" plain @click="startPractice(item)">
            <el-icon><Reading /></el-icon>
            针对练习
          </el-button>
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
          <div class="confidence-copy">
            <span v-if="confidenceText(item.question?.confidence ?? null)" class="muted">{{ confidenceText(item.question?.confidence ?? null) }}</span>
            <el-alert v-if="confidenceWarning(item)" type="warning" :title="confidenceWarning(item)" :closable="false" show-icon />
          </div>
        </footer>
      </article>

      <el-empty v-if="!loading && !hasQuestions" description="暂无符合条件的错题" :image-size="76">
        <el-button v-if="selectedSubject" type="primary" plain @click="filterBySubject('')">查看全部错题</el-button>
        <el-button v-else type="primary" @click="router.push('/chat')">返回对话</el-button>
      </el-empty>
    </section>
  </div>
</template>

<style scoped>
.wrong-questions-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

.page-intro {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding: 24px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.page-intro h2 {
  margin: 8px 0;
  font-size: 28px;
  font-weight: 600;
}

.page-context {
  font-size: 14px;
  opacity: 0.9;
  margin: 0;
}

.muted {
  opacity: 0.8;
  font-size: 14px;
}

.panel {
  background: white;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.filter-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.filter-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
}

.filter-controls {
  display: flex;
  gap: 12px;
  align-items: center;
}

.filter-label {
  font-weight: 500;
  color: #606266;
}

.subject-select {
  width: 200px;
}

.wrong-question-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wrong-question-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.3s;
}

.wrong-question-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.wrong-question-header {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
  align-items: flex-start;
}

.question-index {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 8px;
  font-weight: 600;
  font-size: 18px;
}

.question-heading {
  flex: 1;
}

.tag-row {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.wrong-count {
  font-size: 12px;
  color: #909399;
}

.question-heading h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.question-content {
  margin-bottom: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 6px;
}

.question-content p {
  margin: 0;
  line-height: 1.6;
}

.answer-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.answer-block {
  padding: 12px;
  border-radius: 6px;
}

.student-answer {
  background: #fef0f0;
  border-left: 3px solid #f56c6c;
}

.reference-answer {
  background: #f0f9eb;
  border-left: 3px solid #67c23a;
}

.answer-label {
  display: block;
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 8px;
  color: #606266;
}

.answer-block p {
  margin: 0;
  line-height: 1.6;
}

.wrong-question-footer {
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.wrong-reason {
  margin-bottom: 12px;
}

.confidence-copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 768px) {
  .answer-grid {
    grid-template-columns: 1fr;
  }

  .page-intro {
    flex-direction: column;
    gap: 16px;
  }
}
</style>
