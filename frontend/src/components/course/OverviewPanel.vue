<template>
  <div class="overview-panel">
    <div class="overview-grid">
      <!-- 左：课程简介 + 公告 -->
      <div class="ov-left">
        <!-- 课程简介 -->
        <div class="cc-card ov-card">
          <div class="card-head">
            <h3 class="card-title">课程简介</h3>
          </div>
          <div class="card-body">
            <p class="ov-desc">{{ course?.overview || '暂无简介' }}</p>
            <div class="ov-meta">
              <span class="meta-chip"><el-icon :size="14"><User /></el-icon>{{ course?.teacher_name || `教师 #${course?.teacher_id}` }}</span>
              <span class="meta-chip" v-if="course?.course_code"><el-icon :size="14"><Collection /></el-icon>{{ course.course_code }}</span>
              <span class="meta-chip" v-if="course"><el-icon :size="14"><Calendar /></el-icon>{{ formatDate(course.created_at) }}</span>
            </div>
          </div>
        </div>

        <!-- 最新公告 -->
        <div class="cc-card ov-card">
          <div class="card-head">
            <h3 class="card-title">课程公告</h3>
            <el-link type="primary" :underline="false" @click="$emit('goto', 'announcements')">查看全部</el-link>
          </div>
          <div class="card-body" v-loading="annLoading">
            <el-empty v-if="!annLoading && announcements.length === 0" description="暂无公告" :image-size="70" />
            <div v-else class="ann-list">
              <div v-for="a in announcements.slice(0, 3)" :key="a.id" class="ann-item" @click="$emit('goto', 'announcements')">
                <span class="ann-pin" v-if="a.pinned">置顶</span>
                <span class="ann-title">{{ a.title }}</span>
                <span class="ann-time">{{ fromNow(a.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右：进度概览 -->
      <div class="ov-right">
        <div class="cc-card ov-card">
          <div class="card-head">
            <h3 class="card-title">{{ isTeacher ? '课程数据' : '学习进度' }}</h3>
          </div>
          <div class="card-body">
            <div class="progress-stats">
              <div class="ps-item">
                <div class="ps-value">{{ progressData.resource_count }}</div>
                <div class="ps-label">课程资源</div>
              </div>
              <div class="ps-item">
                <div class="ps-value">{{ progressData.assignment_count }}</div>
                <div class="ps-label">作业</div>
              </div>
              <div class="ps-item">
                <div class="ps-value">{{ progressData.done_count }}/{{ progressData.assignment_count }}</div>
                <div class="ps-label">已完成</div>
              </div>
            </div>
            <div class="progress-bar-wrap" v-if="progressData.assignment_count > 0">
              <el-progress :percentage="progressData.percent" :stroke-width="10" />
              <div class="pb-label">{{ isTeacher ? '作业平均提交率' : '作业完成进度' }} {{ progressData.percent }}%</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { announcementApi } from '@/api'
import type { Announcement, CourseResponse } from '@/api/types'
import { formatDate, fromNow } from '@/utils/format'

const props = defineProps<{
  course: (CourseResponse & { teacher_name?: string }) | null
  isTeacher: boolean
  courseId: number
}>()
defineEmits<{ goto: [tab: string] }>()

const announcements = ref<Announcement[]>([])
const annLoading = ref(false)

onMounted(async () => {
  annLoading.value = true
  try {
    announcements.value = await announcementApi.listByCourse(props.courseId)
  } catch {
    announcements.value = []
  } finally {
    annLoading.value = false
  }
})

// 进度概览（mock 数据，真实接口待补）
const progressData = computed(() => ({
  resource_count: 7,
  assignment_count: 3,
  done_count: 2,
  percent: 67,
}))
</script>

<style scoped>
.overview-grid {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 16px;
  align-items: start;
}
@media (max-width: 900px) {
  .overview-grid { grid-template-columns: 1fr; }
}
.ov-left, .ov-right {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.ov-card { overflow: hidden; }
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
}
.card-title { margin: 0; font-size: 15px; font-weight: 600; }
.card-body { padding: 16px 18px; }
.ov-desc {
  margin: 0 0 14px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--text-regular);
}
.ov-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.meta-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12.5px;
  color: var(--text-secondary);
  background: var(--bg-soft);
  padding: 5px 12px;
  border-radius: 4px;
}
.ann-list { display: flex; flex-direction: column; }
.ann-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 4px;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}
.ann-item:last-child { border-bottom: none; }
.ann-item:hover .ann-title { color: var(--brand); }
.ann-pin {
  font-size: 11px;
  color: var(--orange);
  background: #fdf3e3;
  padding: 1px 7px;
  border-radius: 3px;
  flex-shrink: 0;
}
.ann-title {
  flex: 1;
  font-size: 13.5px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ann-time {
  font-size: 12px;
  color: var(--text-faint);
  flex-shrink: 0;
}
.progress-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.ps-item {
  text-align: center;
  background: var(--bg-soft);
  border-radius: var(--radius-md);
  padding: 14px 8px;
}
.ps-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--brand);
}
.ps-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 3px;
}
.pb-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 6px;
  text-align: center;
}
</style>
