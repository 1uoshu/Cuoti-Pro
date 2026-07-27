import request from '@/utils/request'

// ===== 认证 API =====
export const authApi = {
  getPowChallenge: (purpose) =>
    request.get('/auth/pow/challenge', { params: { purpose } }),
  login: (data) => request.post('/auth/login', data),
  register: (data) => request.post('/auth/register', data),
  logout: () => request.post('/auth/logout'),
  getUserInfo: () => request.get('/auth/me'),
  updateProfile: (data) => request.put('/auth/me', data),
  changePassword: (data) => request.put('/auth/password', data)
}

// ===== Agent 会话 API =====
export const agentApi = {
  // 会话 CRUD
  createSession: (title = '新对话') =>
    request.post('/agent/sessions', null, { params: { title } }),
  listSessions: () =>
    request.get('/agent/sessions'),
  renameSession: (id, title) => {
    const form = new FormData()
    form.append('title', title)
    return request.patch(`/agent/sessions/${id}`, form)
  },
  deleteSession: (id) =>
    request.delete(`/agent/sessions/${id}`),

  // 消息
  listMessages: (sessionId, params = {}) =>
    request.get(`/agent/sessions/${sessionId}/messages`, { params }),
  sendMessage: (sessionId, content) => {
    const form = new FormData()
    form.append('content', content)
    return request.post(`/agent/sessions/${sessionId}/messages`, form)
  },

  // 上传
  upload: (file, subject, title, sessionId) => {
    const form = new FormData()
    form.append('file', file)
    form.append('subject', subject)
    if (title) form.append('title', title)
    if (sessionId) form.append('session_id', sessionId)
    return request.post('/agent/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  },

  // 事件回放
  replay: (sessionId, since) =>
    request.get(`/agent/sessions/${sessionId}/replay`, {
      params: since ? { since } : {}
    }),

  // Tab 联想
  addressSuggestions: (prefix = '') =>
    request.get('/agent/address-suggestions', { params: { prefix } })
}

// ===== 批改 API =====
export const gradingApi = {
  uploadAssignment: (formData) =>
    request.post('/assignments', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  getList: () => request.get('/assignments'),
  getDetail: (id) => request.get(`/assignments/${id}`),
  getTaskStatus: (taskId) => request.get(`/tasks/${taskId}`),
  feedback: (questionId, rating) => {
    const form = new FormData()
    form.append('rating', rating)
    return request.post(`/questions/${questionId}/feedback`, form)
  }
}

// ===== 错题本 API =====
export const wrongQuestionApi = {
  getList: (subject) =>
    request.get('/wrong-questions', { params: subject ? { subject } : {} }),
  getDetail: (questionId) =>
    request.get(`/wrong-questions/${questionId}`),
  updateStatus: (questionId, status) => {
    const form = new FormData()
    form.append('status', status)
    return request.patch(`/wrong-questions/${questionId}/status`, form)
  },
  confirmReview: (questionId) =>
    request.post(`/questions/${questionId}/confirm-review`)
}

// ===== 仪表盘 API =====
export const dashboardApi = {
  getStats: () => request.get('/dashboard')
}

// ===== 错题本 API（旧，保留兼容）=====
export const errorBookApi = {
  getList: (params) => request.get('/wrong-questions', { params })
}

// ===== 管理员 API =====
export const adminApi = {
  getConfig: () => request.get('/admin/config'),
  updateConfig: (data) => request.put('/admin/config', data),
  listUsers: (params) => request.get('/admin/users', { params })
}

export default {
  authApi, agentApi, gradingApi, wrongQuestionApi,
  dashboardApi, errorBookApi, adminApi
}
