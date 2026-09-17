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
      <!-- 顶栏 -->
      <div class="qa-topbar">
        <div class="qa-left">
          <CourseSelector v-model="selectedCourseId" />
          <span v-if="runState !== 'idle'" class="run-state" :class="`is-${runState}`">
            <el-icon :class="{ 'animate-pulse': runState !== 'stopped' }" :size="13">
              <Loading v-if="runState !== 'stopped'" />
              <VideoPause v-else />
            </el-icon>
            {{ runStateText }}
          </span>
          <el-tag v-else-if="messagesLoading" type="info" effect="plain" size="small" class="streaming-tag">
            <el-icon class="animate-pulse" :size="12"><Loading /></el-icon> 加载历史…
          </el-tag>
        </div>
        <div class="qa-right">
          <el-button v-if="isStreaming" text :icon="VideoPause" @click="onStop">停止接收</el-button>
          <el-button
            v-else-if="runState === 'stalled'"
            text
            :icon="RefreshRight"
            @click="onContinue"
          >
            重新连接
          </el-button>
          <el-button v-else-if="canContinue" text :icon="RefreshRight" @click="onContinue">
            继续接收
          </el-button>
          <el-button
            v-if="activeSession?.threadId"
            text
            :icon="Refresh"
            :loading="messagesLoading"
            @click="onRefresh"
          >
            刷新历史
          </el-button>
          <el-button
            v-if="messages.length > 0"
            text
            :icon="Download"
            @click="onExport"
          >
            导出
          </el-button>
        </div>
      </div>

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
          <!-- 空会话 + 没选课程：提示先选课程 -->
          <div v-if="messages.length === 0 && selectedCourseId == null" class="chat-welcome">
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

          <!-- 消息列表 -->
          <template v-for="m in messages" :key="m.id">
            <div v-if="m.role === 'user'" class="msg-row is-user">
              <div class="user-side">
                <span v-if="m.scopeLabel" class="scope-tag">📚 {{ m.scopeLabel }}</span>
                <div class="msg-bubble user-bubble">{{ m.content }}</div>
              </div>
              <UserAvatar :name="auth.user?.real_name" :size="34" />
            </div>

            <div v-else class="msg-row is-ai">
              <div class="ai-avatar"><el-icon :size="18" color="#2d6cdf"><MagicStick /></el-icon></div>
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
                  <span class="waiting-text typing-cursor">正在思考</span>
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
            <el-button v-if="!atBottom" class="to-bottom" circle :icon="Bottom" @click="scrollToBottom(true)" />
          </transition>
        </div>

        <!-- 未选课程时：提问被拦住，但历史照常可看 -->
        <div v-if="selectedCourseId == null" class="need-course">
          <el-icon :size="14"><InfoFilled /></el-icon>
          请先在右上角选择课程知识库，之后才能继续提问（选择只影响下一次提问，不会影响已有记录）
        </div>

        <!-- 输入区 -->
        <div class="chat-input-area">
          <el-input
            v-model="input"
            type="textarea"
            :rows="1"
            :autosize="{ minRows: 1, maxRows: 5 }"
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
  InfoFilled,
  VideoPause,
  RefreshRight,
  Search,
  Download,
  DocumentCopy,
  CircleCheckFilled,
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
import UserAvatar from '@/components/UserAvatar.vue'
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

/** 当前角色下可选的课程（与右上角 CourseSelector 用同一份逻辑，保证「默认选中」的一定在列表里） */
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

async function scrollToBottom(force = false) {
  await nextTick()
  const el = msgBox.value
  if (force || atBottom.value) {
    if (el) el.scrollTop = el.scrollHeight
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

async function onCopyAnswer(m: AgentChatMessage) {
  const text =
    m.parts
      .filter((p) => p.type === 'text')
      .map((p) => p.content || '')
      .join('\n\n')
      .trim() || m.content
  const ok = await copyText(text)
  if (ok) ElMessage.success('已复制回答')
  else ElMessage.error('复制失败，请手动选择文本')
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
</script>

<style scoped>
.qa-page {
  height: calc(100vh - 52px);
  display: flex;
  overflow: hidden;
}

/* ============ 左侧会话列表 ============ */
.qa-sidebar {
  width: 230px;
  flex-shrink: 0;
  background: #fff;
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
  font-size: 11.5px;
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
  font-size: 12.5px;
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
  font-size: 13px;
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
  font-size: 11.5px;
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
  font-size: 12px;
  color: var(--brand);
  flex-shrink: 0;
}

/* ============ 右侧主体 ============ */
.qa-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 16px 24px 0;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}
.qa-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  gap: 12px;
  flex-wrap: wrap;
}
.qa-left {
  display: flex;
  align-items: center;
  gap: 12px;
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
  font-size: 12.5px;
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
.qa-right {
  display: flex;
}
.sync-alert {
  margin-top: 10px;
  flex-shrink: 0;
}
.sync-alert-tip {
  font-size: 12.5px;
}
.qa-empty {
  margin-top: 20px;
  padding: 40px 0;
}

.qa-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin-top: 6px;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 6px;
  position: relative;
}
.chat-welcome {
  text-align: center;
  padding: 36px 20px;
}
.cw-logo {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}
.chat-welcome h3 {
  margin: 0 0 8px;
  font-size: 20px;
}
.chat-welcome p {
  color: var(--text-secondary);
  margin: 0 0 24px;
}
.suggest-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
  max-width: 680px;
  margin: 0 auto;
}
.suggest-chip {
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 13px 15px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}
.suggest-chip:hover {
  border-color: var(--brand);
  background: var(--brand-light);
  transform: translateY(-2px);
}

/* 消息 */
.msg-row {
  display: flex;
  gap: 10px;
  margin: 16px 0;
  align-items: flex-start;
}
.msg-row.is-user {
  justify-content: flex-end;
}
.user-side {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}
.scope-tag {
  font-size: 11px;
  color: var(--brand);
  background: var(--brand-light);
  border: 1px solid var(--brand-border);
  padding: 1px 8px;
  border-radius: 3px;
  flex-shrink: 0;
}
.msg-bubble {
  padding: 11px 15px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
}
.user-bubble {
  background: var(--brand);
  color: #fff;
  border-bottom-right-radius: 4px;
  white-space: pre-wrap;
  max-width: 72%;
}
.ai-avatar {
  width: 34px;
  height: 34px;
  border-radius: 6px;
  background: var(--brand-light);
  border: 1px solid var(--brand-border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.ai-content {
  max-width: 78%;
  min-width: 0;
  flex: 1;
}
.waiting-box {
  margin-bottom: 10px;
}
.waiting-text {
  color: var(--text-faint);
  font-size: 13.5px;
}
.msg-time {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 5px;
  padding-left: 2px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.msg-action {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  cursor: pointer;
  color: var(--text-faint);
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}
.msg-row.is-ai:hover .msg-action {
  opacity: 1;
}
.msg-action:hover {
  color: var(--brand);
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
  font-size: 12.5px;
  font-weight: 600;
  color: #1fa06d;
  margin-bottom: 6px;
}
.ae-row {
  display: flex;
  gap: 8px;
  font-size: 12.5px;
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

/* 未选课程提示条 */
.need-course {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  margin-bottom: 2px;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: var(--radius-sm);
  font-size: 12.5px;
  color: #8c6d1f;
  flex-shrink: 0;
}

/* 输入区 */
.chat-input-area {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 14px 4px 16px;
  border-top: 1px solid var(--border);
  background: var(--bg-page);
  flex-shrink: 0;
}
.chat-input-area :deep(.el-textarea__inner) {
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  line-height: 1.6;
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

@media (max-width: 900px) {
  .qa-sidebar {
    width: 170px;
  }
  .qa-main {
    padding: 12px 12px 0;
  }
}
</style>
