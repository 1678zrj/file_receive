<template>
  <div class="qa-page">
    <!-- ============ 左侧：会话列表 ============ -->
    <aside class="qa-sidebar">
      <div class="sidebar-head">
        <el-button type="primary" class="btn-primary new-btn" :icon="Plus" @click="onNewSession">
          新建会话
        </el-button>
      </div>
      <div class="session-list">
        <el-empty
          v-if="sessions.length === 0"
          description="暂无会话"
          :image-size="60"
          class="session-empty"
        />
        <div
          v-for="s in sessions"
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
            <div class="session-meta">{{ timeLabel(s.updatedAt) }} · {{ s.messages.length }} 条</div>
          </div>
          <el-icon class="session-del" :size="14" @click.stop="onRemoveSession(s.id)" title="删除会话">
            <Delete />
          </el-icon>
        </div>
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
          <el-tag v-if="isStreaming" type="primary" effect="plain" size="small" class="streaming-tag">
            <el-icon class="animate-pulse" :size="12"><Loading /></el-icon> 思考中…
          </el-tag>
          <el-tag v-else-if="restored && messages.length > 0" type="info" effect="plain" size="small">
            已恢复对话
          </el-tag>
        </div>
        <div class="qa-right">
          <el-button v-if="messages.length > 0" text :icon="Delete" @click="confirmClear">清空本会话</el-button>
        </div>
      </div>

      <!-- 未选择课程 -->
      <div v-if="selectedCourseId == null" class="qa-empty cc-card">
        <el-empty description="请先选择一门课程，开始 Agent 智能问答" :image-size="120" />
      </div>

      <!-- 对话区 -->
      <div v-else class="qa-body">
        <div ref="msgBox" class="chat-messages" @scroll="onScroll">
          <!-- 欢迎页 -->
          <div v-if="messages.length === 0" class="chat-welcome">
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
                <MessagePartItem v-for="(p, pi) in m.parts" :key="`${m.id}-${pi}`" :part="p" />

                <div v-if="m.streaming && m.parts.length === 0" class="waiting-box">
                  <span class="waiting-text typing-cursor">正在思考</span>
                </div>

                <InterruptForm v-if="m.interrupt" :interrupt="m.interrupt" @submit="onInterruptSubmit" />

                <div class="msg-time">
                  <span v-if="m.scopeLabel" class="scope-tag">📚 {{ m.scopeLabel }}</span>
                  {{ formatDateTime(m.created_at, 'HH:mm:ss') }}
                </div>
              </div>
            </div>
          </template>

          <transition name="fade">
            <el-button v-if="!atBottom" class="to-bottom" circle :icon="Bottom" @click="scrollToBottom(true)" />
          </transition>
        </div>

        <!-- 输入区 -->
        <div class="chat-input-area">
          <el-input
            v-model="input"
            type="textarea"
            :rows="1"
            :autosize="{ minRows: 1, maxRows: 5 }"
            resize="none"
            placeholder="输入问题，Enter 发送，Shift + Enter 换行..."
            :disabled="isStreaming"
            @keydown.enter.exact.prevent="send"
          />
          <el-button
            type="primary"
            class="send-btn btn-primary"
            :icon="Promotion"
            circle
            size="large"
            :disabled="!input.trim() || isStreaming"
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
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Promotion, Bottom, Delete, MagicStick, Plus, Loading } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useCourseStore } from '@/stores/course'
import { useAgentChat } from '@/composables/useAgentChat'
import { formatDateTime, fromNow } from '@/utils/format'
import CourseSelector from '@/components/CourseSelector.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import InterruptForm from '@/components/agent/InterruptForm.vue'
import MessagePartItem from '@/components/agent/MessagePartItem.vue'

const route = useRoute()
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

const suggestions = [
  '这门课程主要讲了哪些内容？',
  '帮我总结知识库中的重点知识',
  '根据课程资料出一道练习题',
  '解释一下课程中的核心概念',
]

// Agent 多会话
const {
  sessions,
  activeId,
  messages,
  isStreaming,
  restored,
  anyStreaming,
  newSession,
  switchSession,
  removeSession,
  clearCurrent,
  send: agentSend,
  resume: agentResume,
} = useAgentChat(() =>
  selectedCourseId.value != null
    ? { scope: 'course', scope_id: `course_${selectedCourseId.value}`, label: courseName.value }
    : null,
)

const input = ref('')
const msgBox = ref<HTMLDivElement>()
const atBottom = ref(true)

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

onMounted(async () => {
  if (auth.user) await courseStore.refreshMyCourses(auth.user.role)
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
  input.value = ''
  atBottom.value = true
  await agentSend(text)
  scrollToBottom(true)
}

function onNewSession() {
  newSession()
  ElMessage.success('已新建会话')
}

async function onRemoveSession(id: string) {
  await ElMessageBox.confirm('确定删除该会话吗？', '提示', { type: 'warning' })
  removeSession(id)
  ElMessage.success('已删除会话')
}

function onInterruptSubmit(answers: unknown) {
  agentResume(answers)
  scrollToBottom(true)
}

async function confirmClear() {
  await ElMessageBox.confirm('确定清空当前会话吗？（下次提问会开启新的后端会话）', '提示', {
    type: 'warning',
  })
  clearCurrent()
  ElMessage.success('已清空当前会话')
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
.new-btn {
  width: 100%;
}
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
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
.qa-right {
  display: flex;
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

.to-bottom {
  position: sticky;
  bottom: 12px;
  margin-left: auto;
  display: flex;
  box-shadow: var(--shadow-md);
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
