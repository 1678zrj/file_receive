/**
 * Agent 多会话对话逻辑
 *
 * 设计要点：
 *  1. 多会话并发：每个会话（对应后端一个 Thread）拥有独立的 messages / runId / streaming，
 *     后端锁粒度是 Thread，因此不同 Thread 可以同时跑（同一用户可并行多个会话）。
 *  2. 刷新恢复：会话数据持久化到 localStorage；若刷新时有会话正在运行，
 *     重新连接该 run 的 SSE（不带 Last-Event-ID → 后端从 Redis Stream 头重放全部事件），
 *     从而完整恢复正在进行的对话。
 *  3. scope 属于每次 Run：切换知识库只影响「下一次提问」，不影响历史消息与 Thread。
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { agentApi } from '@/api'
import type {
  AgentChatMessage,
  ChatSession,
  InterruptPayload,
} from '@/api/types'
import { streamSSE, type SSEEvent } from '@/api/sse'

export interface AgentScope {
  scope: string
  scope_id: string
  /** 显示用标签（如课程名） */
  label?: string
}

const STORAGE_KEY = 'agent_sessions_v1'
/** 最多持久化的会话数 / 每会话消息数（避免超 localStorage 容量） */
const MAX_PERSIST_SESSIONS = 20
const MAX_PERSIST_MESSAGES = 60
/** 单块内容持久化上限 */
const MAX_PART_CHARS = 8000

let _seq = 0
function nextId(prefix = 'id') {
  return `${prefix}-${Date.now()}-${_seq++}`
}
function uuid() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function useAgentChat(getScope: () => AgentScope | null) {
  const sessions = ref<ChatSession[]>([])
  const activeId = ref<string | null>(null)
  const error = ref('')
  /** 每个会话独立的 SSE 取消控制器 */
  const controllers = new Map<string, AbortController>()

  const activeSession = computed<ChatSession | null>(
    () => sessions.value.find((s) => s.id === activeId.value) ?? null,
  )
  const messages = computed<AgentChatMessage[]>(() => activeSession.value?.messages ?? [])
  const streaming = computed(() => activeSession.value?.streaming ?? false)
  const isStreaming = computed(() => streaming.value)
  const pendingInterrupt = computed<InterruptPayload | null>(
    () => activeSession.value?.pendingInterrupt ?? null,
  )
  const threadId = computed(() => activeSession.value?.threadId ?? null)
  /** 是否有任意会话正在运行（用于会话列表上的小圆点） */
  const anyStreaming = computed(() => sessions.value.some((s) => s.streaming))

  // ============================================================
  // 持久化
  // ============================================================
  let persistTimer: ReturnType<typeof setTimeout> | null = null

  function persistNow() {
    try {
      const payload = {
        activeId: activeId.value,
        sessions: sessions.value.slice(0, MAX_PERSIST_SESSIONS).map((s) => ({
          ...s,
          messages: s.messages.slice(-MAX_PERSIST_MESSAGES).map((m) => ({
            ...m,
            streaming: false,
            parts: m.parts.map((p) => ({
              ...p,
              content:
                p.content && p.content.length > MAX_PART_CHARS
                  ? `${p.content.slice(0, MAX_PART_CHARS)}…`
                  : p.content,
            })),
          })),
        })),
        updatedAt: Date.now(),
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
    } catch {
      /* 容量超限忽略 */
    }
  }

  function schedulePersist() {
    if (persistTimer) clearTimeout(persistTimer)
    persistTimer = setTimeout(persistNow, 400)
  }

  function clearStorage() {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      /* 忽略 */
    }
  }

  /** 从 localStorage 恢复会话，返回需要重连的会话列表 */
  function restoreLocal(): ChatSession[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return []
      const data = JSON.parse(raw)
      if (!Array.isArray(data.sessions) || data.sessions.length === 0) return []
      sessions.value = data.sessions.map((s: ChatSession) => ({
        ...s,
        // 刷新后 SSS 连接已断，先重置流式标记
        streaming: false,
        messages: (s.messages || []).map((m) => ({ ...m, streaming: false })),
      }))
      activeId.value =
        data.activeId && sessions.value.some((s) => s.id === data.activeId)
          ? data.activeId
          : sessions.value[0].id
      // 返回「上一次正在运行」的会话，交给重连逻辑处理
      return sessions.value.filter((s) => s.currentRunId && hasIncompleteRun(s))
    } catch {
      /* 解析失败忽略 */
    }
    return []
  }

  /** 该会话是否有未完成的 run（刷新后需要重连重放） */
  function hasIncompleteRun(s: ChatSession): boolean {
    return !!s.currentRunId && !s.runFinished
  }

  // ============================================================
  // 会话管理
  // ============================================================
  function newSession(): ChatSession {
    const s: ChatSession = {
      id: nextId('sess'),
      title: '新会话',
      threadId: null,
      messages: [],
      currentRunId: null,
      runFinished: true,
      streaming: false,
      pendingInterrupt: null,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    sessions.value.unshift(s)
    activeId.value = s.id
    schedulePersist()
    return s
  }

  /** 确保存在活跃会话 */
  function ensureSession(): ChatSession {
    return activeSession.value ?? newSession()
  }

  function switchSession(id: string) {
    if (sessions.value.some((s) => s.id === id)) {
      activeId.value = id
      schedulePersist()
    }
  }

  function removeSession(id: string) {
    controllers.get(id)?.abort()
    controllers.delete(id)
    const idx = sessions.value.findIndex((s) => s.id === id)
    if (idx >= 0) sessions.value.splice(idx, 1)
    if (activeId.value === id) {
      activeId.value = sessions.value[0]?.id ?? null
    }
    schedulePersist()
  }

  /** 清空当前会话（保留会话，但下次提问会新建后端 Thread） */
  function clearCurrent() {
    const s = activeSession.value
    if (!s) return
    controllers.get(s.id)?.abort()
    controllers.delete(s.id)
    s.messages = []
    s.currentRunId = null
    s.runFinished = true
    s.streaming = false
    s.pendingInterrupt = null
    s.threadId = null
    s.title = '新会话'
    s.updatedAt = Date.now()
    schedulePersist()
  }

  /** 清空全部会话 */
  function reset() {
    controllers.forEach((c) => c.abort())
    controllers.clear()
    sessions.value = []
    activeId.value = null
    error.value = ''
    clearStorage()
  }

  // ============================================================
  // 发送 / 流式
  // ============================================================

  /** 按 id 取回会话内的 reactive 消息对象 */
  function getMsg(session: ChatSession, id: string): AgentChatMessage | undefined {
    return session.messages.find((m) => m.id === id)
  }

  async function ensureThread(session: ChatSession, title?: string): Promise<string> {
    if (session.threadId) return session.threadId
    const t = await agentApi.createThread({ title: title || '新会话' })
    session.threadId = t.id
    return t.id
  }

  /** 在活跃会话中发送一条消息 */
  async function send(prompt: string) {
    const scope = getScope()
    if (!scope) {
      error.value = '请先选择课程'
      return
    }
    const text = prompt.trim()
    if (!text) return

    const session = ensureSession()
    // 仅限制「同一会话」并发；不同会话可同时运行
    if (session.streaming) return

    error.value = ''
    session.pendingInterrupt = null
    session.streaming = true
    session.updatedAt = Date.now()
    if (session.messages.length === 0) {
      session.title = text.slice(0, 20)
    }

    // 用户消息
    session.messages.push({
      id: nextId('u'),
      role: 'user',
      content: text,
      parts: [],
      streaming: false,
      scopeLabel: scope.label,
      created_at: new Date().toISOString(),
    })
    // assistant 占位
    const assistantMsgId = nextId('a')
    session.messages.push({
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      parts: [],
      streaming: true,
      interrupt: null,
      scopeLabel: scope.label,
      created_at: new Date().toISOString(),
    })

    try {
      const tid = await ensureThread(session, text.slice(0, 20))
      const run = await agentApi.createRun(tid, {
        prompt: text,
        scope: scope.scope,
        scope_id: scope.scope_id,
        idempotency_key: uuid(),
      })
      session.currentRunId = run.run_id
      session.runFinished = false
      // 标记消息所属 run
      const um = session.messages[session.messages.length - 2]
      const am = getMsg(session, assistantMsgId)
      if (um) um.runId = run.run_id
      if (am) am.runId = run.run_id

      // 后台消费流（不 await）
      consumeStream(session, run.run_id, assistantMsgId).catch((e: any) => {
        setErrorText(session, assistantMsgId, e?.message || '请求失败')
        session.streaming = false
        schedulePersist()
      })
    } catch (e: any) {
      setErrorText(session, assistantMsgId, e?.message || '请求失败')
      session.streaming = false
      error.value = e?.message || '请求失败'
      schedulePersist()
    }
  }

  /** 把错误写入 assistant 消息 */
  function setErrorText(session: ChatSession, msgId: string, text: string) {
    const m = getMsg(session, msgId)
    if (!m) return
    m.streaming = false
    m.parts.push({ type: 'text', content: `😥 出错了：${text}` })
  }

  /**
   * 消费 SSE 长连接。
   * @param lastEventId 不传 = 后端从 Redis Stream 头重放（用于刷新重连）
   */
  async function consumeStream(
    session: ChatSession,
    runId: string,
    msgId: string,
    lastEventId?: string,
  ) {
    if (!session.threadId) return
    const ctrl = new AbortController()
    controllers.set(session.id, ctrl)
    try {
      await streamSSE(
        agentApi.streamUrl(session.threadId, runId),
        (evt: SSEEvent) => handleEvent(evt, session, msgId),
        lastEventId,
        ctrl.signal,
      )
    } finally {
      controllers.delete(session.id)
      const m = getMsg(session, msgId)
      if (m) m.streaming = false
      session.streaming = false
      schedulePersist()
    }
  }

  /** 处理单个 SSE 事件 */
  function handleEvent(evt: SSEEvent, session: ChatSession, msgId: string) {
    const msg = getMsg(session, msgId)
    if (!msg) return
    const type = evt.event || 'message'
    let data: any = {}
    try {
      data = evt.data ? JSON.parse(evt.data) : {}
    } catch {
      /* 非 JSON 忽略 */
    }

    switch (type) {
      case 'thought_delta':
        appendDelta(msg, 'thought', data.delta || '')
        break
      case 'text_delta':
        appendDelta(msg, 'text', data.delta || '')
        break
      case 'tool_call':
        msg.parts.push({
          type: 'tool_call',
          tool_call_id: data.id || data.tool_call_id,
          name: data.name,
          args: data.args,
          status: data.status || 'running',
        })
        break
      case 'tool_result': {
        const tcid = data.id || data.tool_call_id
        const target = msg.parts.find((p) => p.type === 'tool_call' && p.tool_call_id === tcid)
        if (target) {
          target.status = data.status
          target.content = data.content
        } else {
          msg.parts.push({
            type: 'tool_call',
            tool_call_id: tcid,
            status: data.status,
            content: data.content,
          })
        }
        break
      }
      case 'requires_action':
        msg.interrupt = data as InterruptPayload
        session.pendingInterrupt = data as InterruptPayload
        break
      case 'completed':
      case 'failed':
      case 'canceled':
        msg.streaming = false
        session.streaming = false
        session.runFinished = true
        schedulePersist()
        break
      default:
        break
    }
  }

  /** 复刻后端 RunExecutionAccumulator：相邻同类型累加，否则新起一块 */
  function appendDelta(msg: AgentChatMessage, type: 'thought' | 'text', delta: string) {
    if (!delta) return
    const last = msg.parts[msg.parts.length - 1]
    if (last && last.type === type) {
      last.content = (last.content || '') + delta
    } else {
      msg.parts.push({ type, content: delta })
    }
  }

  /** 回复当前会话的中断 */
  async function resume(answers: unknown) {
    const session = activeSession.value
    const interrupt = session?.pendingInterrupt
    if (!session || !interrupt || !session.threadId || !session.currentRunId) return
    error.value = ''

    const msg = session.messages.find((m) => m.interrupt?.interrupt_id === interrupt.interrupt_id)
    if (msg) msg.interrupt = null
    session.pendingInterrupt = null

    try {
      await agentApi.resumeRun(session.threadId, session.currentRunId, answers)
      // 原 SSE 连接仍在接收，无需重连
    } catch (e: any) {
      error.value = e?.message || '回复失败'
      if (msg) {
        msg.streaming = false
        msg.parts.push({ type: 'text', content: `😥 回复失败：${e?.message || '请求失败'}` })
      }
      session.streaming = false
      schedulePersist()
    }
  }

  // ============================================================
  // 刷新后重连（利用 Redis Stream 的事件重放）
  // ============================================================
  async function reconnect(session: ChatSession) {
    if (!session.threadId || !session.currentRunId) return
    const runId = session.currentRunId
    const msg = session.messages.find((m) => m.role === 'assistant' && m.runId === runId)
    if (!msg) return

    // 清空该消息的内容，准备用 Redis Stream 里的事件完整重放
    msg.parts = []
    msg.interrupt = null
    msg.streaming = true
    session.streaming = true
    try {
      // 不传 Last-Event-ID → 后端从 "0-0" 读，重放该 run 的全部事件
      await consumeStream(session, runId, msg.id)
    } catch {
      // run 已终止（403）或网络异常：保持本地缓存内容，结束流式
      msg.streaming = false
      session.streaming = false
      schedulePersist()
    }
  }

  // 启动时恢复：本地会话立即可见；对「未完成」的会话重连（利用 Redis Stream 重放）
  const pendingReconnectList = restoreLocal()
  const restored = ref(sessions.value.length > 0)
  for (const s of pendingReconnectList) {
    reconnect(s)
  }

  // 变化时持久化
  watch(
    () => {
      const s = activeSession.value
      const last = s?.messages[s.messages.length - 1]
      const len = last ? last.parts.reduce((sum, p) => sum + (p.content?.length || 0), 0) : 0
      return `${sessions.value.length}-${s?.id ?? ''}-${s?.messages.length ?? 0}-${len}-${s?.streaming ? 1 : 0}`
    },
    schedulePersist,
  )

  // 刷新/关闭前强制落盘
  if (typeof window !== 'undefined') {
    const flush = () => persistNow()
    window.addEventListener('beforeunload', flush)
    onUnmounted(() => window.removeEventListener('beforeunload', flush))
  }

  return {
    // 会话
    sessions,
    activeId,
    activeSession,
    anyStreaming,
    newSession,
    switchSession,
    removeSession,
    clearCurrent,
    reset,
    // 当前会话便捷访问
    messages,
    threadId,
    streaming,
    isStreaming,
    pendingInterrupt,
    restored,
    error,
    // 操作
    send,
    resume,
    persistNow,
  }
}
