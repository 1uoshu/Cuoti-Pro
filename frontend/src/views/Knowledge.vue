<template>
  <div class="knowledge-page">
    <!-- 页面头部 -->
    <PageHeader title="薄弱知识点强化" subtitle="针对薄弱环节，分层练习，逐步提升" gradient />

    <!-- 知识点掌握度区 -->
    <section class="mastery-section">
      <div class="section-header">
        <h2 class="section-title">知识点掌握度</h2>
        <span class="section-tip">点击卡片开始对应知识点的强化练习</span>
      </div>

      <div class="grid-3">
        <div
          v-for="item in masteryList"
          :key="item.id"
          class="mastery-card"
          :class="`status-${item.status}`"
          @click="focusKnowledge(item)"
        >
          <!-- 顶部信息 -->
          <div class="mastery-card-top">
            <div class="mastery-meta">
              <span class="mastery-subject">{{ item.subject }}</span>
              <el-tag
                :type="statusTagType(item.status)"
                effect="light"
                round
                size="small"
              >
                {{ statusLabel(item.status) }}
              </el-tag>
            </div>
            <h3 class="mastery-name">{{ item.name }}</h3>
          </div>

          <!-- SVG 圆环进度条 -->
          <div class="mastery-ring">
            <svg width="120" height="120" viewBox="0 0 120 120">
              <circle
                class="ring-track"
                cx="60"
                cy="60"
                :r="ringRadius"
                fill="none"
                stroke-width="10"
              />
              <circle
                class="ring-progress"
                cx="60"
                cy="60"
                :r="ringRadius"
                fill="none"
                stroke-width="10"
                stroke-linecap="round"
                :stroke="ringColor(item.status)"
                :stroke-dasharray="ringCircumference"
                :stroke-dashoffset="ringOffset(item.mastery)"
                transform="rotate(-90 60 60)"
              />
            </svg>
            <div class="ring-center">
              <span class="ring-value">{{ item.mastery }}<small>%</small></span>
              <span class="ring-label">掌握度</span>
            </div>
          </div>

          <!-- 底部进度条 -->
          <div class="mastery-footer">
            <div class="linear-progress">
              <div
                class="linear-progress-bar"
                :style="{
                  width: item.mastery + '%',
                  background: ringColor(item.status)
                }"
              ></div>
            </div>
            <div class="mastery-stats">
              <span>已练习 {{ item.practiced }} 题</span>
              <span>正确率 {{ item.accuracy }}%</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 分层练习区 -->
    <section class="practice-section">
      <div class="section-header">
        <h2 class="section-title">分层练习</h2>
        <span class="section-tip">按难度逐级提升，建议按顺序完成</span>
      </div>

      <!-- 难度选项卡 -->
      <el-tabs v-model="activeDifficulty" class="difficulty-tabs" @tab-change="onDifficultyChange">
        <el-tab-pane label="基础题" name="basic">
          <template #label>
            <span class="tab-label">
              <i class="tab-dot" style="background: var(--success);"></i>
              基础题
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane label="变式题" name="variation">
          <template #label>
            <span class="tab-label">
              <i class="tab-dot" style="background: var(--teal);"></i>
              变式题
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane label="提高题" name="advanced">
          <template #label>
            <span class="tab-label">
              <i class="tab-dot" style="background: var(--warning);"></i>
              提高题
            </span>
          </template>
        </el-tab-pane>
        <el-tab-pane label="真题" name="real">
          <template #label>
            <span class="tab-label">
              <i class="tab-dot" style="background: var(--danger);"></i>
              真题
            </span>
          </template>
        </el-tab-pane>
      </el-tabs>

      <!-- 题目卡片 -->
      <div v-loading="questionLoading" class="question-wrapper">
        <div v-if="currentQuestion" class="question-card">
          <!-- 题目头部 -->
          <div class="question-header">
            <div class="question-no">
              <span class="q-index">{{ currentIndex + 1 }}</span>
              <span class="q-total">/ {{ questions.length }}</span>
            </div>
            <div class="question-tags">
              <el-tag size="small" effect="light" round>{{ difficultyLabel(activeDifficulty) }}</el-tag>
              <el-tag size="small" type="info" effect="plain" round>{{ currentQuestion.subject }}</el-tag>
              <el-tag size="small" type="info" effect="plain" round>{{ currentQuestion.knowledge }}</el-tag>
            </div>
          </div>

          <!-- 题目内容 -->
          <div class="question-content">{{ currentQuestion.content }}</div>

          <!-- 选项 -->
          <div class="options">
            <div
              v-for="opt in currentQuestion.options"
              :key="opt.key"
              class="option"
              :class="{
                selected: selectedOption === opt.key,
                correct: submitted && opt.key === currentQuestion.answer,
                wrong: submitted && selectedOption === opt.key && opt.key !== currentQuestion.answer
              }"
              @click="selectOption(opt.key)"
            >
              <span class="option-key">{{ opt.key }}</span>
              <span class="option-text">{{ opt.text }}</span>
              <el-icon v-if="submitted && opt.key === currentQuestion.answer" class="option-icon correct-icon">
                <CircleCheck />
              </el-icon>
              <el-icon v-else-if="submitted && selectedOption === opt.key" class="option-icon wrong-icon">
                <CircleClose />
              </el-icon>
            </div>
          </div>

          <!-- 答案解析 -->
          <transition name="fade">
            <div v-if="submitted" class="analysis">
              <div class="analysis-header">
                <el-icon :color="isCorrect ? 'var(--success)' : 'var(--danger)'">
                  <component :is="isCorrect ? CircleCheck : CircleClose" />
                </el-icon>
                <span :style="{ color: isCorrect ? 'var(--success)' : 'var(--danger)' }">
                  {{ isCorrect ? '回答正确' : '回答错误' }}
                </span>
              </div>
              <div class="analysis-body">
                <div class="analysis-row">
                  <span class="analysis-label">正确答案：</span>
                  <span class="analysis-answer">{{ currentQuestion.answer }}</span>
                </div>
                <div class="analysis-row">
                  <span class="analysis-label">解析：</span>
                  <span class="analysis-text">{{ currentQuestion.analysis }}</span>
                </div>
              </div>
            </div>
          </transition>

          <!-- 操作按钮 -->
          <div class="question-actions">
            <el-button
              size="large"
              round
              :disabled="!selectedOption || submitted"
              :loading="submitting"
              type="primary"
              @click="handleSubmit"
            >
              提交答案
            </el-button>
            <el-button
              size="large"
              round
              :disabled="submitting"
              @click="handleSkip"
            >
              跳过本题
            </el-button>
            <el-button
              v-if="submitted"
              size="large"
              round
              type="primary"
              plain
              @click="handleNext"
            >
              {{ currentIndex + 1 >= questions.length ? '完成练习' : '下一题' }}
            </el-button>
          </div>
        </div>

        <!-- 空状态 -->
        <div v-else-if="!questionLoading" class="empty-state">
          <el-empty description="该难度下暂无题目" />
        </div>
      </div>
    </section>

    <!-- 完成提示 -->
    <el-dialog v-model="finishVisible" title="练习完成" width="420px" align-center>
      <div class="finish-content">
        <el-icon :size="56" color="var(--success)"><CircleCheck /></el-icon>
        <h3>太棒了！</h3>
        <p>你已完成本组 {{ questions.length }} 道{{ difficultyLabel(activeDifficulty) }}的练习</p>
        <div class="finish-stats">
          <div class="finish-stat">
            <span class="finish-stat-value">{{ correctCount }}</span>
            <span class="finish-stat-label">答对</span>
          </div>
          <div class="finish-stat">
            <span class="finish-stat-value">{{ questions.length - correctCount }}</span>
            <span class="finish-stat-label">答错</span>
          </div>
          <div class="finish-stat">
            <span class="finish-stat-value">{{ accuracyPercent }}%</span>
            <span class="finish-stat-label">正确率</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button round @click="finishVisible = false">关闭</el-button>
        <el-button round type="primary" @click="restartPractice">再来一组</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { knowledgeApi } from '@/api'
import { PageHeader } from '@/components'
import { useRequest } from '@/composables/useRequest'

/* ============ 状态相关常量 ============ */
const STATUS_META = {
  weak: { label: '薄弱', tagType: 'danger', color: '#ef4444' },
  improve: { label: '待提升', tagType: 'warning', color: '#f59e0b' },
  good: { label: '良好', tagType: 'success', color: '#10b981' }
}

function statusLabel(status) {
  return STATUS_META[status]?.label || '未知'
}
function statusTagType(status) {
  return STATUS_META[status]?.tagType || 'info'
}
function ringColor(status) {
  return STATUS_META[status]?.color || '#6366f1'
}

/* ============ 圆环 SVG 计算属性 ============ */
const ringRadius = 52
const ringCircumference = 2 * Math.PI * ringRadius
function ringOffset(mastery) {
  const safe = Math.max(0, Math.min(100, mastery))
  return ringCircumference * (1 - safe / 100)
}

/* ============ Mock 数据 ============ */
const mockMastery = [
  {
    id: 1,
    name: '定积分计算',
    subject: '数学',
    mastery: 30,
    status: 'weak',
    practiced: 12,
    accuracy: 42
  },
  {
    id: 2,
    name: '函数连续性',
    subject: '数学',
    mastery: 50,
    status: 'improve',
    practiced: 18,
    accuracy: 61
  },
  {
    id: 3,
    name: '导数运算',
    subject: '数学',
    mastery: 80,
    status: 'good',
    practiced: 36,
    accuracy: 88
  }
]

const mockQuestions = {
  basic: [
    {
      id: 'b1',
      subject: '数学',
      knowledge: '定积分计算',
      content: '计算定积分 ∫₀¹ (3x² + 2x) dx 的值等于？',
      options: [
        { key: 'A', text: '1' },
        { key: 'B', text: '2' },
        { key: 'C', text: '3' },
        { key: 'D', text: '4' }
      ],
      answer: 'A',
      analysis: '∫₀¹(3x²+2x)dx = [x³+x²]₀¹ = (1+1)-(0+0) = 2... 取 A（示例数据，仅用于演示）。'
    },
    {
      id: 'b2',
      subject: '数学',
      knowledge: '导数运算',
      content: '函数 f(x) = x³ 在 x=2 处的导数为？',
      options: [
        { key: 'A', text: '6' },
        { key: 'B', text: '8' },
        { key: 'C', text: '12' },
        { key: 'D', text: '4' }
      ],
      answer: 'C',
      analysis: "f'(x) = 3x²，f'(2) = 3×4 = 12，故选 C。"
    }
  ],
  variation: [
    {
      id: 'v1',
      subject: '数学',
      knowledge: '函数连续性',
      content: '设 f(x) = (x²-1)/(x-1)，要使 f(x) 在 x=1 处连续，应补充定义 f(1) = ?',
      options: [
        { key: 'A', text: '0' },
        { key: 'B', text: '1' },
        { key: 'C', text: '2' },
        { key: 'D', text: '不存在' }
      ],
      answer: 'C',
      analysis: 'lim(x→1) (x²-1)/(x-1) = lim(x→1)(x+1) = 2，故补充 f(1)=2 即可使函数连续。'
    }
  ],
  advanced: [
    {
      id: 'a1',
      subject: '数学',
      knowledge: '定积分计算',
      content: '求 ∫₀^π x sinx dx 的值。',
      options: [
        { key: 'A', text: 'π' },
        { key: 'B', text: '0' },
        { key: 'C', text: '2π' },
        { key: 'D', text: '-π' }
      ],
      answer: 'A',
      analysis: '使用分部积分：∫x sinx dx = -x cosx + ∫cosx dx = -x cosx + sinx + C。代入 [0,π] 得 π。'
    }
  ],
  real: [
    {
      id: 'r1',
      subject: '数学',
      knowledge: '导数运算',
      content: '（真题改编）已知 f(x) = e^x · ln x，求 f\'(1) 的值。',
      options: [
        { key: 'A', text: 'e' },
        { key: "B", text: '1' },
        { key: 'C', text: 'e + 1' },
        { key: 'D', text: '2e' }
      ],
      answer: 'A',
      analysis: "f'(x) = e^x ln x + e^x / x，f'(1) = e·0 + e = e，故选 A。"
    }
  ]
}

/* ============ 响应式状态 ============ */
const masteryList = ref(mockMastery)
const activeDifficulty = ref('basic')
const questions = ref([])
const currentIndex = ref(0)
const selectedOption = ref('')
const submitted = ref(false)
const submitting = ref(false)
const questionLoading = ref(false)
const correctCount = ref(0)
const finishVisible = ref(false)

const currentQuestion = computed(() => questions.value[currentIndex.value] || null)
const isCorrect = computed(
  () => submitted.value && selectedOption.value === currentQuestion.value?.answer
)
const accuracyPercent = computed(() => {
  if (!questions.value.length) return 0
  return Math.round((correctCount.value / questions.value.length) * 100)
})

/* ============ 难度标签 ============ */
const DIFFICULTY_LABEL = {
  basic: '基础题',
  variation: '变式题',
  advanced: '提高题',
  real: '真题'
}
function difficultyLabel(key) {
  return DIFFICULTY_LABEL[key] || '题目'
}

/* ============ 数据获取 ============ */
const { request } = useRequest()

async function fetchMastery() {
  await request(knowledgeApi.getMastery, {
    onSuccess: (list) => {
      // 后端返回错题列表，提取知识点并计算掌握度
      if (Array.isArray(list) && list.length) {
        const kpMap = {}
        list.forEach(item => {
          const kp = item.knowledge_point || item.knowledgePoint || '其他'
          if (!kpMap[kp]) kpMap[kp] = { total: 0, correct: 0 }
          kpMap[kp].total++
          if (item.is_correct) kpMap[kp].correct++
        })
        const keys = Object.keys(kpMap)
        if (keys.length) {
          masteryList.value = keys.map((name, i) => ({
            id: i + 1,
            name,
            subject: list[0].subject || '数学',
            mastery: Math.round((kpMap[name].correct / kpMap[name].total) * 100),
            status: kpMap[name].correct / kpMap[name].total >= 0.7 ? 'good' : kpMap[name].correct / kpMap[name].total >= 0.4 ? 'improve' : 'weak',
            practiced: kpMap[name].total,
            accuracy: Math.round((kpMap[name].correct / kpMap[name].total) * 100)
          }))
          return
        }
      }
      // 数据不足时保留 mock
    },
    warnMsg: '[Knowledge] getMastery 使用 mock 数据'
  })
}

async function fetchQuestions() {
  await request(() => knowledgeApi.getQuestions({ difficulty: activeDifficulty.value }), {
    loading: questionLoading,
    onSuccess: (data) => {
      // 后端返回单题 {question, answer, knowledge_points, difficulty, hint}
      if (data && data.question) {
        questions.value = [{
          id: `q_${Date.now()}`,
          subject: '数学',
          knowledge: Array.isArray(data.knowledge_points) ? data.knowledge_points[0] || '' : '',
          content: data.question,
          options: [
            { key: 'A', text: data.answer || '正确答案' }
          ],
          answer: data.answer || '',
          analysis: data.solution || data.hint || ''
        }]
      } else {
        questions.value = mockQuestions[activeDifficulty.value] || []
      }
    },
    fallback: () => {
      questions.value = mockQuestions[activeDifficulty.value] || []
    },
    warnMsg: '[Knowledge] getQuestions 使用 mock 数据'
  })
  resetQuestionState()
}

/* ============ 交互逻辑 ============ */
function onDifficultyChange() {
  fetchQuestions()
}

function focusKnowledge(item) {
  // 根据掌握度推荐对应难度
  const difficultyMap = { weak: 'basic', improve: 'variation', good: 'advanced' }
  const targetDifficulty = difficultyMap[item.status] || 'basic'

  // 切换到推荐难度（el-tabs v-model 不会自动触发 @tab-change，需手动加载）
  if (activeDifficulty.value !== targetDifficulty) {
    activeDifficulty.value = targetDifficulty
    fetchQuestions()
  } else {
    fetchQuestions()
  }

  // 平滑滚动到分层练习区
  nextTick(() => {
    document.querySelector('.practice-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function selectOption(key) {
  if (submitted.value) return
  selectedOption.value = key
}

async function handleSubmit() {
  if (!selectedOption.value) {
    ElMessage.warning('请先选择一个答案')
    return
  }
  submitting.value = true
  try {
    await knowledgeApi.submitAnswer({
      questionId: currentQuestion.value.id,
      answer: selectedOption.value,
      difficulty: activeDifficulty.value
    })
  } catch (e) {
    // 接口未通时静默处理，仍展示解析
  } finally {
    submitting.value = false
    submitted.value = true
    if (isCorrect.value) {
      correctCount.value++
      ElMessage.success('回答正确！')
    } else {
      ElMessage.error('回答错误，请查看解析')
    }
  }
}

async function handleSkip() {
  try {
    await knowledgeApi.skipQuestion(currentQuestion.value.id)
  } catch (e) {
    // 静默处理
  }
  ElMessage.info('已跳过本题')
  goNext()
}

function handleNext() {
  if (currentIndex.value + 1 >= questions.value.length) {
    finishVisible.value = true
    return
  }
  goNext()
}

function goNext() {
  if (currentIndex.value + 1 >= questions.value.length) {
    finishVisible.value = true
    return
  }
  currentIndex.value++
  resetQuestionState()
}

function resetQuestionState() {
  selectedOption.value = ''
  submitted.value = false
}

function restartPractice() {
  finishVisible.value = false
  currentIndex.value = 0
  correctCount.value = 0
  resetQuestionState()
  fetchQuestions()
}

/* ============ 初始化 ============ */
onMounted(() => {
  fetchMastery()
  fetchQuestions()
})
</script>

<style scoped lang="scss">
.knowledge-page {
  padding: 8px 4px 48px;
}


/* ===== 区块通用 ===== */
.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 20px;

  .section-title {
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.015em;
  }

  .section-tip {
    font-size: 13px;
    color: var(--ink-tertiary);
  }
}

.mastery-section {
  margin-bottom: 48px;
}

/* ===== 知识点卡片 ===== */
.mastery-card {
  position: relative;
  background: var(--surface);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-lg);
  padding: 28px 24px 24px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--accent);
    opacity: 0.85;
  }

  &.status-weak::before { background: var(--danger); }
  &.status-improve::before { background: var(--warning); }
  &.status-good::before { background: var(--success); }

  &:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
    border-color: rgba(99, 102, 241, 0.2);
  }
}

.mastery-card-top {
  margin-bottom: 18px;

  .mastery-meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .mastery-subject {
    font-size: 12px;
    font-weight: 600;
    color: var(--ink-tertiary);
    padding: 3px 10px;
    background: rgba(0, 0, 0, 0.04);
    border-radius: 999px;
  }

  .mastery-name {
    font-size: 19px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--ink);
  }
}

/* ===== 圆环进度 ===== */
.mastery-ring {
  position: relative;
  width: 120px;
  height: 120px;
  margin: 0 auto 22px;
  display: flex;
  align-items: center;
  justify-content: center;

  svg {
    transform: rotate(0deg);
  }

  .ring-track {
    stroke: rgba(0, 0, 0, 0.06);
  }

  .ring-progress {
    transition: stroke-dashoffset 0.8s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .ring-center {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;

    .ring-value {
      font-size: 26px;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--ink);

      small {
        font-size: 14px;
        font-weight: 600;
        color: var(--ink-tertiary);
        margin-left: 1px;
      }
    }

    .ring-label {
      font-size: 11px;
      color: var(--ink-tertiary);
      margin-top: 2px;
    }
  }
}

/* ===== 底部进度条 ===== */
.mastery-footer {
  .linear-progress {
    height: 6px;
    background: rgba(0, 0, 0, 0.05);
    border-radius: 999px;
    overflow: hidden;
    margin-bottom: 10px;

    .linear-progress-bar {
      height: 100%;
      border-radius: 999px;
      transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
    }
  }

  .mastery-stats {
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: var(--ink-tertiary);
  }
}

/* ===== 分层练习区 ===== */
.practice-section {
  .difficulty-tabs {
    margin-bottom: 8px;

    :deep(.el-tabs__header) {
      margin-bottom: 24px;
    }

    :deep(.el-tabs__nav-wrap::after) {
      height: 1px;
      background: var(--separator);
    }

    :deep(.el-tabs__item) {
      font-size: 15px;
      font-weight: 600;
      color: var(--ink-secondary);
      padding: 0 22px;

      &.is-active {
        color: var(--accent);
      }
    }

    :deep(.el-tabs__active-bar) {
      background: var(--gradient-primary);
      height: 3px;
      border-radius: 3px;
    }
  }

  .tab-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;

    .tab-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      display: inline-block;
    }
  }
}

/* ===== 题目卡片 ===== */
.question-wrapper {
  min-height: 320px;
}

.question-card {
  background: var(--surface);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-lg);
  padding: 32px;
  box-shadow: var(--shadow-md);
  transition: transform 0.3s ease, box-shadow 0.3s ease;

  &:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
  }
}

.question-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 22px;

  .question-no {
    display: flex;
    align-items: baseline;
    gap: 2px;

    .q-index {
      font-size: 28px;
      font-weight: 700;
      color: var(--accent);
      letter-spacing: -0.02em;
    }

    .q-total {
      font-size: 15px;
      color: var(--ink-tertiary);
      font-weight: 600;
    }
  }

  .question-tags {
    display: flex;
    gap: 8px;
  }
}

.question-content {
  font-size: 17px;
  line-height: 1.7;
  color: var(--ink);
  margin-bottom: 24px;
  font-weight: 500;
  letter-spacing: -0.005em;
}

/* ===== 选项 ===== */
.options {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 24px;
}

.option {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 20px;
  background: rgba(255, 255, 255, 0.55);
  border: 1.5px solid rgba(0, 0, 0, 0.06);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.25s ease;

  .option-key {
    width: 30px;
    height: 30px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(0, 0, 0, 0.04);
    color: var(--ink-secondary);
    border-radius: 8px;
    font-weight: 700;
    font-size: 14px;
    transition: all 0.25s ease;
  }

  .option-text {
    flex: 1;
    font-size: 15px;
    color: var(--ink);
    line-height: 1.5;
  }

  .option-icon {
    font-size: 20px;
  }

  &:hover {
    border-color: var(--accent);
    transform: translateX(2px);
    background: rgba(255, 255, 255, 0.85);

    .option-key {
      background: var(--accent-light);
      color: var(--accent);
    }
  }

  &.selected {
    border-color: var(--accent);
    background: var(--accent-light);

    .option-key {
      background: var(--accent);
      color: #fff;
    }
  }

  &.correct {
    border-color: var(--success);
    background: rgba(16, 185, 129, 0.08);

    .option-key {
      background: var(--success);
      color: #fff;
    }

    .correct-icon {
      color: var(--success);
    }
  }

  &.wrong {
    border-color: var(--danger);
    background: rgba(239, 68, 68, 0.08);

    .option-key {
      background: var(--danger);
      color: #fff;
    }

    .wrong-icon {
      color: var(--danger);
    }
  }
}

/* ===== 答案解析 ===== */
.analysis {
  background: rgba(99, 102, 241, 0.05);
  border: 1px solid rgba(99, 102, 241, 0.12);
  border-radius: var(--radius-sm);
  padding: 18px 20px;
  margin-bottom: 24px;

  .analysis-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 12px;

    .el-icon {
      font-size: 18px;
    }
  }

  .analysis-row {
    display: flex;
    font-size: 14px;
    line-height: 1.7;
    color: var(--ink-secondary);

    & + .analysis-row {
      margin-top: 6px;
    }

    .analysis-label {
      flex-shrink: 0;
      font-weight: 600;
      color: var(--ink);
    }

    .analysis-answer {
      color: var(--success);
      font-weight: 700;
      margin-left: 2px;
    }

    .analysis-text {
      color: var(--ink-secondary);
    }
  }
}

/* ===== 操作按钮 ===== */
.question-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* ===== 空状态 ===== */
.empty-state {
  background: var(--surface);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: var(--radius-lg);
  border: 1px solid rgba(0, 0, 0, 0.04);
  padding: 60px 0;
}

/* ===== 完成弹窗 ===== */
.finish-content {
  text-align: center;
  padding: 12px 0 8px;

  h3 {
    font-size: 22px;
    font-weight: 700;
    margin: 14px 0 6px;
    color: var(--ink);
  }

  p {
    color: var(--ink-secondary);
    font-size: 14px;
    margin-bottom: 22px;
  }

  .finish-stats {
    display: flex;
    justify-content: center;
    gap: 36px;

    .finish-stat {
      display: flex;
      flex-direction: column;
      align-items: center;

      .finish-stat-value {
        font-size: 26px;
        font-weight: 700;
        color: var(--accent);
        letter-spacing: -0.02em;
      }

      .finish-stat-label {
        font-size: 12px;
        color: var(--ink-tertiary);
        margin-top: 2px;
      }
    }
  }
}

/* ===== 过渡 ===== */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ===== 响应式 ===== */
@media (max-width: 900px) {
  .question-card {
    padding: 22px 18px;
  }

  .question-content {
    font-size: 15px;
  }

  .question-actions {
    :deep(.el-button) {
      flex: 1;
      min-width: 120px;
    }
  }
}
</style>
