<template>
  <div class="course-card cc-card cc-card-hover" @click="goDetail">
    <!-- 封面色块 + 课程代码 -->
    <div class="card-cover" :style="{ background: coverGradient }">
      <span class="cover-code">{{ course.course_code || '—' }}</span>
    </div>
    <div class="card-body">
      <h3 class="course-name" :title="course.name">{{ course.name }}</h3>
      <p class="course-overview">{{ course.overview || '暂无简介' }}</p>
      <div class="card-footer">
        <span class="meta-item">
          <el-icon :size="13"><User /></el-icon>
          <span>{{ course.teacher_name || `教师 #${course.teacher_id}` }}</span>
        </span>
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { CourseResponse } from '@/api/types'
import { courseCover } from '@/utils/format'

const props = defineProps<{ course: CourseResponse & { teacher_name?: string } }>()
const router = useRouter()

const coverGradient = computed(() => courseCover(props.course.name))

function goDetail() {
  router.push({ name: 'course-detail', params: { id: props.course.id } })
}
</script>

<style scoped>
.course-card {
  overflow: hidden;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.2s, transform 0.2s;
}
.course-card:hover {
  transform: translateY(-2px);
}
.card-cover {
  height: 96px;
  display: flex;
  align-items: flex-start;
  justify-content: flex-end;
  padding: 10px 12px;
}
.cover-code {
  color: rgba(255, 255, 255, 0.92);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
  background: rgba(0, 0, 0, 0.16);
  padding: 2px 9px;
  border-radius: 3px;
}
.card-body {
  padding: 14px 16px 12px;
  display: flex;
  flex-direction: column;
  flex: 1;
}
.course-name {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.course-overview {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  flex: 1;
}
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  border-top: 1px solid var(--border);
  padding-top: 10px;
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
