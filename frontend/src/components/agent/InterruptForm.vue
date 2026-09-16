<template>
  <div class="interrupt-form">
    <div class="if-header">
      <el-icon :size="16" color="#e8930c"><QuestionFilled /></el-icon>
      <span class="if-title">需要你确认以下信息</span>
    </div>

    <!-- 每个问题 -->
    <div v-for="q in interrupt.questions" :key="q.id" class="if-question">
      <div class="if-q-header">
        <span class="if-q-header-text">{{ q.header }}</span>
      </div>
      <div class="if-q-body">{{ q.question }}</div>

      <!-- 选项（radio）或自由文本 -->
      <el-radio-group v-if="q.options && q.options.length" v-model="answers[q.id]" class="if-options">
        <el-radio v-for="opt in q.options" :key="opt.label" :value="opt.label" class="if-option">
          <div class="if-opt-label">{{ opt.label }}</div>
          <div v-if="opt.description" class="if-opt-desc">{{ opt.description }}</div>
        </el-radio>
      </el-radio-group>
      <el-input
        v-else
        v-model="answers[q.id]"
        placeholder="请输入你的回答..."
        class="if-input"
      />
    </div>

    <div class="if-footer">
      <el-button type="primary" class="btn-primary" :loading="submitting" @click="submit">
        提交
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { InterruptPayload } from '@/api/types'

const props = defineProps<{ interrupt: InterruptPayload }>()
const emit = defineEmits<{ submit: [answers: Array<{ id: string; selected: string[] }>] }>()

const answers = reactive<Record<string, string | string[]>>({})
const submitting = ref(false)

/** 初始化答案（默认留空，等待用户选择/输入） */
props.interrupt.questions.forEach((q) => {
  if (!(q.id in answers)) {
    answers[q.id] = ''
  }
})

function submit() {
  const result: Array<{ id: string; selected: string[] }> = []
  for (const q of props.interrupt.questions) {
    const val = answers[q.id]
    if (val == null || val === '') {
      ElMessage.warning(`请回答「${q.header}」`)
      return
    }
    const selected = Array.isArray(val) ? val : [String(val)]
    result.push({ id: q.id, selected })
  }
  submitting.value = true
  emit('submit', result)
  // 提交后由父组件决定是否重置；这里短暂显示 loading
  setTimeout(() => (submitting.value = false), 500)
}
</script>

<style scoped>
.interrupt-form {
  margin-top: 8px;
  border: 1px solid #f0d9a8;
  background: #fffaf0;
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.if-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}
.if-title {
  font-size: 13.5px;
  font-weight: 600;
  color: #b7760a;
}
.if-question {
  margin-bottom: 14px;
}
.if-question:last-of-type {
  margin-bottom: 4px;
}
.if-q-header-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}
.if-q-body {
  font-size: 13px;
  color: var(--text-regular);
  margin: 4px 0 8px;
  line-height: 1.6;
}
.if-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
}
.if-option {
  height: auto;
  align-items: flex-start;
  padding: 6px 0;
  margin-right: 0;
  white-space: normal;
}
.if-option :deep(.el-radio__label) {
  white-space: normal;
  line-height: 1.5;
}
.if-opt-label {
  font-size: 13px;
  font-weight: 500;
}
.if-opt-desc {
  font-size: 12px;
  color: var(--text-secondary);
}
.if-input {
  margin-top: 4px;
}
.if-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>
