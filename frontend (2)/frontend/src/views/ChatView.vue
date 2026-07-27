<template>
  <div class="chat-container">
    <!-- 左栏：会话列表 -->
    <aside class="session-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <el-button type="primary" @click="createNewSession" :icon="Plus" circle size="small" />
        <span v-if="!sidebarCollapsed" class="sidebar-title">我的对话</span>
      </div>
      <div class="session-list" v-if="!sidebarCollapsed">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSession?.id === session.id }"
          @click="switchSession(session)"
        >
          <div class="session-info">
            <div class="session-title">{{ session.title }}</div>
            <div class="session-time">{{ formatTime(session.last_active_at) }}</div>
          </div>
          <el-dropdown trigger="click" @command="handleSessionAction($event, session)" @click.stop>
            <el-icon class="session-more"><MoreFilled /></el-icon>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="rename">重命名</el-dropdown-item>
                <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <div v-if="sessions.length === 0 && !loadingSessions" class="session-empty">
          <p>暂无对话</p>
          <p class="hint">点击左上角 + 创建新对话</p>
        </div>
      </div>
    </aside>

    <!-- 折叠/展开按钮（始终可见，在 sidebar 外部） -->
    <div class="sidebar-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
      <el-icon :size="16"><Expand v-if="sidebarCollapsed" /><Fold v-else /></el-icon>
    </div>

    <!-- 右栏：聊天区 -->
    <main class="chat-main">
      <!-- 顶栏 -->
      <header class="chat-header">
        <h3>{{ currentSession?.title || '新对话' }}</h3>
        <div class="header-actions">
          <el-tag v-if="wsConnected" type="success" size="small" effect="dark">已连接</el-tag>
          <el-tag v-else type="info" size="small" effect="plain">未连接</el-tag>
        </div>
      </header>

      <!-- 消息流 -->
      <div class="message-list" ref="messageListRef">
        <div v-if="messages.length === 0 && !streamingText" class="empty-state">
          <el-icon :size="64" color="#c0c4cc"><ChatDotRound /></el-icon>
          <p class="empty-title">开始对话吧！</p>
          <p class="empty-hint">你可以问我任何学习问题，或者上传作业让我批改。</p>
        </div>
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-row"
          :class="msg.role"
        >
          <div class="message-avatar">
            <el-avatar v-if="msg.role === 'student'" :size="36" class="avatar-student">
              {{ userInitial }}
            </el-avatar>
            <el-avatar v-else :size="36" class="avatar-agent">AI</el-avatar>
          </div>
          <div class="message-body">
            <div class="message-content" v-html="renderContent(msg)" />
            <div class="message-time">{{ formatTime(msg.created_at) }}</div>
          </div>
        </div>

        <!-- 流式输出中（空消息 + 加载动画） -->
        <div v-if="waitingForReply" class="message-row agent">
          <div class="message-avatar">
            <el-avatar :size="36" class="avatar-agent">AI</el-avatar>
          </div>
          <div class="message-body">
            <div class="message-content loading">
              <span class="spinner"></span>
              <span class="loading-text">AI 正在思考...</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <!-- 文件预览 -->
        <div v-if="pendingFile" class="file-preview">
          <div class="file-chip">
            <el-icon><Document /></el-icon>
            <span class="file-name">{{ pendingFile.name }}</span>
            <span class="file-size">({{ formatFileSize(pendingFile.size) }})</span>
            <el-icon class="file-remove" @click="removePendingFile"><Close /></el-icon>
          </div>
          <el-select v-model="pendingSubject" placeholder="学科" size="small" style="width: 100px">
            <el-option label="数学" value="数学" />
            <el-option label="物理" value="物理" />
            <el-option label="化学" value="化学" />
            <el-option label="语文" value="语文" />
            <el-option label="英语" value="英语" />
            <el-option label="生物" value="生物" />
            <el-option label="历史" value="历史" />
            <el-option label="地理" value="地理" />
          </el-select>
        </div>

        <!-- 插件工具栏 -->
        <div class="plugin-toolbar">
          <div class="toolbar-label">可用工具：</div>
          <div class="plugin-chips">
            <div
              v-for="tool in availableTools"
              :key="tool.name"
              class="plugin-chip"
              :class="{ active: selectedTool === tool.name }"
              @click="selectTool(tool)"
              :title="tool.description"
            >
              <span class="chip-icon">🔧</span>
              <span class="chip-name">{{ tool.short_intent }}</span>
            </div>
          </div>
        </div>

        <!-- Tab 联想下拉 -->
        <div v-if="suggestions.length > 0" class="suggestions-dropdown">
          <div
            v-for="s in suggestions"
            :key="s.name"
            class="suggestion-item"
            @click="applySuggestion(s)"
          >
            <span class="suggestion-name">{{ s.name }}</span>
            <span class="suggestion-intent">{{ s.short_intent }}</span>
            <span class="suggestion-effect" :class="s.side_effect">{{ s.side_effect }}</span>
          </div>
        </div>

        <div class="input-toolbar">
          <el-upload
            :show-file-list="false"
            :before-upload="handleFileSelect"
            accept=".jpg,.jpeg,.png,.pdf"
          >
            <el-button :icon="Paperclip" circle size="small" />
          </el-upload>
        </div>
        <div class="input-row">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="1"
            :autosize="{ minRows: 1, maxRows: 4 }"
            :placeholder="selectedTool ? `使用 ${selectedTool} 中...` : (pendingFile ? '描述一下作业内容（可选）...' : '输入消息... (Shift+Enter 换行，Enter 发送)')"
            @keydown.enter.exact.prevent="sendMessage"
            @keydown="handleKeydown"
            @input="handleInput"
            ref="inputRef"
          />
          <el-button
            type="primary"
            @click="sendMessage"
            :loading="sending"
            :disabled="(!inputText.trim() && !pendingFile) || !currentSession"
          >
            发送
          </el-button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import {
  Plus, Fold, Expand, MoreFilled, Paperclip, ChatDotRound, Document, Close
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { useUserStore } from '@/stores/user'
import { agentApi } from '@/api'

const userStore = useUserStore()
const token = computed(() => userStore.token)
const userInitial = computed(() => (userStore.userInfo?.nickname || 'U')[0])

// ========== 状态 ==========
const sessions = ref([])
const currentSession = ref(null)
const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const waitingForReply = ref(false)  // 等待 Agent 回复（显示加载动画）
let currentAgentMsgId = null
const sidebarCollapsed = ref(false)
const messageListRef = ref(null)
const inputRef = ref(null)
const pendingFile = ref(null)
const pendingSubject = ref('数学')
const availableTools = ref([])
const selectedTool = ref('')
const suggestions = ref([])
const loadingSessions = ref(false)

// ========== WebSocket 状态（手动管理，支持会话切换） ==========
const wsConnected = ref(false)
let ws = null
let reconnectTimer = null
let reconnectAttempts = 0
const MAX_RECONNECT_ATTEMPTS = 10
const BASE_DELAY = 1000

function getWsUrl(sessionId) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  return `${protocol}//${host}/api/agent/ws?session_id=${sessionId}&token=${token.value}`
}

function wsConnect(sessionId) {
  wsDisconnect()
  if (!sessionId || !token.value) return

  try {
    ws = new WebSocket(getWsUrl(sessionId))
  } catch (e) {
    console.error('[WS] Failed to create WebSocket:', e)
    return
  }

  ws.onopen = () => {
    wsConnected.value = true
    reconnectAttempts = 0
    console.log('[WS] Connected to session', sessionId)
  }

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      // 后端事件用 data.event 字段，区分事件和普通消息
      if (data.event) {
        handleWsEvent(data)
      } else {
        handleWsMessage(data)
      }
    } catch (e) {
      console.warn('[WS] Failed to parse message:', event.data)
    }
  }

  ws.onerror = (e) => {
    console.error('[WS] Error:', e)
  }

  ws.onclose = (e) => {
    wsConnected.value = false
    console.log('[WS] Disconnected:', e.code, e.reason)

    // 认证失败不重连
    if (e.code === 4001) return

    // 自动重连
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS && currentSession.value?.id === sessionId) {
      const delay = BASE_DELAY * Math.pow(2, reconnectAttempts)
      reconnectTimer = setTimeout(() => {
        reconnectAttempts++
        console.log(`[WS] Reconnecting (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`)
        wsConnect(sessionId)
      }, delay)
    }
  }
}

function wsSend(data) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(typeof data === 'string' ? data : JSON.stringify(data))
  }
}

function wsSendMessage(content, tool = null) {
  const msg = { type: 'chat.message', content }
  if (tool) msg.tool = tool
  wsSend(msg)
}

function wsDisconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  if (ws) {
    ws.onclose = null // 阻止 onclose 中的重连逻辑
    ws.close()
    ws = null
  }
  wsConnected.value = false
  reconnectAttempts = 0
}

// ========== 生命周期 ==========
onMounted(async () => {
  await loadSessions()
  await loadTools()
  if (sessions.value.length > 0) {
    await switchSession(sessions.value[0])
  }
})

onUnmounted(() => {
  wsDisconnect()
})

// ========== 会话操作 ==========
async function loadSessions() {
  loadingSessions.value = true
  try {
    const res = await agentApi.listSessions()
    sessions.value = res.data || []
  } catch (e) {
    console.error('Failed to load sessions:', e)
  } finally {
    loadingSessions.value = false
  }
}

async function createNewSession() {
  try {
    const res = await agentApi.createSession()
    sessions.value.unshift(res.data)
    await switchSession(res.data)
  } catch (e) {
    ElMessage.error('创建会话失败')
  }
}

async function switchSession(session) {
  if (currentSession.value?.id === session.id) return

  // 断开旧会话的 WebSocket
  wsDisconnect()
  currentSession.value = session
  messages.value = []
  currentAgentMsgId = null
  waitingForReply.value = false

  try {
    const res = await agentApi.listMessages(session.id)
    messages.value = res.data || []
    await nextTick()
    scrollToBottom()

    // 连接新会话的 WebSocket
    wsConnect(session.id)
  } catch (e) {
    ElMessage.error('加载消息失败')
  }
}

async function handleSessionAction(action, session) {
  if (action === 'rename') {
    try {
      const { value } = await ElMessageBox.prompt('输入新标题', '重命名', {
        inputValue: session.title,
        confirmButtonText: '确定',
        cancelButtonText: '取消'
      })
      if (value && value.trim()) {
        await agentApi.renameSession(session.id, value.trim())
        session.title = value.trim()
      }
    } catch {
      // 用户取消
    }
  } else if (action === 'delete') {
    try {
      await ElMessageBox.confirm('确定删除这个会话？删除后无法恢复。', '删除', {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消'
      })
      await agentApi.deleteSession(session.id)
      sessions.value = sessions.value.filter(s => s.id !== session.id)
      if (currentSession.value?.id === session.id) {
        wsDisconnect()
        currentSession.value = null
        messages.value = []
        // 自动切换到下一个会话
        if (sessions.value.length > 0) {
          await switchSession(sessions.value[0])
        }
      }
    } catch {
      // 用户取消
    }
  }
}

// ========== 消息发送 ==========
async function sendMessage() {
  const text = inputText.value.trim()
  const file = pendingFile.value
  if ((!text && !file) || !currentSession.value) return

  inputText.value = ''
  sending.value = true

  // 如果有文件，先上传
  let uploadInfo = null
  if (file) {
    try {
      const res = await agentApi.upload(file, pendingSubject.value, file.name, currentSession.value.id)
      uploadInfo = res.data
    } catch (e) {
      ElMessage.error('文件上传失败')
      sending.value = false
      return
    }
    pendingFile.value = null

    // 上传成功，显示附件消息（只显示文件名，不显示系统信息）
    const studentMsg = {
      id: `student-${Date.now()}`,
      role: 'student',
      content: `[附件: ${file.name}]`,
      card_type: 'uploading',
      card_payload: uploadInfo,
      created_at: new Date().toISOString()
    }
    messages.value.push(studentMsg)

    // 复用已有的 Agent 气泡，如果没有才创建
    if (!currentAgentMsgId) {
      waitingForReply.value = true
      const agentMsg = {
        id: `agent-${Date.now()}`,
        role: 'agent',
        content: '',
        _streaming: true,
        created_at: new Date().toISOString()
      }
      messages.value.push(agentMsg)
      currentAgentMsgId = agentMsg.id
    }
    scrollToBottom()

    // 通过 WebSocket 告知后端有文件上传（带文字或空）
    // 不替用户说话，让后端意图识别根据图片内容判断
    const wsContent = text || '[用户上传了文件，未附带文字说明]'
    wsSendMessage(wsContent, selectedTool.value || null)
    selectedTool.value = ''
    sending.value = false
    return
  }

  // 纯文字消息
  const studentMsg = {
    id: `student-${Date.now()}`,
    role: 'student',
    content: text,
    card_type: null,
    card_payload: null,
    created_at: new Date().toISOString()
  }
  messages.value.push(studentMsg)

  // 复用已有的 Agent 气泡，如果没有才创建
  if (!currentAgentMsgId) {
    waitingForReply.value = true
    const agentMsg = {
      id: `agent-${Date.now()}`,
      role: 'agent',
      content: '',
      _streaming: true,
      created_at: new Date().toISOString()
    }
    messages.value.push(agentMsg)
    currentAgentMsgId = agentMsg.id
  }
  scrollToBottom()

  try {
    wsSendMessage(text, selectedTool.value || null)
    selectedTool.value = ''
  } catch (e) {
    ElMessage.error('发送失败')
  } finally {
    sending.value = false
  }
}

// ========== 文件上传 ==========
function handleFileSelect(file) {
  if (!currentSession.value) {
    ElMessage.warning('请先创建或选择一个会话')
    return false
  }
  // 存储文件，不立即上传
  pendingFile.value = file
  return false // 阻止 el-upload 自动上传
}

function removePendingFile() {
  pendingFile.value = null
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// ========== 插件工具栏 ==========
async function loadTools() {
  try {
    const res = await agentApi.addressSuggestions()
    availableTools.value = res.data || []
  } catch (e) {
    console.error('Failed to load tools:', e)
  }
}

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function selectTool(tool) {
  if (selectedTool.value === tool.name) {
    // 取消选择
    selectedTool.value = ''
    inputText.value = inputText.value.replace(new RegExp(`^${escapeRegex(tool.name)}\\s*`), '')
  } else {
    selectedTool.value = tool.name
    // 在输入框开头插入工具名
    if (!inputText.value.startsWith(tool.name)) {
      inputText.value = tool.name + ' ' + inputText.value
    }
  }
  inputRef.value?.focus()
}

// 输入变化时检查联想
function handleInput() {
  const text = inputText.value
  // 检查是否在输入 Plugin::Tool 格式
  const match = text.match(/([A-Za-z_]+::[A-Za-z_]*)$/)
  if (match) {
    const prefix = match[1].toLowerCase()
    suggestions.value = availableTools.value.filter(t =>
      t.name.toLowerCase().startsWith(prefix) ||
      t.short_intent.toLowerCase().includes(prefix)
    ).slice(0, 5)
  } else {
    suggestions.value = []
  }
}

// 应用联想
function applySuggestion(tool) {
  const text = inputText.value
  // 替换最后输入的前缀为完整工具名
  const replaced = text.replace(/([A-Za-z_]+::[A-Za-z_]*)$/, tool.name)
  inputText.value = replaced + ' '
  selectedTool.value = tool.name
  suggestions.value = []
  inputRef.value?.focus()
}

// 键盘事件（Tab 补全）
function handleKeydown(e) {
  if (e.key === 'Tab' && suggestions.value.length > 0) {
    e.preventDefault()
    applySuggestion(suggestions.value[0])
  } else if (e.key === 'Escape') {
    suggestions.value = []
  }
}

// ========== WebSocket 事件处理 ==========
function handleWsEvent(event) {
  switch (event.event) {
    case 'session.welcome':
      console.log('[Chat] Session welcome:', event.data)
      break

    case 'chat.text.delta':
      // 隐藏加载动画
      waitingForReply.value = false
      // 流式文本 → 追加到当前 Agent 消息
      if (currentAgentMsgId) {
        const msg = messages.value.find(m => m.id === currentAgentMsgId)
        if (msg) {
          msg.content += event.data.delta
          scrollToBottom()
        }
      }
      break

    case 'plan.step.tool_call':
      waitingForReply.value = false
      // 工具调用 → 显示进度卡片（带旋转动画）
      messages.value.push({
        id: `tool-${Date.now()}`,
        role: 'agent',
        content: '',
        card_type: 'tool_progress',
        card_payload: event.data,
        _progress: true,
        created_at: new Date().toISOString()
      })
      scrollToBottom()
      break

    case 'plan.step.tool_result':
      // 工具完成 → 更新进度卡片为结果卡片
      const progressMsg = messages.value.findLast(m => m.card_type === 'tool_progress' && m._progress)
      if (progressMsg) {
        progressMsg._progress = false
        progressMsg.card_type = 'tool_result'
        progressMsg.card_payload = event.data.result
      } else {
        messages.value.push({
          id: `result-${Date.now()}`,
          role: 'agent',
          content: '',
          card_type: 'tool_result',
          card_payload: event.data.result,
          created_at: new Date().toISOString()
        })
      }
      scrollToBottom()
      break

    case 'plan.step.error':
      messages.value.push({
        id: `error-${Date.now()}`,
        role: 'agent',
        content: event.data.error,
        card_type: 'error',
        created_at: new Date().toISOString()
      })
      scrollToBottom()
      break

    case 'plan.done':
      waitingForReply.value = false
      // 流式结束 → 标记当前 Agent 消息为已完成
      if (currentAgentMsgId) {
        const msg = messages.value.find(m => m.id === currentAgentMsgId)
        if (msg) {
          msg._streaming = false
          if (!msg.content && !msg.card_type) {
            messages.value = messages.value.filter(m => m.id !== currentAgentMsgId)
          }
        }
        currentAgentMsgId = null
      }
      break

    default:
      console.log('[Chat] Unhandled event:', event.type, event.data)
  }
}

function handleWsMessage(msg) {
  console.log('[Chat] Raw message:', msg)
}

// ========== 辅助函数 ==========
// 配置 marked
marked.setOptions({
  breaks: true,     // 支持换行
  gfm: true,        // GitHub 风格 Markdown
})

function renderContent(msg) {
  if (msg.card_type === 'tool_progress') {
    const toolName = msg.card_payload?.tool_name || '处理中'
    const intent = msg.card_payload?.intent || ''
    return `<div class="card tool-progress"><span class="spinner"></span><strong>${escapeHtml(toolName)}</strong>${intent ? '<br/>' + escapeHtml(intent) : ''}</div>`
  }
  if (msg.card_type === 'tool_call') {
    return `<div class="card tool-call"><strong>🔧 工具调用</strong><br/>${escapeHtml(msg.card_payload?.tool_name || '')}</div>`
  }
  if (msg.card_type === 'tool_result') {
    // 结果卡片：显示工具名和输出摘要
    const payload = msg.card_payload
    let detail = ''
    if (payload && typeof payload === 'object') {
      // python_verify 结果
      if (payload.ok !== undefined) {
        detail = payload.ok
          ? `<pre>${escapeHtml(String(payload.value || '').slice(0, 500))}</pre>`
          : `<span class="error-text">${escapeHtml(String(payload.error || '').slice(0, 300))}</span>`
      } else {
        detail = `<pre>${escapeHtml(JSON.stringify(payload, null, 2).slice(0, 500))}</pre>`
      }
    }
    return `<div class="card tool-result"><strong>✅ 工具输出</strong>${detail ? '<br/>' + detail : ''}</div>`
  }
  if (msg.card_type === 'uploading') {
    return `<div class="card uploading-card"><strong>📎 上传中</strong><br/>${escapeHtml(msg.content)}</div>`
  }
  if (msg.card_type === 'error') {
    return `<div class="card error-card"><strong>❌ 出错</strong><br/>${escapeHtml(msg.content)}</div>`
  }
  // Agent 消息用 Markdown 渲染，学生消息纯文本
  const content = msg.content || ''
  let html
  if (msg.role === 'agent') {
    html = marked.parse(content)
  } else {
    html = escapeHtml(content).replace(/\n/g, '<br/>')
  }
  // 流式消息显示光标
  if (msg._streaming && html) {
    return html.replace(/<\/p>$/, '<span class="cursor">|</span></p>')
      || html + '<span class="cursor">|</span>'
  }
  return html
}

function escapeHtml(text) {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const time = d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return time
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) + ' ' + time
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}
</script>

<style scoped>
/* ========== 容器布局 ========== */
.chat-container {
  display: flex;
  height: 100vh;
  background: #f5f7fa;
  overflow: hidden;
}

/* ========== 左栏：会话侧边栏 ========== */
.session-sidebar {
  width: 260px;
  min-width: 260px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease, min-width 0.3s ease;
}
.session-sidebar.collapsed {
  width: 0;
  min-width: 0;
  overflow: hidden;
  border-right: none;
}

/* 折叠/展开按钮（始终可见） */
.sidebar-toggle {
  width: 24px;
  min-width: 24px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #909399;
  transition: color 0.2s, background 0.2s;
}
.sidebar-toggle:hover {
  color: #409eff;
  background: #ecf5ff;
}

.sidebar-header {
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}
.sidebar-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.session-item {
  padding: 12px 16px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background 0.2s;
}
.session-item:hover {
  background: #f5f7fa;
}
.session-item.active {
  background: #ecf5ff;
  border-left: 3px solid #409eff;
  padding-left: 13px;
}
.session-info {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.session-title {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-time {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.session-more {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
  cursor: pointer;
  color: #909399;
}
.session-more:hover {
  color: #409eff;
}
.session-item:hover .session-more {
  opacity: 1;
}

.session-empty {
  padding: 32px 16px;
  text-align: center;
  color: #909399;
  font-size: 13px;
}
.session-empty .hint {
  font-size: 12px;
  color: #c0c4cc;
  margin-top: 4px;
}

/* ========== 右栏：聊天区 ========== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.chat-header {
  padding: 12px 20px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}
.chat-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ========== 消息流 ========== */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  scroll-behavior: smooth;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
  user-select: none;
}
.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: #606266;
  margin: 16px 0 8px;
}
.empty-hint {
  font-size: 14px;
  color: #c0c4cc;
}

/* ========== 消息行 ========== */
.message-row {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  animation: fadeIn 0.3s ease;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-row.student {
  flex-direction: row-reverse;
}
.message-row.student .message-body {
  align-items: flex-end;
}

.message-avatar {
  flex-shrink: 0;
}
.avatar-student {
  background: linear-gradient(135deg, #667eea, #764ba2);
  color: #fff;
  font-weight: 600;
}
.avatar-agent {
  background: linear-gradient(135deg, #409eff, #53a8ff);
  color: #fff;
  font-weight: 700;
  font-size: 13px;
}

.message-body {
  display: flex;
  flex-direction: column;
  max-width: 70%;
  min-width: 0;
}

.message-content {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}
.student .message-content {
  background: linear-gradient(135deg, #409eff, #53a8ff);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.agent .message-content {
  background: #fff;
  color: #303133;
  border: 1px solid #e4e7ed;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

/* 工具卡片样式 */
.message-content :deep(.card) {
  padding: 10px 12px;
  border-radius: 8px;
  margin: 4px 0;
  font-size: 13px;
}
.message-content :deep(.card strong) {
  display: inline-block;
  margin-bottom: 4px;
}
.message-content :deep(.tool-call) {
  background: #fdf6ec;
  border: 1px solid #e6a23c;
  color: #e6a23c;
}
.message-content :deep(.tool-progress) {
  background: #e6f7ff;
  border: 1px solid #91d5ff;
  color: #1890ff;
  display: flex;
  align-items: center;
  gap: 10px;
}
.message-content :deep(.spinner) {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid #91d5ff;
  border-top: 2px solid #1890ff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  flex-shrink: 0;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.message-content :deep(.tool-result) {
  background: #f0f9eb;
  border: 1px solid #67c23a;
  color: #67c23a;
}
.message-content :deep(.tool-result pre) {
  margin: 4px 0 0;
  white-space: pre-wrap;
  font-size: 12px;
  color: #606266;
  max-height: 200px;
  overflow-y: auto;
}
.message-content :deep(.error-text) {
  color: #f56c6c;
  font-size: 12px;
}
.message-content :deep(.error-card) {
  background: #fef0f0;
  border: 1px solid #f56c6c;
  color: #f56c6c;
}

.message-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
  padding: 0 4px;
}

/* 文件预览 */
.file-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: #f0f9eb;
  border: 1px solid #b3e19d;
  border-radius: 8px;
  margin-bottom: 8px;
}
.file-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
}
.file-name { font-weight: 500; }
.file-size { color: #909399; font-size: 12px; }
.file-remove { cursor: pointer; color: #f56c6c; }
.file-remove:hover { color: #f00; }

/* 上传中卡片 */
.card.uploading-card {
  background: #e6f7ff;
  border: 1px solid #91d5ff;
}

/* Markdown 内容样式 */
.message-content :deep(p) { margin: 0 0 8px 0; }
.message-content :deep(p:last-child) { margin-bottom: 0; }
.message-content :deep(ul), .message-content :deep(ol) { margin: 4px 0; padding-left: 20px; }
.message-content :deep(code) {
  background: #f5f7fa;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  font-family: 'Consolas', 'Monaco', monospace;
}
.message-content :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}
.message-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}
.message-content :deep(blockquote) {
  border-left: 3px solid #409eff;
  margin: 8px 0;
  padding: 4px 12px;
  color: #606266;
  background: #f5f7fa;
  border-radius: 0 4px 4px 0;
}
.message-content :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
}
.message-content :deep(th), .message-content :deep(td) {
  border: 1px solid #e4e7ed;
  padding: 6px 12px;
  text-align: left;
}
.message-content :deep(th) { background: #f5f7fa; font-weight: 600; }
.message-content :deep(h1), .message-content :deep(h2), .message-content :deep(h3) {
  margin: 12px 0 8px 0;
  font-weight: 600;
}
.message-content :deep(h1) { font-size: 1.3em; }
.message-content :deep(h2) { font-size: 1.2em; }
.message-content :deep(h3) { font-size: 1.1em; }
.message-content :deep(hr) {
  border: none;
  border-top: 1px solid #e4e7ed;
  margin: 12px 0;
}

/* 流式光标 */
.cursor {
  animation: blink 0.8s infinite;
  color: #409eff;
  font-weight: 300;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 加载动画（三个点跳动） */
.dot-typing {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #909399;
  animation: dotTyping 1.2s infinite ease-in-out;
  position: relative;
}
.dot-typing::before,
.dot-typing::after {
  content: '';
  position: absolute;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #909399;
}
.dot-typing::before {
  left: -10px;
  animation: dotTyping 1.2s infinite ease-in-out 0.2s;
}
.dot-typing::after {
  left: 10px;
  animation: dotTyping 1.2s infinite ease-in-out 0.4s;
}
@keyframes dotTyping {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

/* 加载状态 */
.message-content.loading {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #909399;
  font-size: 13px;
}
.loading-text {
  animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 1; }
}

/* ========== 输入区 ========== */
.input-area {
  background: #fff;
  border-top: 1px solid #e4e7ed;
  padding: 12px 20px;
  flex-shrink: 0;
  position: relative;
}
.input-toolbar {
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.input-row {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}
.input-row .el-textarea {
  flex: 1;
}

/* 插件工具栏 */
.plugin-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  overflow-x: auto;
}
.toolbar-label {
  font-size: 12px;
  color: #909399;
  flex-shrink: 0;
}
.plugin-chips {
  display: flex;
  gap: 6px;
  flex-wrap: nowrap;
  overflow-x: auto;
}
.plugin-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 16px;
  font-size: 12px;
  color: #606266;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.plugin-chip:hover {
  background: #ecf5ff;
  border-color: #b3d8ff;
  color: #409eff;
}
.plugin-chip.active {
  background: #409eff;
  border-color: #409eff;
  color: #fff;
}
.chip-icon { font-size: 12px; }
.chip-name { font-weight: 500; }

/* Tab 联想下拉 */
.suggestions-dropdown {
  position: absolute;
  bottom: 100%;
  left: 0;
  right: 0;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 -4px 12px rgba(0,0,0,0.1);
  max-height: 200px;
  overflow-y: auto;
  z-index: 100;
}
.suggestion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 13px;
}
.suggestion-item:hover {
  background: #f5f7fa;
}
.suggestion-name {
  font-weight: 600;
  color: #303133;
}
.suggestion-intent {
  color: #909399;
  flex: 1;
}
.suggestion-effect {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}
.suggestion-effect.read { background: #f0f9eb; color: #67c23a; }
.suggestion-effect.write { background: #fdf6ec; color: #e6a23c; }
.suggestion-effect.send { background: #fef0f0; color: #f56c6c; }

/* ========== 移动端适配 ========== */
@media (max-width: 768px) {
  .session-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 1000;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.1);
  }
  .session-sidebar.collapsed {
    box-shadow: none;
  }
  .message-body {
    max-width: 85%;
  }
}
</style>
