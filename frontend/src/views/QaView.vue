<template>
  <div class="qa-page">
    <!-- ============ 左侧：会话列表 ============ -->
    <aside class="qa-sidebar">
      <div class="sidebar-head">
        <el-button type="primary" class="btn-primary new-btn" :icon="Plus" @click="onNewSession">
          新建会话
        </el-button>
      </div>
      <div class="sidebar-search">
        <el-input
          v-model="sessionQuery"
          size="small"
          clearable
          :prefix-icon="Search"
          placeholder="搜索会话标题/内容"
        />
      </div>
      <div class="session-list">
        <div v-if="threadsLoading" class="session-loading">
          <el-icon class="animate-pulse" :size="13"><Loading /></el-icon> 加载会话列表…
        </div>
        <el-empty
          v-else-if="sessions.length === 0"
          description="暂无会话"
          :image-size="60"
          class="session-empty"
        />
        <el-empty
          v-else-if="filteredSessions.length === 0"
          description="没有匹配的会话"
          :image-size="50"
          class="session-empty"
        />
        <template v-for="group in groupedSessions" :key="group.label">
          <div class="session-group">{{ group.label }}</div>
          <div
            v-for="s in group.items"
            :key="s.id"
            class="session-item"
            :class="{ active: s.id === activeId }"
            @click="switchSession(s.id)"
          >
            <div class="session-main">
              <div class="session-title" :title="s.title">
                <el-icon v-if="s.streaming" class="animate-pulse running-dot" :size="12"><Loading /></el-icon>
                {{ s.title }}
              </div>
              <div class="session-meta">
                {{ timeLabel(s.updatedAt) }}
                <template v-if="s.loaded"> · {{ s.messages.length }} 条</template>
                <template v-else-if="s.id === activeId"> · 加载中…</template>
              </div>
            </div>
            <el-icon class="session-del" :size="14" @click.stop="onRemoveSession(s.id)" title="删除会话">
              <Delete />
            </el-icon>
          </div>
        </template>
      </div>
      <div v-if="anyStreaming" class="sidebar-foot">
        <el-icon class="animate-pulse" :size="12"><Loading /></el-icon>
        有会话正在运行
      </div>
    </aside>

    <!-- ============ 右侧：对话主体 ============ -->
    <div class="qa-main">
      <!--
        这里刻意**没有顶栏**：聊天区直接顶到最上面，把纵向空间全留给消息。
        原来顶栏里的东西都并进了输入区上方那一行（见下方 scope-row）：
        课程选择、运行状态 = 左侧；停止/继续接收、会话操作「⋯」= 右侧。
        这些控件只在需要时出现，空闲时那一行几乎只有一个课程芯片。
      -->

      <el-alert
        v-if="syncError"
        type="warning"
        :closable="false"
        show-icon
        class="sync-alert"
        :title="syncError"
      >
        <template #default>
          <span class="sync-alert-tip">当前可能显示的是本地缓存内容，后端恢复后可点「刷新历史」重新同步。</span>
        </template>
      </el-alert>

      <!--
        对话区：**始终渲染**。
        知识库 scope 只决定「下一次提问去哪个库检索」，跟历史消息无关，
        所以没选课程时也要能看会话记录（只有"提问"需要先选课程）。
      -->
      <div class="qa-body">
        <div ref="msgBox" class="chat-messages" @scroll="onScroll">
          <!-- 居中窄栏：消息、欢迎页、骨架屏都收在这一列里，像 DeepSeek / Gemini 那样 -->
          <div class="chat-column">
            <!-- 加载历史骨架屏（比一个「加载中」标签更能说明正在发生什么） -->
            <div v-if="messagesLoading && messages.length === 0" class="cc-skeleton">
            <div v-for="i in 3" :key="i" class="cc-skeleton-row">
              <div class="cc-skeleton-avatar cc-sk-shimmer"></div>
              <div class="cc-skeleton-lines">
                <div class="cc-sk-line cc-sk-shimmer" :class="i % 2 ? 'is-mid' : ''"></div>
                <div class="cc-sk-line cc-sk-shimmer"></div>
                <div class="cc-sk-line is-short cc-sk-shimmer"></div>
              </div>
            </div>
          </div>

          <!-- 空会话 + 没选课程：提示先选课程 -->
          <div v-else-if="messages.length === 0 && selectedCourseId == null" class="chat-welcome">
            <div class="cw-logo"><el-icon :size="40" color="#2d6cdf"><MagicStick /></el-icon></div>
            <h3>课程 Agent 智能助手</h3>
            <p>请先在右上角选择一门课程知识库，然后就可以开始提问了</p>
          </div>

          <!-- 空会话 + 已选课程：欢迎页 + 推荐问题 -->
          <div v-else-if="messages.length === 0" class="chat-welcome">
            <div class="cw-logo"><el-icon :size="40" color="#2d6cdf"><MagicStick /></el-icon></div>
            <h3>课程 Agent 智能助手</h3>
            <p>基于《{{ courseName }}》的知识库，可检索资料、并在需要时向你提问澄清</p>
            <div class="suggest-grid">
              <div v-for="(s, i) in suggestions" :key="i" class="suggest-chip" @click="ask(s)">{{ s }}</div>
            </div>
          </div>

          <!-- 消息列表：不带头像，靠「左文右泡」区分角色（DeepSeek / Gemini 的做法） -->
          <template v-for="m in messages" :key="m.id">
            <div v-if="m.role === 'user'" class="msg-row is-user">
              <div class="user-side">
                <span v-if="m.scopeLabel" class="scope-tag">📚 {{ m.scopeLabel }}</span>
                <div class="msg-bubble user-bubble">{{ m.content }}</div>
                <!--
                  操作行放在用户消息**下方**（和助手消息的操作位置一致）。
                  用固定高度 + opacity 而不是 v-if/display：
                  悬停出现时不会把下面的消息顶下去（布局不跳动）。
                  将来要加「编辑消息」「重新生成」直接往这一行里塞即可。
                -->
                <div class="user-actions">
                  <span
                    class="msg-action"
                    title="复制这条提问"
                    @click="onCopyText(m.content, '提问')"
                  >
                    <el-icon :size="12"><DocumentCopy /></el-icon> 复制
                  </span>
                </div>
              </div>
            </div>

            <div v-else class="msg-row is-ai">
              <div class="ai-content">
                <!--
                  所有块都按 parts 的顺序渲染。
                  中断（提问表单 / 已回复卡片）也是 parts 的一员 —— 它必须留在时间轴上的原位，
                  否则回答之后模型继续输出时，新内容会跑到卡片下面，看起来像卡片一直贴在最底部。
                -->
                <template v-for="(p, pi) in m.parts" :key="`${m.id}-${pi}`">
                  <div v-if="p.type === 'interrupt'" class="part part-interrupt">
                    <InterruptForm
                      v-if="!p.answers?.length && p.interrupt"
                      :interrupt="p.interrupt"
                      @submit="onInterruptSubmit"
                    />
                    <div v-else-if="p.answers?.length" class="answer-echo">
                      <div class="ae-head">
                        <el-icon :size="13" color="#1fa06d"><CircleCheckFilled /></el-icon>
                        已回复
                      </div>
                      <div v-for="a in p.answers" :key="a.id" class="ae-row">
                        <span class="ae-q">{{ a.question }}</span>
                        <span class="ae-a">{{ a.selected.length ? a.selected.join('、') : '（空）' }}</span>
                      </div>
                    </div>
                  </div>
                  <MessagePartItem
                    v-else
                    :part="p"
                    :streaming="m.streaming"
                    :default-collapsed="!m.streaming"
                  />
                </template>

                <div v-if="m.streaming && m.parts.length === 0" class="waiting-box">
                  <span class="cc-dots"><i></i><i></i><i></i></span>
                  <span class="waiting-text">
                    {{ runState === 'queued' ? '排队等待执行' : '正在检索与思考' }}
                  </span>
                </div>

                <!-- 发送失败 → 复用同一幂等键重试 -->
                <div v-if="m.retry && !m.streaming" class="retry-box">
                  <el-button size="small" :icon="RefreshRight" @click="onRetry(m.id)">
                    重试发送（复用同一幂等键，不会产生重复会话轮次）
                  </el-button>
                </div>

                <div class="msg-time">
                  <span v-if="m.scopeLabel" class="scope-tag">📚 {{ m.scopeLabel }}</span>
                  {{ formatDateTime(m.created_at, 'HH:mm:ss') }}
                  <span
                    v-if="!m.streaming && m.parts.some((p) => p.type === 'text' && p.content)"
                    class="msg-action"
                    @click="onCopyAnswer(m)"
                  >
                    <el-icon :size="12"><DocumentCopy /></el-icon> 复制
                  </span>
                </div>
              </div>
            </div>
          </template>

          <transition name="fade">
            <el-button
              v-if="!atBottom"
              class="to-bottom"
              :class="{ 'has-new': isStreaming }"
              round
              :icon="Bottom"
              @click="scrollToBottom(true, true)"
            >
              {{ isStreaming ? '新内容' : '回到底部' }}
            </el-button>
          </transition>
          </div>
        </div>

        <!-- 输入区：与消息同一列宽，做成一个圆角输入卡（DeepSeek / Gemini 那种 composer） -->
        <div class="chat-input-area">
          <div class="chat-column">
            <!--
              这一行承担了原来顶栏的全部职责，但不额外占一行高度：
                左：知识库作用域（scope 属于每一次提问）+ 运行状态
                右：运行控制（停止/继续）+ 会话操作「⋯」
              空闲时左只剩一个课程芯片、右只剩一个「⋯」，几乎不占视线。
            -->
            <div class="scope-row">
              <div class="scope-picker">
                <CourseSelector v-model="selectedCourseId" compact />
              </div>

              <span v-if="runState !== 'idle'" class="run-state" :class="`is-${runState}`">
                <el-icon :class="{ 'animate-pulse': runState !== 'stopped' }" :size="13">
                  <Loading v-if="runState !== 'stopped'" />
                  <VideoPause v-else />
                </el-icon>
                {{ runStateText }}
              </span>
              <el-tag
                v-else-if="messagesLoading"
                type="info"
                effect="plain"
                size="small"
                class="streaming-tag"
              >
                <el-icon class="animate-pulse" :size="12"><Loading /></el-icon> 加载历史…
              </el-tag>
              <span v-else class="scope-note">
                <template v-if="selectedCourseId == null">请先选择课程知识库，之后才能提问</template>
                <template v-else>只影响这一次提问，历史记录不受影响</template>
              </span>

              <span class="scope-row-actions">
                <el-button v-if="isStreaming" text size="small" :icon="VideoPause" @click="onStop">
                  停止接收
                </el-button>
                <el-button
                  v-else-if="runState === 'stalled'"
                  text
                  size="small"
                  :icon="RefreshRight"
                  @click="onContinue"
                >
                  重新连接
                </el-button>
                <el-button
                  v-else-if="canContinue"
                  text
                  size="small"
                  :icon="RefreshRight"
                  @click="onContinue"
                >
                  继续接收
                </el-button>

                <el-dropdown trigger="click" placement="top-end" @command="onSessionCommand">
                  <el-button text size="small" :icon="MoreFilled" title="会话操作" />
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item
                        command="refresh"
                        :icon="Refresh"
                        :disabled="!activeSession?.threadId"
                      >
                        刷新历史
                      </el-dropdown-item>
                      <el-dropdown-item
                        command="export"
                        :icon="Download"
                        :disabled="messages.length === 0"
                      >
                        导出为 Markdown
                      </el-dropdown-item>
                      <el-dropdown-item
                        command="delete"
                        :icon="Delete"
                        divided
                        :disabled="!activeSession"
                      >
                        删除本会话
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </span>
            </div>

            <div class="composer-box">
              <el-input
                v-model="input"
                type="textarea"
                :rows="1"
                :autosize="{ minRows: 1, maxRows: 6 }"
                resize="none"
                :placeholder="
                  selectedCourseId == null
                    ? '请先选择课程知识库后再提问...'
                    : '输入问题，Enter 发送，Shift + Enter 换行...'
                "
                :disabled="isStreaming || selectedCourseId == null"
                @keydown.enter.exact.prevent="send"
              />
              <el-button
                type="primary"
                class="send-btn btn-primary"
                :icon="Promotion"
                circle
                size="large"
                :disabled="!input.trim() || isStreaming || selectedCourseId == null"
                @click="send"
                title="发送"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Promotion,
  Bottom,
  Delete,
  MagicStick,
  Plus,
  Loading,
  Refresh,
  VideoPause,
  RefreshRight,
  Search,
  Download,
  DocumentCopy,
  CircleCheckFilled,
  MoreFilled,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useKnowledgeStore } from '@/stores/knowledge'
import { pickCoursesForRole, useCourseStore } from '@/stores/course'
import { useAgentChat } from '@/composables/useAgentChat'
import { formatDateTime, fromNow } from '@/utils/format'
import { copyText } from '@/utils/clipboard'
import { downloadText, safeFileName, sessionToMarkdown } from '@/utils/chatExport'
import type { AgentChatMessage, ChatSession, InterruptAnswerInput } from '@/api/types'
import CourseSelector from '@/components/CourseSelector.vue'
import InterruptForm from '@/components/agent/InterruptForm.vue'
import MessagePartItem from '@/components/agent/MessagePartItem.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const knowledgeStore = useKnowledgeStore()
const courseStore = useCourseStore()

const selectedCourseId = ref<number | null>(
  route.query.courseId ? Number(route.query.courseId) : knowledgeStore.selectedCourseId,
)

watch(selectedCourseId, (val) => {
  knowledgeStore.setCourseId(val)
  // 切换知识库【不】清空对话：Thread 是持久容器，scope 属于每个 Run
  const topic = route.query.topic as string | undefined
  if (topic && val != null) {
    input.value = `关于「${topic}」，请帮我总结核心知识点`
  }
})

const courseName = computed(() => {
  const c = courseStore.allCourses.find((x) => x.id === selectedCourseId.value)
  return c?.name || '当前课程'
})

/** 当前角色下可选的课程（与输入区的 CourseSelector 用同一份逻辑，保证「默认选中」的一定在列表里） */
const availableCourses = computed(() =>
  pickCoursesForRole(auth.user?.role, {
    teaching: courseStore.teaching,
    enrolled: courseStore.enrolled,
    allList: courseStore.allList,
  }),
)

/**
 * 首次进入时默认选中第一门课程。
 * 知识库 scope 只影响「提问去哪个库检索」，默认选上能省掉一次无意义的点击；
 * 用户仍然可以随时改，改完只影响下一次提问（不影响已有历史）。
 */
function ensureCourseSelected() {
  if (selectedCourseId.value != null) return
  const first = availableCourses.value[0]
  if (first) selectedCourseId.value = first.id
}

const suggestions = [
  '这门课程主要讲了哪些内容？',
  '帮我总结知识库中的重点知识',
  '根据课程资料出一道练习题',
  '解释一下课程中的核心概念',
]

// Agent 多会话（会话列表/历史消息以后端为准）
const {
  sessions,
  activeId,
  activeSession,
  messages,
  isStreaming,
  runState,
  runStateText,
  canContinue,
  threadsLoading,
  messagesLoading,
  syncError,
  anyStreaming,
  newSession,
  switchSession,
  removeSession,
  refreshCurrent,
  stopCurrent,
  continueCurrent,
  send: agentSend,
  retryMessage,
  resume: agentResume,
  threadsReady,
} = useAgentChat(
  () =>
    selectedCourseId.value != null
      ? { scope: 'course', scope_id: `course_${selectedCourseId.value}`, label: courseName.value }
      : null,
  {
    /**
     * 历史消息的「📚 课程名」标签。
     * 后端补上消息级 scope_id 之后这里立刻生效（scope_id 形如 `course_1`，反查课程名即可）。
     */
    resolveScopeLabel: (_scope, scopeId) => {
      const raw = (scopeId || '').trim()
      const id = Number(raw.replace(/^course_/, ''))
      if (!raw || !Number.isFinite(id) || id <= 0) return undefined
      return courseStore.allCourses.find((c) => c.id === id)?.name
    },
  },
)

const input = ref('')
const msgBox = ref<HTMLDivElement>()
const atBottom = ref(true)
const sessionQuery = ref('')

// ============================================================
// 会话列表：搜索 + 按时间分组
// ============================================================
const filteredSessions = computed<ChatSession[]>(() => {
  const q = sessionQuery.value.trim().toLowerCase()
  // 空查询直接返回原列表：这样不会去读每条消息的内容，
  // 也就不会在流式输出时因为「消息内容变了」而反复重算过滤结果
  if (!q) return sessions.value
  return sessions.value.filter((s) => {
    if (s.title.toLowerCase().includes(q)) return true
    // 也搜已加载的消息内容（未加载的会话只有标题可比）
    return s.messages.some(
      (m) =>
        m.content.toLowerCase().includes(q) ||
        m.parts.some(
          (p) =>
            (p.content || '').toLowerCase().includes(q) ||
            (p.answers || []).some((a) => a.selected.join(' ').toLowerCase().includes(q)),
        ),
    )
  })
})

const groupedSessions = computed<Array<{ label: string; items: ChatSession[] }>>(() => {
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const startOfYesterday = startOfToday - 86_400_000
  const startOf7Days = startOfToday - 6 * 86_400_000
  const buckets: Array<{ label: string; items: ChatSession[] }> = [
    { label: '今天', items: [] },
    { label: '昨天', items: [] },
    { label: '近 7 天', items: [] },
    { label: '更早', items: [] },
  ]
  for (const s of filteredSessions.value) {
    if (s.updatedAt >= startOfToday) buckets[0].items.push(s)
    else if (s.updatedAt >= startOfYesterday) buckets[1].items.push(s)
    else if (s.updatedAt >= startOf7Days) buckets[2].items.push(s)
    else buckets[3].items.push(s)
  }
  return buckets.filter((b) => b.items.length > 0)
})

// ============================================================
// 会话深链：URL 上带 ?thread=<后端 thread id>
// 这样刷新、收藏、前进后退都能精确回到同一个会话（不再只依赖 localStorage）
// ============================================================
/**
 * 进页面时 URL 上指定的会话。
 * 必须在这里就抓下来：下面 loadThreads/mergeThreads 可能会把 activeId 换成
 * 「上次活跃的会话」，若那时还允许「当前会话 → URL」的同步，就会把 URL 里的
 * ?thread= 覆盖掉，首屏定位也就跟着错了。
 */
const initialThreadParam = (route.query.thread as string | undefined) || ''
/** 首屏定位完成前，不把当前会话写回 URL */
const urlReady = ref(false)

const threadParam = computed(() => (route.query.thread as string | undefined) || '')

/** 当前会话 → 同步到 URL（用 thread id 而不是本地会话 id，链接才可分享/跨设备有效） */
watch(
  () => activeSession.value?.threadId ?? '',
  (tid) => {
    if (!urlReady.value) return
    if (tid === threadParam.value) return
    const query = { ...route.query }
    if (tid) query.thread = tid
    else delete query.thread
    void router.replace({ query })
  },
)

/** URL → 切到对应会话（浏览器前进后退、外部链接、手输地址） */
watch(threadParam, (tid) => {
  if (!urlReady.value) return
  if (!tid) return
  if (activeSession.value?.threadId === tid) return
  const target = sessions.value.find((s) => s.threadId === tid)
  if (target) {
    switchSession(target.id)
    return
  }
  // 列表里还没有它：可能列表尚未对齐，等一次再试
  void threadsReady.then(() => {
    const again = sessions.value.find((s) => s.threadId === tid)
    if (again) switchSession(again.id)
    else clearThreadParam()
  })
})

function clearThreadParam() {
  if (!route.query.thread) return
  const query = { ...route.query }
  delete query.thread
  void router.replace({ query })
}

// 流式内容增长时自动滚动（仅当前会话）
watch(
  () => {
    const last = messages.value[messages.value.length - 1]
    if (!last) return ''
    const len = last.parts.reduce((sum, p) => sum + (p.content?.length || 0), 0)
    return `${messages.value.length}-${len}-${last.interrupt ? 'i' : 'n'}`
  },
  () => {
    if (atBottom.value) scrollToBottom()
  },
)

/**
 * 手动刷新历史时保住滚动位置：
 * 消息整体被替换后 scrollHeight 会变，如果用户当时正在往上翻，直接跳到底部很难受。
 */
let scrollRestore: { fromBottom: number; wasAtBottom: boolean } | null = null

watch(messages, async () => {
  const pending = scrollRestore
  if (!pending) return
  scrollRestore = null
  await nextTick()
  const el = msgBox.value
  if (!el) return
  el.scrollTop = pending.wasAtBottom
    ? el.scrollHeight
    : Math.max(0, el.scrollHeight - el.clientHeight - pending.fromBottom)
})
onMounted(async () => {
  if (auth.user) await courseStore.refreshMyCourses(auth.user.role)

  // 首次进入：默认选中第一门课程（URL 里带了 courseId 的话以 URL 为准）
  ensureCourseSelected()

  // 首屏：优先按 URL 里的 ?thread= 定位会话（用进页面时就抓下来的值）
  await threadsReady
  if (initialThreadParam) {
    const target = sessions.value.find((s) => s.threadId === initialThreadParam)
    if (target) switchSession(target.id)
  }
  // 之后才允许把「当前会话」写回 URL，避免上面这种首屏定位被反向覆盖
  urlReady.value = true
  if (initialThreadParam && activeSession.value?.threadId !== initialThreadParam) {
    // URL 里指定的会话不存在（已删除/别人的链接）→ 清掉参数
    clearThreadParam()
  }

  const topic = route.query.topic as string | undefined
  if (topic && selectedCourseId.value != null) {
    setTimeout(() => send(), 0)
  }
})

function timeLabel(ts: number) {
  return fromNow(new Date(ts).toISOString())
}

function onScroll() {
  const el = msgBox.value
  if (!el) return
  atBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 60
}

async function scrollToBottom(force = false, smooth = false) {
  await nextTick()
  const el = msgBox.value
  if (!el) return
  if (force || atBottom.value) {
    // 流式自动滚动必须瞬时（smooth 会让视口一直追不上），用户主动点击才平滑
    if (smooth) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
    else el.scrollTop = el.scrollHeight
  }
}

function ask(text: string) {
  input.value = text
  send()
}

async function send() {
  const text = input.value
  if (!text.trim()) return
  if (selectedCourseId.value == null) {
    ElMessage.warning('请先在右上角选择课程知识库')
    return
  }
  input.value = ''
  atBottom.value = true
  await agentSend(text)
  scrollToBottom(true)
}

function onNewSession() {
  const before = activeId.value
  newSession()
  ElMessage.success(activeId.value === before ? '当前已经是空会话' : '已新建会话')
}

async function onRemoveSession(id: string) {
  const target = sessions.value.find((s) => s.id === id)
  if (target?.streaming) {
    ElMessage.warning('该会话正在运行，请等本轮结束再删除')
    return
  }
  try {
    await ElMessageBox.confirm(
      target?.threadId
        ? '确定删除该会话吗？删除后服务端也会一并移除（软删除），不可恢复。'
        : '确定删除该会话吗？',
      '提示',
      { type: 'warning' },
    )
  } catch {
    return // 用户取消
  }
  const err = await removeSession(id)
  if (err) ElMessage.error(err)
  else ElMessage.success('已删除会话')
}

function onInterruptSubmit(answers: InterruptAnswerInput[]) {
  void agentResume(answers)
  scrollToBottom(true)
}

async function onRetry(msgId: string) {
  const ok = await retryMessage(msgId)
  if (ok) {
    atBottom.value = true
    await scrollToBottom(true)
  }
}

/** 复制任意文本（用户提问 / 助手回答都走这里） */
async function onCopyText(text: string, label = '内容') {
  const ok = await copyText(text)
  if (ok) ElMessage.success(`已复制${label}`)
  else ElMessage.error('复制失败，请手动选择文本')
}

async function onCopyAnswer(m: AgentChatMessage) {
  const text =
    m.parts
      .filter((p) => p.type === 'text')
      .map((p) => p.content || '')
      .join('\n\n')
      .trim() || m.content
  await onCopyText(text, '回答')
}

function onExport() {
  const title = activeSession.value?.title || '会话记录'
  if (messages.value.length === 0) {
    ElMessage.warning('当前会话还没有内容')
    return
  }
  downloadText(safeFileName(title), sessionToMarkdown(title, messages.value))
  ElMessage.success('已导出为 Markdown')
}

async function onRefresh() {
  // 记录当前滚动位置，替换消息后恢复
  const el = msgBox.value
  if (el) {
    scrollRestore = {
      fromBottom: el.scrollHeight - el.scrollTop - el.clientHeight,
      wasAtBottom: atBottom.value,
    }
    // 兜底：若这次刷新并没有真的替换消息（服务端条数更少被守卫拦下），
    // 定时清掉，免得下一次无关的消息变化错误地套用旧位置
    setTimeout(() => {
      scrollRestore = null
    }, 3000)
  }
  await refreshCurrent()
  // refreshCurrent 失败时会把原因写进 syncError（顶部告警条同时会显示）
  if (syncError.value) ElMessage.error(syncError.value)
  else ElMessage.success('已从服务端刷新历史')
}

function onStop() {
  if (stopCurrent()) {
    ElMessage.info('已停止接收（后端可能仍在执行，可点「继续接收」重新接上）')
  }
}

async function onContinue() {
  const ok = await continueCurrent()
  if (!ok) ElMessage.warning('当前没有可继续接收的对话')
}

/** 顶栏「⋯」菜单：会话级操作都收在这里，避免顶栏被按钮占满 */
type SessionCommand = 'refresh' | 'export' | 'delete'
async function onSessionCommand(command: SessionCommand) {
  if (command === 'refresh') {
    await onRefresh()
  } else if (command === 'export') {
    onExport()
  } else if (command === 'delete') {
    const id = activeId.value
    if (id) await onRemoveSession(id)
  }
}
</script>

<style scoped>
/*
 * 布局要点（参考 DeepSeek / Gemini 的网页端）：
 *  - 消息不再是「占满可用宽度再给正文限窄」，而是整列**居中限宽**（--chat-col），
 *    顶栏、消息、输入卡都对齐到同一条栏宽 —— 这样容器宽度 = 阅读宽度，两侧留白是对称的，
 *    不会出现「容器很宽、文字很窄、两边大片死区」的逼仄感。
 *  - 聊天区用纯白，侧栏用浅灰：让视线集中在 Agent 的输出上。
 *  - 用户消息改成淡蓝底 + 深色字（原来是与正文抢注意力的高饱和蓝底白字）。
 */
.qa-page {
  --chat-col: 840px;
  --chat-gutter: 28px;
  height: calc(100vh - 52px);
  display: flex;
  overflow: hidden;
  background: var(--bg-card);
}

/* ============ 左侧会话列表 ============ */
.qa-sidebar {
  width: 248px;
  flex-shrink: 0;
  background: var(--bg-soft);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}
.sidebar-head {
  padding: 14px 12px;
  border-bottom: 1px solid var(--border);
}
.sidebar-search {
  padding: 8px 10px 4px;
  flex-shrink: 0;
}
.session-group {
  padding: 8px 10px 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-faint);
  letter-spacing: 0.02em;
}
.new-btn {
  width: 100%;
}
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.session-loading {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 14px 10px;
  font-size: 13px;
  color: var(--text-faint);
}
.session-empty {
  margin-top: 20px;
}
.session-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  margin-bottom: 2px;
  transition: background 0.2s;
}
.session-item:hover {
  background: var(--bg-soft);
}
.session-item.active {
  background: var(--brand-light);
}
.session-main {
  flex: 1;
  min-width: 0;
}
.session-title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-item.active .session-title {
  color: var(--brand);
}
.running-dot {
  flex-shrink: 0;
  color: var(--brand);
}
.session-meta {
  font-size: 12px;
  color: var(--text-faint);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-del {
  flex-shrink: 0;
  color: var(--text-faint);
  opacity: 0;
  transition: opacity 0.15s;
}
.session-item:hover .session-del {
  opacity: 1;
}
.session-del:hover {
  color: var(--red);
}
.sidebar-foot {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 10px 14px;
  border-top: 1px solid var(--border);
  font-size: 12.5px;
  color: var(--brand);
  flex-shrink: 0;
}

/* ============ 右侧主体 ============ */
.qa-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  /* 没有顶栏，聊天区直接顶到最上面，纵向空间全给消息 */
  background: var(--bg-card);
}
.streaming-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
/* 运行状态条：把「排队中/执行中/等待回答/重连中/无响应/已停止」如实画出来 */
.run-state {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  padding: 2px 9px;
  border-radius: 11px;
  border: 1px solid var(--brand-border);
  background: var(--brand-light);
  color: var(--brand);
  white-space: nowrap;
}
.run-state.is-queued {
  border-color: var(--border);
  background: var(--bg-soft);
  color: var(--text-secondary);
}
.run-state.is-waiting {
  border-color: #ffe58f;
  background: #fffbe6;
  color: #8c6d1f;
}
.run-state.is-reconnecting,
.run-state.is-stalled {
  border-color: #ffd591;
  background: #fff7e6;
  color: #ad4e00;
}
.run-state.is-stopped {
  border-color: var(--border);
  background: var(--bg-soft);
  color: var(--text-secondary);
}
.sync-alert {
  /* 提示条也收进居中栏，避免通栏横幅打断阅读栏 */
  width: calc(100% - var(--chat-gutter) * 2);
  max-width: var(--chat-col);
  margin: 12px auto 0;
  flex-shrink: 0;
}
.sync-alert-tip {
  font-size: 13px;
}

.qa-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

/* 居中栏：消息 / 欢迎页 / 输入卡共用同一条宽度 */
.chat-column {
  width: 100%;
  max-width: var(--chat-col);
  margin: 0 auto;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  /* 顶部只留一点点：聊天区紧贴布局顶栏下方，纵向空间尽量给消息 */
  padding: 14px var(--chat-gutter) 10px;
  position: relative;
  /*
   * 这里刻意**不加** scroll-behavior: smooth：
   * 流式输出时每个 token 都要把视口钉在底部，平滑滚动会让画面一直「追不上」而发飘。
   * 只有用户主动点「回到底部」时才用平滑滚动（见 scrollToBottom 的 smooth 参数）。
   */
}
.chat-welcome {
  text-align: center;
  padding: 26px 16px 32px;
}
.cw-logo {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}
.chat-welcome h3 {
  margin: 0 0 10px;
  font-size: 21px;
  font-weight: 600;
  color: var(--text-main);
}
.chat-welcome p {
  color: var(--text-secondary);
  margin: 0 0 32px;
  font-size: 14px;
}
.suggest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 12px;
  max-width: 640px;
  margin: 0 auto;
}
.suggest-chip {
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  font-size: 13.5px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
  color: var(--text-regular);
}
.suggest-chip:hover {
  border-color: var(--brand);
  background: var(--brand-light);
  color: var(--brand);
  transform: translateY(-2px);
}

/* 消息行：单列内容，靠对齐方式区分角色（不带头像） */
.msg-row {
  display: flex;
  margin-bottom: 28px;
  align-items: flex-start;
}
/* 新一轮提问前多留一点空，让「问答」成为视觉分组 */
.msg-row.is-user {
  justify-content: flex-end;
  margin-top: 34px;
}
/* 第一条消息（通常是提问）不需要上方留白，否则聊天区顶部会空一大块 */
.chat-column > .msg-row:first-child {
  margin-top: 0;
}
.user-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 5px;
  max-width: 78%;
}
/*
 * 用户消息下方的操作行。
 * 固定高度 + opacity（而非 v-if / display:none）：悬停出现时不会引起布局跳动；
 * 将来加「编辑消息」等多个操作用同一行即可。
 *
 * 显隐**只在这一层控制**：行内的按钮不再自己设 opacity。
 * ⚠️ 踩坑记录：CSS 的 opacity 是相乘的。如果容器是 0→1、里面按钮又自带 opacity: 0，
 * 结果永远是 1 × 0 = 0，按钮看起来「悬停也不出现」。所以这里明确分工：
 *   - 助手消息：.msg-time .msg-action 自己隐藏，靠 .msg-row.is-ai:hover 揭示
 *   - 用户消息：整个 .user-actions 一起隐藏/显示
 */
.user-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  height: 18px;
  opacity: 0;
  transition: opacity 0.15s;
}
.scope-tag {
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-soft);
  border: 1px solid var(--border);
  padding: 1px 8px;
  border-radius: 3px;
  flex-shrink: 0;
}
.msg-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 15.5px;
  line-height: 1.75;
  word-break: break-word;
}
/* 用户消息：淡蓝底 + 深色字，不再用高饱和蓝底白字抢 Agent 输出的注意力 */
.user-bubble {
  background: var(--brand-light);
  color: var(--text-main);
  border: 1px solid var(--brand-border);
  border-bottom-right-radius: 5px;
  white-space: pre-wrap;
  /* 在 flex 行里要能收缩换行 */
  min-width: 0;
}
.ai-content {
  /* 没有头像占位了，正文直接吃满整条居中栏（栏宽本身就是阅读宽度） */
  max-width: 100%;
  min-width: 0;
  flex: 1;
}
/* 栏宽从约 520px 放到 840px 后，正文与代码都放大一档，行宽/字号更平衡 */
.ai-content :deep(.md-body) {
  font-size: 15.5px;
  line-height: 1.82;
}
/* 代码块再单独抬一点：等宽字体的视觉尺寸比中文小，同字号下会显得更小 */
.ai-content :deep(.md-code-lang) {
  font-size: 12.5px;
}
.ai-content :deep(.md-code-copy) {
  font-size: 13px;
}
.waiting-box {
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.waiting-text {
  color: var(--text-faint);
  font-size: 14px;
}
.msg-time {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 5px;
  padding-left: 2px;
  display: flex;
  align-items: center;
  gap: 6px;
}
/* 操作按钮的通用外观（不负责显隐，显隐交给所在的容器） */
.msg-action {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  cursor: pointer;
  color: var(--text-faint);
  transition: opacity 0.15s, color 0.15s;
}
/* 助手消息：按钮藏在时间行里，单独隐藏（用户消息由 .user-actions 整行控制，见上） */
.msg-time .msg-action {
  opacity: 0;
}
.msg-row.is-ai:hover .msg-action,
.msg-row.is-user:hover .user-actions,
.msg-row.is-ai:focus-within .msg-action,
.msg-row.is-user:focus-within .user-actions {
  opacity: 1;
}
.msg-action:hover {
  color: var(--brand);
}
/*
 * 触屏设备没有 hover：复制按钮不能靠悬停才出现，
 * 否则手机上永远点不到。
 */
@media (hover: none) {
  .msg-time .msg-action,
  .user-actions {
    opacity: 1;
  }
}

/* 中断回答回显 */
.answer-echo {
  background: #f4fbf7;
  border: 1px solid #b7e4cb;
  border-radius: var(--radius-md);
  padding: 9px 13px;
  margin-bottom: 10px;
}
.ae-head {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 600;
  color: #1fa06d;
  margin-bottom: 6px;
}
.ae-row {
  display: flex;
  gap: 8px;
  font-size: 13px;
  line-height: 1.7;
  padding: 2px 0;
}
.ae-q {
  color: var(--text-secondary);
  flex-shrink: 0;
}
.ae-q::after {
  content: '：';
}
.ae-a {
  color: var(--text-main);
  word-break: break-word;
}

/* 失败重试 */
.retry-box {
  margin-bottom: 10px;
}

.to-bottom {
  position: sticky;
  bottom: 12px;
  margin-left: auto;
  display: flex;
  box-shadow: var(--shadow-md);
}
/* 流式输出且用户往上翻时，用「新内容」提示把注意力叫回来 */
.to-bottom.has-new {
  border-color: var(--brand);
  color: var(--brand);
  background: #fff;
}

/* 输入框上方那一行：作用域 + 状态 + 运行控制 + 会话操作 */
.scope-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 2px 9px;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.scope-picker {
  /* 芯片式选择器：不抢视线，但随时可点着换知识库 */
  width: 232px;
  max-width: 100%;
  flex-shrink: 0;
}
.scope-note {
  font-size: 12.5px;
  color: var(--text-faint);
  min-width: 0;
}
/* 右侧操作组推到最右 */
.scope-row-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

/* 输入区：一个圆角输入卡，浮在底部（DeepSeek / Gemini 的 composer 形态） */
.chat-input-area {
  position: relative;
  flex-shrink: 0;
  padding: 10px var(--chat-gutter) 22px;
  background: var(--bg-card);
}
/* 内容往输入卡下面滚时用一层白色渐隐过渡，避免文字「硬切」在卡片边上 */
.chat-input-area::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 26px;
  transform: translateY(-100%);
  background: linear-gradient(to top, var(--bg-card), transparent);
  pointer-events: none;
}
.composer-box {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 9px 10px 9px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-dark);
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(31, 39, 51, 0.05);
  transition: border-color 0.18s, box-shadow 0.18s;
}
.composer-box:focus-within {
  border-color: var(--brand);
  box-shadow: 0 3px 16px rgba(45, 108, 223, 0.13);
}
/* 去掉 textarea 自己的边框/阴影，让整张卡看起来是一个输入框 */
.chat-input-area :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  background: transparent;
  padding: 7px 0;
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
}
.chat-input-area :deep(.el-textarea__inner):focus {
  box-shadow: none;
}
.chat-input-area :deep(.el-textarea.is-disabled .el-textarea__inner) {
  background: transparent;
}
.send-btn {
  flex-shrink: 0;
}
.fade-enter-active {
  transition: opacity 0.2s;
}
.fade-enter-from {
  opacity: 0;
}

@media (max-width: 1100px) {
  .qa-page {
    --chat-col: 100%;
    --chat-gutter: 18px;
  }
}
@media (max-width: 900px) {
  .qa-page {
    --chat-gutter: 12px;
  }
  .qa-sidebar {
    width: 176px;
  }
  .msg-row.is-user {
    margin-top: 26px;
  }
  .user-side {
    max-width: 88%;
  }
}
</style>
