<template>
  <div class="course-selector">
    <span class="cs-label">选择课程</span>
    <el-select
      :model-value="modelValue"
      placeholder="请选择课程"
      style="width: 240px"
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
import { useCourseStore } from '@/stores/course'
import type { CourseResponse } from '@/api/types'

const props = defineProps<{ modelValue: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [v: number | null] }>()

const auth = useAuthStore()
const courseStore = useCourseStore()

onMounted(async () => {
  if (auth.user) await courseStore.refreshMyCourses(auth.user.role)
})

/** 可选的课程：教师＝我教的课；管理员＝所有课程；学生＝我学的课 */
const courses = computed<CourseResponse[]>(() => {
  if (auth.isAdmin) return courseStore.allList
  if (auth.isTeacher) return courseStore.teaching
  return courseStore.enrolled
})

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
.cs-label {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.option-code {
  float: right;
  color: var(--text-faint);
  font-size: 12px;
}
</style>
