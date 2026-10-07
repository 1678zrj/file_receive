<template>
  <div class="course-selector" :class="{ 'is-compact': compact }">
    <span v-if="!compact" class="cs-label">选择课程</span>
    <el-select
      :model-value="modelValue"
      :placeholder="compact ? '选择课程知识库' : '请选择课程'"
      :style="{ width: compact ? '100%' : '240px' }"
      :size="compact ? 'small' : 'default'"
      filterable
      @update:model-value="onChange"
    >
      <el-option
        v-for="c in courses"
        :key="c.id"
        :label="c.name"
        :value="c.id"
      >
        <span class="option-label">{{ c.name }}</span>
        <span class="option-code">{{ c.course_code || '' }}</span>
      </el-option>
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { pickCoursesForRole, useCourseStore } from '@/stores/course'
import type { CourseResponse } from '@/api/types'

/**
 * compact：用于「输入区」里当作用域切换芯片（不显示标签、更小、撑满容器）。
 * 非 compact：用于课程/知识库页面的常规选择器。
 */
const props = withDefaults(defineProps<{ modelValue: number | null; compact?: boolean }>(), {
  compact: false,
})
const emit = defineEmits<{ 'update:modelValue': [v: number | null] }>()

const auth = useAuthStore()
const courseStore = useCourseStore()

onMounted(async () => {
  if (auth.user) await courseStore.refreshMyCourses(auth.user.role)
})

/** 可选的课程：教师＝我教的课；管理员＝所有课程；学生＝我学的课 */
const courses = computed<CourseResponse[]>(() =>
  pickCoursesForRole(auth.user?.role, {
    teaching: courseStore.teaching,
    enrolled: courseStore.enrolled,
    allList: courseStore.allList,
  }),
)

function onChange(v: number | null) {
  emit('update:modelValue', v)
}
</script>

<style scoped>
.course-selector {
  display: flex;
  align-items: center;
  gap: 10px;
}
.course-selector.is-compact {
  gap: 0;
  width: 100%;
}
.cs-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.option-label {
  margin-right: 12px;
}
.option-code {
  float: right;
  color: var(--text-faint);
  font-size: 12px;
}

/* 紧凑模式：做成一个圆角芯片，去掉表单控件的边框感 */
.is-compact :deep(.el-select__wrapper) {
  background: var(--bg-soft);
  box-shadow: none;
  border-radius: 999px;
  padding: 3px 12px;
  min-height: 30px;
  font-size: 13px;
  color: var(--text-regular);
  transition: background 0.16s;
}
.is-compact :deep(.el-select__wrapper:hover) {
  background: var(--brand-light);
}
.is-compact :deep(.el-select__wrapper.is-focused) {
  background: var(--brand-light);
  box-shadow: 0 0 0 1px var(--brand-border) inset;
}
</style>
