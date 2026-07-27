<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { LockKeyhole, UserRound } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { errorMessage } from '../api'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const form = ref({ username: '', password: '', nickname: '', grade: '', main_subject: '数学' })

async function submit() {
  const username = form.value.username.trim()
  if (!username || !form.value.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  if (mode.value === 'register' && !/^[A-Za-z0-9_]{3,32}$/.test(username)) {
    ElMessage.warning('用户名需为 3-32 位字母、数字或下划线')
    return
  }
  if (mode.value === 'register' && form.value.password.length < 8) {
    ElMessage.warning('密码至少需要 8 位')
    return
  }
  if (mode.value === 'register' && !form.value.nickname.trim()) {
    ElMessage.warning('请输入昵称')
    return
  }
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(username, form.value.password)
    } else {
      await auth.register({
        username,
        password: form.value.password,
        nickname: form.value.nickname.trim(),
        grade: form.value.grade.trim() || undefined,
        main_subject: form.value.main_subject || undefined,
      })
    }
    await router.replace('/')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-intro">
      <div class="intro-content">
        <span class="brand-mark large">知</span>
        <p class="page-context">学习闭环</p>
        <h1>知错学习</h1>
        <p class="intro-copy">上传作业，定位错误，把每一次订正变成下一次掌握。</p>
        <img class="auth-visual" src="../assets/hero.png" alt="" aria-hidden="true" />
        <div class="intro-steps">
          <span>批改作业</span><i></i><span>归纳错题</span><i></i><span>针对练习</span>
        </div>
      </div>
    </section>

    <section class="auth-panel">
      <form class="auth-form" @submit.prevent="submit">
        <p class="page-context">学生入口</p>
        <h2>{{ mode === 'login' ? '继续你的学习' : '创建学习账号' }}</h2>
        <p class="muted">{{ mode === 'login' ? '登录后查看作业、错题和练习记录。' : '注册后即可开始上传和批改作业。' }}</p>

        <label v-if="mode === 'register'">昵称
          <el-input v-model="form.nickname" placeholder="如：小林" maxlength="64" autocomplete="nickname" required />
        </label>
        <label>用户名
          <el-input v-model="form.username" placeholder="3-32 位字母、数字或下划线" :prefix-icon="UserRound" autocomplete="username" required />
        </label>
        <label>密码
          <el-input v-model="form.password" type="password" show-password placeholder="至少 8 位" :prefix-icon="LockKeyhole" :autocomplete="mode === 'login' ? 'current-password' : 'new-password'" required />
        </label>
        <template v-if="mode === 'register'">
          <label>年级
            <el-input v-model="form.grade" placeholder="如：初二" maxlength="32" />
          </label>
          <label>主要学科
            <el-select v-model="form.main_subject" placeholder="选择学科">
              <el-option label="数学" value="数学" /><el-option label="语文" value="语文" />
              <el-option label="英语" value="英语" /><el-option label="物理" value="物理" />
              <el-option label="化学" value="化学" />
            </el-select>
          </label>
        </template>
        <el-button native-type="submit" type="primary" :loading="loading" class="full-width">
          {{ mode === 'login' ? '登录' : '注册并进入' }}
        </el-button>
        <p class="form-switch">
          {{ mode === 'login' ? '还没有账号？' : '已有账号？' }}
          <button type="button" @click="mode = mode === 'login' ? 'register' : 'login'">
            {{ mode === 'login' ? '注册' : '登录' }}
          </button>
        </p>
      </form>
    </section>
  </main>
</template>
