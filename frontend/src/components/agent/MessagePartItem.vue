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

  <div v-if="part.type === 'text'" class="part part-text md-body" v-html="renderedText"></div>

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
import { computed, ref } from 'vue'
import { View, ArrowDown, ArrowUp, Loading, CircleCheckFilled, CircleCloseFilled } from '@element-plus/icons-vue'
import type { MessagePart } from '@/api/types'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ part: MessagePart }>()

/** 折叠状态（默认展开） */
const collapsed = ref(false)

const renderedText = computed(() => renderMarkdown(props.part.content || ''))

const preview = computed(() => {
  const t = (props.part.content || '').replace(/\s+/g, ' ')
  return t.length > 50 ? `${t.slice(0, 50)}…` : t
})

const statusColor = computed(() => {
  if (props.part.status === 'completed') return '#1fa06d'
  if (props.part.status === 'failed') return '#e5484d'
  return '#2d6cdf'
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
  font-size: 12.5px;
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
  font-size: 12px;
}
.part-status {
  font-size: 12px;
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
  font-size: 12.5px;
  color: var(--text-regular);
  line-height: 1.75;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow-y: auto;
}

/* 正文块（无边框纯文本，视觉上最突出） */
.part-text {
  font-size: 14.5px;
  color: var(--text-main);
  line-height: 1.75;
}

/* 工具调用块 */
.part-tool {
  background: #fff;
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
  padding: 9px 13px;
  border-top: 1px solid var(--border);
  background: var(--bg-soft);
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.65;
  max-height: 260px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
