<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { BookOpenCheck, RefreshCw, SlidersHorizontal, Sparkles } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { api, errorMessage, request } from '../api'
import type { WrongQuestion } from '../types'

const router = useRouter()
const wrongQuestions = ref<WrongQuestion[]>([])
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

function questionText(item: WrongQuestion) {
  return item.question?.content?.trim() || '题目内容暂未识别'
}

function confidenceText(confidence: number | null) {
  if (confidence === null || !Number.isFinite(confidence)) return ''
  const normalized = confidence <= 1 ? confidence * 100 : confidence
  return `判定置信度 ${Math.round(Math.max(0, Math.min(100, normalized)))}%`
}

function confidenceWarning(item: WrongQuestion) {
  return item.question?.confidence_warning || (item.question?.needs_review ? '这道题的判定置信度偏低，请结合自己的推导和参考答案自行判断。' : '')
}

function answerText(value: string | null | undefined, fallback: string) {
  return value?.trim() || fallback
}

async function load() {
  const sequence = ++loadSequence
  loading.value = true
  error.value = ''
  try {
    const params = selectedSubject.value ? { subject: selectedSubject.value } : undefined
    const data = await request<WrongQuestion[]>(api.get('/wrong-questions', { params }))
    if (sequence === loadSequence) wrongQuestions.value = Array.isArray(data) ? data : []
  } catch (loadError) {
    if (sequence === loadSequence) {
      error.value = errorMessage(loadError, '错题加载失败，请稍后重试')
      wrongQuestions.value = []
    }
  } finally {
    if (sequence === loadSequence) loading.value = false
  }
}

function filterBySubject(subject: string) {
  selectedSubject.value = subject
  void load()
}

function startPractice(item: WrongQuestion) {
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
      <RouterLink class="action-link" to="/practice"><Sparkles :size="17" /> 开始针对练习</RouterLink>
    </section>

    <section class="panel filter-panel" aria-label="错题筛选">
      <div class="filter-heading">
        <div class="filter-title"><SlidersHorizontal :size="18" /><strong>筛选错题</strong></div>
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
        <el-button class="refresh-button" plain :icon="RefreshCw" :loading="loading" @click="load">刷新</el-button>
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
          <el-button class="practice-button" type="primary" plain :icon="BookOpenCheck" @click="startPractice(item)">针对练习</el-button>
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
        <el-button v-else type="primary" @click="router.push('/assignments')">先去提交作业</el-button>
      </el-empty>
    </section>
  </div>
</template>
