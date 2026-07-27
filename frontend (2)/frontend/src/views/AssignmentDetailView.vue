<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { AlertCircle, ArrowLeft, CheckCircle2, Pencil, RotateCcw } from 'lucide-vue-next'
import { api, errorMessage, request } from '../api'
import type { Assignment, AssignmentQuestion, Task } from '../types'

const route = useRoute()
const router = useRouter()
const assignment = ref<Assignment | null>(null)
const loading = ref(true)
const editOpen = ref(false)
const submitting = ref(false)
const selected = ref<AssignmentQuestion | null>(null)
const edit = ref({ content: '', student_answer: '', correct_answer: '', knowledge_point: '' })
let timer: number | undefined

const assignmentId = computed(() => Number(route.params.id))

function statusType(status: Assignment['status']) {
  return status === 'completed' ? 'success' : status === 'failed' ? 'danger' : 'warning'
}

async function load() {
  loading.value = true
  try {
    assignment.value = await request<Assignment>(api.get(`/assignments/${assignmentId.value}`))
    if (assignment.value.task && ['queued', 'processing'].includes(assignment.value.status)) poll()
  } catch (error) {
    ElMessage.error(errorMessage(error))
    await router.replace('/assignments')
  } finally {
    loading.value = false
  }
}

function poll() {
  if (timer || !assignment.value?.task) return
  const taskId = assignment.value.task.id
  timer = window.setInterval(async () => {
    try {
      const task = await request<Task>(api.get(`/tasks/${taskId}`))
      if (assignment.value) {
        assignment.value.task = task
        assignment.value.status = task.status
      }
      if (['completed', 'failed'].includes(task.status)) {
        if (timer) window.clearInterval(timer)
        timer = undefined
        await load()
      }
    } catch (error) {
      if (timer) window.clearInterval(timer)
      timer = undefined
      ElMessage.error(errorMessage(error))
    }
  }, 2000)
}

function openEdit(question: AssignmentQuestion) {
  selected.value = question
  edit.value = {
    content: question.content,
    student_answer: question.student_answer || '',
    correct_answer: question.correct_answer || '',
    knowledge_point: question.knowledge_point || '',
  }
  editOpen.value = true
}

async function regrade() {
  if (!selected.value) return
  submitting.value = true
  try {
    const question = await request<AssignmentQuestion>(api.put(`/questions/${selected.value.id}`, edit.value))
    if (assignment.value?.questions) {
      const index = assignment.value.questions.findIndex((item) => item.id === question.id)
      if (index >= 0) assignment.value.questions[index] = question
    }
    editOpen.value = false
    ElMessage.success('已重新批改并同步错题记录')
    await load()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

onMounted(load)
onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div v-loading="loading" class="stack-lg">
    <template v-if="assignment">
      <button class="back-link" @click="router.push('/assignments')"><ArrowLeft :size="16" /> 返回作业列表</button>
      <section class="assignment-hero">
        <div><p class="page-context">{{ assignment.subject }}</p><h2>{{ assignment.title }}</h2><p>{{ new Date(assignment.created_at).toLocaleString('zh-CN') }}</p></div>
        <div class="score-summary"><el-tag :type="statusType(assignment.status)" effect="plain">{{ assignment.status === 'completed' ? '批改完成' : assignment.status === 'failed' ? '批改失败' : '正在批改' }}</el-tag><strong v-if="assignment.student_score !== null">{{ assignment.student_score }}<small>/{{ assignment.total_score }}</small></strong></div>
      </section>

      <section v-if="assignment.task && ['queued','processing'].includes(assignment.status)" class="panel processing-panel"><div><h3>{{ assignment.task.step }}</h3><p>批改过程将在本页自动更新，请保持页面打开。</p></div><el-progress type="dashboard" :percentage="assignment.task.progress" color="var(--color-primary)" /></section>
      <el-alert v-else-if="assignment.status === 'failed'" type="error" :title="assignment.task?.error_message || '批改任务未能完成'" show-icon :closable="false" />

      <template v-else-if="assignment.status === 'completed'">
        <section class="comment-panel"><div><p class="page-context">学习建议</p><h3>本次批改总结</h3><p>{{ assignment.overall_comment || '本次批改暂未生成整体建议。' }}</p></div><div class="weak-tags"><span>待巩固</span><el-tag v-for="point in assignment.weak_points" :key="point" type="warning" effect="light">{{ point }}</el-tag><span v-if="!assignment.weak_points.length" class="muted">暂无</span></div></section>
        <section class="question-stack"><article v-for="question in assignment.questions" :key="question.id" class="question-card" :class="{ correct: question.is_correct, incorrect: question.is_correct === false }"><header><div class="question-number">{{ question.question_number }}</div><div><span class="question-meta">{{ question.question_type || '题目' }}<template v-if="question.knowledge_point"> · {{ question.knowledge_point }}</template></span><h3>{{ question.content }}</h3></div><div class="question-result"><component :is="question.is_correct ? CheckCircle2 : AlertCircle" :size="20" /><strong>{{ question.score ?? '—' }}/{{ question.max_score ?? '—' }}</strong></div></header><div class="answer-grid"><div><small>学生作答</small><p>{{ question.student_answer || '未识别到作答' }}</p></div><div><small>参考答案</small><p>{{ question.correct_answer || '暂未提供' }}</p></div></div><footer><div class="explanation-copy"><p><strong>批改说明：</strong>{{ question.explanation || '暂无说明' }}</p><small v-if="question.confidence !== null">置信度 {{ Math.round(question.confidence * 100) }}%</small></div><el-alert v-if="question.confidence_warning" type="warning" :title="question.confidence_warning" show-icon :closable="false" /><el-button text type="primary" :icon="Pencil" @click="openEdit(question)">修正并重新批改</el-button></footer></article></section>
      </template>
    </template>

    <el-dialog v-model="editOpen" title="修正题目后重新批改" width="min(640px, calc(100vw - 32px))">
      <p class="dialog-hint">重新批改会替换该题目的得分、错题记录和掌握度贡献。</p>
      <el-form label-position="top"><el-form-item label="题目内容"><el-input v-model="edit.content" type="textarea" :rows="3" /></el-form-item><el-form-item label="学生作答"><el-input v-model="edit.student_answer" type="textarea" :rows="2" /></el-form-item><el-form-item label="参考答案"><el-input v-model="edit.correct_answer" type="textarea" :rows="2" /></el-form-item><el-form-item label="知识点"><el-input v-model="edit.knowledge_point" maxlength="128" /></el-form-item></el-form>
      <template #footer><el-button @click="editOpen = false">取消</el-button><el-button type="primary" :icon="RotateCcw" :loading="submitting" @click="regrade">重新批改</el-button></template>
    </el-dialog>
  </div>
</template>
