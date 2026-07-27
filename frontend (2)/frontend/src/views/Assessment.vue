<template>
  <div class="assessment-page">
    <!-- 页面头部 -->
    <PageHeader title="阶段评估验证" subtitle="定向组卷，检测阶段性学习成果" gradient />

    <!-- 组卷设置表单卡片 -->
    <section class="paper-setting-section">
      <div class="section-header">
        <h2 class="section-title">组卷设置</h2>
        <span class="section-tip">选择科目、知识点与难度，定向生成阶段评估试卷</span>
      </div>

      <div class="setting-card" v-loading="generating" element-loading-text="正在生成试卷...">
        <el-form :model="form" label-position="top" class="setting-form">
          <div class="form-grid">
            <el-form-item label="科目">
              <el-select
                v-model="form.subject"
                placeholder="请选择科目"
                style="width: 100%"
                @change="onSubjectChange"
              >
                <el-option
                  v-for="item in subjectOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="知识点范围">
              <el-select
                v-model="form.knowledgeRange"
                placeholder="请选择知识点范围"
                style="width: 100%"
              >
                <el-option
                  v-for="item in knowledgeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="难度等级">
              <el-select
                v-model="form.difficulty"
                placeholder="请选择难度等级"
                style="width: 100%"
              >
                <el-option
                  v-for="item in difficultyOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="题目数量">
              <el-input-number
                v-model="form.count"
                :min="5"
                :max="50"
                :step="5"
                style="width: 100%"
              />
            </el-form-item>
          </div>

          <div class="form-actions">
            <el-button
              type="primary"
              size="large"
              round
              :loading="generating"
              @click="handleGenerate"
            >
              <el-icon style="margin-right: 6px"><Document /></el-icon>
              生成试卷
            </el-button>
            <el-button
              size="large"
              round
              :loading="generating"
              @click="handleRandom"
            >
              <el-icon style="margin-right: 6px"><MagicStick /></el-icon>
              随机组卷
            </el-button>
          </div>
        </el-form>
      </div>
    </section>

    <!-- 评估结果区 -->
    <section class="result-section">
      <div class="section-header">
        <h2 class="section-title">评估结果</h2>
        <span class="section-tip">本次评估相对上次的提升情况</span>
      </div>

      <div class="grid-2">
        <!-- 左：成绩对比卡片 -->
        <div class="result-card score-card">
          <div class="card-header">
            <div class="card-icon" style="background: var(--gradient-primary)">
              <el-icon><Trophy /></el-icon>
            </div>
            <div class="card-title-group">
              <h3 class="card-title">成绩对比</h3>
              <span class="card-desc">上次评估 → 本次评估</span>
            </div>
          </div>

          <div class="score-compare">
            <div class="score-item score-prev">
              <span class="score-label">上次得分</span>
              <span class="score-value">{{ scoreCompare.lastScore }}</span>
            </div>

            <div class="score-arrow">
              <el-icon :size="32"><Right /></el-icon>
            </div>

            <div class="score-item score-current">
              <span class="score-label">本次得分</span>
              <span class="score-value gradient-text">{{ scoreCompare.currentScore }}</span>
            </div>
          </div>

          <div class="score-improve">
            <div class="improve-badge">
              <el-icon><Top /></el-icon>
              <span>提升 {{ scoreCompare.improvement }} 分</span>
            </div>
            <div class="improve-rate">
              相对提升
              <strong>+{{ improveRate }}%</strong>
            </div>
          </div>
        </div>

        <!-- 右：知识点掌握变化卡片 -->
        <div class="result-card mastery-card">
          <div class="card-header">
            <div class="card-icon" style="background: var(--gradient-cool)">
              <el-icon><TrendCharts /></el-icon>
            </div>
            <div class="card-title-group">
              <h3 class="card-title">知识点掌握变化</h3>
              <span class="card-desc">各知识点本次提升幅度</span>
            </div>
          </div>

          <div class="mastery-list">
            <div
              v-for="(item, index) in masteryChange"
              :key="item.name"
              class="mastery-item"
            >
              <div class="mastery-info">
                <span class="mastery-name">{{ item.name }}</span>
                <span class="mastery-change" :style="{ color: changeColor(item.change) }">
                  <el-icon><Top /></el-icon>
                  +{{ item.change }}%
                </span>
              </div>
              <div class="mastery-bar-wrapper">
                <div class="mastery-bar-track">
                  <div
                    class="mastery-bar-fill"
                    :style="{
                      width: item.current + '%',
                      background: barGradient(index)
                    }"
                  ></div>
                  <div
                    v-if="item.previous > 0"
                    class="mastery-bar-prev"
                    :style="{ width: item.previous + '%' }"
                  ></div>
                </div>
                <span class="mastery-percent">{{ item.current }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 试卷生成结果弹窗 -->
    <el-dialog
      v-model="paperDialogVisible"
      title="试卷已生成"
      width="480px"
      align-center
    >
      <div class="paper-result">
        <div class="paper-result-icon">
          <el-icon :size="48" color="var(--success)"><CircleCheck /></el-icon>
        </div>
        <h3>{{ generatedPaper.title || '阶段评估试卷' }}</h3>
        <p class="paper-result-desc">试卷已按你的设置生成，可前往作业模块开始答题</p>
        <div class="paper-meta">
          <div class="paper-meta-item">
            <span class="paper-meta-label">科目</span>
            <span class="paper-meta-value">{{ generatedPaper.subject || form.subject }}</span>
          </div>
          <div class="paper-meta-item">
            <span class="paper-meta-label">题量</span>
            <span class="paper-meta-value">{{ generatedPaper.count || form.count }} 题</span>
          </div>
          <div class="paper-meta-item">
            <span class="paper-meta-label">难度</span>
            <span class="paper-meta-value">{{ difficultyLabel(form.difficulty) }}</span>
          </div>
          <div class="paper-meta-item">
            <span class="paper-meta-label">预计时长</span>
            <span class="paper-meta-value">{{ generatedPaper.duration || form.count * 2 }} 分钟</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button round @click="paperDialogVisible = false">稍后再做</el-button>
        <el-button round type="primary" @click="goToExam">开始答题</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Document,
  MagicStick,
  Trophy,
  TrendCharts,
  Right,
  Top,
  CircleCheck
} from '@element-plus/icons-vue'
import { assessmentApi } from '@/api'
import { PageHeader } from '@/components'
import { useRequest } from '@/composables/useRequest'

/* ============ 下拉选项 ============ */
const subjectOptions = [
  { label: '数学', value: '数学' },
  { label: '语文', value: '语文' },
  { label: '英语', value: '英语' },
  { label: '物理', value: '物理' },
  { label: '化学', value: '化学' }
]

const knowledgeOptionsMap = {
  数学: [
    { label: '全部知识点', value: 'all' },
    { label: '定积分', value: 'definite-integral' },
    { label: '函数连续性', value: 'continuity' },
    { label: '导数运算', value: 'derivative' },
    { label: '级数求和', value: 'series' },
    { label: '极限运算', value: 'limit' }
  ],
  语文: [
    { label: '全部知识点', value: 'all' },
    { label: '文言文阅读', value: 'classical' },
    { label: '现代文阅读', value: 'modern' },
    { label: '写作', value: 'writing' }
  ],
  英语: [
    { label: '全部知识点', value: 'all' },
    { label: '阅读理解', value: 'reading' },
    { label: '完形填空', value: 'cloze' },
    { label: '书面表达', value: 'writing' }
  ],
  物理: [
    { label: '全部知识点', value: 'all' },
    { label: '力学', value: 'mechanics' },
    { label: '电磁学', value: 'electromagnetism' },
    { label: '热学', value: 'thermodynamics' }
  ],
  化学: [
    { label: '全部知识点', value: 'all' },
    { label: '化学方程式', value: 'equation' },
    { label: '有机化学', value: 'organic' },
    { label: '无机化学', value: 'inorganic' }
  ]
}

const difficultyOptions = [
  { label: '基础', value: 'basic' },
  { label: '中等', value: 'medium' },
  { label: '较难', value: 'hard' },
  { label: '混合难度', value: 'mixed' }
]

const DIFFICULTY_LABEL = {
  basic: '基础',
  medium: '中等',
  hard: '较难',
  mixed: '混合难度'
}
function difficultyLabel(key) {
  return DIFFICULTY_LABEL[key] || '未设置'
}

/* ============ Mock 数据 ============ */
const mockScoreCompare = {
  lastScore: 72,
  currentScore: 85,
  improvement: 13
}

const mockMasteryChange = [
  { name: '定积分', previous: 45, current: 60, change: 15 },
  { name: '函数连续性', previous: 55, current: 65, change: 10 },
  { name: '导数运算', previous: 78, current: 80, change: 2 },
  { name: '级数求和', previous: 40, current: 48, change: 8 },
  { name: '极限运算', previous: 58, current: 70, change: 12 }
]

/* ============ 响应式状态 ============ */
const form = reactive({
  subject: '数学',
  knowledgeRange: 'all',
  difficulty: 'mixed',
  count: 20
})

const knowledgeOptions = ref(knowledgeOptionsMap['数学'])
const generating = ref(false)
const paperDialogVisible = ref(false)
const generatedPaper = ref({})

const scoreCompare = ref({ ...mockScoreCompare })
const masteryChange = ref(JSON.parse(JSON.stringify(mockMasteryChange)))

/* ============ 计算属性 ============ */
const improveRate = computed(() => {
  const { lastScore, improvement } = scoreCompare.value
  if (!lastScore) return 0
  return Math.round((improvement / lastScore) * 100)
})

/* ============ 工具方法 ============ */
function onSubjectChange(val) {
  knowledgeOptions.value = knowledgeOptionsMap[val] || []
  form.knowledgeRange = 'all'
}

function changeColor(change) {
  if (change >= 12) return 'var(--success)'
  if (change >= 8) return 'var(--accent)'
  if (change >= 4) return 'var(--teal)'
  return 'var(--warning)'
}

function barGradient(index) {
  const gradients = [
    'linear-gradient(90deg, #6366f1 0%, #8b5cf6 100%)',
    'linear-gradient(90deg, #06b6d4 0%, #6366f1 100%)',
    'linear-gradient(90deg, #10b981 0%, #34d399 100%)',
    'linear-gradient(90deg, #f59e0b 0%, #ef4444 100%)',
    'linear-gradient(90deg, #ec4899 0%, #8b5cf6 100%)'
  ]
  return gradients[index % gradients.length]
}

/* ============ 组卷逻辑 ============ */
async function handleGenerate() {
  if (!form.subject) {
    ElMessage.warning('请先选择科目')
    return
  }
  generating.value = true
  try {
    const res = await assessmentApi.generatePaper({ ...form })
    if (res && res.data) {
      generatedPaper.value = res.data
    } else {
      // mock 回退
      generatedPaper.value = {
        title: `${form.subject}·阶段评估试卷`,
        subject: form.subject,
        count: form.count,
        duration: form.count * 2
      }
    }
    paperDialogVisible.value = true
    ElMessage.success('试卷生成成功')
  } catch (e) {
    console.warn('[Assessment] generatePaper 使用 mock 回退：', e?.message)
    generatedPaper.value = {
      title: `${form.subject}·阶段评估试卷`,
      subject: form.subject,
      count: form.count,
      duration: form.count * 2
    }
    paperDialogVisible.value = true
    ElMessage.success('试卷生成成功')
  } finally {
    generating.value = false
  }
}

async function handleRandom() {
  if (!form.subject) {
    ElMessage.warning('请先选择科目')
    return
  }
  generating.value = true
  try {
    const res = await assessmentApi.randomPaper({ subject: form.subject, count: form.count })
    if (res && res.data) {
      generatedPaper.value = res.data
    } else {
      generatedPaper.value = {
        title: `${form.subject}·随机评估试卷`,
        subject: form.subject,
        count: form.count,
        duration: form.count * 2
      }
    }
    paperDialogVisible.value = true
    ElMessage.success('随机组卷完成')
  } catch (e) {
    console.warn('[Assessment] randomPaper 使用 mock 回退：', e?.message)
    generatedPaper.value = {
      title: `${form.subject}·随机评估试卷`,
      subject: form.subject,
      count: form.count,
      duration: form.count * 2
    }
    paperDialogVisible.value = true
    ElMessage.success('随机组卷完成')
  } finally {
    generating.value = false
  }
}

function goToExam() {
  paperDialogVisible.value = false
  ElMessage.info('即将跳转至作业答题模块')
}

/* ============ 评估结果获取 ============ */
// 后端暂无独立的结果查询接口，保留 mock 数据展示
// 等试卷批改完成后再从后端获取实际结果

/* ============ 初始化 ============ */
onMounted(() => {
  // 评分数据和知识点变化保留 mock 值展示
})
</script>

<style scoped lang="scss">
.assessment-page {
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

.paper-setting-section {
  margin-bottom: 48px;
}

/* ===== 设置卡片（毛玻璃） ===== */
.setting-card {
  background: var(--surface);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-lg);
  padding: 32px;
  box-shadow: var(--shadow-md);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.setting-form {
  .form-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    margin-bottom: 8px;
  }

  :deep(.el-form-item) {
    margin-bottom: 0;
  }

  :deep(.el-form-item__label) {
    font-size: 13px;
    font-weight: 600;
    color: var(--ink-secondary);
    padding-bottom: 6px;
  }
}

.form-actions {
  display: flex;
  gap: 12px;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--separator);

  :deep(.el-button) {
    padding: 0 28px;
    height: 46px;
  }
}

/* ===== 结果区 ===== */
.result-section {
  margin-bottom: 16px;
}

/* ===== 结果卡片（毛玻璃） ===== */
.result-card {
  background: var(--surface);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-lg);
  padding: 28px;
  box-shadow: var(--shadow-sm);
  transition: transform 0.3s ease, box-shadow 0.3s ease;

  &:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 28px;

  .card-icon {
    width: 44px;
    height: 44px;
    border-radius: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #fff;
    font-size: 22px;
    box-shadow: var(--shadow-sm);
  }

  .card-title-group {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .card-title {
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.01em;
    color: var(--ink);
  }

  .card-desc {
    font-size: 12px;
    color: var(--ink-tertiary);
  }
}

/* ===== 成绩对比卡片 ===== */
.score-card {
  display: flex;
  flex-direction: column;
}

.score-compare {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0 24px;

  .score-item {
    display: flex;
    flex-direction: column;
    align-items: center;
    flex: 1;

    .score-label {
      font-size: 13px;
      color: var(--ink-tertiary);
      margin-bottom: 8px;
      font-weight: 600;
    }

    .score-value {
      font-size: 56px;
      font-weight: 700;
      letter-spacing: -0.03em;
      line-height: 1;
      color: var(--ink-secondary);
    }
  }

  .score-current .score-value {
    color: var(--accent);
  }

  .score-arrow {
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent);
    padding-bottom: 8px;
  }
}

.gradient-text {
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.score-improve {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.18);
  border-radius: var(--radius-sm);

  .improve-badge {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--success);
    font-size: 15px;
    font-weight: 700;

    .el-icon {
      font-size: 18px;
    }
  }

  .improve-rate {
    font-size: 13px;
    color: var(--ink-secondary);

    strong {
      color: var(--success);
      font-size: 16px;
      margin-left: 4px;
    }
  }
}

/* ===== 知识点掌握变化卡片 ===== */
.mastery-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.mastery-item {
  .mastery-info {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;

    .mastery-name {
      font-size: 14px;
      font-weight: 600;
      color: var(--ink);
    }

    .mastery-change {
      display: inline-flex;
      align-items: center;
      gap: 2px;
      font-size: 13px;
      font-weight: 700;

      .el-icon {
        font-size: 14px;
      }
    }
  }

  .mastery-bar-wrapper {
    display: flex;
    align-items: center;
    gap: 12px;

    .mastery-bar-track {
      position: relative;
      flex: 1;
      height: 10px;
      background: rgba(0, 0, 0, 0.05);
      border-radius: 999px;
      overflow: hidden;

      .mastery-bar-prev {
        position: absolute;
        top: 0;
        left: 0;
        height: 100%;
        background: rgba(0, 0, 0, 0.08);
        border-radius: 999px;
        z-index: 0;
      }

      .mastery-bar-fill {
        position: relative;
        height: 100%;
        border-radius: 999px;
        z-index: 1;
        transition: width 0.9s cubic-bezier(0.4, 0, 0.2, 1);
      }
    }

    .mastery-percent {
      font-size: 13px;
      font-weight: 700;
      color: var(--ink-secondary);
      min-width: 38px;
      text-align: right;
    }
  }
}

/* ===== 试卷生成结果弹窗 ===== */
.paper-result {
  text-align: center;
  padding: 12px 0 8px;

  .paper-result-icon {
    margin-bottom: 14px;
  }

  h3 {
    font-size: 20px;
    font-weight: 700;
    color: var(--ink);
    margin-bottom: 6px;
    letter-spacing: -0.01em;
  }

  .paper-result-desc {
    font-size: 13px;
    color: var(--ink-secondary);
    margin-bottom: 22px;
  }

  .paper-meta {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
    padding: 18px;
    background: var(--accent-light);
    border-radius: var(--radius-sm);

    .paper-meta-item {
      display: flex;
      flex-direction: column;
      gap: 4px;
      text-align: left;

      .paper-meta-label {
        font-size: 12px;
        color: var(--ink-tertiary);
      }

      .paper-meta-value {
        font-size: 15px;
        font-weight: 700;
        color: var(--ink);
      }
    }
  }
}

/* ===== 响应式 ===== */
@media (max-width: 1100px) {
  .setting-form .form-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 900px) {
  .setting-form .form-grid {
    grid-template-columns: 1fr;
  }

  .score-compare {
    .score-value {
      font-size: 42px;
    }

    .score-arrow .el-icon {
      font-size: 24px;
    }
  }

  .form-actions {
    :deep(.el-button) {
      flex: 1;
    }
  }
}
</style>
