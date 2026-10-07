<template>
  <div v-if="part.type === 'thought'" class="part part-thought">
    <div class="part-head" @click="collapsed = !collapsed">
      <el-icon :size="13" class="part-icon"><View /></el-icon>
      <span class="part-title">思考过程</span>
      <span v-if="collapsed && part.content" class="part-preview">{{ preview }}</span>
      <el-icon class="part-arrow" :size="12">
        <ArrowDown v-if="collapsed" />
        <ArrowUp v-else />
      </el-icon>
    </div>
    <div v-if="!collapsed" class="part-thought-body">{{ part.content }}</div>
  </div>

  <div
    v-if="part.type === 'text'"
    class="part part-text md-body"
    :class="{ 'is-streaming': streaming }"
    v-html="renderedText"
    @click="onContentClick"
  ></div>

  <div v-if="part.type === 'tool_call'" class="part part-tool">
    <div class="part-head" @click="collapsed = !collapsed">
      <el-icon :size="13" class="part-icon" :color="statusColor">
        <Loading v-if="part.status === 'running'" class="animate-pulse" />
        <CircleCheckFilled v-else-if="part.status === 'completed'" />
        <CircleCloseFilled v-else />
      </el-icon>
      <span class="part-title">{{ toolLabel }}</span>
      <span class="part-status">{{ statusText }}</span>
      <el-icon v-if="part.content" class="part-arrow" :size="12">
        <ArrowDown v-if="collapsed" />
        <ArrowUp v-else />
      </el-icon>
    </div>
    <div v-if="part.content && !collapsed" class="part-tool-result">{{ part.content }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { View, ArrowDown, ArrowUp, Loading, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import type { MessagePart } from '@/api/types'
import { renderMarkdown } from '@/utils/markdown'
import { copyText } from '@/utils/clipboard'

const props = defineProps<{
  part: MessagePart
  /** 所属消息是否正在流式输出（流式中做节流渲染 + 关闭代码高亮） */
  streaming?: boolean
  /** 初始是否折叠（历史消息默认折叠，流式中的新块默认展开） */
  defaultCollapsed?: boolean
}>()

/** 折叠状态。默认展开，但历史消息会以折叠态起步，避免满屏思考过程 */
const collapsed = ref(!!props.defaultCollapsed)

/**
 * 正文渲染节流策略。
 *
 * 背景：SSE 每个 token 都会改 part.content。改造前每次都全量跑 markdown-it + highlight.js，
 * 一段 N 字的回答会做 O(N²) 的解析工作（这是真正贵的地方）。
 *
 * 但节流间隔不能一刀切：间隔太大（试过 120ms ≈ 8 次/秒）虽然省 CPU，
 * 肉眼会觉得文字「一段一段蹦出来」，反而不如以前流畅。
 * 所以按内容长度分档：
 *  - 短内容（绝大多数回答）：按帧渲染（16ms），观感和改造前一致；
 *  - 长内容：放宽到 48ms，避免 O(N) 解析在长回答上占满主线程。
 * 另外流式期间**关掉代码高亮**（highlight.js 是最贵的一步），终态再做一次带高亮的完整渲染。
 */
const SHORT_CONTENT_CHARS = 3000
const FRAME_INTERVAL = 16
const LONG_CONTENT_INTERVAL = 48

function renderInterval(len: number): number {
  return len <= SHORT_CONTENT_CHARS ? FRAME_INTERVAL : LONG_CONTENT_INTERVAL
}

const renderedText = ref('')
let lastRenderAt = 0
let timer: ReturnType<typeof setTimeout> | null = null

function renderNow(highlight: boolean) {
  renderedText.value = renderMarkdown(props.part.content || '', { highlight })
  lastRenderAt = Date.now()
}

function scheduleRender(delay: number) {
  if (timer) return
  timer = setTimeout(() => {
    timer = null
    renderNow(!props.streaming)
  }, delay)
}

watch(
  () => props.part.content,
  () => {
    // 只有正文块需要渲染 markdown；思考块/工具块是纯文本
    if (props.part.type !== 'text') return
    if (!props.streaming) {
      // 非流式（历史消息 / 定稿）：直接完整渲染
      renderNow(true)
      return
    }
    const interval = renderInterval((props.part.content || '').length)
    const elapsed = Date.now() - lastRenderAt
    if (elapsed >= interval) renderNow(false)
    else scheduleRender(interval - elapsed)
  },
  { immediate: true },
)

// 流式结束 → 立刻补一次带高亮的完整渲染
watch(
  () => props.streaming,
  (now, before) => {
    if (before && !now) {
      if (timer) {
        clearTimeout(timer)
        timer = null
      }
      if (props.part.type === 'text') renderNow(true)
    }
  },
)

onUnmounted(() => {
  if (timer) clearTimeout(timer)
})

/** 下面几个都是 computed（惰性）：只有真正渲染到时才算，不会随每个 token 重算 */
const preview = computed(() => {
  const t = (props.part.content || '').replace(/\s+/g, ' ')
  return t.length > 50 ? `${t.slice(0, 50)}…` : t
})

const statusColor = computed(() => {
  // 用 CSS 变量而不是写死颜色：深色主题下会自动换成提亮过的状态色
  if (props.part.status === 'completed') return 'var(--green)'
  if (props.part.status === 'failed') return 'var(--red)'
  return 'var(--brand)'
})

const statusText = computed(() => {
  if (props.part.status === 'running') return '调用中…'
  if (props.part.status === 'failed') return '失败'
  return '完成'
})

const toolLabel = computed(() => {
  const n = props.part.name || '工具'
  if (n === 'rag') return '检索知识库'
  if (n === 'ask_user_question') return '向用户提问'
  return n
})

/**
 * 代码块复制按钮的点击处理（事件委托）。
 * 按钮是 markdown 渲染出来的 HTML（v-html 注入），没法给它绑 Vue 事件，
 * 所以在容器上委托；代码内容直接从同级的 <code> 读，不用把代码塞进属性里。
 */
async function onContentClick(e: MouseEvent) {
  const target = e.target as HTMLElement | null
  const btn = target?.closest?.('.md-code-copy') as HTMLElement | null
  if (!btn) return
  // 按钮在顶部信息条里，<code> 是它的「兄弟节点的子节点」，
  // 所以要从整个 .md-code 卡片里找，不能用 btn.parentElement
  const code = btn.closest('.md-code')?.querySelector('code')?.textContent ?? ''
  if (!code) return
  const ok = await copyText(code)
  const original = btn.dataset.label || '复制'
  btn.dataset.label = original
  btn.textContent = ok ? '已复制' : '复制失败'
  setTimeout(() => {
    btn.textContent = original
  }, 1400)
}
</script>

<style scoped>
.part {
  margin-bottom: 10px;
}
.part:last-child {
  margin-bottom: 2px;
}
.part-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13.5px;
  color: var(--text-secondary);
  user-select: none;
  cursor: pointer;
}
.part-icon {
  flex-shrink: 0;
}
.part-title {
  font-weight: 500;
  color: var(--text-regular);
}
.part-preview {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-faint);
  font-size: 12.5px;
}
.part-status {
  font-size: 12.5px;
  color: var(--text-faint);
}
.part-arrow {
  margin-left: auto;
  flex-shrink: 0;
  color: var(--text-secondary);
}

/* 思考块 */
.part-thought {
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.part-thought .part-head {
  padding: 10px 13px;
}
.part-thought .part-head:hover .part-title {
  color: var(--brand);
}
.part-thought-body {
  padding: 0 13px 11px;
  font-size: 13.5px;
  color: var(--text-regular);
  line-height: 1.78;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
}

/*
 * 正文块（无边框纯文本，视觉上最突出）。
 * 字号/行高交给 .md-body（全局 Markdown 样式）统一决定 ——
 * 这里再写一次会和 QaView 里对 .md-body 的覆盖产生同权重冲突，谁生效取决于样式注入顺序。
 */
.part-text {
  color: var(--text-main);
}

/* 工具调用块 */
.part-tool {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.part-tool .part-head {
  padding: 9px 13px;
}
.part-tool .part-head:hover .part-title {
  color: var(--brand);
}
.part-tool-result {
  padding: 10px 13px;
  border-top: 1px solid var(--border);
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.7;
  max-height: 260px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
