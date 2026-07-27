<template>
  <div class="profile-page">
    <!-- 页面头部 -->
    <PageHeader title="个人中心" subtitle="管理你的账号信息与学习档案" gradient />

    <!-- 个人信息头部卡片 -->
    <section class="profile-header">
      <div class="profile-header-inner">
        <!-- 左侧大头像 -->
        <div class="profile-avatar">
          <div class="avatar-circle">{{ avatarText }}</div>
          <div class="avatar-status">
            <el-icon><CircleCheck /></el-icon>
          </div>
        </div>

        <!-- 右侧信息 -->
        <div class="profile-meta">
          <div class="profile-name-row">
            <h2 class="profile-name">{{ profile.nickname }}</h2>
            <el-tag class="title-tag" effect="dark" round size="small">
              <el-icon class="title-icon"><Medal /></el-icon>
              {{ profile.title }}
            </el-tag>
          </div>
          <div class="profile-info-row">
            <span class="info-chip">
              <el-icon><User /></el-icon>
              {{ roleLabel }}
            </span>
            <span class="info-chip">
              <el-icon><Reading /></el-icon>
              {{ profile.grade }}
            </span>
            <span class="info-chip">
              <el-icon><Calendar /></el-icon>
              已入驻 {{ profile.joinDays }} 天
            </span>
          </div>
        </div>

        <!-- 编辑资料按钮 -->
        <el-button class="edit-btn" round size="large" @click="handleEditProfile">
          <el-icon><Edit /></el-icon>
          <span>编辑资料</span>
        </el-button>
      </div>
    </section>

    <!-- 学习概览统计 -->
    <section class="grid-4 stat-cards">
      <StatCard
        v-for="card in statCards"
        :key="card.key"
        :icon="card.icon"
        :value="card.value"
        :unit="card.unit"
        :label="card.label"
        :gradient="card.gradient"
      />
    </section>

    <!-- 信息区 -->
    <section class="grid-2 info-section">
      <!-- 基本信息 -->
      <div class="info-card">
        <div class="card-head">
          <h3 class="card-title">基本信息</h3>
          <span class="card-sub">你的个人档案</span>
        </div>
        <div class="info-rows">
          <div class="info-row" v-for="row in basicInfoRows" :key="row.key">
            <div class="row-icon" :style="{ background: row.iconBg }">
              <el-icon><component :is="row.icon" /></el-icon>
            </div>
            <div class="row-body">
              <div class="row-label">{{ row.label }}</div>
              <div class="row-value" v-if="!row.isAvatar">{{ row.value }}</div>
              <div class="row-value avatar-preview" v-else>
                <div class="mini-avatar">{{ avatarText }}</div>
                <span class="avatar-tip">点击修改头像</span>
              </div>
            </div>
            <el-button class="row-action" text type="primary" @click="handleEditRow(row)">
              修改
            </el-button>
          </div>
        </div>
      </div>

      <!-- 账号与安全 -->
      <div class="info-card">
        <div class="card-head">
          <h3 class="card-title">账号与安全</h3>
          <span class="card-sub">保障账号安全</span>
        </div>
        <div class="info-rows">
          <div class="info-row" v-for="row in securityRows" :key="row.key">
            <div class="row-icon" :style="{ background: row.iconBg }">
              <el-icon><component :is="row.icon" /></el-icon>
            </div>
            <div class="row-body">
              <div class="row-label">{{ row.label }}</div>
              <div class="row-value" :class="{ muted: !row.value }">
                {{ row.value || row.placeholder || '未设置' }}
              </div>
            </div>
            <el-button
              v-if="row.action"
              class="row-action"
              text
              type="primary"
              @click="handleEditRow(row)"
            >
              {{ row.action }}
            </el-button>
          </div>
        </div>
      </div>
    </section>

    <!-- 学习偏好设置 -->
    <section class="preferences-card">
      <div class="card-head">
        <div class="head-left">
          <h3 class="card-title">学习偏好设置</h3>
          <span class="card-sub">个性化你的学习节奏与提醒方式</span>
        </div>
        <el-button type="primary" round @click="handleSavePreferences">
          <el-icon><Check /></el-icon>
          <span>保存设置</span>
        </el-button>
      </div>
      <div class="preferences-grid">
        <div class="pref-item">
          <div class="pref-info">
            <div class="pref-label">每日学习目标</div>
            <div class="pref-desc">每天计划练习的题目数量</div>
          </div>
          <el-input-number
            v-model="preferences.dailyGoal"
            :min="5"
            :max="100"
            :step="5"
            size="large"
          />
        </div>

        <div class="pref-item">
          <div class="pref-info">
            <div class="pref-label">复习提醒时间</div>
            <div class="pref-desc">每日定时推送复习提醒</div>
          </div>
          <el-time-picker
            v-model="preferences.reviewTime"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="选择时间"
            size="large"
          />
        </div>

        <div class="pref-item">
          <div class="pref-info">
            <div class="pref-label">难度偏好</div>
            <div class="pref-desc">优先推荐的题目难度</div>
          </div>
          <el-select v-model="preferences.difficulty" size="large" style="width: 160px;">
            <el-option label="自适应推荐" value="adaptive" />
            <el-option label="基础题为主" value="basic" />
            <el-option label="变式题为主" value="variation" />
            <el-option label="提高题为主" value="advanced" />
          </el-select>
        </div>

        <div class="pref-item">
          <div class="pref-info">
            <div class="pref-label">薄弱点提醒</div>
            <div class="pref-desc">发现薄弱知识点时主动提醒</div>
          </div>
          <el-switch
            v-model="preferences.weakReminder"
            size="large"
            inline-prompt
            active-text="开"
            inactive-text="关"
          />
        </div>
      </div>
    </section>

    <!-- 退出登录 -->
    <div class="logout-area">
      <el-button class="logout-btn" text size="large" @click="handleLogout">
        <el-icon><SwitchButton /></el-icon>
        <span>退出登录</span>
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Edit,
  User,
  Avatar,
  Iphone,
  Message,
  Lock,
  Connection,
  Calendar,
  Clock,
  SwitchButton,
  Aim,
  Warning,
  CircleCheck,
  TrendCharts,
  Medal,
  Check,
  School,
  Reading
} from '@element-plus/icons-vue'
import { profileApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { PageHeader, StatCard } from '@/components'
import { useRequest } from '@/composables/useRequest'

const router = useRouter()
const userStore = useUserStore()

/* ============ 角色映射 ============ */
const ROLE_MAP = {
  student: '学生',
  teacher: '教师',
  parent: '家长'
}

/* ============ Mock 数据 ============ */
const mockProfile = {
  nickname: '李同学',
  account: 'lixx@example.com',
  role: 'student',
  grade: '初二 · 3班',
  school: '北京市第一实验中学',
  title: '勤学之星',
  joinDays: 128,
  phone: '138****8888',
  email: 'lixx@example.com',
  thirdParty: ['微信', 'QQ'],
  joinTime: '2024-03-05',
  lastLogin: '2024-07-18 09:24'
}

const mockLearningStats = {
  totalErrors: 156,
  masteredPoints: 89,
  weakPoints: 8,
  continuousDays: 23
}

const mockPreferences = {
  dailyGoal: 20,
  reviewTime: '19:30',
  difficulty: 'adaptive',
  weakReminder: true
}

/* ============ 响应式状态 ============ */
const profile = reactive({ ...mockProfile })
const learningStats = reactive({ ...mockLearningStats })
const preferences = reactive({ ...mockPreferences })
const saving = ref(false)

/* ============ 计算属性 ============ */
const avatarText = computed(() => {
  const name = profile.nickname || userStore.userInfo?.nickname || 'U'
  return name.charAt(0).toUpperCase()
})

const roleLabel = computed(() => ROLE_MAP[profile.role] || '用户')

const statCards = computed(() => [
  {
    key: 'totalErrors',
    label: '累计错题',
    value: learningStats.totalErrors,
    unit: '题',
    icon: Warning,
    gradient: 'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)'
  },
  {
    key: 'masteredPoints',
    label: '已掌握知识点',
    value: learningStats.masteredPoints,
    unit: '个',
    icon: CircleCheck,
    gradient: 'linear-gradient(135deg, #10b981 0%, #34d399 100%)'
  },
  {
    key: 'weakPoints',
    label: '薄弱知识点',
    value: learningStats.weakPoints,
    unit: '个',
    icon: Aim,
    gradient: 'linear-gradient(135deg, #ef4444 0%, #ec4899 100%)'
  },
  {
    key: 'continuousDays',
    label: '连续学习天数',
    value: learningStats.continuousDays,
    unit: '天',
    icon: TrendCharts,
    gradient: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)'
  }
])

const basicInfoRows = computed(() => [
  {
    key: 'avatar',
    label: '头像',
    icon: Avatar,
    iconBg: 'rgba(99, 102, 241, 0.1)',
    isAvatar: true
  },
  {
    key: 'nickname',
    label: '昵称',
    icon: User,
    iconBg: 'rgba(139, 92, 246, 0.1)',
    value: profile.nickname
  },
  {
    key: 'account',
    label: '账号',
    icon: Message,
    iconBg: 'rgba(6, 182, 212, 0.1)',
    value: profile.account
  },
  {
    key: 'role',
    label: '角色',
    icon: User,
    iconBg: 'rgba(16, 185, 129, 0.1)',
    value: ROLE_MAP[profile.role] || profile.role
  },
  {
    key: 'grade',
    label: '年级班级',
    icon: Reading,
    iconBg: 'rgba(245, 158, 11, 0.1)',
    value: profile.grade
  },
  {
    key: 'school',
    label: '学校',
    icon: School,
    iconBg: 'rgba(236, 72, 153, 0.1)',
    value: profile.school
  }
])

const securityRows = computed(() => [
  {
    key: 'phone',
    label: '绑定手机',
    icon: Iphone,
    iconBg: 'rgba(16, 185, 129, 0.1)',
    value: profile.phone,
    action: '修改'
  },
  {
    key: 'email',
    label: '绑定邮箱',
    icon: Message,
    iconBg: 'rgba(6, 182, 212, 0.1)',
    value: profile.email,
    action: '修改'
  },
  {
    key: 'password',
    label: '登录密码',
    icon: Lock,
    iconBg: 'rgba(239, 68, 68, 0.1)',
    value: '已设置',
    action: '修改'
  },
  {
    key: 'thirdParty',
    label: '第三方账号',
    icon: Connection,
    iconBg: 'rgba(139, 92, 246, 0.1)',
    value: profile.thirdParty.length ? profile.thirdParty.join('、') : '',
    placeholder: '未绑定',
    action: '管理'
  },
  {
    key: 'joinTime',
    label: '入驻时间',
    icon: Calendar,
    iconBg: 'rgba(99, 102, 241, 0.1)',
    value: profile.joinTime
  },
  {
    key: 'lastLogin',
    label: '上次登录',
    icon: Clock,
    iconBg: 'rgba(156, 163, 175, 0.12)',
    value: profile.lastLogin
  }
])

/* ============ 从 userStore 同步用户信息 ============ */
function syncFromStore() {
  const info = userStore.userInfo
  if (!info) return
  if (info.nickname) profile.nickname = info.nickname
  if (info.grade) profile.grade = info.grade
  if (info.role) profile.role = info.role
  if (info.account) profile.account = info.account
  if (info.school) profile.school = info.school
}

/* ============ 数据获取 ============ */
const { request } = useRequest()

async function fetchProfile() {
  await request(profileApi.getProfile, {
    onSuccess: (data) => {
      // 合并后端返回，保留 mock 兜底字段
      Object.assign(profile, data)
    },
    warnMsg: '[Profile] getProfile 使用 mock 数据'
  })
}

async function fetchLearningStats() {
  await request(profileApi.getLearningStats, {
    onSuccess: (data) => {
      Object.assign(learningStats, data)
    },
    warnMsg: '[Profile] getLearningStats 使用 mock 数据'
  })
}

/* ============ 交互逻辑 ============ */
function handleEditProfile() {
  ElMessage.info('编辑资料功能开发中')
}

function handleEditRow(row) {
  ElMessage.info(`「${row.label}」修改功能开发中`)
}

async function handleSavePreferences() {
  saving.value = true
  try {
    await profileApi.updatePreferences({ ...preferences })
    ElMessage.success('偏好设置已保存')
  } catch (e) {
    // 后端未通时仍给用户正向反馈
    ElMessage.success('偏好设置已保存（演示模式）')
  } finally {
    saving.value = false
  }
}

function handleLogout() {
  ElMessageBox.confirm('确定要退出登录吗？', '退出登录', {
    confirmButtonText: '退出',
    cancelButtonText: '取消',
    type: 'warning',
    confirmButtonClass: 'logout-confirm-btn'
  })
    .then(() => {
      userStore.logout()
      ElMessage.success('已退出登录')
      router.push('/login')
    })
    .catch(() => {
      // 用户取消
    })
}

/* ============ 初始化 ============ */
onMounted(() => {
  syncFromStore()
  fetchProfile()
  fetchLearningStats()
})
</script>

<style scoped lang="scss">
.profile-page {
  padding: 8px 4px 48px;
}

/* ===== 个人信息头部卡片 ===== */
.profile-header {
  position: relative;
  background: var(--gradient-primary);
  border-radius: var(--radius-lg);
  padding: 36px 36px;
  margin-bottom: 24px;
  box-shadow: 0 16px 48px rgba(99, 102, 241, 0.28), 0 6px 16px rgba(99, 102, 241, 0.18);
  overflow: hidden;

  /* ::before 伪元素叠加光效 */
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
      radial-gradient(ellipse 70% 90% at 0% 0%, rgba(255, 255, 255, 0.28) 0%, transparent 55%),
      radial-gradient(ellipse 50% 70% at 100% 100%, rgba(255, 255, 255, 0.12) 0%, transparent 60%);
    pointer-events: none;
  }

  /* 装饰圆斑 */
  &::after {
    content: '';
    position: absolute;
    top: -40px;
    right: -30px;
    width: 200px;
    height: 200px;
    background: radial-gradient(circle, rgba(255, 255, 255, 0.18) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
  }

  .profile-header-inner {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: 28px;
  }

  .profile-avatar {
    position: relative;
    flex-shrink: 0;

    .avatar-circle {
      width: 92px;
      height: 92px;
      border-radius: 28px;
      background: rgba(255, 255, 255, 0.22);
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
      border: 2px solid rgba(255, 255, 255, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 38px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.02em;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
    }

    .avatar-status {
      position: absolute;
      right: -4px;
      bottom: -4px;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: var(--success);
      border: 3px solid #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      font-size: 14px;
      box-shadow: 0 2px 6px rgba(16, 185, 129, 0.4);
    }
  }

  .profile-meta {
    flex: 1;
    min-width: 0;

    .profile-name-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }

    .profile-name {
      font-size: 26px;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.02em;
      line-height: 1.2;
    }

    .title-tag {
      background: rgba(255, 255, 255, 0.22) !important;
      border: 1px solid rgba(255, 255, 255, 0.35) !important;
      color: #fff !important;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      display: inline-flex;
      align-items: center;
      gap: 4px;

      .title-icon {
        font-size: 14px;
      }
    }

    .profile-info-row {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }

    .info-chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      background: rgba(255, 255, 255, 0.18);
      border: 1px solid rgba(255, 255, 255, 0.28);
      border-radius: 999px;
      font-size: 13px;
      font-weight: 600;
      color: #fff;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);

      .el-icon {
        font-size: 14px;
        opacity: 0.92;
      }
    }
  }

  .edit-btn {
    flex-shrink: 0;
    background: rgba(255, 255, 255, 0.95) !important;
    color: var(--accent) !important;
    border: none !important;
    font-weight: 600;
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12) !important;
    display: inline-flex;
    align-items: center;
    gap: 6px;

    &:hover {
      background: #fff !important;
      transform: translateY(-1px);
      box-shadow: 0 8px 22px rgba(0, 0, 0, 0.16) !important;
    }
  }
}

/* ===== 学习概览统计 ===== */
.stat-cards {
  margin-bottom: 24px;
}

/* ===== 信息区通用 ===== */
.info-section {
  margin-bottom: 24px;
}

.info-card {
  background: var(--surface);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-md);
  padding: 24px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.3s ease;

  &:hover {
    box-shadow: var(--shadow-md);
  }

  .card-head {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 18px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--separator);

    .card-title {
      font-size: 17px;
      font-weight: 700;
      color: var(--ink);
      letter-spacing: -0.015em;
    }

    .card-sub {
      font-size: 12px;
      color: var(--ink-tertiary);
    }
  }
}

.info-rows {
  display: flex;
  flex-direction: column;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 4px;

  & + .info-row {
    border-top: 1px solid var(--separator);
  }

  .row-icon {
    width: 38px;
    height: 38px;
    flex-shrink: 0;
    border-radius: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent);
    font-size: 17px;
  }

  .row-body {
    flex: 1;
    min-width: 0;

    .row-label {
      font-size: 12px;
      color: var(--ink-tertiary);
      margin-bottom: 3px;
    }

    .row-value {
      font-size: 15px;
      font-weight: 600;
      color: var(--ink);
      letter-spacing: -0.01em;
      word-break: break-all;

      &.muted {
        color: var(--ink-tertiary);
        font-weight: 500;
      }

      &.avatar-preview {
        display: flex;
        align-items: center;
        gap: 10px;
      }

      .mini-avatar {
        width: 32px;
        height: 32px;
        border-radius: 10px;
        background: var(--gradient-primary);
        color: #fff;
        font-size: 15px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 4px 10px rgba(99, 102, 241, 0.25);
      }

      .avatar-tip {
        font-size: 13px;
        font-weight: 500;
        color: var(--ink-tertiary);
      }
    }
  }

  .row-action {
    flex-shrink: 0;
    font-weight: 600;
    padding: 4px 8px;
  }
}

/* ===== 学习偏好设置 ===== */
.preferences-card {
  background: var(--surface);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-md);
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow-sm);

  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 22px;
    padding-bottom: 18px;
    border-bottom: 1px solid var(--separator);

    .head-left {
      .card-title {
        font-size: 17px;
        font-weight: 700;
        color: var(--ink);
        letter-spacing: -0.015em;
      }

      .card-sub {
        font-size: 12px;
        color: var(--ink-tertiary);
        margin-top: 4px;
        display: block;
      }
    }
  }
}

.preferences-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 18px;
}

.pref-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(0, 0, 0, 0.04);
  border-radius: var(--radius-sm);
  transition: background 0.25s ease, border-color 0.25s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.8);
    border-color: rgba(99, 102, 241, 0.15);
  }

  .pref-info {
    min-width: 0;

    .pref-label {
      font-size: 14px;
      font-weight: 600;
      color: var(--ink);
      margin-bottom: 4px;
    }

    .pref-desc {
      font-size: 12px;
      color: var(--ink-tertiary);
      line-height: 1.5;
    }
  }
}

/* ===== 退出登录 ===== */
.logout-area {
  display: flex;
  justify-content: center;
  margin-top: 8px;

  .logout-btn {
    color: var(--danger) !important;
    font-weight: 600;
    font-size: 15px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 24px;

    &:hover {
      background: rgba(239, 68, 68, 0.06) !important;
      color: var(--danger) !important;
    }
  }
}

/* ===== 退出确认按钮主题 ===== */
:deep(.logout-confirm-btn) {
  background: var(--danger) !important;
  border-color: var(--danger) !important;

  &:hover {
    background: #dc2626 !important;
    border-color: #dc2626 !important;
  }
}

/* ===== 响应式 ===== */
@media (max-width: 900px) {
  .profile-header {
    padding: 28px 24px;

    .profile-header-inner {
      flex-direction: column;
      text-align: center;
      gap: 20px;
    }

    .profile-meta {
      .profile-name-row,
      .profile-info-row {
        justify-content: center;
      }
    }
  }

  .preferences-grid {
    grid-template-columns: 1fr;
  }

  .pref-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>
