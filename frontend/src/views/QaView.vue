<template>
  <div class="qa-page">
    <!-- 顶栏：课程选择 + 工具 -->
    <div class="qa-topbar">
      <div class="qa-left">
        <CourseSelector v-model="selectedCourseId" />
      </div>
      <div class="qa-right">
        <el-button v-if="messages.length > 0" text :icon="Delete" @click="confirmClear">清空对话</el-button>
      </div>
    </div>

    <!-- 未选择课程 -->
    <div v-if="selectedCourseId == null" class="qa-empty cc-card">
      <el-empty description="请先选择一门课程，开始知识库问答" :image-size="120" />
    </div>

    <!-- 对话主体 -->
    <div v-else class="qa-body">
      <!-- 消息区 -->
      <div ref="msgBox" class="chat-messages" @scroll="onScroll">
        <!-- 欢迎页 -->
        <div v-if="messages.length === 0" class="chat-welcome">
          <div class="cw-logo"><el-icon :size="40" color="#2d6cdf"><ChatDotRound /></el-icon></div>
          <h3>课程知识库智能助手</h3>
          <p>基于《{{ courseName }}》的知识库内容回答问题，支持来源引用追溯</p>
          <div class="suggest-grid">
            <div v-for="(s, i) in suggestions" :key="i" class="suggest-chip" @click="ask(s)">{{ s }}</div>
          </div>
          <el-alert v-if="apiMissing" type="warning" :closable="false" show-icon class="chat-alert">
            <template #title>问答接口尚未提供（建议：POST /api/v1/kb/chat），待后端补充后自动可用。</template>
          </el-alert>
        </div>

        <!-- 消息列表 -->
        <template v-for="m in messages" :key="m.id">
          <div v-if="m.role === 'user'" class="msg-row is-user">
            <div class="msg-bubble user-bubble">{{ m.content }}</div>
            <UserAvatar :name="auth.user?.real_name" :size="34" />
          </div>

          <div v-else class="msg-row is-ai">
            <div class="ai-avatar"><el-icon :size="18" color="#2d6cdf"><MagicStick /></el-icon></div>
            <div class="ai-content">
              <div class="msg-bubble ai-bubble" :class="{ 'typing-cursor': m.streaming }">
                <div class="md-body" v-html="renderMd(m.content)"></div>
              </div>
              <div v-if="m.sources?.length" class="sources-box">
                <div class="sources-title">参考来源（{{ m.sources.length }}）</div>
                <div
                  v-for="(s, i) in m.sources"
                  :key="i"
                  class="source-item"
                  @click="expandedSource = expandedSource === `${m.id}-${i}` ? null : `${m.id}-${i}`"
                >
                  <div class="source-head">
                    <span class="source-index">{{ i + 1 }}</span>
                    <span class="source-title">{{ s.title }}</span>
                    <el-icon class="source-arrow">
                      <ArrowDown v-if="expandedSource !== `${m.id}-${i}`" /><ArrowUp v-else />
                    </el-icon>
                  </div>
                  <div v-if="expandedSource === `${m.id}-${i}`" class="source-text">{{ s.chunk_text }}</div>
                </div>
              </div>
              <div class="msg-time">{{ formatDateTime(m.created_at, 'HH:mm:ss') }}</div>
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
          :disabled="answering"
          @keydown.enter.exact.prevent="send"
        />
        <el-button
          type="primary"
          class="send-btn btn-primary"
          :icon="answering ? VideoPause : Promotion"
          circle
          size="large"
          :disabled="!input.trim() && !answering"
          @click="answering ? stop() : send()"
          :title="answering ? '停止生成' : '发送'"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Promotion, Bottom, VideoPause, Delete, MagicStick, ChatDotRound } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { useAuthStore } from '@/stores/auth'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useCourseStore } from '@/stores/course'
import { useKbChat } from '@/composables/useKbChat'
import { formatDateTime } from '@/utils/format'
import CourseSelector from '@/components/CourseSelector.vue'
import UserAvatar from '@/components/UserAvatar.vue'

const route = useRoute()
const auth = useAuthStore()
const knowledgeStore = useKnowledgeStore()
const courseStore = useCourseStore()

const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(code, { language: lang }).value}</code></pre>`
      } catch {
        /* noop */
      }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(code)}</code></pre>`
  },
})
function renderMd(text: string) {
  return md.render(text || '')
}

const selectedCourseId = ref<number | null>(
  route.query.courseId ? Number(route.query.courseId) : knowledgeStore.selectedCourseId,
)

watch(selectedCourseId, (val) => {
  knowledgeStore.setCourseId(val)
  clear()
  // 若从路由带了 topic，预填问题
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

const { messages, input, answering, apiMissing, msgBox, atBottom, expandedSource, onScroll, scrollToBottom, ask, send, stop, clear } =
  useKbChat(() => selectedCourseId.value)

onMounted(async () => {
  if (auth.user) await courseStore.refreshMyCourses(auth.user.role)
  const topic = route.query.topic as string | undefined
  if (topic && selectedCourseId.value != null) {
    setTimeout(() => send(), 0)
  }
})

async function confirmClear() {
  await ElMessageBox.confirm('确定清空当前对话吗？', '提示', { type: 'warning' })
  clear()
  ElMessage.success('已清空对话')
}
</script>

<style scoped>
.qa-page {
  height: calc(100vh - 52px);
  display: flex;
  flex-direction: column;
  max-width: 1200px;
  margin: 0 auto;
  padding: 16px 24px 0;
}

/* 顶栏 */
.qa-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}
.qa-right {
  display: flex;
}

/* 空状态 */
.qa-empty {
  margin-top: 20px;
  padding: 40px 0;
}

/* 对话主体 */
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
.chat-alert {
  margin-top: 24px;
  text-align: left;
  border-radius: var(--radius-md);
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
.msg-bubble {
  max-width: 72%;
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
  max-width: 72%;
  min-width: 0;
}
.ai-bubble {
  background: #fff;
  border: 1px solid var(--border);
  border-bottom-left-radius: 4px;
  box-shadow: var(--shadow-sm);
}
.ai-bubble .md-body {
  font-size: 14px;
}
.msg-time {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 5px;
  padding-left: 2px;
}

/* 来源引用 */
.sources-box {
  margin-top: 8px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
}
.sources-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-regular);
  margin-bottom: 8px;
}
.source-item {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 7px 10px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.source-item:hover {
  border-color: var(--brand);
}
.source-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.source-index {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--brand);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.source-title {
  font-size: 12.5px;
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.source-arrow {
  color: var(--text-secondary);
  font-size: 12px;
}
.source-text {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-regular);
  line-height: 1.7;
  background: var(--bg-soft);
  padding: 8px 10px;
  border-radius: 6px;
  max-height: 160px;
  overflow-y: auto;
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
</style>
