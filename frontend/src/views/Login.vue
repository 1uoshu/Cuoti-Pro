<template>
  <div class="auth-overlay">
    <div class="auth-container">
      <div class="auth-card">
        <!-- Logo -->
        <div class="auth-logo">
          <div class="auth-logo-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="white">
              <path d="M13 2L3 14h7l-1 8 10-12h-7l1-8z" />
            </svg>
          </div>
          <div class="auth-title">智学错题</div>
          <div class="auth-subtitle">AI 驱动的个性化学习伴侣</div>
        </div>

        <!-- Tab 切换 -->
        <div class="auth-tabs">
          <div class="auth-tab" :class="{ active: activeTab === 'login' }" @click="switchTab('login')">
            登录
          </div>
          <div class="auth-tab" :class="{ active: activeTab === 'register' }" @click="switchTab('register')">
            注册
          </div>
        </div>

        <!-- ============ 登录表单 ============ -->
        <el-form
          v-if="activeTab === 'login'"
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          class="auth-form"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="用户名"
              :prefix-icon="User"
              size="large"
              autocomplete="username"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="密码（8-72 个字符）"
              :prefix-icon="Lock"
              size="large"
              show-password
              autocomplete="current-password"
            />
          </el-form-item>

          <el-button
            type="primary"
            size="large"
            style="width: 100%; border-radius: 980px;"
            :loading="loading"
            @click="handleLogin"
          >
            {{ loading ? '安全验证中...' : '登录' }}
          </el-button>
        </el-form>

        <!-- ============ 注册表单 ============ -->
        <el-form
          v-else
          ref="registerFormRef"
          :model="registerForm"
          :rules="registerRules"
          class="auth-form"
          @submit.prevent="handleRegister"
        >
          <el-form-item prop="nickname">
            <el-input
              v-model="registerForm.nickname"
              placeholder="昵称（1-64 个字符）"
              :prefix-icon="User"
              size="large"
            />
          </el-form-item>
          <el-form-item prop="username">
            <el-input
              v-model="registerForm.username"
              placeholder="用户名（3-32 位字母/数字/下划线）"
              :prefix-icon="Message"
              size="large"
              autocomplete="username"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="registerForm.password"
              type="password"
              placeholder="设置密码（8-72 个字符）"
              :prefix-icon="Lock"
              size="large"
              show-password
              autocomplete="new-password"
              @input="checkPasswordStrength"
            />
            <div class="password-strength">
              <div class="strength-bar" :class="strengthClass[0]" />
              <div class="strength-bar" :class="strengthClass[1]" />
              <div class="strength-bar" :class="strengthClass[2]" />
            </div>
            <div class="strength-text" :style="{ color: strengthColor }">{{ strengthText }}</div>
          </el-form-item>
          <el-form-item prop="confirmPassword">
            <el-input
              v-model="registerForm.confirmPassword"
              type="password"
              placeholder="确认密码"
              :prefix-icon="Lock"
              size="large"
              show-password
              autocomplete="new-password"
            />
          </el-form-item>

          <!-- 可选扩展信息 -->
          <div class="optional-fields">
            <div class="optional-toggle" @click="showOptional = !showOptional">
              <el-icon><component :is="showOptional ? ArrowUp : ArrowDown" /></el-icon>
              {{ showOptional ? '收起' : '展开' }}更多信息（选填）
            </div>
            <transition name="fade">
              <div v-if="showOptional" class="optional-grid">
                <el-form-item prop="grade">
                  <el-input
                    v-model="registerForm.grade"
                    placeholder="年级（如：高三）"
                    size="large"
                  />
                </el-form-item>
                <el-form-item prop="main_subject">
                  <el-input
                    v-model="registerForm.main_subject"
                    placeholder="主修学科（如：数学）"
                    size="large"
                  />
                </el-form-item>
              </div>
            </transition>
          </div>

          <el-button
            type="primary"
            size="large"
            style="width: 100%; border-radius: 980px; margin-top: 8px;"
            :loading="loading"
            @click="handleRegister"
          >
            {{ loading ? '安全验证中...' : '注册并登录' }}
          </el-button>
        </el-form>

        <div class="auth-footer">角色由系统自动分配，首个注册用户为管理员</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Message, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const activeTab = ref('login')
const loading = ref(false)
const loginFormRef = ref()
const registerFormRef = ref()
const showOptional = ref(false)

/* ========== 登录表单 ========== */
const loginForm = reactive({
  username: 'demo',
  password: 'demo1234'
})

const loginRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '用户名长度 3-32 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' }
  ]
}

/* ========== 注册表单 ========== */
const registerForm = reactive({
  nickname: '',
  username: '',
  password: '',
  confirmPassword: '',
  grade: '',
  main_subject: ''
})

/** 用户名校验：仅 ASCII 字母、数字、下划线 */
function validateUsername(rule, value, callback) {
  if (!value) {
    callback(new Error('请输入用户名'))
    return
  }
  if (value.length < 3 || value.length > 32) {
    callback(new Error('用户名长度 3-32 个字符'))
    return
  }
  if (!/^[A-Za-z0-9_]+$/.test(value)) {
    callback(new Error('用户名只能包含字母、数字、下划线'))
    return
  }
  callback()
}

const registerRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { min: 1, max: 64, message: '昵称长度 1-64 个字符', trigger: 'blur' }
  ],
  username: [
    { validator: validateUsername, trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, max: 72, message: '密码长度 8-72 个字符', trigger: 'blur' }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (rule, value, callback) => {
        if (value !== registerForm.password) {
          callback(new Error('两次密码不一致'))
        } else {
          callback()
        }
      },
      trigger: 'blur'
    }
  ]
}

/* ========== 密码强度 ========== */
const strengthClass = ref(['', '', ''])
const strengthText = ref('')
const strengthColor = ref('var(--ink-tertiary)')

function checkPasswordStrength(password) {
  strengthClass.value = ['', '', '']

  if (!password) {
    strengthText.value = ''
    return
  }

  let strength = 0
  if (password.length >= 8) strength++
  if (password.length >= 12 && /[A-Z]/.test(password) && /[a-z]/.test(password)) strength++
  if (/\d/.test(password) && /[^A-Za-z0-9]/.test(password)) strength++

  if (strength === 0 || strength === 1) {
    strengthClass.value = ['active-1', '', '']
    strengthText.value = '弱'
    strengthColor.value = 'var(--danger)'
  } else if (strength === 2) {
    strengthClass.value = ['active-2', 'active-2', '']
    strengthText.value = '中'
    strengthColor.value = 'var(--warning)'
  } else {
    strengthClass.value = ['active-3', 'active-3', 'active-3']
    strengthText.value = '强'
    strengthColor.value = 'var(--success)'
  }
}

/* ========== Tab 切换 ========== */
function switchTab(tab) {
  activeTab.value = tab
  loading.value = false
}

/* ========== 登录 ========== */
async function handleLogin() {
  if (!loginFormRef.value) return
  const valid = await loginFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login({
      username: loginForm.username,
      password: loginForm.password
    })
    ElMessage.success('登录成功')
    router.push('/')
  } catch (e) {
    // request.js 已展示错误提示，此处不再重复
    console.warn('[Login] 登录失败:', e?.message || e)
  } finally {
    loading.value = false
  }
}

/* ========== 注册 ========== */
async function handleRegister() {
  if (!registerFormRef.value) return
  const valid = await registerFormRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.register({
      username: registerForm.username,
      password: registerForm.password,
      nickname: registerForm.nickname,
      grade: registerForm.grade || undefined,
      main_subject: registerForm.main_subject || undefined
    })
    ElMessage.success('注册成功')
    router.push('/')
  } catch (e) {
    // 409 用户名冲突时 request.js 已提示，此处不再重复
    console.warn('[Register] 注册失败:', e?.message || e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.auth-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background:
    radial-gradient(ellipse 60% 50% at 30% 20%, rgba(99, 102, 241, 0.15) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 70% 80%, rgba(139, 92, 246, 0.12) 0%, transparent 60%),
    radial-gradient(ellipse 80% 60% at 50% 50%, rgba(6, 182, 212, 0.06) 0%, transparent 70%),
    linear-gradient(180deg, #f8f9fc 0%, #eef2ff 100%);
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.auth-container {
  width: 100%;
  max-width: 440px;
}

.auth-card {
  background: rgba(255, 255, 255, 0.75);
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border-radius: var(--radius-lg);
  padding: 44px 38px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.1), 0 8px 24px rgba(99, 102, 241, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(255, 255, 255, 0.6);
}

.auth-logo {
  text-align: center;
  margin-bottom: 30px;

  .auth-logo-icon {
    width: 72px;
    height: 72px;
    background: var(--gradient-primary);
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 18px;
    box-shadow: 0 12px 32px rgba(99, 102, 241, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.3);
  }

  .auth-title {
    font-size: 25px;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin-bottom: 5px;
  }

  .auth-subtitle {
    font-size: 14px;
    color: var(--ink-tertiary);
  }
}

.auth-tabs {
  display: flex;
  gap: 4px;
  background: rgba(0, 0, 0, 0.04);
  padding: 4px;
  border-radius: var(--radius-sm);
  margin-bottom: 28px;

  .auth-tab {
    flex: 1;
    padding: 10px;
    border-radius: 10px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.25s;
    color: var(--ink-secondary);
    text-align: center;

    &.active {
      background: var(--surface-solid);
      color: var(--ink);
      box-shadow: var(--shadow-sm);
    }
  }
}

/* ===== 可选扩展信息 ===== */
.optional-fields {
  margin-bottom: 16px;

  .optional-toggle {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 13px;
    color: var(--accent);
    cursor: pointer;
    font-weight: 500;
    margin-bottom: 12px;
    user-select: none;

    &:hover {
      opacity: 0.8;
    }

    .el-icon {
      font-size: 14px;
    }
  }

  .optional-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
}

/* ===== 密码强度 ===== */
.password-strength {
  display: flex;
  gap: 4px;
  margin-top: 8px;
  width: 100%;

  .strength-bar {
    flex: 1;
    height: 3px;
    border-radius: 2px;
    background: rgba(0, 0, 0, 0.08);
    transition: background 0.3s;

    &.active-1 { background: var(--danger); }
    &.active-2 { background: var(--warning); }
    &.active-3 { background: var(--success); }
  }
}

.strength-text {
  font-size: 11px;
  margin-top: 4px;
}

.auth-footer {
  text-align: center;
  margin-top: 24px;
  font-size: 13px;
  color: var(--ink-tertiary);
  line-height: 1.5;
}

/* ===== 过渡 ===== */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

:deep(.el-input__wrapper) {
  border-radius: var(--radius-sm);
  padding: 14px 16px;
}
</style>
