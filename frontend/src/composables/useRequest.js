import { ref } from 'vue'

/**
 * useRequest — 统一 API 请求封装
 *
 * 消除各页面重复的 try-catch + console.warn + mock 回退模式。
 *
 * ## 基础用法（loading 由 composable 管理）
 *
 *   const { loading, request } = useRequest()
 *   await request(api.getData, {
 *     onSuccess: (data) => { table.value = data },
 *     warnMsg: '加载失败'
 *   })
 *
 * ## 注入外部 loading ref（如页面的 refreshing / questionLoading）
 *
 *   const refreshing = ref(false)
 *   const { request } = useRequest()
 *   await request(api.getData, {
 *     loading: refreshing,
 *     onSuccess: (data) => { ... },
 *     warnMsg: '刷新失败'
 *   })
 *
 * ## 带 mock 回退
 *
 *   await request(() => api.getQuestions({ difficulty }), {
 *     onSuccess: (data) => { questions.value = data },
 *     fallback: () => { questions.value = MOCK_DATA },
 *     warnMsg: '题目加载失败'
 *   })
 */
export function useRequest() {
  const loading = ref(false)
  const error = ref(null)

  /**
   * 执行请求
   * @param {Function} apiFn    — 返回 Promise 的 API 调用
   * @param {Object}   options
   * @param {Function} [options.onSuccess]  — 请求成功且数据存在时调用，传 data
   * @param {Function} [options.fallback]   — 请求失败或数据为空时调用
   * @param {string}   [options.warnMsg]    — warn 日志前缀
   * @param {Ref}      [options.loading]    — 外部 loading ref，不传则用内部 loading
   * @returns {Promise<*>}  data 或 null
   */
  async function request(apiFn, options = {}) {
    const { onSuccess, fallback, warnMsg = '[API] 请求失败', loading: loadingRef } = options
    const loadingState = loadingRef || loading

    loadingState.value = true
    error.value = null

    try {
      const res = await apiFn()
      // 处理后端标准格式 { code, data, message }，也兼容直接返回 data
      const data = res?.data !== undefined ? res.data : res
      if (data !== null && data !== undefined) {
        onSuccess?.(data)
        return data
      }
      // 后端返回了成功 code 但 data 为空
      fallback?.()
      return null
    } catch (e) {
      error.value = e
      console.warn(`${warnMsg}：`, e?.message || e)
      fallback?.()
      return null
    } finally {
      loadingState.value = false
    }
  }

  return { loading, error, request }
}
