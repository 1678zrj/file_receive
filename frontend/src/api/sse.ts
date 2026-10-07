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

/** SSE 建连失败时带 HTTP 状态码，便于上层区分「403=run 已终止」与网络异常 */
export interface SSEError extends Error {
  status?: number
}

export type SSEEventCallback = (evt: SSEEvent) => void

/**
 * 建立 SSE 连接并流式解析事件。
 *
 * 事件对象里 `id` 是 Redis Stream 的条目 id（后端每条事件都会带上），
 * 上层应当记住最后收到的 id，断线时作为 `Last-Event-ID` 传回来即可**增量续传**
 * （Redis `XREAD` 语义是「取大于该 id 的条目」，所以不会重复）。
 *
 * @param url stream_url（相对路径，如 /api/v1/agent/threads/.../stream）
 * @param onEvent 事件回调（心跳会以 `event: 'heartbeat'` 的伪事件形式派发）
 * @param lastEventId 断线重连起点（不传 = 后端从 Redis Stream 头部重放）
 * @param signal 取消信号
 * @returns 本次连接收到的最后一个事件 id（没有任何事件时为 undefined）
 */
export async function streamSSE(
  url: string,
  onEvent: SSEEventCallback,
  lastEventId?: string,
  signal?: AbortSignal,
): Promise<string | undefined> {
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
    const err: SSEError = new Error(`SSE 连接失败 (${resp.status})`)
    err.status = resp.status
    throw err
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
          /*
           * 注释行。后端每 15s 发一次 ": heartbeat" 心跳。
           * 它不是标准 SSE 事件，但对前端来说是「连接仍然活着、Agent 仍在执行」的证据，
           * 所以派发成一个 event='heartbeat' 的伪事件，交给上层做存活检测。
           * 注意：伪事件不带 data，也不会推进 lastEventId。
           */
          const comment = line.slice(1).trim()
          if (comment) {
            onEvent({ id: currentId, event: 'heartbeat', data: comment })
          }
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
    return currentId
  } finally {
    reader.releaseLock()
  }
}
