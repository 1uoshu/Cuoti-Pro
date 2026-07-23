import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

/**
 * Axios 实例 — 对接 Smart Learning Agent API
 *
 * 后端统一返回：{ code: 0, message: "success", data: {} }
 * 成功时 code 固定为 0；4xx 优先展示 message；5xx 使用通用失败提示
 */

const request = axios.create({
  baseURL: '/api',                // 配合 vite.config.js proxy
  timeout: 30000,                 // 默认 30s（练习提交等长耗时请求需单独覆盖）
  headers: { 'Content-Type': 'application/json' }
})

/* ========== 请求拦截器：自动携带 JWT ========== */
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

/* ========== 响应拦截器 ========== */
request.interceptors.response.use(
  // ---- 2xx 响应 ----
  (response) => {
    // Token 续期：后端在 token 接近过期时通过 Set-Token 响应头下发新 token
    const setToken = response.headers['set-token']
    if (setToken) {
      localStorage.setItem('token', setToken)
      window.dispatchEvent(new CustomEvent('token-refresh', { detail: setToken }))
    }

    const res = response.data

    // 成功：code === 0
    if (res.code === 0) {
      return res
    }

    // 业务错误（code !== 0），展示后端 message
    ElMessage.error(res.message || '请求失败')
    return Promise.reject(new Error(res.message || '请求失败'))
  },

  // ---- HTTP 错误 ----
  async (error) => {
    if (error.response) {
      const { status, data } = error.response
      const message = data?.message || ''

      switch (status) {
        case 401:
          // token 过期/无效 → 清除登录态, 跳转登录页
          await clearAuthState()
          ElMessage.error('登录已过期，请重新登录')
          router.push('/login')
          break

        case 403:
          ElMessage.error('没有权限访问')
          break

        case 404:
          ElMessage.error('请求的资源不存在')
          break

        case 405:
          ElMessage.error('请求方法不允许')
          break

        case 409:
          ElMessage.error(message || '资源冲突，请检查后重试')
          break

        case 422:
          // Pydantic 校验失败，展示第一个错误详情
          const firstErr = data?.data?.errors?.[0]
          ElMessage.error(firstErr?.msg || message || '请求参数校验失败')
          break

        case 429:
          ElMessage.error('操作过于频繁，请稍后重试')
          break

        default:
          // 5xx 服务端错误使用通用提示，不暴露内部细节
          if (status >= 500) {
            ElMessage.error('服务器内部错误，请稍后重试')
          } else {
            ElMessage.error(message || `请求失败 (${status})`)
          }
      }
    } else if (error.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，请检查网络后重试')
    } else {
      ElMessage.error('网络异常，请检查连接')
    }

    return Promise.reject(error)
  }
)

/**
 * 清除登录态 — 用于 401 时跳转
 * 使用动态 import 避免与 stores/user 循环引用
 */
async function clearAuthState() {
  try {
    const { useUserStore } = await import('@/stores/user')
    const store = useUserStore()
    store.$reset()
  } catch {
    localStorage.removeItem('token')
    localStorage.removeItem('userInfo')
  }
}

export default request
