/** WebSocket 客户端 — 扫描进度实时推送，自动重连，fallback 轮询。 */

const PING_INTERVAL = 30000 // 心跳间隔 30s
const RECONNECT_DELAY = [2000, 5000, 10000, 30000] // 重连退避

export function createScanProgressSocket(token) {
  let ws = null
  let pingTimer = null
  let reconnectAttempt = 0
  let destroyed = false
  let _onMessage = null

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/ws/scan-progress?token=${encodeURIComponent(token)}`

  function scheduleReconnect() {
    if (destroyed) return
    const delay = RECONNECT_DELAY[Math.min(reconnectAttempt, RECONNECT_DELAY.length - 1)]
    reconnectAttempt++
    setTimeout(connect, delay)
  }

  function startPing() {
    stopPing()
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send('ping')
      }
    }, PING_INTERVAL)
  }

  function stopPing() {
    if (pingTimer) {
      clearInterval(pingTimer)
      pingTimer = null
    }
  }

  function connect() {
    if (destroyed) return
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return
    }

    stopPing()
    try { ws && ws.close() } catch {}

    ws = new WebSocket(url)

    ws.onopen = () => {
      reconnectAttempt = 0
      startPing()
    }

    ws.onmessage = (event) => {
      if (event.data === 'pong') return
      try {
        const data = JSON.parse(event.data)
        if (_onMessage && data && data.id) {
          _onMessage(data)
        }
      } catch { /* ignore parse errors */ }
    }

    ws.onclose = () => {
      stopPing()
      scheduleReconnect()
    }

    ws.onerror = () => {
      stopPing()
      try { ws && ws.close() } catch {}
    }
  }

  function onMessage(fn) {
    _onMessage = fn
  }

  function destroy() {
    destroyed = true
    stopPing()
    try { ws && ws.close() } catch {}
    ws = null
    _onMessage = null
  }

  connect()

  return { onMessage, destroy, connect }
}
