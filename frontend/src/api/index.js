import request from '@/utils/request'

/**
 * API 接口定义 — 对接 Smart Learning Agent API
 *
 * 后端统一返回：{ code: 0, data: {...}, message: "success" }
 * request.js 拦截器已处理 code === 0 为成功
 *
 * ── 各 API 模块分工 ──
 *   authApi      →  你（张涵）
 *   uploadApi    →  你
 *   errorBookApi →  你
 *   knowledgeApi →  队友
 *   profileApi   →  队友
 *   reviewApi    →  队友（预览，保留 mock）
 *   assessmentApi → 队友（预览，保留 mock）
 *   trackingApi  →  队友（预览，保留 mock）
 */

// ===== 认证 API =====
export const authApi = {
  /** 获取 PoW Challenge（登录/注册前调用） */
  getPowChallenge: (purpose) =>
    request.get('/auth/pow/challenge', { params: { purpose } }),

  /** 登录 POST /api/auth/login */
  login: (data) => request.post('/auth/login', data),

  /** 注册 POST /api/auth/register */
  register: (data) => request.post('/auth/register', data),

  /** 登出 POST /api/auth/logout */
  logout: () => request.post('/auth/logout'),

  /** 获取当前用户信息 GET /api/auth/me */
  getUserInfo: () => request.get('/auth/me'),

  /** 更新个人信息 PUT /api/auth/me */
  updateProfile: (data) => request.put('/auth/me', data),

  /** 修改密码 PUT /api/auth/password */
  changePassword: (data) => request.put('/auth/password', data)
}

// ===== 作业上传与批改 =====
export const uploadApi = {
  /** 上传作业 POST /api/assignments (multipart) */
  uploadAssignment: (formData) => request.post('/assignments', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000
  }),

  /** 轮询任务进度 GET /api/tasks/{taskId} */
  getTaskStatus: (taskId) => request.get(`/tasks/${taskId}`),

  /** 作业列表 GET /api/assignments */
  getList: () => request.get('/assignments'),

  /** 作业详情（含题目）GET /api/assignments/{id} */
  getDetail: (id) => request.get(`/assignments/${id}`),

  /** 修正题目 PUT /api/questions/{questionId} */
  updateQuestion: (questionId, data) => request.put(`/questions/${questionId}`, data)
}

// ===== 学习仪表盘 =====
export const dashboardApi = {
  /** 首页统计 GET /api/dashboard */
  getStats: () => request.get('/dashboard')
}

// ===== 练习（对应后端 /practice 系列）=====
export const knowledgeApi = {
  /** 生成练习题 POST /api/practice/generate (form-urlencoded) */
  getQuestions: (params) => request.post('/practice/generate',
    `student_id=${getSid()}&weak_points=${encodeURIComponent(params.weak_points || '')}&difficulty=${params.difficulty || 'base'}`,
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  ),

  /** 提交答案 POST /api/practice/answer (form-urlencoded) */
  submitAnswer: (data) => request.post('/practice/answer',
    `student_id=${getSid()}&question_json=${encodeURIComponent(JSON.stringify(data))}&student_answer=${encodeURIComponent(data.answer || '')}`,
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  ),

  /** 掌握度列表 — 后端暂无独立接口，从错题数据推导 */
  getMastery: () => request.get(`/mistakes/${getSid()}`)
}

// ===== 复盘（对应后端 /review/{student_id}）=====
export const reviewApi = {
  /** 获取复盘报告 GET /api/review/{student_id}?period=xxx */
  getStats: (period) => request.get(`/review/${getSid()}`, { params: { period } })
}

// ===== 组卷（对应后端 /exam 系列）=====
export const assessmentApi = {
  /** 生成试卷 POST /api/exam/generate */
  generatePaper: (data) => request.post('/exam/generate', { student_id: getSid(), ...data }),

  /** 批改试卷 POST /api/exam/grade (form-urlencoded) */
  gradeExam: (data) => request.post('/exam/grade',
    `student_id=${getSid()}&exam_json=${encodeURIComponent(data.exam_json || '{}')}&answers_json=${encodeURIComponent(data.answers_json || '{}')}`,
    { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
  )
}

// ===== 追踪（对应后端 /tracker/{student_id}）=====
export const trackingApi = {
  /** 获取追踪数据 GET /api/tracker/{student_id} */
  getTracker: () => request.get(`/tracker/${getSid()}`)
}

// ===== 错题本 =====
export const errorBookApi = {
  /** 错题列表 GET /api/wrong-questions?subject=xxx */
  getList: (params) => request.get('/wrong-questions', { params })
}

// ===== 个人中心（后端暂无独立接口，用 mock）=====
export const profileApi = {
  getProfile: () => request.get('/auth/userinfo'),
  getLearningStats: () => request.get('/auth/userinfo'),
  updatePreferences: (data) => request.put('/auth/profile', data)
}

export default {
  authApi,
  uploadApi,
  knowledgeApi,
  reviewApi,
  assessmentApi,
  trackingApi,
  errorBookApi,
  profileApi
}
