<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  AlertCircle,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  ClipboardCheck,
  RefreshCw,
  Send,
  Sparkles,
} from 'lucide-vue-next'
import { api, errorMessage, request } from '../api'
import type { PracticeQuestion, PracticeTask, WrongQuestion } from '../types'

type PracticeMode = 'setup' | 'answering' | 'results'

const subjects = ['数学', '物理', '化学', '语文', '英语']
const difficulties: Array<{ value: PracticeTask['difficulty']; label: string; description: string }> = [
  { value: '基础补漏', label: '基础补漏', description: '先把核心概念和基础方法练扎实' },
  { value: '同类变式', label: '同类变式', description: '在相近题型中迁移解题方法' },
  { value: '综合提升', label: '综合提升', description: '组合多个知识点，训练综合推理' },
  { value: '高考真题', label: '高考真题', description: '用真题强度检验掌握程度' },
]

const mode = ref<PracticeMode>('setup')
const loadingWeakPoints = ref(false)
const generating = ref(false)
const submitting = ref(false)
const error = ref('')
const weakPointError = ref('')
const weakQuestions = ref<WrongQuestion[]>([])
const task = ref<PracticeTask | null>(null)
const answerDrafts = ref<Record<string, string>>({})

const form = ref({
  subject: '数学',
  knowledge_point: '',
  difficulty: '基础补漏' as PracticeTask['difficulty'],
  question_count: 5,
})

const knowledgePointOptions = computed(() => {
  const values = new Set<string>()
  weakQuestions.value
    .filter((item) => item.subject === form.value.subject)
    .forEach((item) => {
      if (item.knowledge_point) values.add(item.knowledge_point)
    })
  if (form.value.knowledge_point) values.add(form.value.knowledge_point)
  return Array.from(values)
})

const questions = computed(() => task.value?.questions || [])
const answeredCount = computed(() => questions.value.filter((question) => Boolean(answerDrafts.value[String(question.id)]?.trim())).length)
const allAnswered = computed(() => questions.value.length > 0 && answeredCount.value === questions.value.length)
const scoreLabel = computed(() => {
  if (task.value?.student_score === null || task.value?.student_score === undefined) return '待评分'
  return `${task.value.student_score}分`
})

function questionAnswer(question: PracticeQuestion) {
  return question.answers?.[question.answers.length - 1] || null
}

function confidencePercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return ''
  return `${Math.round(value * 100)}%`
}

function setTask(nextTask: PracticeTask) {
  task.value = nextTask
  answerDrafts.value = {}
  nextTask.questions.forEach((question) => {
    const previousAnswer = questionAnswer(question)?.answer
    if (previousAnswer) answerDrafts.value[String(question.id)] = previousAnswer
  })
  mode.value = nextTask.status === 'completed' ? 'results' : 'answering'
}

async function loadWeakPoints() {
  loadingWeakPoints.value = true
  weakPointError.value = ''
  try {
    weakQuestions.value = await request<WrongQuestion[]>(api.get('/wrong-questions'))
  } catch (loadError) {
    // The free-text knowledge-point field keeps practice usable when the archive is unavailable.
    weakPointError.value = errorMessage(loadError, '暂时无法加载历史薄弱点，可直接输入知识点')
  } finally {
    loadingWeakPoints.value = false
  }
}

function validateForm() {
  if (!form.value.subject.trim()) {
    error.value = '请选择学科'
    return false
  }
  form.value.knowledge_point = form.value.knowledge_point.trim()
  if (!form.value.knowledge_point) {
    error.value = '请输入或选择一个知识点'
    return false
  }
  const questionCount = Number(form.value.question_count)
  if (!Number.isInteger(questionCount) || questionCount < 1 || questionCount > 10) {
    error.value = '题目数量需在 1 到 10 之间'
    return false
  }
  form.value.question_count = questionCount
  return true
}

async function generatePractice() {
  error.value = ''
  if (!validateForm()) return
  generating.value = true
  try {
    const result = await request<PracticeTask>(
      api.post(
        '/practices',
        {
          subject: form.value.subject,
          knowledge_point: form.value.knowledge_point,
          difficulty: form.value.difficulty,
          question_count: form.value.question_count,
        },
        { timeout: 300_000 },
      ),
    )
    if (result.status === 'failed') {
      throw new Error('练习题生成失败，请稍后重试')
    }
    setTask(result)
    ElMessage.success('练习题已准备好，开始作答吧')
  } catch (generateError) {
    error.value = errorMessage(generateError, '练习题生成失败，请稍后重试')
  } finally {
    generating.value = false
  }
}

function leavePractice() {
  if (submitting.value || generating.value) return
  mode.value = 'setup'
  task.value = null
  answerDrafts.value = {}
  error.value = ''
}

async function submitPractice() {
  if (!task.value || submitting.value) return
  error.value = ''
  if (!allAnswered.value) {
    error.value = '请完成每一道题后再提交'
    ElMessage.warning(error.value)
    return
  }

  submitting.value = true
  try {
    const payload = {
      answers: task.value.questions.map((question) => ({
        question_id: question.id,
        answer: answerDrafts.value[String(question.id)].trim(),
      })),
    }
    const result = await request<PracticeTask>(
      api.post(`/practices/${task.value.id}/submit`, payload, { timeout: 300_000 }),
    )
    setTask(result)
    mode.value = 'results'
    ElMessage.success('提交完成，下面是本次练习反馈')
  } catch (submitError) {
    error.value = errorMessage(submitError, '提交失败，请检查网络后重试')
  } finally {
    submitting.value = false
  }
}

onMounted(loadWeakPoints)
</script>

<template>
  <div class="stack-lg practice-view">
    <section class="practice-intro">
      <div>
        <p class="page-context">针对练习</p>
        <h2>把薄弱点练成掌握项</h2>
        <p>选择一个知识点，生成一组有梯度的题目。每次提交后，系统会给出判题解析和置信度提示。</p>
      </div>
      <span class="practice-intro-mark" aria-hidden="true"><Sparkles :size="26" /></span>
    </section>

    <el-alert v-if="error" type="error" :title="error" show-icon :closable="false" />

    <template v-if="mode === 'setup'">
      <section class="practice-layout">
        <div class="panel practice-form-panel">
          <div class="panel-heading">
            <div>
              <p class="page-context">开始一组新练习</p>
              <h3>配置练习内容</h3>
            </div>
            <ClipboardCheck :size="22" aria-hidden="true" />
          </div>

          <el-form label-position="top" @submit.prevent="generatePractice">
            <el-form-item label="学科" required>
              <el-select v-model="form.subject" class="full-width" aria-label="选择学科">
                <el-option v-for="subject in subjects" :key="subject" :label="subject" :value="subject" />
              </el-select>
            </el-form-item>

            <el-form-item label="知识点" required>
              <el-select
                v-model="form.knowledge_point"
                class="full-width"
                filterable
                allow-create
                default-first-option
                :reserve-keyword="false"
                :loading="loadingWeakPoints"
                aria-label="选择或输入知识点"
                placeholder="例如：导数单调性"
              >
                <el-option
                  v-for="point in knowledgePointOptions"
                  :key="point"
                  :label="point"
                  :value="point"
                />
              </el-select>
              <p class="form-helper">
                {{ weakPointError || (knowledgePointOptions.length ? '已从错题本列出你的薄弱点，也可以直接输入。' : '可以直接输入想练习的知识点。') }}
              </p>
            </el-form-item>

            <el-form-item label="练习难度" required>
              <el-radio-group v-model="form.difficulty" class="difficulty-options" aria-label="选择练习难度">
                <el-radio-button v-for="item in difficulties" :key="item.value" :value="item.value">
                  {{ item.label }}
                </el-radio-button>
              </el-radio-group>
              <p class="form-helper">{{ difficulties.find((item) => item.value === form.difficulty)?.description }}</p>
            </el-form-item>

            <el-form-item label="题目数量" required>
              <el-input-number v-model="form.question_count" :min="1" :max="10" :step="1" controls-position="right" aria-label="题目数量" />
              <p class="form-helper">每组 1–10 题，提交时需要一次完成全部题目。</p>
            </el-form-item>

            <el-button type="primary" size="large" class="practice-primary-action" :loading="generating" :icon="Sparkles" native-type="submit">
              {{ generating ? '正在生成题目…' : '生成练习题' }}
            </el-button>
          </el-form>
        </div>

        <aside class="panel practice-info-panel" aria-label="练习说明">
          <div class="practice-info-icon"><BookOpen :size="22" aria-hidden="true" /></div>
          <h3>一次练习，闭环巩固</h3>
          <ul class="practice-checklist">
            <li><CheckCircle2 :size="17" aria-hidden="true" /><span>题目按照难度逐层推进</span></li>
            <li><CheckCircle2 :size="17" aria-hidden="true" /><span>答案提交后统一判题，不打断思路</span></li>
            <li><CheckCircle2 :size="17" aria-hidden="true" /><span>低置信度结果会明确提醒你复核</span></li>
          </ul>
          <p class="muted">涉及数学、物理等强逻辑题目时，请结合解析判断。置信度提示仅作参考，不代表人工复核。</p>
        </aside>
      </section>
    </template>

    <template v-else-if="task && mode === 'answering'">
      <section class="panel practice-progress-panel">
        <button class="back-link" type="button" :disabled="submitting" @click="leavePractice"><ArrowLeft :size="16" /> 返回配置</button>
        <div class="practice-progress-copy">
          <div>
            <p class="page-context">{{ task.subject }} · {{ task.difficulty }}</p>
            <h3>{{ task.knowledge_point }}</h3>
            <p>先独立完成，再一次提交。你可以随时修改答案。</p>
          </div>
          <div class="practice-progress-count" aria-live="polite"><strong>{{ answeredCount }}</strong><span>/ {{ questions.length }} 已完成</span></div>
        </div>
        <el-progress :percentage="questions.length ? Math.round((answeredCount / questions.length) * 100) : 0" :show-text="false" :stroke-width="8" color="var(--color-primary)" />
      </section>

      <section class="question-stack practice-question-stack" aria-label="练习题目">
        <el-empty v-if="!questions.length" description="暂时没有可作答的题目，请重新生成" :image-size="76">
          <el-button type="primary" :icon="RefreshCw" @click="leavePractice">重新配置</el-button>
        </el-empty>
        <article v-for="question in questions" :key="question.id" class="question-card practice-question-card">
          <header class="question-card-header">
            <div class="question-number">{{ question.question_number }}</div>
            <div class="question-heading-copy"><span class="question-meta">第 {{ question.question_number }} 题</span><h3>{{ question.content }}</h3></div>
          </header>
          <el-alert v-if="question.confidence_warning" type="warning" :title="question.confidence_warning" show-icon :closable="false" />
          <el-form-item :label="`第 ${question.question_number} 题答案`" class="practice-answer-field" required>
            <el-input
              v-model="answerDrafts[String(question.id)]"
              type="textarea"
              :rows="4"
              maxlength="5000"
              show-word-limit
              :aria-label="`第 ${question.question_number} 题答案`"
              placeholder="写下你的解题过程或最终答案"
            />
          </el-form-item>
          <small v-if="question.confidence !== null && question.confidence !== undefined" class="confidence-note">出题置信度 {{ confidencePercent(question.confidence) }}</small>
        </article>
      </section>

      <div class="practice-submit-bar">
        <span>{{ allAnswered ? '已完成全部题目，可以提交。' : `还差 ${questions.length - answeredCount} 题未完成` }}</span>
        <el-button type="primary" size="large" :loading="submitting" :disabled="!allAnswered" :icon="Send" @click="submitPractice">一次提交并查看结果</el-button>
      </div>
    </template>

    <template v-else-if="task && mode === 'results'">
      <section class="practice-result-hero">
        <div>
          <p class="page-context">练习完成</p>
          <h2>{{ task.knowledge_point }}</h2>
          <p>{{ task.subject }} · {{ task.difficulty }} · 共 {{ questions.length }} 题</p>
        </div>
        <div class="practice-score" aria-label="本次练习得分"><strong>{{ scoreLabel }}</strong><span>本次得分</span></div>
      </section>

      <el-alert type="info" title="判题结果用于帮助你定位思路，不替代自主判断。看到置信度偏低提示时，请优先结合题目和解析复核。" show-icon :closable="false" />

      <section class="question-stack practice-question-stack" aria-label="练习结果">
        <el-empty v-if="!questions.length" description="本次练习没有返回题目" :image-size="76" />
        <article
          v-for="question in questions"
          :key="question.id"
          class="question-card practice-question-card"
          :class="{ correct: questionAnswer(question)?.is_correct, incorrect: questionAnswer(question) && !questionAnswer(question)?.is_correct }"
        >
          <header class="question-card-header">
            <div class="question-number">{{ question.question_number }}</div>
            <div class="question-heading-copy"><span class="question-meta">第 {{ question.question_number }} 题</span><h3>{{ question.content }}</h3></div>
            <div class="question-result" aria-live="polite">
              <component :is="questionAnswer(question)?.is_correct ? CheckCircle2 : AlertCircle" :size="20" aria-hidden="true" />
              <strong>{{ questionAnswer(question)?.score ?? '—' }} 分</strong>
            </div>
          </header>

          <div class="answer-grid">
            <div><small>你的答案</small><p>{{ questionAnswer(question)?.answer || '未提交答案' }}</p></div>
            <div><small>参考答案</small><p>{{ question.standard_answer }}</p></div>
          </div>
          <div class="explanation-copy"><p><strong>解析</strong>{{ questionAnswer(question)?.explanation || question.explanation }}</p></div>
          <el-alert v-if="question.confidence_warning" type="warning" :title="question.confidence_warning" show-icon :closable="false" />
          <el-alert v-if="questionAnswer(question)?.confidence_warning" type="warning" :title="questionAnswer(question)?.confidence_warning || ''" show-icon :closable="false" />
          <small v-if="questionAnswer(question)?.confidence !== undefined" class="confidence-note">判题置信度 {{ confidencePercent(questionAnswer(question)?.confidence) }}</small>
        </article>
      </section>

      <div class="practice-submit-bar practice-result-actions">
        <span>想继续巩固同一个知识点？</span>
        <el-button type="primary" :icon="RefreshCw" @click="leavePractice">再来一组</el-button>
      </div>
    </template>
  </div>
</template>
