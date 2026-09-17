/**
 * Agent 多会话对话逻辑
 *
 * 设计要点：
 *  1. 服务端为准：会话列表来自 GET /agent/threads（已过滤 active），历史消息来自
 *     GET /agent/threads/{thread_id}/messages（带 run_id），删除会话走 DELETE。
 *     localStorage 只作为「首屏秒开 + 断网兜底」缓存。
 *  2. 多会话并发：每个会话（对应后端一个 Thread）拥有独立的 messages / runId / streaming，
 *     后端锁粒度是 Thread，因此不同 Thread 可以同时跑（同一用户可并行多个会话）。
 *  3. 刷新恢复：若刷新时有会话正在运行，按 runId 定位承载消息后重新连接该 run 的 SSE
 *     （不带 Last-Event-ID → 后端从 Redis Stream 头重放全部事件）；若该 run 其实已终止
 *     （后端 403），改为回拉历史接口。收到真正的终态事件后再拉一次历史，校正被缓存截断的内容。
 *  4. scope 属于每次 Run：切换知识库只影响「下一次提问」，不影响历史消息与 Thread。
 *  5. 懒加载：会话列表只返回骨架，切到某个会话时才拉它的历史消息（避免一次拉 N 个会话）。
 *  6. 失败兜底：后端 worker 异常时不 publish failed/canceled，表现为「连接干净关闭但无终态事件」，
 *     这里把「干净关闭」也视作终态，避免刷新后又去重连一个已终止的 run。
 */
import { computed, onUnmounted, ref, watch } from 'vue'
import { agentApi } from '@/api'
import type {
  AgentChatMessage,
  AgentMessageItem,
  AgentQuestion,
  AgentThread,
  BackendMessagePart,
  ChatSession,
  InterruptAnswer,
  InterruptAnswerInput,
  InterruptPayload,
  MessagePart,
  RetryPayload,
  ToolCall,
} from '@/api/types'
import { streamSSE, type SSEEvent } from '@/api/sse'

export interface AgentScope {
  scope: string
  scope_id: string
  /** 显示用标签（如课程名） */
  label?: string
}

export interface UseAgentChatOptions {
  /**
   * 把后端历史消息里的 scope / scope_id 还原成展示用标签（课程名）。
   *
   * 服务端消息只存 scope_id（形如 `course_1`），标签要靠课程列表反查；
   * 这里做成回调是因为 composable 不该依赖课程 store。
   */
  resolveScopeLabel?: (scope?: string | null, scopeId?: string | null) => string | undefined
}

/** 当前会话的运行状态（用于状态提示条） */
export type AgentRunState =
  | 'idle'
  | 'queued'
  | 'running'
  | 'waiting'
  | 'reconnecting'
  | 'stalled'
  | 'stopped'

const STORAGE_KEY = 'agent_sessions_v1'
/** 最多持久化的会话数 / 每会话消息数（避免超 localStorage 容量） */
const MAX_PERSIST_SESSIONS = 20
const MAX_PERSIST_MESSAGES = 60
/** 单块内容持久化上限 */
const MAX_PART_CHARS = 8000
/** SSE 断线自动重连上限（用 Last-Event-ID 增量续传） */
const MAX_STREAM_RETRY = 4
/** 连接维持超过这个时长后断开，认为是一次「正常长连接中断」，重试计数归零 */
const STREAM_STABLE_MS = 5000
/** 超过这个时长既没有事件也没有心跳，判定为连接可能已经僵死 */
const STALL_MS = 35_000

let _seq = 0
function nextId(prefix = 'id') {
  return `${prefix}-${Date.now()}-${_seq++}`
}
function uuid() {
  return typeof crypto !== 'undefined' && crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
}
/** 后端时间字符串 → 毫秒时间戳 */
function toTs(s?: string | null): number {
  if (!s) return Date.now()
  const t = Date.parse(s)
  return Number.isNaN(t) ? Date.now() : t
}

export function useAgentChat(
  getScope: () => AgentScope | null,
  options: UseAgentChatOptions = {},
) {
  const sessions = ref<ChatSession[]>([])
  const activeId = ref<string | null>(null)
  const error = ref('')
  /** 与服务端同步相关的提示（列表/历史拉取失败等） */
  const syncError = ref('')
  /** 会话列表是否已成功从后端加载 */
  const serverReady = ref(false)
  /** 正在拉取会话列表 / 某会话的历史消息（仅首次加载时置位，避免切换时闪烁） */
  const threadsLoading = ref(false)
  const messagesLoading = ref(false)
  /** 每个会话独立的 SSE 取消控制器 */
  const controllers = new Map<string, AbortController>()
  /**
   * 本次页面会话中由前端创建的 thread id。
   * 用于避免「会话列表快照早于 Thread 创建」时把自己正在用的会话误判为已删除。
   */
  const locallyCreatedThreads = new Set<string>()
  /**
   * 本次页面会话中已被前端删除的 thread id。
   * 用于避免「会话列表快照早于删除动作」时，把已删除的会话又按快照重建出来。
   */
  const locallyDeletedThreads = new Set<string>()

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

  /**
   * 每秒跳一次的时钟。仅在有会话运行/重连时开启，用于重算「僵死」判定，
   * 不会一直空转。
   */
  const nowMs = ref(Date.now())
  let clockTimer: ReturnType<typeof setInterval> | null = null
  function stopClock() {
    if (clockTimer) {
      clearInterval(clockTimer)
      clockTimer = null
    }
  }

  /** 当前会话的运行状态（排队中 / 执行中 / 等待回答 / 重连中 / 无响应 / 已停止） */
  const runState = computed<AgentRunState>(() => {
    const s = activeSession.value
    if (!s) return 'idle'
    if (s.pendingInterrupt) return 'waiting'
    if (s.stopped) return 'stopped'
    if (s.reconnecting) return 'reconnecting'
    if (!s.streaming) return 'idle'
    // in_progress 是 worker 抢到锁、开始执行之后才发的，在那之前确实在排队
    if (!s.started) return 'queued'
    if (s.lastEventAt && nowMs.value - s.lastEventAt > STALL_MS) return 'stalled'
    return 'running'
  })

  const runStateText = computed(() => {
    const s = activeSession.value
    switch (runState.value) {
      case 'queued':
        return '排队中…（等待执行线程）'
      case 'running':
        return '思考中…'
      case 'waiting':
        return '等待你的回答'
      case 'reconnecting':
        return `连接中断，正在重连（第 ${s?.reconnecting ?? 1} 次）…`
      case 'stalled':
        return '长时间没有新内容，连接可能已断开'
      case 'stopped':
        return '已停止接收（后端可能仍在执行）'
      default:
        return ''
    }
  })

  /** 处于「已停止但这一轮还没结束」状态 → 可以继续接收 */
  const canContinue = computed(() => {
    const s = activeSession.value
    return !!s && !!s.stopped && !!s.currentRunId && !s.runFinished
  })

  // ============================================================
  // 本地持久化（仅作缓存，不参与"真相"判定）
  // ============================================================
  let persistTimer: ReturnType<typeof setTimeout> | null = null

  function persistNow() {
    // 先把帧缓冲里还没落盘的增量刷掉，否则最后一段内容会丢
    flushAllBuffers()
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
        // 刷新后 SSE 连接已断，先重置流式标记
        streaming: false,
        // 本地有内容即可先渲染；服务端数据随后在切换/完成时校正
        loaded: Array.isArray(s.messages) && s.messages.length > 0,
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

  /**
   * 取回 `sessions` 数组里的响应式会话对象。
   *
   * ⚠️ 关键：把一个普通对象 push/unshift 进 `ref` 数组后，Vue 只在**读取**时才把它包成响应式代理；
   * 如果调用方持有了原始对象并直接改它（`session.streaming = true`、`msg.parts.push(...)`），
   * 视图不会更新 —— 表现就是「流式输出完全不动」。
   * 因此所有会改会话/消息的地方，都先经过这个函数归一化。
   */
  function liveSession(session: ChatSession): ChatSession {
    return sessions.value.find((s) => s.id === session.id) ?? session
  }

  // ============================================================
  // 增量缓冲：把 SSE 的 token 级增量按帧合并后再写入响应式状态
  //
  // 为什么要这么做：SSE 的到达频率常常高于屏幕刷新率（尤其是模型吐字快的时候），
  // 每个 token 都改一次 part.content 就会触发一轮组件更新 + markdown 重渲染。
  // 这里把相邻同类型的增量先合并成「一段」，再用 requestAnimationFrame 每帧最多刷一次。
  // 注意顺序语义：非增量事件（tool_call / requires_action / 终态）在写入前会先强制 flush，
  // 因此结果与逐条处理完全等价。
  // ============================================================
  interface DeltaBuffer {
    session: ChatSession
    runId: string
    msgId: string
    /** 已合并的增量段（相邻同类型已合并） */
    runs: Array<{ type: 'thought' | 'text'; content: string }>
    handle: number | ReturnType<typeof setTimeout> | null
    viaRaf: boolean
  }
  const buffers = new Map<string, DeltaBuffer>()

  /**
   * 缓冲区 key 必须带上 runId。
   *
   * ⚠️ 这里踩过坑：最初只用 `session.id` 做 key，而 flush 之后只是把 runs 清空、
   * 并不删除条目，于是「同一个会话里问第二句」时拿到的是上一轮遗留的 buffer
   * （里面的 runId / msgId 还是旧的），新一轮的增量会被追加到**上一条回答**里，
   * 新的占位消息一直是空的 —— 表现就是「消息错位」。
   * 带上 runId 后每轮 Run 各自一个缓冲区，从结构上杜绝这类串台。
   */
  function bufferKey(sessionId: string, runId: string) {
    return `${sessionId}|${runId}`
  }

  /**
   * 每个会话当前「有效」的流编号。
   * 用来解决「旧连接被掐掉后它的收尾逻辑又跑一遍」的竞态：
   * 例如用户点「重新连接」时，新连接的收尾早于旧连接的 finally，
   * 旧连接就会把新连接刚置好的 streaming 状态又抹掉（或者两条流同时往一条消息里写）。
   * 收尾时校验编号，不是当前有效流就直接跳过状态写入。
   */
  const streamTokens = new Map<string, number>()

  function nextStreamToken(key: string): number {
    const token = (streamTokens.get(key) ?? 0) + 1
    streamTokens.set(key, token)
    return token
  }

  function hasRaf(): boolean {
    return typeof requestAnimationFrame === 'function'
  }

  function scheduleFlush(key: string) {
    const buf = buffers.get(key)
    if (!buf || buf.handle !== null) return
    if (hasRaf()) {
      buf.viaRaf = true
      buf.handle = requestAnimationFrame(() => {
        buf.handle = null
        flushBuffer(key)
      })
    } else {
      // 无 rAF 环境（如后台标签页被节流、测试环境）退化为 16ms 定时器
      buf.viaRaf = false
      buf.handle = setTimeout(() => {
        buf.handle = null
        flushBuffer(key)
      }, 16)
    }
  }

  function flushBuffer(key: string) {
    const buf = buffers.get(key)
    if (!buf) return
    if (buf.handle !== null) {
      if (buf.viaRaf) cancelAnimationFrame(buf.handle as number)
      else clearTimeout(buf.handle as never)
      buf.handle = null
    }
    const runs = buf.runs
    buf.runs = []
    if (runs.length === 0) return
    const msg = findRunMessage(buf.session, buf.runId, buf.msgId)
    if (!msg) return
    for (const run of runs) appendDelta(msg, run.type, run.content)
  }

  /** 立刻把所有会话的待刷增量落盘（切页面/关页面前必须调用，否则会丢最后一段） */
  function flushAllBuffers() {
    for (const key of [...buffers.keys()]) flushBuffer(key)
  }

  function queueDelta(
    session: ChatSession,
    runId: string,
    msgId: string,
    type: 'thought' | 'text',
    delta: string,
  ) {
    if (!delta) return
    const key = bufferKey(session.id, runId)
    let buf = buffers.get(key)
    if (!buf) {
      buf = { session, runId, msgId, runs: [], handle: null, viaRaf: false }
      buffers.set(key, buf)
    }
    const last = buf.runs[buf.runs.length - 1]
    if (last && last.type === type) last.content += delta
    else buf.runs.push({ type, content: delta })
    scheduleFlush(key)
  }

  function sleep(ms: number, signal?: AbortSignal) {
    return new Promise<void>((resolve) => {
      const timer = setTimeout(resolve, ms)
      signal?.addEventListener(
        'abort',
        () => {
          clearTimeout(timer)
          resolve()
        },
        { once: true },
      )
    })
  }

  // ============================================================
  // 多标签页同步
  //
  // 要解决两个真实问题：
  //  1. A 标签页删了会话，B 标签页还留着（点进去必然 404/409）；
  //  2. 两个标签页同时开着同一个会话时，会各自连一条 SSE 往**各自**的
  //     localStorage 里写，互相覆盖；而且同一 Run 被读两遍。
  // 处理方式：删除/新增会话广播给其它页；某页开始接收某 Thread 的流时广播「认领」，
  // 其它正在接收同一 Thread 的页面主动让出（可随时再点「继续接收」抢回来）。
  // ============================================================
  const TAB_ID = nextId('tab')
  const SYNC_CHANNEL = 'agent-sync'

  interface SyncMessage {
    from: string
    type: 'threads-changed' | 'session-deleted' | 'stream-claim'
    threadId?: string
  }

  let channel: BroadcastChannel | null = null

  function postSync(msg: Omit<SyncMessage, 'from'>) {
    try {
      channel?.postMessage({ ...msg, from: TAB_ID })
    } catch {
      /* 通道不可用时静默降级为「无多标签同步」 */
    }
  }

  function setupSync() {
    if (typeof BroadcastChannel === 'undefined') return
    try {
      channel = new BroadcastChannel(SYNC_CHANNEL)
    } catch {
      channel = null
      return
    }
    channel.onmessage = (ev: MessageEvent<SyncMessage>) => {
      const data = ev.data
      if (!data || data.from === TAB_ID) return
      if (data.type === 'threads-changed') {
        // 别的标签页新建/删除了会话 → 对齐列表（mergeThreads 已保证不会误删流式中的会话）
        void loadThreads()
        return
      }
      if (data.type === 'session-deleted' && data.threadId) {
        const tid = data.threadId
        locallyDeletedThreads.add(tid)
        const idx = sessions.value.findIndex((s) => s.threadId === tid)
        if (idx >= 0) {
          controllers.get(sessions.value[idx].id)?.abort()
          controllers.delete(sessions.value[idx].id)
          sessions.value.splice(idx, 1)
          if (!sessions.value.some((s) => s.id === activeId.value)) {
            activeId.value = sessions.value[0]?.id ?? null
          }
          schedulePersist()
        }
        return
      }
      if (data.type === 'stream-claim' && data.threadId) {
        // 另一个标签页开始接收同一 Thread 的流 → 让出，避免重复写入
        const mine = sessions.value.find((s) => s.threadId === data.threadId)
        if (mine && mine.streaming) {
          controllers.get(mine.id)?.abort()
          controllers.delete(mine.id)
          const live = liveSession(mine)
          const runId = live.currentRunId
          if (runId) flushBuffer(bufferKey(live.id, runId))
          const m = runId ? findRunMessage(live, runId) : undefined
          if (m) m.streaming = false
          live.streaming = false
          live.stopped = true
          schedulePersist()
        }
      }
    }
  }

  // ============================================================
  // 后端数据 → 前端模型
  // ============================================================
  /**
   * 后端 parts → 前端 parts。
   * 后端把 tool_call 与 tool_result 存成相邻的两块，前端只保留一块
   * （tool_call 携带 name/args，工具返回内容合并成它的 content），与流式时的处理保持一致。
   *
   * 特例：`ask_user_question` 是「向用户提问」，不当作普通工具卡片，
   * 而是还原成前端自己的 `interrupt` 块 —— 位置和回答都能从服务端数据里得到：
   *  - 位置：这个 tool_call 块本来就在 parts 的时间轴顺序里
   *  - 回答：resume 之后工具正常结束，产生对应的 tool_result，content 就是 resolution
   */
  function convertParts(raw?: BackendMessagePart[] | null): MessagePart[] {
    const out: MessagePart[] = []
    if (!Array.isArray(raw)) return out
    for (const p of raw) {
      if (!p || typeof p !== 'object') continue
      if (p.type === 'thought' || p.type === 'text') {
        const text = typeof p.content === 'string' ? p.content : ''
        if (text) out.push({ type: p.type, content: text })
      } else if (p.type === 'tool_call') {
        if (p.name === 'ask_user_question') {
          // 提问不算工具卡片，转成 interrupt 块；用户回答稍后由配对的 tool_result 补上
          out.push({
            type: 'interrupt',
            tool_call_id: p.tool_call_id,
            interrupt: {
              // interrupt_id 不在 parts 里（interrupt 表也没有接口），历史回放用空串占位；
              // 它只用于「定位是哪一个中断」，展示与 resume 都不依赖它
              interrupt_id: '',
              action_type: 'clarify',
              questions: extractQuestions(p.args),
            },
          })
          continue
        }
        out.push({
          type: 'tool_call',
          tool_call_id: p.tool_call_id,
          name: p.name,
          args: (p.args || {}) as Record<string, unknown>,
          status: p.status || 'completed',
        })
      } else if (p.type === 'tool_result') {
        // 提问的回答落在配对的 interrupt 块上（而不是变成工具返回值）
        const target = out.find((x) => x.tool_call_id === p.tool_call_id)
        const content = typeof p.content === 'string' ? p.content : ''
        if (target?.type === 'interrupt') {
          const answers = parseInterruptAnswers(target.interrupt?.questions, content)
          if (answers.length) target.answers = answers
        } else if (target) {
          target.status = p.status || 'completed'
          target.content = content
        } else {
          out.push({
            type: 'tool_call',
            tool_call_id: p.tool_call_id,
            status: p.status || 'completed',
            content,
          })
        }
      } else if (p.type === 'interrupt') {
        /*
         * 中断块。
         * 后端目前**不会**把中断落进 parts（`requires_action` 只 publish 事件、不 append part），
         * 所以这一支是为「后端将来补上」预留的 —— 补上之后历史消息里中断的位置也会准确。
         * 兼容几种可能的落库形态：{interrupt:{...}} / {payload:{...}}。
         */
        const raw = p as BackendMessagePart & {
          interrupt?: InterruptPayload
          payload?: InterruptPayload
          answers?: InterruptAnswer[]
        }
        out.push({
          type: 'interrupt',
          interrupt: raw.interrupt ?? raw.payload,
          answers: Array.isArray(raw.answers) ? raw.answers : undefined,
        })
      } else {
        /*
         * 未知块类型：**不要丢弃**。
         * 后端的 parts.type 是自由字符串，将来加新块（引用、图表、练习题卡片…）时，
         * 旧前端如果直接 continue 掉，用户看到的就是「内容凭空少了一段」。
         * 这里退化为文本块，至少让内容可见。
         */
        const text =
          typeof p.content === 'string'
            ? p.content
            : p.content != null
              ? JSON.stringify(p.content)
              : ''
        if (text) out.push({ type: 'text', content: text })
      }
    }
    return out
  }

  /** 从 tool_call 的 args 里取回问题列表（与 live 的 requires_action.questions 同构） */
  function extractQuestions(args?: Record<string, unknown> | null): AgentQuestion[] {
    const qs = (args as { questions?: unknown } | null | undefined)?.questions
    if (!Array.isArray(qs)) return []
    return qs.filter((q) => q && typeof q === 'object') as AgentQuestion[]
  }

  /**
   * 解析历史里 `ask_user_question` 的用户回答。
   *
   * 后端的 tool_result content 是 Python 的 `str(list[dict])`，形如
   * `[{'id': 'q1', 'selected': ['方案A']}]`（**不是 JSON**，单引号）。
   * 所以先按 JSON 试（后端若改成 json.dumps 就直接命中），失败再按宽松规则抽取。
   * 抽到的 id / selected 与 args 里的 questions 按 id 配对，补上问题文本用于展示。
   */
  function parseInterruptAnswers(
    questions: AgentQuestion[] | undefined,
    content: string,
  ): InterruptAnswer[] {
    const text = (content || '').trim()
    if (!text || (text[0] !== '[' && text[0] !== '{')) return []
    const pairs: Array<{ id: string; selected: string[] }> = []

    // 1) 标准 JSON
    try {
      const parsed = JSON.parse(text)
      const arr = Array.isArray(parsed) ? parsed : [parsed]
      for (const item of arr) {
        if (item && typeof item === 'object' && typeof item.id === 'string') {
          const sel = (item as { selected?: unknown }).selected
          pairs.push({
            id: item.id,
            selected: Array.isArray(sel) ? sel.map((s) => String(s)) : sel != null ? [String(sel)] : [],
          })
        }
      }
    } catch {
      /* 落到宽松解析 */
    }

    // 2) Python repr：按 'id' / "id" 抓每一段，再抽出 selected 数组里的字符串
    if (pairs.length === 0) {
      const itemRe =
        /['"]id['"]\s*:\s*(['"])((?:\\.|(?!\1)[^\\])*)\1[\s\S]*?['"]selected['"]\s*:\s*\[([^\]]*)\]/g
      let m: RegExpExecArray | null
      while ((m = itemRe.exec(text))) {
        pairs.push({ id: m[2], selected: extractQuoted(m[3]) })
      }
    }

    const byId = new Map(questions?.map((q) => [q.id, q]) ?? [])
    return pairs.map((pair) => ({
      id: pair.id,
      question: byId.get(pair.id)?.header || byId.get(pair.id)?.question || pair.id,
      selected: pair.selected,
    }))
  }

  /** 抽出一段文本里所有被引号包住的字符串（单双引号都认，支持反斜杠转义） */
  function extractQuoted(text: string): string[] {
    const out: string[] = []
    const re = /(['"])((?:\\.|(?!\1)[^\\])*)\1/g
    let m: RegExpExecArray | null
    while ((m = re.exec(text))) {
      out.push(m[2].replace(/\\(['"\\])/g, '$1'))
    }
    return out
  }

  /**
   * 判断某个 Thread 是否正停在「等用户回答」的中断上。
   *
   * 判据来自服务端数据本身：assistant 消息的 `status` 仍是 `pending`（说明这轮没结束），
   * 且存在一个 `ask_user_question` 的 tool_call **没有配对的 tool_result**。
   * 用它可以在刷新/换设备后重新接上 pendingInterrupt + currentRunId，
   * 让用户继续回答并接着看后续输出。
   */
  function detectPendingInterrupt(
    list: AgentMessageItem[],
  ): { runId: string; questions: AgentQuestion[] } | null {
    for (let i = list.length - 1; i >= 0; i--) {
      const m = list[i]
      if (m.role !== 'assistant' || !m.run_id || m.status !== 'pending') continue
      if (!Array.isArray(m.parts)) continue
      const answered = new Set<string>()
      for (const p of m.parts) {
        if (p.type === 'tool_result' && p.tool_call_id) answered.add(p.tool_call_id)
      }
      for (const p of m.parts) {
        if (
          p.type === 'tool_call' &&
          p.name === 'ask_user_question' &&
          p.tool_call_id &&
          !answered.has(p.tool_call_id)
        ) {
          const questions = extractQuestions(p.args ?? undefined)
          if (questions.length) return { runId: m.run_id, questions }
        }
      }
    }
    return null
  }

  /** 兜底：parts 缺失时用 tool_calls 还原工具块（兼容早期数据） */
  function partsFromToolCalls(tcs?: ToolCall[] | null): MessagePart[] {
    if (!Array.isArray(tcs)) return []
    return tcs
      .filter((t) => t && typeof t === 'object')
      .map((t) => ({
        type: 'tool_call' as const,
        tool_call_id: t.tool_call_id || t.id,
        name: t.name,
        args: (t.args || {}) as Record<string, unknown>,
        status: t.status || 'completed',
        content: t.content,
      }))
  }

  /** 后端 SingleMessageResponse → 前端 AgentChatMessage */
  function toChatMessage(
    m: AgentMessageItem,
    answersByRun?: Record<string, InterruptAnswer[]>,
  ): AgentChatMessage {
    const isAssistant = m.role === 'assistant'
    let parts: MessagePart[] = []
    if (isAssistant) {
      parts = convertParts(m.parts)
      if (parts.length === 0) parts = partsFromToolCalls(m.tool_calls)
      // 极端情况：parts 没落库但 content 有内容 → 至少把正文显示出来
      if (parts.length === 0 && m.content) parts = [{ type: 'text', content: m.content }]
    }
    // 历史接口不给中断的 resolution，用本地留存的回答按 runId 补回一个 interrupt 块。
    // 注意：后端没记录中断在时间轴上的位置，所以刷新/换设备后只能补在**末尾**（尽力而为）；
    // 若后端在 requires_action 时往 parts 里落一个 interrupt 块，位置就能完全准确。
    const answers = m.run_id ? answersByRun?.[m.run_id] : undefined
    if (isAssistant && answers?.length && !parts.some((p) => p.type === 'interrupt')) {
      parts = [...parts, { type: 'interrupt', answers }]
    }
    return {
      id: m.id,
      role: isAssistant ? 'assistant' : 'user',
      content: m.content || '',
      parts,
      streaming: false,
      interrupt: null,
      // 后端补上 scope/scope_id 后，历史消息也能显示「📚 课程名」（详见 types.ts 的说明）
      scopeLabel: options.resolveScopeLabel?.(m.scope, m.scope_id),
      // 后端已返回 run_id：用于刷新后精确定位「该 Run 的 assistant 消息」
      runId: m.run_id ?? undefined,
      created_at: m.created_at,
    }
  }

  /** 由后端 thread 造一个会话骨架（消息懒加载） */
  function makeServerSession(t: AgentThread): ChatSession {
    return {
      // 用 threadId 派生，保证多次 listThreads 后 id 稳定、不重复
      id: `thread-${t.id}`,
      title: t.title || '未命名会话',
      threadId: t.id,
      messages: [],
      loaded: false,
      currentRunId: null,
      runFinished: true,
      streaming: false,
      pendingInterrupt: null,
      createdAt: toTs(t.created_at),
      updatedAt: toTs(t.updated_at),
    }
  }

  // ============================================================
  // 服务端同步：会话列表 / 历史消息
  // ============================================================
  /** 拉取会话列表并与本地缓存合并（后端为准） */
  async function loadThreads(): Promise<void> {
    threadsLoading.value = true
    try {
      const threads = await agentApi.listThreads()
      serverReady.value = true
      syncError.value = ''
      mergeThreads(threads)
    } catch (e: any) {
      // 后端不可用/未登录：保留本地缓存，前端仍可用（不阻塞）
      syncError.value = describeLoadError(e, '会话列表')
    } finally {
      threadsLoading.value = false
    }
  }

  function mergeThreads(threads: AgentThread[]) {
    const merged: ChatSession[] = []
    const seen = new Set<string>()

    // 1) 本地会话：有 threadId 的用后端信息校正标题
    for (const s of sessions.value) {
      if (!s.threadId) {
        // 本地新建的空会话（草稿），后端还没有它
        merged.push(s)
        continue
      }
      // 本次页面里已经删掉的不再复活（删完之后才返回的旧快照可能还带着它）
      if (locallyDeletedThreads.has(s.threadId)) continue
      const t = threads.find((x) => x.id === s.threadId)
      if (!t) {
        /*
         * 服务端列表里没有它。两种可能：
         *   a) 列表快照早于该 Thread 被创建（loadThreads 与 send 并发）—— 绝不能删，否则
         *      正在流式的会话会被从列表里摘掉，界面表现为「流式输出突然消失」；
         *   b) 真的被删了（软删除后列表按 active 过滤）。
         * 只有明确不是 a) 的情况才丢弃。
         */
        if (
          s.streaming ||
          hasIncompleteRun(s) ||
          locallyCreatedThreads.has(s.threadId)
        ) {
          merged.push(s)
        }
        continue
      }
      if (t.title) s.title = t.title
      seen.add(t.id)
      merged.push(s)
    }

    // 2) 后端有、本地没有的会话 → 建骨架
    for (const t of threads) {
      if (seen.has(t.id) || locallyDeletedThreads.has(t.id)) continue
      merged.push(makeServerSession(t))
    }

    merged.sort((a, b) => b.updatedAt - a.updatedAt)
    sessions.value = merged
    if (!activeId.value || !merged.some((s) => s.id === activeId.value)) {
      activeId.value = merged[0]?.id ?? null
    }
    schedulePersist()
  }

  /**
   * 拉取某会话的历史消息。
   *
   * 采用服务端结果时带一道「不回退」保险：只有当服务端消息数不少于本地时才覆盖。
   * 原因：run 结束时落库与前端收到 completed 事件之间可能有一瞬竞态，
   * 无条件覆盖会让刚流式出来的回答被清掉；而本地缓存被截断（条数/单块字数上限）时，
   * 服务端条数只会更多，仍能正常校正。
   */
  async function loadMessages(session: ChatSession) {
    session = liveSession(session)
    const tid = session.threadId
    if (!tid) {
      session.loaded = true
      return
    }
    if (session.streaming) return
    const first = !session.loaded
    if (first) messagesLoading.value = true
    try {
      const list = await agentApi.listMessages(tid)
      // 请求期间该会话可能已经开始新一轮 → 不覆盖实时内容
      if (session.streaming) return
      const converted = list.map((m) => toChatMessage(m, session.interruptAnswers))
      if (session.loaded && converted.length < session.messages.length) return
      session.messages = converted
      session.loaded = true
      /*
       * 历史里如果还有「已提问但未回答」的中断，就把 pendingInterrupt / currentRunId 接回来。
       * 这样刷新（甚至换设备）后仍然能回答，并接着看后续输出 ——
       * 判据完全来自服务端数据（见 detectPendingInterrupt）。
       */
      const pending = detectPendingInterrupt(list)
      if (pending) {
        session.pendingInterrupt = {
          interrupt_id: '',
          action_type: 'clarify',
          questions: pending.questions,
        }
        session.currentRunId = pending.runId
        session.runFinished = false
      } else if (session.pendingInterrupt && !session.runFinished) {
        // 服务端显示这一轮已经不在等回答了（例如别处已回复）→ 清掉本地挂起状态
        session.pendingInterrupt = null
      }
      // 历史接口不返回 interrupt：仍挂起的中断重新挂到最后一条 assistant 消息上
      if (session.pendingInterrupt && !session.runFinished) {
        const last = [...converted].reverse().find((m) => m.role === 'assistant')
        if (last) last.interrupt = session.pendingInterrupt
      }
      syncError.value = ''
      schedulePersist()
    } catch (e: any) {
      if (first) session.loaded = true
      syncError.value = describeLoadError(e, '历史消息')
    } finally {
      if (first) messagesLoading.value = false
    }
  }

  function describeLoadError(e: any, what: string): string {
    const status = e?.status
    if (status === 401) return `${what}加载失败：登录已过期，请重新登录`
    if (status === 404) return `${what}加载失败：会话已不存在`
    if (status === 409) return `${what}加载失败：该会话不是 active 状态（已归档/已删除）`
    if (status === 500) return `${what}加载失败：服务端内部错误（500），请查看后端日志`
    return `${what}加载失败：${e?.detail || e?.message || '网络异常'}`
  }

  /** 手动刷新当前会话历史（以服务端为准） */
  async function refreshCurrent() {
    const s = activeSession.value
    if (!s) return
    if (!s.threadId) {
      syncError.value = ''
      return
    }
    await loadMessages(s)
  }

  // ============================================================
  // 会话管理
  // ============================================================
  function newSession(): ChatSession {
    // 已经站在一个「还没提问过的空会话」里就不重复造，避免草稿会话堆积
    const cur = sessions.value.find((s) => s.id === activeId.value)
    if (cur && !cur.threadId && cur.messages.length === 0 && !cur.streaming) return cur
    const s: ChatSession = {
      id: nextId('sess'),
      title: '新会话',
      threadId: null,
      messages: [],
      loaded: true,
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
    // ⚠️ 必须返回数组里的响应式代理，不能返回原始对象 `s`（否则后续改动不触发视图更新）
    return liveSession(s)
  }

  /** 确保存在活跃会话（返回的必定是响应式代理） */
  function ensureSession(): ChatSession {
    const cur = sessions.value.find((s) => s.id === activeId.value)
    return cur ?? newSession()
  }

  function switchSession(id: string) {
    const s = sessions.value.find((x) => x.id === id)
    if (!s) return
    activeId.value = id
    schedulePersist()
    // 切过去时同步服务端历史（未加载过的会显示 loading；已加载的静默校正）
    if (s.threadId) void loadMessages(s)
  }

  /**
   * 确认某 thread 是否真的已从服务端消失。
   * 用于 DELETE 返回 404 时判定「本来就没有」还是「删除接口没生效」——
   * 光看 404 分不清：路由不存在（未重启后端/路径写错）也是 404。
   */
  async function isThreadGone(threadId: string): Promise<boolean> {
    try {
      const threads = await agentApi.listThreads()
      return !threads.some((t) => t.id === threadId)
    } catch {
      // 连列表都拿不到 → 无法确认，按「未删除成功」处理更安全
      return false
    }
  }

  /**
   * 删除会话：先删服务端（软删除），成功后再从本地移除。
   *
   * ⚠️ 不能在 404 时直接当成「已删除」：路由不存在（后端没重启、路径写错）同样返回 404，
   * 那样界面会"假装删除成功"，刷新后会话又冒出来（真实踩过这个坑）。
   * 所以 404 时回查一次会话列表来判定。
   *
   * @returns 成功返回 null，失败返回给用户看的原因
   */
  async function removeSession(id: string): Promise<string | null> {
    const s = sessions.value.find((x) => x.id === id)
    if (!s) return null
    // 后端 DELETE 不校验活跃 Run（只把 thread 置为 deleted，worker 仍会继续跑并落库），
    // 所以这里前端自己拦一下，避免删掉一个正在运行的会话。
    if (s.streaming) return '该会话正在运行，请等本轮结束再删除'
    const tid = s.threadId
    if (tid) {
      try {
        await agentApi.deleteThread(tid)
      } catch (e: any) {
        if (e?.status === 404) {
          if (await isThreadGone(tid)) {
            // 服务端确实已经没有它了 → 按成功处理，继续移除本地
          } else {
            return `删除失败：服务端仍存在该会话，DELETE /agent/threads/{thread_id} 没有生效（请确认后端已重启、该路由已注册，且路径没有被其它路由抢占）`
          }
        } else {
          return describeLoadError(e, '删除会话')
        }
      }
    }
    controllers.get(id)?.abort()
    controllers.delete(id)
    const idx = sessions.value.findIndex((x) => x.id === id)
    if (idx >= 0) sessions.value.splice(idx, 1)
    if (activeId.value === id) {
      activeId.value = sessions.value[0]?.id ?? null
      const next = sessions.value[0]
      if (next?.threadId) void loadMessages(next)
    }
    // 记录已删除：防止「删除前发出的会话列表请求」返回后把它重建出来
    if (tid) {
      locallyDeletedThreads.add(tid)
      locallyCreatedThreads.delete(tid)
    }
    schedulePersist()
    // 通知其它标签页同步移除
    if (tid) postSync({ type: 'session-deleted', threadId: tid })
    postSync({ type: 'threads-changed' })
    return null
  }

  /** 清空全部本地缓存（服务端会话下次进入会重新拉回） */
  function reset() {
    controllers.forEach((c) => c.abort())
    controllers.clear()
    sessions.value = []
    activeId.value = null
    error.value = ''
    syncError.value = ''
    clearStorage()
  }

  // ============================================================
  // 发送 / 流式
  // ============================================================

  /** 按 id 取回会话内的 reactive 消息对象 */
  function getMsg(session: ChatSession, id: string): AgentChatMessage | undefined {
    return liveSession(session).messages.find((m) => m.id === id)
  }

  /**
   * 定位某个 Run 的 assistant 消息。
   *
   * ⚠️ 为什么优先按 runId 而不是消息 id：一次 Run 只对应一条 assistant 消息，
   * 而 `loadMessages()` 会用服务端数据整体替换 `session.messages`（新对象、新 id）。
   * 如果 SSE 回调还按旧 id 查找，替换之后就永远找不到目标消息，
   * 表现同样是「流式输出不动了」。按 runId 查找可以穿过数组替换。
   */
  function findRunMessage(
    session: ChatSession,
    runId: string,
    fallbackId?: string,
  ): AgentChatMessage | undefined {
    const live = liveSession(session)
    return (
      live.messages.find((m) => m.role === 'assistant' && m.runId === runId) ??
      (fallbackId ? live.messages.find((m) => m.id === fallbackId) : undefined)
    )
  }

  async function ensureThread(session: ChatSession, title?: string): Promise<string> {
    if (session.threadId) return session.threadId
    const t = await agentApi.createThread({ title: title || '新会话' })
    session.threadId = t.id
    session.loaded = true
    // 记下来：会话列表快照可能早于它，避免被 mergeThreads 误删
    locallyCreatedThreads.add(t.id)
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

    // ensureSession 已保证返回响应式代理；这里再兜一层，防止以后改动再次退化
    const session = liveSession(ensureSession())
    // 仅限制「同一会话」并发；不同会话可同时运行
    if (session.streaming) return

    error.value = ''
    session.pendingInterrupt = null
    session.streaming = true
    session.stopped = false
    session.started = false
    session.reconnecting = 0
    session.lastEventAt = Date.now()
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

    await startRun(session, assistantMsgId, {
      text,
      // 幂等键在这里生成并随消息保存；重试时复用同一个键，
      // 这样「第一次请求其实已经建了 Run，只是响应丢了」的情况不会产生第二个 Run
      idempotencyKey: uuid(),
      scope: scope.scope,
      scope_id: scope.scope_id,
      scopeLabel: scope.label,
    })
  }

  /**
   * 真正发起一轮 Run（send / retryMessage 共用）。
   * payload 里带着幂等键与 scope，失败时留在消息上供重试复用。
   */
  async function startRun(
    session: ChatSession,
    assistantMsgId: string,
    payload: RetryPayload,
  ) {
    const msg = getMsg(session, assistantMsgId)
    if (msg) {
      msg.retry = payload
      msg.streaming = true
    }
    try {
      const tid = await ensureThread(session, payload.text.slice(0, 20))
      const run = await agentApi.createRun(tid, {
        prompt: payload.text,
        scope: payload.scope,
        scope_id: payload.scope_id,
        idempotency_key: payload.idempotencyKey,
      })
      session.currentRunId = run.run_id
      session.runFinished = false
      // 标记消息所属 run（用户消息是倒数第二条）
      const um = session.messages[session.messages.length - 2]
      const am = getMsg(session, assistantMsgId)
      if (um) um.runId = run.run_id
      if (am) {
        am.runId = run.run_id
        // 已经成功建 Run → 不需要再「重试发送」
        am.retry = undefined
      }

      // 告诉其它标签页：这个会话开始跑了（它们会主动让出，避免两条流写同一条消息）
      postSync({ type: 'threads-changed' })

      // 后台消费流（不 await）。consumeStream 内部已兜底重连与错误提示，
      // 这里再挂一个空 catch，纯粹为了避免未捕获的 Promise 拒绝
      void consumeStream(session, run.run_id, assistantMsgId).catch(() => undefined)
    } catch (e: any) {
      setErrorText(session, assistantMsgId, e?.message || '请求失败')
      session.streaming = false
      error.value = e?.message || '请求失败'
      schedulePersist()
    }
  }

  /**
   * 重试一次失败的发送：复用原来的幂等键与 scope。
   * 后端 `uq_runs_user_idempotency_key` + 幂等返回保证不会因为重试多出一个 Run。
   */
  async function retryMessage(msgId: string): Promise<boolean> {
    const current = activeSession.value
    if (!current) return false
    const session = liveSession(current)
    if (session.streaming) return false
    const msg = getMsg(session, msgId)
    if (!msg || !msg.retry) return false
    const payload = msg.retry
    error.value = ''
    session.streaming = true
    session.stopped = false
    session.started = false
    session.reconnecting = 0
    session.lastEventAt = Date.now()
    session.updatedAt = Date.now()
    msg.parts = []
    msg.interrupt = null
    await startRun(session, msgId, payload)
    return true
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
    startEventId?: string,
  ) {
    session = liveSession(session)
    if (!session.threadId) return
    const threadId = session.threadId
    // 流编号与帧缓冲都以 session 为粒度（同一时刻一个会话只有一条有效流）
    const token = nextStreamToken(session.id)
    // 增量缓冲按「会话 + run」定位，见 bufferKey 的说明
    const key = bufferKey(session.id, runId)
    const ctrl = new AbortController()
    controllers.set(session.id, ctrl)
    // 认领这个 Thread 的流：其它标签页若也在接收，会主动让出（防止两条流写同一条消息）。
    // 放在这里而不是 send() 里，是为了让「刷新后重连」的路径也走同一套让出逻辑。
    postSync({ type: 'stream-claim', threadId })

    /** 本次连接真正收到过的最后一个事件 id（用于 Last-Event-ID 增量续传） */
    let lastId = startEventId
    /** 是否收到过服务端明确的终态事件（completed / failed / canceled） */
    let terminalEventSeen = false
    /** 服务端明确告知 run 已终止（403）或 thread 不可用（404） */
    let forcedEnd = false
    let endedCleanly = false
    let stoppedByUser = false
    let giveUpError: any = null

    try {
      for (let attempt = 0; ; attempt++) {
        const connectedAt = Date.now()
        // 每次（重）连之前先把手里的增量刷掉，保证写入顺序与事件顺序一致
        flushBuffer(key)
        try {
          await streamSSE(
            agentApi.streamUrl(threadId, runId),
            (evt: SSEEvent) => {
              // 心跳：只更新存活时间，不参与渲染
              if (evt.event === 'heartbeat') {
                session.lastEventAt = Date.now()
                return
              }
              session.lastEventAt = Date.now()
              if (evt.id) lastId = evt.id
              if (evt.event === 'completed' || evt.event === 'failed' || evt.event === 'canceled') {
                terminalEventSeen = true
              }
              // 事件回调里按 runId 解析目标消息（见 findRunMessage 的说明）
              handleEvent(evt, session, runId, msgId)
            },
            lastId,
            ctrl.signal,
          )
          endedCleanly = true
          break
        } catch (e: any) {
          // 用户点了「停止接收」→ 静默收尾
          if (ctrl.signal.aborted) {
            stoppedByUser = true
            break
          }
          // 403 = run 已终止；404 = thread 已不存在。都不重试
          if (e?.status === 403 || e?.status === 404) {
            forcedEnd = true
            if (e?.status === 404) {
              syncError.value = 'SSE 连接失败：会话已不存在'
            }
            break
          }
          // 连了挺久才断，说明不是「服务端一直连不上」，重试计数归零重新开始
          if (Date.now() - connectedAt > STREAM_STABLE_MS) attempt = 0
          if (attempt >= MAX_STREAM_RETRY) {
            giveUpError = e
            break
          }
          session.reconnecting = attempt + 1
          schedulePersist()
          // 指数退避：0.8s → 1.6s → 3.2s → 5s
          await sleep(Math.min(800 * 2 ** attempt, 5000), ctrl.signal)
          if (ctrl.signal.aborted) {
            stoppedByUser = true
            break
          }
        }
      }
    } finally {
      flushBuffer(key)
      // 本条流已经不是这个会话的「当前有效流」→ 有更新的连接接管了，不要动状态
      if (streamTokens.get(session.id) === token) {
        controllers.delete(session.id)
        session.reconnecting = 0
        const msg = findRunMessage(session, runId, msgId)
        if (msg) msg.streaming = false
        session.streaming = false
        session.lastEventAt = undefined

        if (forcedEnd) {
          // 服务端说这一轮已经结束（stream 路由对终态 run 直接 403）
          session.runFinished = true
          session.stopped = false
        } else if (endedCleanly && !terminalEventSeen && !stoppedByUser) {
          /*
           * 后端 worker 只 publish 了 completed，**异常路径并不 publish failed/canceled**
           * （agent_tasks.py 的 except 分支只 `raise`）。此时 stream 路由会在
           * 「15s 轮询发现 run 已终态」后直接 return，表现为「连接正常关闭但没有任何终态事件」。
           * 既然是干净关闭，就说明服务端已判定该 run 结束，这里补一个终态，
           * 避免下次刷新又去重连一个已终止的 run（那会 403）。
           */
          session.runFinished = true
          session.stopped = false
          if (msg && msg.parts.length === 0 && !msg.content) {
            msg.parts.push({
              type: 'text',
              content:
                '😥 本轮没有返回任何内容：Agent 执行失败或被中断（后端当前不会推送 failed/canceled 事件）。',
            })
          }
        }

        if (giveUpError) {
          const detail = giveUpError?.status
            ? `HTTP ${giveUpError.status}`
            : giveUpError?.message || '网络异常'
          const note = `😥 流式连接中断且重连失败（${detail}），已保留已收到的内容。可点「继续接收」重新拉取。`
          if (msg && !msg.parts.some((p) => p.content === note)) {
            msg.parts.push({ type: 'text', content: note })
          }
          syncError.value = `流式连接中断：${detail}`
        }

        schedulePersist()
        // 收到终态事件 / 服务端明确说已结束 → 稍等片刻对一次服务端，校正被缓存截断的内容
        if ((terminalEventSeen || forcedEnd) && session.threadId) {
          setTimeout(() => void loadMessages(session), 400)
        }
      }
    }
  }

  /** 处理单个 SSE 事件 */
  function handleEvent(evt: SSEEvent, session: ChatSession, runId: string, msgId: string) {
    // 归一化成响应式对象，否则流式增量改了也不刷新
    const live = liveSession(session)
    const msg = findRunMessage(live, runId, msgId)
    if (!msg) return
    const type = evt.event || 'message'
    let data: any = {}
    try {
      data = evt.data ? JSON.parse(evt.data) : {}
    } catch {
      /* 非 JSON 忽略 */
    }

    switch (type) {
      case 'in_progress':
        // worker 抢到锁、开始执行了：可用于区分「排队中」与「执行中」
        live.started = true
        break
      case 'thought_delta':
        live.started = true
        // 增量先入帧缓冲，不直接写响应式状态
        queueDelta(live, runId, msgId, 'thought', data.delta || '')
        break
      case 'text_delta':
        live.started = true
        queueDelta(live, runId, msgId, 'text', data.delta || '')
        break
      case 'tool_call':
        // 非增量事件：先把手里的增量落盘，保证顺序
        flushBuffer(bufferKey(live.id, runId))
        live.started = true
        msg.parts.push({
          type: 'tool_call',
          tool_call_id: data.id || data.tool_call_id,
          name: data.name,
          args: data.args,
          status: data.status || 'running',
        })
        break
      case 'tool_result': {
        flushBuffer(bufferKey(live.id, runId))
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
      case 'requires_action': {
        // 非增量事件：先把手里的增量落盘，保证顺序
        flushBuffer(bufferKey(live.id, runId))
        const payload = data as InterruptPayload
        /*
         * 把中断也插入 parts 时间轴。
         *
         * ⚠️ 这里踩过坑：最初「待回答表单」和「已回复」卡片是渲染在 parts 之外的固定位置，
         * 结果回答之后模型继续输出 token 时，新内容会跑到卡片**下面** ——
         * 视觉上就像「已回复」一直贴在最底部。中断是时间轴上的一步，必须在 parts 里有自己的位置。
         */
        const iid = payload?.interrupt_id
        const exists =
          !!iid &&
          msg.parts.some((p) => p.type === 'interrupt' && p.interrupt?.interrupt_id === iid)
        if (!exists) msg.parts.push({ type: 'interrupt', interrupt: payload })
        msg.interrupt = payload
        live.pendingInterrupt = payload
        break
      }
      case 'completed':
      case 'failed':
      case 'canceled':
        flushBuffer(bufferKey(live.id, runId))
        msg.streaming = false
        live.streaming = false
        live.runFinished = true
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

  /**
   * 停止接收当前会话的流式输出。
   *
   * 注意：这只是**前端断开接收**，后端 worker 不会因此停下（真正的取消需要后端提供
   * cancel 接口 —— 目前 `RunStatus.CANCELED` 定义了但不可达，`agent_tasks.py` 里
   * 「取消信号检测」还是 TODO）。所以提示文案不能写成「已停止生成」。
   * 已收到的内容会保留，之后可以用「继续接收」重新接上。
   */
  function stopCurrent(): boolean {
    const current = activeSession.value
    if (!current) return false
    const session = liveSession(current)
    if (!session.streaming) return false
    session.stopped = true
    controllers.get(session.id)?.abort()
    controllers.delete(session.id)
    // 保住帧缓冲里还没刷出去的最后一段
    if (session.currentRunId) flushBuffer(bufferKey(session.id, session.currentRunId))
    const msg = session.currentRunId
      ? findRunMessage(session, session.currentRunId)
      : undefined
    if (msg) msg.streaming = false
    session.streaming = false
    session.reconnecting = 0
    schedulePersist()
    return true
  }

  /** 继续接收：重新接上同一个 run 的 stream（后端从 Redis Stream 重放，不会丢内容） */
  async function continueCurrent(): Promise<boolean> {
    const current = activeSession.value
    if (!current) return false
    const session = liveSession(current)
    if (!session.currentRunId || !session.threadId) return false
    // 可能还有一条连接挂着（比如「无响应」状态下其实没断）→ 先掐掉，
    // 否则两条流会同时往同一条消息里写。旧流的收尾会被 streamTokens 拦住。
    controllers.get(session.id)?.abort()
    controllers.delete(session.id)
    session.stopped = false
    await reconnect(session)
    return true
  }

  /** 回复当前会话的中断 */
  async function resume(answers: InterruptAnswerInput[]) {
    const current = activeSession.value
    const session = current ? liveSession(current) : null
    const interrupt = session?.pendingInterrupt
    if (!session || !interrupt || !session.threadId || !session.currentRunId) return
    error.value = ''

    const msg = session.messages.find((m) => m.interrupt?.interrupt_id === interrupt.interrupt_id)
    if (msg) msg.interrupt = null
    session.pendingInterrupt = null

    /*
     * 记录「用户选了什么」用于回显。
     *
     * 回答挂在 parts 里对应的 interrupt 块上（保持时间轴位置），
     * 同时按 runId 存到会话上并持久化 —— 因为后端历史接口不返回 resolution，
     * 刷新后要靠 toChatMessage 依据消息的 run_id 把这块重新补回 parts。
     */
    const runId = session.currentRunId
    if (runId) {
      const echo: InterruptAnswer[] = interrupt.questions.map((q) => ({
        id: q.id,
        question: q.header || q.question,
        selected: answers.find((a) => a.id === q.id)?.selected ?? [],
      }))
      const part = msg?.parts.find(
        (p) => p.type === 'interrupt' && p.interrupt?.interrupt_id === interrupt.interrupt_id,
      )
      if (part) part.answers = echo
      session.interruptAnswers = { ...(session.interruptAnswers || {}), [runId]: echo }
    }

    try {
      await agentApi.resumeRun(session.threadId, runId, answers)
      /*
       * 正常情况（本页一直在收流）SSE 连接还在，无需重连。
       * 但如果这次回答是「刷新/换设备后从历史里接回来的」，本地并没有连接，
       * 这里补一次连接，让用户能直接看到中断之后的输出。
       */
      if (!session.streaming) void reconnect(session)
      schedulePersist()
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
    session = liveSession(session)
    if (!session.threadId || !session.currentRunId) return
    const runId = session.currentRunId
    const findAssistant = () =>
      session.messages.find((m) => m.role === 'assistant' && m.runId === runId)

    // 先把 streaming 打开：这样 loadMessages / switchSession 不会在下面的 async 里
    // 把 messages 整体换掉，避免拿到游离的老消息对象（事件会被全部丢弃）
    session.streaming = true

    // 优先按 runId 精确匹配本地那条 assistant 消息
    let msg = findAssistant()
    if (!msg && !session.loaded) {
      // 换设备/首屏：先拉一次历史（后端已返回 run_id），再按 runId 精确匹配。
      // 这段时间临时放开 streaming，否则 loadMessages 会直接 return
      session.streaming = false
      await loadMessages(session)
      session.streaming = true
      msg = findAssistant()
    }
    if (!msg) {
      // 历史里也没有（例如 assistant 消息还没落库）→ 退化为「最后一条 assistant 消息」
      msg = [...session.messages].reverse().find((m) => m.role === 'assistant')
    }
    if (!msg) {
      // 连 assistant 消息都还没有（例如 user 消息刚落库）→ 建一个占位来承载重放
      msg = {
        id: nextId('a'),
        role: 'assistant',
        content: '',
        parts: [],
        streaming: true,
        interrupt: null,
        created_at: new Date().toISOString(),
      }
      session.messages.push(msg)
    }
    msg.runId = runId

    // 清空该消息的内容，准备用 Redis Stream 里的事件完整重放
    msg.parts = []
    msg.interrupt = null
    msg.streaming = true
    session.streaming = true
    session.stopped = false
    session.reconnecting = 0
    session.lastEventAt = Date.now()
    // 注意：这里【不】重置 started。重连意味着这一轮早就开始执行了，
    // 若重置为 false，增量续传（不回放 in_progress）时界面会误显示「排队中」。
    try {
      // consumeStream 内部自行处理重连/403/错误提示
      await consumeStream(session, runId, msg.id)
    } catch (e: any) {
      // 理论上不会走到这里；真抛了也不能让会话永远卡在 streaming
      session.streaming = false
      msg.streaming = false
      syncError.value = `恢复流式接收失败：${e?.message || '未知错误'}`
    }
    schedulePersist()
  }

  // 启动时：先渲染本地缓存（秒开），再拉服务端列表对齐
  setupSync()
  const pendingReconnectList = restoreLocal()
  for (const s of pendingReconnectList) {
    void reconnect(s)
  }
  /** 会话列表首次对齐完成的信号（页面层据此把 URL 里的 ?thread= 定位到具体会话） */
  const threadsReady = loadThreads().then(() => {
    // 列表对齐后：若当前会话还是没有内容的后端会话，补拉一次历史
    const cur = activeSession.value
    if (cur?.threadId && !cur.streaming) void loadMessages(cur)
  })

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

  // 只有存在运行中/重连中的会话时才开秒级时钟（用于「无响应」判定），避免空转
  watch(
    () => anyStreaming.value || sessions.value.some((s) => !!s.reconnecting),
    (active) => {
      if (active && !clockTimer) {
        clockTimer = setInterval(() => {
          nowMs.value = Date.now()
        }, 1000)
      } else if (!active) {
        stopClock()
      }
    },
    { immediate: true },
  )

  // 刷新/关闭前强制落盘（persistNow 内部会先 flush 帧缓冲）
  if (typeof window !== 'undefined') {
    const flush = () => persistNow()
    window.addEventListener('beforeunload', flush)
    // 切到后台时把增量刷掉，避免标签页被节流后 rAF 长时间不触发
    const onHidden = () => {
      if (document.visibilityState === 'hidden') flushAllBuffers()
    }
    document.addEventListener('visibilitychange', onHidden)
    onUnmounted(() => {
      window.removeEventListener('beforeunload', flush)
      document.removeEventListener('visibilitychange', onHidden)
      stopClock()
      try {
        channel?.close()
      } catch {
        /* 忽略 */
      }
      channel = null
    })
  } else {
    onUnmounted(stopClock)
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
    reset,
    // 当前会话便捷访问
    messages,
    threadId,
    streaming,
    isStreaming,
    pendingInterrupt,
    // 运行状态（排队中/执行中/等待回答/重连中/无响应/已停止）
    runState,
    runStateText,
    canContinue,
    // 服务端同步状态
    serverReady,
    threadsLoading,
    messagesLoading,
    syncError,
    loadThreads,
    loadMessages,
    refreshCurrent,
    /** 首次会话列表对齐完成（Promise） */
    threadsReady,
    error,
    // 操作
    send,
    retryMessage,
    resume,
    stopCurrent,
    continueCurrent,
    persistNow,
  }
}
