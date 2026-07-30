<template>
  <div class="chat-container">
    <!-- 左栏：会话列表 -->
    <aside class="session-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <div class="brand">
          <div class="brand-icon">
            <el-icon :size="20"><ChatDotRound /></el-icon>
          </div>
          <span class="brand-text">智学错题Agent</span>
        </div>
        <el-icon class="menu-toggle" :size="18" @click="sidebarCollapsed = !sidebarCollapsed">
          <Menu />
        </el-icon>
      </div>
      <div class="session-list" v-if="!sidebarCollapsed">
        <div class="new-chat-wrap">
          <el-button class="new-chat-btn" @click="createNewSession" :icon="Plus">
            <span>新建会话</span>
          </el-button>
        </div>
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
          <p class="hint">点击上方「新对话」开始</p>
        </div>
      </div>

      <!-- 侧边栏底部：错题本 -->
      <div v-if="!sidebarCollapsed" class="sidebar-footer">
        <el-button class="wrong-questions-btn" plain @click="goToWrongQuestions">
          <el-icon><Collection /></el-icon>
          <span>错题本</span>
        </el-button>
      </div>
    </aside>

    <!-- 右栏：聊天区 -->
    <main class="chat-main">
      <!-- 折叠态左上角 menu 按钮 -->
      <div
        v-if="sidebarCollapsed"
        class="floating-menu-btn"
        @click="sidebarCollapsed = false"
      >
        <el-icon :size="18"><Menu /></el-icon>
      </div>

      <!-- 顶栏 -->
      <header class="chat-header" :class="{ 'with-menu-offset': sidebarCollapsed }">
        <div class="header-title">
          <h3>{{ currentSession?.title || '新对话' }}</h3>
        </div>
      </header>

      <!-- 消息流 -->
      <div
        class="message-list"
        :class="{ 'with-margin': sidebarCollapsed }"
        ref="messageListRef"
      >
        <div v-if="messages.length === 0 && !waitingForReply" class="empty-state">
          <div class="empty-avatar">
            <el-icon :size="48"><ChatDotRound /></el-icon>
          </div>
          <p class="empty-title">有什么可以帮你的？</p>
          <p class="empty-hint">你可以问我任何学习问题，或者上传作业让我批改。</p>
          <div class="quick-prompts">
            <div
              v-for="prompt in quickPrompts"
              :key="prompt"
              class="quick-prompt"
              @click="applyQuickPrompt(prompt)"
            >
              {{ prompt }}
            </div>
          </div>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-row"
          :class="msg.role"
        >
          <div class="message-body">
            <div class="message-content" v-html="renderContent(msg)" />
            <div class="message-meta">
              <span class="message-time">{{ formatTime(msg.created_at) }}</span>
              <el-button
                v-if="msg.role === 'agent' && !msg._streaming && !msg.card_type"
                class="copy-btn"
                size="small"
                text
                :icon="CopyDocument"
                @click="copyMessage(msg)"
              >
                复制
              </el-button>
            </div>
          </div>
        </div>

        <!-- 流式输出中 -->
        <div v-if="waitingForReply" class="message-row agent">
          <div class="message-body">
            <div class="message-content loading">
              <span class="thinking-dots">
                <span></span><span></span><span></span>
              </span>
              <span class="loading-text">AI 正在思考…</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-wrapper">
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

          <div class="input-row">
            <el-upload
              :show-file-list="false"
              :before-upload="handleFileSelect"
              accept=".jpg,.jpeg,.png,.pdf"
            >
              <el-button class="attach-btn" :icon="Paperclip" circle />
            </el-upload>
            <el-input
              v-model="inputText"
              class="chat-input"
              type="textarea"
              :rows="1"
              :autosize="{ minRows: 1, maxRows: 6 }"
              :placeholder="inputPlaceholder"
              @keydown.enter.exact.prevent="sendMessage"
              @keydown="handleKeydown"
              @input="handleInput"
              ref="inputRef"
            />
            <el-button
              class="send-btn"
              type="primary"
              circle
              :icon="Promotion"
              @click="sendMessage"
              :loading="sending"
              :disabled="(!inputText.trim() && !pendingFile) || !currentSession"
            />
          </div>
        </div>
      </div>
      <div class="input-disclaimer">AI 生成内容仅供参考，可能存在错误，请自行核实。</div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  Plus, Fold, Expand, MoreFilled, Paperclip, ChatDotRound,
  Document, Close, Collection, Promotion, CopyDocument, Menu
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import { useUserStore } from '@/stores/user'
import { agentApi } from '@/api'

const router = useRouter()

const userStore = useUserStore()
const token = computed(() => userStore.token)
const userInitial = computed(() => (userStore.userInfo?.nickname || 'U')[0])

// ========== 状态 ==========
const sessions = ref([])
const currentSession = ref(null)
const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const waitingForReply = ref(false)
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

const quickPrompts = [
  '这道数学题怎么解？',
  '分析我的错题薄弱点',
  '这道物理题怎么解？',
  '帮我总结今天的知识点'
]

const inputPlaceholder = computed(() => {
  if (selectedTool.value) return `使用 ${selectedTool.value} 中…`
  if (pendingFile.value) return '描述一下作业内容（可选）…'
  return '输入消息…'
})

// ========== WebSocket 状态 ==========
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
    if (e.code === 4001) return
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
  } else {
    console.warn('[WS] Cannot send - WebSocket not open. State:', ws?.readyState)
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
    ws.onclose = null
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

  if (file) {
    let uploadInfo = null
    try {
      const res = await agentApi.upload(file, pendingSubject.value, file.name, currentSession.value.id)
      uploadInfo = res.data
    } catch (e) {
      ElMessage.error('文件上传失败')
      sending.value = false
      return
    }
    pendingFile.value = null

    const studentMsg = {
      id: `student-${Date.now()}`,
      role: 'student',
      content: `[附件: ${file.name}]`,
      card_type: 'uploading',
      card_payload: uploadInfo,
      created_at: new Date().toISOString()
    }
    messages.value.push(studentMsg)

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

    const wsContent = text || '[用户上传了文件，未附带文字说明]'
    wsSendMessage(wsContent, selectedTool.value || null)
    selectedTool.value = ''
    sending.value = false
    return
  }

  const studentMsg = {
    id: `student-${Date.now()}`,
    role: 'student',
    content: text,
    card_type: null,
    card_payload: null,
    created_at: new Date().toISOString()
  }
  messages.value.push(studentMsg)

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

// ========== 快捷问题 ==========
function applyQuickPrompt(prompt) {
  inputText.value = prompt
  inputRef.value?.focus()
}

// ========== 文件上传 ==========
function handleFileSelect(file) {
  if (!currentSession.value) {
    ElMessage.warning('请先创建或选择一个会话')
    return false
  }
  pendingFile.value = file
  return false
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
    selectedTool.value = ''
    inputText.value = inputText.value.replace(new RegExp(`^${escapeRegex(tool.name)}\\s*`), '')
  } else {
    selectedTool.value = tool.name
    if (!inputText.value.startsWith(tool.name)) {
      inputText.value = tool.name + ' ' + inputText.value
    }
  }
  inputRef.value?.focus()
}

function handleInput() {
  const text = inputText.value
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

function applySuggestion(tool) {
  const text = inputText.value
  const replaced = text.replace(/([A-Za-z_]+::[A-Za-z_]*)$/, tool.name)
  inputText.value = replaced + ' '
  selectedTool.value = tool.name
  suggestions.value = []
  inputRef.value?.focus()
}

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
      waitingForReply.value = false
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
marked.setOptions({
  breaks: true,
  gfm: true,
})

function renderContent(msg) {
  if (msg.card_type === 'tool_progress') {
    const toolName = msg.card_payload?.tool_name || '处理中'
    const intent = msg.card_payload?.intent || ''
    return `<div class="card tool-progress"><span class="spinner"></span><div><strong>${escapeHtml(toolName)}</strong>${intent ? '<br/>' + escapeHtml(intent) : ''}</div></div>`
  }
  if (msg.card_type === 'tool_call') {
    return `<div class="card tool-call"><strong>🔧 工具调用</strong><br/>${escapeHtml(msg.card_payload?.tool_name || '')}</div>`
  }
  if (msg.card_type === 'tool_result') {
    const payload = msg.card_payload
    let detail = ''
    if (payload && typeof payload === 'object') {
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
  const content = msg.content || ''
  let html
  if (msg.role === 'agent') {
    html = marked.parse(content)
  } else {
    html = escapeHtml(content).replace(/\n/g, '<br/>')
  }
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

function copyMessage(msg) {
  const text = msg.content || ''
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
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

function goToWrongQuestions() {
  router.push('/wrong-questions')
}
</script>

<style scoped>
/* ========== 容器布局 ========== */
.chat-container {
  display: flex;
  height: 100vh;
  background: var(--bg);
  overflow: hidden;
}

/* ========== 左栏：会话侧边栏 ========== */
.session-sidebar {
  width: 260px;
  min-width: 260px;
  background: var(--surface-solid);
  border-right: 1px solid var(--separator);
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1), min-width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.session-sidebar.collapsed {
  width: 0;
  min-width: 0;
  overflow: hidden;
  border-right: none;
}

.sidebar-toggle {
  display: none;
}

.sidebar-header {
  padding: 14px 16px;
  border-bottom: 1px solid var(--separator);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.brand-icon {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--gradient-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}
.brand-text {
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
  white-space: nowrap;
}
.menu-toggle {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--accent);
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.menu-toggle:hover {
  color: #fff;
  background: var(--gradient-primary);
}
.menu-toggle :deep(svg) {
  width: 18px;
  height: 18px;
}

.floating-menu-btn {
  position: absolute;
  top: 16px;
  left: 16px;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: var(--surface-solid);
  border: 1px solid var(--separator);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--accent);
  box-shadow: var(--shadow-sm);
  transition: all 0.2s;
  z-index: 30;
}
.floating-menu-btn:hover {
  color: #fff;
  background: var(--gradient-primary);
  border-color: transparent;
}
.floating-menu-btn :deep(svg) {
  width: 18px;
  height: 18px;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.new-chat-wrap {
  padding: 8px 0 12px;
}

.new-chat-btn {
  width: 100%;
  border-radius: 999px !important;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: #fff !important;
  border: 1px solid var(--separator-strong) !important;
  color: var(--ink) !important;
  box-shadow: none !important;
}
.new-chat-btn:hover {
  background: var(--bg) !important;
  border-color: var(--accent) !important;
  color: var(--accent) !important;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--separator);
  flex-shrink: 0;
}
.wrong-questions-btn {
  width: 100%;
  border-radius: 999px !important;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.session-item {
  padding: 12px;
  cursor: pointer;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.2s ease;
  margin-bottom: 4px;
  position: relative;
}
.session-item:hover {
  background: var(--accent-light);
}
.session-item.active {
  background: var(--accent-light);
  box-shadow: inset 3px 0 0 var(--accent);
}
.session-info {
  flex: 1;
  min-width: 0;
  overflow: hidden;
}
.session-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-time {
  font-size: 12px;
  color: var(--ink-tertiary);
  margin-top: 3px;
}
.session-more {
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
  cursor: pointer;
  color: var(--ink-tertiary);
  padding: 4px;
  border-radius: 6px;
}
.session-more:hover {
  color: var(--accent);
  background: rgba(99, 102, 241, 0.1);
}
.session-item:hover .session-more {
  opacity: 1;
}

.session-empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--ink-tertiary);
  font-size: 13px;
}
.session-empty .hint {
  font-size: 12px;
  color: var(--ink-tertiary);
  margin-top: 4px;
  opacity: 0.7;
}

/* ========== 右栏：聊天区 ========== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  position: relative;
}

.chat-header {
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--separator);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
  z-index: 10;
}
.chat-header.with-menu-offset {
  padding-left: 56px;
}
.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.chat-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ========== 消息流 ========== */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 24px 100px;
  scroll-behavior: smooth;
}
.message-list.with-margin {
  padding-left: 25%;
  padding-right: 25%;
}
.message-list.with-margin .message-row.student {
  justify-content: flex-end;
}
.message-list.with-margin .message-row.agent {
  justify-content: flex-start;
}
.message-list.with-margin .message-body {
  max-width: 100%;
  width: auto;
}
.message-list.with-margin .message-content {
  max-width: 100%;
}

@media (max-width: 1200px) {
  .message-list.with-margin {
    padding-left: 20%;
    padding-right: 20%;
  }
}

@media (max-width: 992px) {
  .message-list.with-margin {
    padding-left: 15%;
    padding-right: 15%;
  }
}

@media (max-width: 768px) {
  .message-list.with-margin {
    padding-left: 12%;
    padding-right: 12%;
  }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--ink-tertiary);
  user-select: none;
  text-align: center;
}
.empty-avatar {
  width: 80px;
  height: 80px;
  border-radius: 24px;
  background: var(--gradient-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  margin-bottom: 20px;
  box-shadow: var(--shadow-glow);
}
.empty-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--ink);
  margin: 0 0 8px;
}
.empty-hint {
  font-size: 14px;
  color: var(--ink-secondary);
  margin: 0 0 24px;
  max-width: 420px;
}
.quick-prompts {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  max-width: 560px;
}
.quick-prompt {
  padding: 10px 16px;
  background: var(--surface-solid);
  border: 1px solid var(--separator);
  border-radius: 999px;
  font-size: 13px;
  color: var(--ink-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}
.quick-prompt:hover {
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

/* ========== 消息行 ========== */
.message-row {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 24px;
  animation: messageIn 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes messageIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-row.student {
  justify-content: flex-end;
}
.message-row.agent {
  justify-content: flex-start;
}
.message-row.student .message-body {
  align-items: flex-end;
}
.message-row.agent .message-body {
  align-items: flex-start;
}

.message-body {
  display: flex;
  flex-direction: column;
  max-width: min(760px, 80%);
  min-width: 0;
}

.message-content {
  padding: 14px 18px;
  border-radius: 18px;
  font-size: 15px;
  line-height: 1.75;
  word-break: break-word;
  box-shadow: var(--shadow-sm);
}
.student .message-content {
  background: #e0f2fe;
  color: var(--ink);
  border-bottom-right-radius: 5px;
}
.agent .message-content {
  background: var(--surface-solid);
  color: var(--ink);
  border: 1px solid var(--separator);
  border-bottom-left-radius: 5px;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 5px;
  padding: 0 6px;
}
.message-time {
  font-size: 11px;
  color: var(--ink-tertiary);
}
.copy-btn {
  opacity: 0;
  transition: opacity 0.2s;
  padding: 2px 6px;
  height: auto;
}
.message-row:hover .copy-btn {
  opacity: 1;
}

/* 工具卡片样式 */
.message-content :deep(.card) {
  padding: 12px 14px;
  border-radius: 12px;
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
  gap: 12px;
}
.message-content :deep(.spinner) {
  display: inline-block;
  width: 18px;
  height: 18px;
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
  margin: 6px 0 0;
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

/* Markdown 内容样式 */
.message-content :deep(p) { margin: 0 0 10px 0; }
.message-content :deep(p:last-child) { margin-bottom: 0; }
.message-content :deep(ul), .message-content :deep(ol) { margin: 8px 0; padding-left: 22px; }
.message-content :deep(li) { margin: 4px 0; }
.message-content :deep(code) {
  background: rgba(99, 102, 241, 0.08);
  padding: 2px 6px;
  border-radius: 5px;
  font-size: 13px;
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
  color: var(--accent);
}
.message-content :deep(pre) {
  background: #1e1e2e;
  color: #e2e8f0;
  padding: 14px;
  border-radius: 12px;
  overflow-x: auto;
  margin: 10px 0;
}
.message-content :deep(pre code) {
  background: transparent;
  padding: 0;
  color: inherit;
}
.message-content :deep(blockquote) {
  border-left: 3px solid var(--accent);
  margin: 10px 0;
  padding: 6px 14px;
  color: var(--ink-secondary);
  background: var(--accent-light);
  border-radius: 0 8px 8px 0;
}
.message-content :deep(table) {
  border-collapse: collapse;
  margin: 10px 0;
  width: 100%;
}
.message-content :deep(th), .message-content :deep(td) {
  border: 1px solid var(--separator-strong);
  padding: 8px 12px;
  text-align: left;
}
.message-content :deep(th) { background: var(--accent-light); font-weight: 600; }
.message-content :deep(h1), .message-content :deep(h2), .message-content :deep(h3) {
  margin: 16px 0 10px 0;
  font-weight: 600;
}
.message-content :deep(h1) { font-size: 1.35em; }
.message-content :deep(h2) { font-size: 1.2em; }
.message-content :deep(h3) { font-size: 1.1em; }
.message-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--separator);
  margin: 14px 0;
}

/* 流式光标 */
.cursor {
  animation: blink 1s infinite;
  color: var(--accent);
  font-weight: 300;
  margin-left: 2px;
}
@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 思考 loading */
.message-content.loading {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--ink-secondary);
  font-size: 14px;
  background: var(--surface-solid);
  border: 1px solid var(--separator);
  box-shadow: none;
}
.thinking-dots {
  display: flex;
  gap: 4px;
}
.thinking-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--accent);
  animation: dotPulse 1.4s infinite ease-in-out both;
}
.thinking-dots span:nth-child(1) { animation-delay: -0.32s; }
.thinking-dots span:nth-child(2) { animation-delay: -0.16s; }
@keyframes dotPulse {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
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
  position: relative;
  flex-shrink: 0;
  padding: 12px 24px 6px;
  background: linear-gradient(to top, var(--bg) 70%, transparent);
  display: flex;
  justify-content: center;
  z-index: 20;
}
.input-wrapper {
  width: 100%;
  max-width: 860px;
  background: var(--surface-solid);
  border: 1px solid var(--separator);
  border-radius: 24px;
  padding: 10px 14px;
  box-shadow: var(--shadow-lg);
  position: relative;
}

/* 文件预览 */
.file-preview {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  background: var(--accent-light);
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 12px;
  margin-bottom: 8px;
}
.file-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--ink-secondary);
  flex: 1;
  min-width: 0;
}
.file-name { font-weight: 500; }
.file-size { color: var(--ink-tertiary); font-size: 12px; }
.file-remove { cursor: pointer; color: var(--danger); flex-shrink: 0; }
.file-remove:hover { color: #d32f2f; }

/* Tab 联想下拉 */
.suggestions-dropdown {
  position: absolute;
  bottom: 100%;
  left: 16px;
  right: 16px;
  background: var(--surface-solid);
  border: 1px solid var(--separator);
  border-radius: 12px;
  box-shadow: var(--shadow-lg);
  max-height: 200px;
  overflow-y: auto;
  z-index: 100;
  margin-bottom: 8px;
}
.suggestion-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 13px;
}
.suggestion-item:hover {
  background: var(--accent-light);
}
.suggestion-name {
  font-weight: 600;
  color: var(--ink);
}
.suggestion-intent {
  color: var(--ink-tertiary);
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

.input-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}
.attach-btn {
  width: 40px;
  height: 40px;
  color: var(--ink-tertiary) !important;
  background: var(--accent-light) !important;
  border: none !important;
  flex-shrink: 0;
}
.attach-btn:hover {
  color: var(--accent) !important;
  background: rgba(99, 102, 241, 0.12) !important;
}
.attach-btn :deep(.el-icon) {
  font-size: 18px;
}
.input-row :deep(.el-textarea__inner) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 8px 0;
  font-size: 15px;
  resize: none;
  line-height: 1.6;
}
.send-btn {
  width: 40px;
  height: 40px;
  border-radius: 50% !important;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}
.send-btn :deep(.el-icon) {
  font-size: 18px;
}
.input-disclaimer {
  text-align: center;
  font-size: 11px;
  color: var(--ink-tertiary);
  opacity: 0.7;
  line-height: 16px;
  padding: 8px 24px 12px;
}

/* ========== 移动端适配 ========== */
@media (max-width: 768px) {
  .session-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 1000;
    box-shadow: 2px 0 12px rgba(0, 0, 0, 0.08);
  }
  .session-sidebar.collapsed {
    box-shadow: none;
  }
  .input-area {
    padding: 8px 12px 18px;
  }
  .input-disclaimer {
    padding: 6px 12px 10px;
  }
  .message-body {
    max-width: 88%;
  }
  .message-content {
    font-size: 14px;
    padding: 12px 14px;
  }
  .input-wrapper {
    border-radius: 20px;
    padding: 10px 12px;
  }
  .copy-btn {
    opacity: 1;
  }
}
</style>
