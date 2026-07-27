<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { CircleUserRound, KeyRound, Save, ShieldCheck } from 'lucide-vue-next'
import { api, errorMessage, request } from '../api'
import { useAuthStore } from '../stores/auth'
import type { User } from '../types'

interface ProfileForm {
  nickname: string
  grade: string
  school: string
  main_subject: string
}

interface PasswordForm {
  current_password: string
  new_password: string
  confirm_password: string
}

const auth = useAuthStore()
const profileFormRef = ref<FormInstance>()
const passwordFormRef = ref<FormInstance>()
const profileForm = ref<ProfileForm>({ nickname: '', grade: '', school: '', main_subject: '数学' })
const passwordForm = ref<PasswordForm>({ current_password: '', new_password: '', confirm_password: '' })
const profileLoading = ref(false)
const passwordLoading = ref(false)
const profileLoadError = ref('')

const profileRules: FormRules = {
  nickname: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { min: 1, max: 64, message: '昵称长度不能超过 64 个字符', trigger: 'blur' },
  ],
}

const passwordRules: FormRules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, max: 72, message: '新密码长度应为 8-72 个字符', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== passwordForm.value.new_password) callback(new Error('两次输入的新密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

function syncForm(user: User | null) {
  if (!user) return
  profileForm.value = {
    nickname: user.nickname || '',
    grade: user.grade || '',
    school: user.school || '',
    main_subject: user.main_subject || '数学',
  }
}

async function loadProfile() {
  profileLoadError.value = ''
  try {
    await auth.refreshProfile()
    syncForm(auth.user)
  } catch (loadError) {
    profileLoadError.value = errorMessage(loadError, '个人资料加载失败，请稍后重试')
    syncForm(auth.user)
  }
}

async function saveProfile() {
  try {
    await profileFormRef.value?.validate()
  } catch {
    return
  }

  profileLoading.value = true
  try {
    const updated = await request<User>(api.put('/auth/me', {
      nickname: profileForm.value.nickname.trim(),
      grade: profileForm.value.grade.trim() || null,
      school: profileForm.value.school.trim() || null,
      main_subject: profileForm.value.main_subject || null,
    }))
    auth.user = updated
    localStorage.setItem('smart-learning-user', JSON.stringify(updated))
    syncForm(updated)
    ElMessage.success('个人资料已更新')
  } catch (saveError) {
    ElMessage.error(errorMessage(saveError, '资料更新失败，请稍后重试'))
  } finally {
    profileLoading.value = false
  }
}

async function changePassword() {
  try {
    await passwordFormRef.value?.validate()
  } catch {
    return
  }

  if (passwordForm.value.current_password === passwordForm.value.new_password) {
    ElMessage.warning('新密码不能与当前密码相同')
    return
  }

  passwordLoading.value = true
  try {
    await request(api.put('/auth/password', {
      current_password: passwordForm.value.current_password,
      new_password: passwordForm.value.new_password,
    }))
    passwordForm.value = { current_password: '', new_password: '', confirm_password: '' }
    passwordFormRef.value?.clearValidate()
    ElMessage.success('密码已更新，请使用新密码登录')
  } catch (passwordError) {
    ElMessage.error(errorMessage(passwordError, '密码更新失败，请检查当前密码'))
  } finally {
    passwordLoading.value = false
  }
}

onMounted(() => {
  void loadProfile()
})
</script>

<template>
  <div class="stack-lg profile-view">
    <el-alert v-if="profileLoadError" type="error" show-icon :closable="false" role="alert" :title="profileLoadError" />

    <section class="profile-summary panel">
      <div class="profile-avatar" aria-hidden="true"><CircleUserRound :size="34" /></div>
      <div class="profile-summary-copy">
        <p class="page-context">账户概览</p>
        <h2>{{ auth.user?.nickname || '学习者' }}</h2>
        <p class="muted">{{ auth.user?.username || '当前账户' }}<template v-if="auth.user?.grade"> · {{ auth.user.grade }}</template><template v-if="auth.user?.main_subject"> · {{ auth.user.main_subject }}</template></p>
      </div>
      <div class="profile-security-note"><ShieldCheck :size="18" /><span>你的资料仅用于学习服务</span></div>
    </section>

    <div class="content-grid two-column profile-grid">
      <section class="panel profile-form-panel">
        <div class="panel-heading">
          <div><p class="page-context">基础信息</p><h3>个人资料</h3></div>
          <el-tag type="info" effect="plain">可随时修改</el-tag>
        </div>
        <el-form ref="profileFormRef" :model="profileForm" :rules="profileRules" label-position="top" @submit.prevent="saveProfile">
          <el-form-item label="昵称" prop="nickname">
            <el-input v-model="profileForm.nickname" maxlength="64" show-word-limit autocomplete="nickname" placeholder="例如：小林" />
          </el-form-item>
          <div class="form-row">
            <el-form-item label="年级" prop="grade">
              <el-input v-model="profileForm.grade" maxlength="32" placeholder="例如：高三" />
            </el-form-item>
            <el-form-item label="主要学科" prop="main_subject">
              <el-select v-model="profileForm.main_subject" class="full-width" placeholder="选择学科">
                <el-option label="数学" value="数学" />
                <el-option label="语文" value="语文" />
                <el-option label="英语" value="英语" />
                <el-option label="物理" value="物理" />
                <el-option label="化学" value="化学" />
              </el-select>
            </el-form-item>
          </div>
          <el-form-item label="学校" prop="school">
            <el-input v-model="profileForm.school" maxlength="128" placeholder="例如：第一中学" autocomplete="organization" />
          </el-form-item>
          <el-button native-type="submit" type="primary" :icon="Save" :loading="profileLoading">保存资料</el-button>
        </el-form>
      </section>

      <section class="panel profile-form-panel">
        <div class="panel-heading">
          <div><p class="page-context">账户安全</p><h3>修改密码</h3></div>
          <KeyRound :size="20" class="panel-heading-icon" aria-hidden="true" />
        </div>
        <p class="dialog-hint">修改密码后，其他设备上的旧登录状态可能需要重新登录。</p>
        <el-form ref="passwordFormRef" :model="passwordForm" :rules="passwordRules" label-position="top" @submit.prevent="changePassword">
          <el-form-item label="当前密码" prop="current_password">
            <el-input v-model="passwordForm.current_password" type="password" show-password autocomplete="current-password" />
          </el-form-item>
          <el-form-item label="新密码" prop="new_password">
            <el-input v-model="passwordForm.new_password" type="password" show-password autocomplete="new-password" placeholder="8-72 个字符" />
          </el-form-item>
          <el-form-item label="确认新密码" prop="confirm_password">
            <el-input v-model="passwordForm.confirm_password" type="password" show-password autocomplete="new-password" />
          </el-form-item>
          <el-button native-type="submit" type="primary" plain :icon="KeyRound" :loading="passwordLoading">更新密码</el-button>
        </el-form>
      </section>
    </div>
  </div>
</template>
