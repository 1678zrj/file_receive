/**
 * SSE（Server-Sent Events）流式解析器
 * 对接后端 /agent/threads/{thread_id}/runs/{run_id}/stream 的 text/event-stream 响应。
 * 支持 Last-Event-ID 断线重连。
 */
import { getAccessToken } from '@/api/http'

export interface SSEEvent {
  id?: string
  event?: string
  data: string
}

export type SSEEventCallback = (evt: SSEEvent) => void

/**
 * 建立 SSE 连接并流式解析事件。
 * @param url stream_url（相对路径，如 /api/v1/agent/threads/.../stream）
 * @param onEvent 事件回调（含 heartbeat 过滤后）
 * @param lastEventId 断线重连起点
 * @param signal 取消信号
 */
export async function streamSSE(
  url: string,
  onEvent: SSEEventCallback,
  lastEventId?: string,
  signal?: AbortSignal,
): Promise<void> {
  const fullUrl = url.startsWith('/api') ? url : `/api/v1${url}`
  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    'Cache-Control': 'no-cache',
  }
  const token = getAccessToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (lastEventId) headers['Last-Event-ID'] = lastEventId

  const resp = await fetch(fullUrl, { headers, signal, credentials: 'include' })
  if (!resp.ok) {
    throw new Error(`SSE 连接失败 (${resp.status})`)
  }
  if (!resp.body) {
    throw new Error('响应不支持流式读取')
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let currentId: string | undefined = lastEventId
  let currentEvent = ''
  let currentDataLines: string[] = []

  const dispatch = () => {
    if (currentDataLines.length === 0 && !currentEvent) return
    const evt: SSEEvent = {
      id: currentId,
      event: currentEvent || 'message',
      data: currentDataLines.join('\n'),
    }
    currentDataLines = []
    currentEvent = ''
    onEvent(evt)
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let idx: number
      while ((idx = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, idx).replace(/\r$/, '')
        buffer = buffer.slice(idx + 1)

        if (line === '') {
          // 空行 = 事件结束
          dispatch()
        } else if (line.startsWith(':')) {
          // 注释行（如 heartbeat），忽略
        } else if (line.startsWith('id:')) {
          currentId = line.slice(3).trim()
        } else if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          currentDataLines.push(line.slice(5).trimStart())
        }
        // 其他字段（retry 等）忽略
      }
    }
    // 流结束，处理残留
    dispatch()
  } finally {
    reader.releaseLock()
  }
}
