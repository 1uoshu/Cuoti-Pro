import { ref, onUnmounted } from 'vue'

/**
 * WebSocket composable — 封装 Agent 实时通信
 *
 * 功能：
 * 1. 自动连接 + JWT 认证
 * 2. 自动重连（指数退避）
 * 3. 事件监听和分发
 * 4. 断线回放
 *
 * @param {Object} options
 * @param {number} options.sessionId - 会话 ID
 * @param {string} options.token - JWT token
 * @param {Function} options.onEvent - 事件回调
 * @param {Function} options.onMessage - 消息回调
 * @param {Function} options.onError - 错误回调
 */
export function useWebSocket({ sessionId, token, onEvent, onMessage, onError }) {
  const connected = ref(false)
  const connecting = ref(false)
  const error = ref(null)
  let ws = null
  let reconnectTimer = null
  let reconnectAttempts = 0
  const MAX_RECONNECT_ATTEMPTS = 10
  const BASE_DELAY = 1000

  function getWsUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/api/agent/ws?session_id=${sessionId}&token=${token}`
  }

  function connect() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }
    connecting.value = true
    error.value = null

    try {
      ws = new WebSocket(getWsUrl())
    } catch (e) {
      error.value = e.message
      connecting.value = false
      return
    }

    ws.onopen = () => {
      connected.value = true
      connecting.value = false
      reconnectAttempts = 0
      console.log('[WS] Connected to session', sessionId)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type) {
          onEvent?.(data)
        } else {
          onMessage?.(data)
        }
      } catch (e) {
        console.warn('[WS] Failed to parse message:', event.data)
      }
    }

    ws.onerror = (e) => {
      error.value = 'WebSocket connection error'
      onError?.(e)
    }

    ws.onclose = (e) => {
      connected.value = false
      connecting.value = false
      console.log('[WS] Disconnected:', e.code, e.reason)

      if (e.code === 4001) {
        error.value = 'Authentication failed'
        return
      }

      if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        const delay = BASE_DELAY * Math.pow(2, reconnectAttempts)
        reconnectTimer = setTimeout(() => {
          reconnectAttempts++
          console.log(`[WS] Reconnecting (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`)
          connect()
        }, delay)
      }
    }
  }

  function send(data) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  function sendMessage(content, tool = null) {
    const msg = { type: 'chat.message', content }
    if (tool) msg.tool = tool
    send(msg)
  }

  function cancel() {
    send({ type: 'action.cancel' })
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    if (ws) ws.close()
    ws = null
    connected.value = false
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    connected,
    connecting,
    error,
    connect,
    send,
    sendMessage,
    cancel,
    disconnect
  }
}
