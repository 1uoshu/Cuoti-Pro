import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api'

/**
 * userStore — 对接 Smart Learning Agent API 认证系统
 *
 * ## 登录流程
 *   GET /api/auth/pow/challenge → 客户端计算 PoW nonce
 *   → POST /api/auth/login { username, password, pow_challenge_id, pow_nonce }
 *   → 保存返回的 { user, access_token, token_type }
 *
 * ## 注册流程
 *   GET /api/auth/pow/challenge → 计算 PoW nonce
 *   → POST /api/auth/register { username, password, nickname, pow_challenge_id, pow_nonce }
 *   → 保存返回的 { user, access_token, token_type }
 *
 * ## 注意
 *   - 登录名使用的是后端 `username`（不是前端 Login.vue 旧的 `account` 字段）
 *   - 角色由后端自动分配（首用户 admin，后续 student）
 */

export const useUserStore = defineStore('user', () => {

  /* ========== State ========== */
  const token = ref(localStorage.getItem('token') || '')
  const userInfo = ref(JSON.parse(localStorage.getItem('userInfo') || 'null'))

  /* ========== Getters ========== */
  const isLoggedIn = computed(() => !!token.value)

  /* ========== Token 续期监听 ========== */
  // request.js 拦截到 Set-Token 响应头后 dispatch 此事件
  if (typeof window !== 'undefined') {
    window.addEventListener('token-refresh', (e) => {
      token.value = e.detail
    })
  }

  /* ============================================================
   *  PoW（Proof of Work）— 登录/注册前的工作量证明
   * ============================================================ */

  /**
   * 获取 PoW Challenge
   * @param {'login'|'register'} purpose
   * @returns {Promise<{challenge_id, purpose, difficulty, nonce_seed, expires_at}>}
   */
  async function getPowChallenge(purpose) {
    const res = await authApi.getPowChallenge(purpose)
    return res.data
  }

  /**
   * 计算 PoW — 寻找 nonce 使 SHA-256(seed:nonce) 以 difficulty 个 0 开头
   * @param {{ difficulty: number, nonce_seed: string }} challenge
   * @returns {Promise<number>} 找到的 nonce
   */
  async function solvePow(challenge) {
    const { difficulty, nonce_seed } = challenge

    // difficulty=0 时无需计算
    if (difficulty <= 0) return 0

    const target = '0'.repeat(difficulty)
    let nonce = 0
    const MAX_NONCE = 10_000_000

    async function sha256(message) {
      const encoder = new TextEncoder()
      const data = encoder.encode(message)
      const hashBuffer = await crypto.subtle.digest('SHA-256', data)
      const hashArray = Array.from(new Uint8Array(hashBuffer))
      return hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
    }

    while (nonce < MAX_NONCE) {
      const hash = await sha256(`${nonce_seed}:${nonce}`)
      if (hash.startsWith(target)) {
        return String(nonce)
      }
      nonce++

      // 每 2000 次让出主线程，防止 UI 卡顿
      if (nonce % 2000 === 0) {
        await new Promise(r => setTimeout(r, 0))
      }
    }

    throw new Error('PoW 求解失败（超过最大尝试次数）')
  }

  /**
   * 一键完成 PoW：获取 Challenge → 计算出 nonce
   * @param {'login'|'register'} purpose
   * @returns {Promise<{challenge_id: string, nonce: string}>}
   */
  async function solvePowFor(purpose) {
    const challenge = await getPowChallenge(purpose)
    const nonce = await solvePow(challenge)
    return { challenge_id: challenge.challenge_id, nonce }
  }

  /* ============================================================
   *  认证方法
   * ============================================================ */

  /**
   * 登录
   * @param {{ username: string, password: string }} form
   */
  async function login(form) {
    const pow = await solvePowFor('login')
    const res = await authApi.login({
      username: form.username,
      password: form.password,
      pow_challenge_id: pow.challenge_id,
      pow_nonce: pow.nonce
    })
    applyAuthData(res.data)
    return res
  }

  /**
   * 注册
   * @param {{ username: string, password: string, nickname: string, grade?: string, main_subject?: string }} form
   */
  async function register(form) {
    const pow = await solvePowFor('register')
    const res = await authApi.register({
      username: form.username,
      password: form.password,
      nickname: form.nickname,
      grade: form.grade || undefined,
      main_subject: form.main_subject || undefined,
      pow_challenge_id: pow.challenge_id,
      pow_nonce: pow.nonce
    })
    applyAuthData(res.data)
    return res
  }

  /**
   * 登出 — 调用后端 API + 清除本地状态
   */
  async function logout() {
    try {
      await authApi.logout()
    } catch (e) {
      // 后端登出是 best-effort（无状态确认），不影响本地清除
      console.warn('[logout] API 调用失败（已忽略）:', e?.message)
    }
    clearLocalState()
  }

  /**
   * 刷新用户信息 — GET /api/auth/me
   */
  async function fetchUserInfo() {
    const res = await authApi.getUserInfo()
    userInfo.value = res.data
    localStorage.setItem('userInfo', JSON.stringify(res.data))
    return res.data
  }

  /**
   * 更新个人资料 — PUT /api/auth/me
   * @param {{ nickname?: string, grade?: string|null, school?: string|null, main_subject?: string|null }} data
   */
  async function updateProfile(data) {
    const res = await authApi.updateProfile(data)
    userInfo.value = { ...userInfo.value, ...res.data }
    localStorage.setItem('userInfo', JSON.stringify(userInfo.value))
    return res.data
  }

  /**
   * 修改密码 — PUT /api/auth/password
   * @param {string} currentPassword
   * @param {string} newPassword
   */
  async function changePassword(currentPassword, newPassword) {
    const res = await authApi.changePassword({
      current_password: currentPassword,
      new_password: newPassword
    })
    return res.data
  }

  /* ============================================================
   *  内部工具
   * ============================================================ */

  /** 登录/注册成功后的统一处理 */
  function applyAuthData(data) {
    const { access_token, user } = data
    token.value = access_token
    userInfo.value = user
    localStorage.setItem('token', access_token)
    localStorage.setItem('userInfo', JSON.stringify(user))
  }

  /** 清除本地状态 */
  function clearLocalState() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }

  /** Pinia $reset 调用此方法 */
  function $reset() {
    clearLocalState()
  }

  return {
    // state
    token,
    userInfo,
    // getters
    isLoggedIn,
    // actions
    login,
    register,
    logout,
    fetchUserInfo,
    updateProfile,
    changePassword,
    // internal (for $reset)
    $reset
  }
})
