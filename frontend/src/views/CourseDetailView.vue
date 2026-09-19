<template>
  <div class="course-space" v-loading="pageLoading">
    <!-- ============ 通栏课程横幅 ============ -->
    <div class="course-banner" :style="{ background: heroGradient }">
      <div class="banner-inner">
        <div class="banner-left">
          <div class="banner-tags">
            <span class="banner-code" v-if="course?.course_code">{{ course.course_code }}</span>
            <span class="banner-teacher-tag" v-if="isCourseTeacher">我创建的课程</span>
          </div>
          <h1 class="banner-title">{{ course?.name || `课程 #${courseId}` }}</h1>
          <div class="banner-meta">
            <span class="banner-meta-item">
              <el-icon :size="14"><User /></el-icon>
              {{ course?.teacher_name || `教师 #${course?.teacher_id ?? '—'}` }}
            </span>
            <span class="banner-meta-item" v-if="course">
              <el-icon :size="14"><Calendar /></el-icon>
              {{ formatDate(course.created_at) }} 创建
            </span>
          </div>
        </div>
        <div class="banner-right" v-if="auth.isStudent && !isCourseTeacher">
          <el-button
            type="primary"
            class="btn-primary"
            :loading="enrolling"
            :disabled="enrolled"
            @click="enrollCourse"
          >
            {{ enrolled ? '已加入学习' : '加入课程' }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- ============ 课程空间主体：左侧导航 + 右侧内容 ============ -->
    <div class="space-body">
      <!-- 左侧课程内导航 -->
      <aside class="space-nav">
        <div
          v-for="item in navItems"
          :key="item.key"
          class="nav-item"
          :class="{ active: activeTab === item.key }"
          @click="switchTab(item.key)"
        >
          <el-icon :size="17"><component :is="item.icon" /></el-icon>
          <span class="nav-label">{{ item.label }}</span>
        </div>
      </aside>

      <!-- 右侧内容区 -->
      <main class="space-content">
        <!-- 概述 -->
        <OverviewPanel v-if="activeTab === 'overview'" :course="course" :is-teacher="isCourseTeacher" :course-id="courseId" @goto="switchTab" />
        <!-- 资源 -->
        <ResourcePanel v-else-if="activeTab === 'resources'" :course-id="courseId" :is-teacher="isCourseTeacher" />
        <!-- 作业 -->
        <AssignmentPanel v-else-if="activeTab === 'assignments'" :course-id="courseId" :is-teacher="isCourseTeacher" />
        <!-- 成绩 -->
        <GradePanel v-else-if="activeTab === 'grades'" :course-id="courseId" />
        <MyGradePanel v-else-if="activeTab === 'my-grade'" :course-id="courseId" />
        <!-- 公告 -->
        <AnnouncementPanel v-else-if="activeTab === 'announcements'" :course-id="courseId" :is-teacher="isCourseTeacher" />
        <!-- 讨论 -->
        <DiscussionPanel v-else-if="activeTab === 'discussion'" :course-id="courseId" />
        <!-- 学生管理 -->
        <StudentsPanel v-else-if="activeTab === 'students'" :course-id="courseId" />
        <!-- 兜底 -->
        <div v-else class="content-placeholder">
          <el-empty description="请选择功能" />
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { courseApi } from '@/api'
import type { CourseResponse } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { useCourseStore } from '@/stores/course'
import { courseCover, formatDate } from '@/utils/format'
import OverviewPanel from '@/components/course/OverviewPanel.vue'
import ResourcePanel from '@/components/course/ResourcePanel.vue'
import AssignmentPanel from '@/components/course/AssignmentPanel.vue'
import StudentsPanel from '@/components/course/StudentsPanel.vue'
import GradePanel from '@/components/course/GradePanel.vue'
import MyGradePanel from '@/components/course/MyGradePanel.vue'
import AnnouncementPanel from '@/components/course/AnnouncementPanel.vue'
import DiscussionPanel from '@/components/course/DiscussionPanel.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const courseStore = useCourseStore()

const courseId = computed(() => Number(route.params.id))
const course = ref<(CourseResponse & { teacher_name?: string }) | null>(null)
const pageLoading = ref(false)
const enrolling = ref(false)
const activeTab = ref('overview')

const isCourseTeacher = computed(() => {
  if (!auth.user) return false
  if (auth.isAdmin) return true
  return course.value?.teacher_id === auth.user.id
})

const enrolled = computed(() => courseStore.enrolled.some((c) => c.id === courseId.value))
const heroGradient = computed(() => courseCover(course.value?.name || `课程${courseId.value}`))

/** 课程内导航项（按角色动态） */
interface NavItem {
  key: string
  label: string
  icon: string
  external?: boolean
}
const navItems = computed<NavItem[]>(() => {
  const items: NavItem[] = [
    { key: 'overview', label: '课程概述', icon: 'HomeFilled' },
    { key: 'resources', label: '课程资源', icon: 'FolderOpened' },
    { key: 'assignments', label: '作业', icon: 'EditPen' },
  ]
  if (isCourseTeacher.value) {
    items.push({ key: 'grades', label: '成绩', icon: 'DataAnalysis' })
  } else {
    items.push({ key: 'my-grade', label: '我的成绩', icon: 'DataAnalysis' })
  }
  items.push(
    { key: 'announcements', label: '公告', icon: 'Bell' },
    { key: 'discussion', label: '讨论', icon: 'ChatDotRound' },
  )
  if (isCourseTeacher.value) {
    items.push({ key: 'students', label: '学生管理', icon: 'UserFilled' })
  }
  // 跳转型入口（知识库 / AI 问答独立模块）
  items.push(
    { key: 'knowledge', label: '知识库', icon: 'Collection', external: true },
    { key: 'qa', label: 'AI 问答', icon: 'MagicStick', external: true },
  )
  return items
})

onMounted(async () => {
  pageLoading.value = true
  try {
    course.value = await courseApi.detail(courseId.value)
  } catch (e: any) {
    ElMessage.error(e?.message || '加载课程详情失败')
  } finally {
    pageLoading.value = false
  }
  if (auth.user) courseStore.refreshMyCourses(auth.user.role)
})

function switchTab(key: string) {
  if (key === 'knowledge') return goKnowledge()
  if (key === 'qa') return goQa()
  activeTab.value = key
}

async function enrollCourse() {
  enrolling.value = true
  try {
    await courseStore.enroll(courseId.value)
    ElMessage.success('已成功加入课程')
    if (auth.user) courseStore.refreshMyCourses(auth.user.role)
  } catch (e: any) {
    ElMessage.error(e?.message || '加入课程失败')
  } finally {
    enrolling.value = false
  }
}

// 知识库 / AI 问答入口保留在左侧导航外（通过顶部或快捷方式）
function goKnowledge() {
  router.push({ name: 'knowledge', query: { courseId: courseId.value } })
}
function goQa() {
  router.push({ name: 'qa', query: { courseId: courseId.value } })
}
</script>

<style scoped>
.course-space {
  min-height: calc(100vh - 52px);
}

/* ---------- 横幅 ---------- */
.course-banner {
  color: #fff;
  position: relative;
  overflow: hidden;
}
.banner-inner {
  max-width: 1440px;
  margin: 0 auto;
  padding: 30px 32px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.banner-tags {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.banner-code {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
  background: rgba(255, 255, 255, 0.18);
  padding: 3px 12px;
  border-radius: 3px;
}
.banner-teacher-tag {
  font-size: 12px;
  background: rgba(255, 255, 255, 0.18);
  padding: 3px 12px;
  border-radius: 3px;
}
.banner-title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.banner-meta {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.banner-meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  opacity: 0.85;
}
.banner-right {
  flex-shrink: 0;
}

/* ---------- 主体 ---------- */
.space-body {
  max-width: 1440px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 0;
  min-height: calc(100vh - 180px);
}
.space-nav {
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 12px 8px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  color: var(--text-regular);
  font-size: 14px;
  margin-bottom: 2px;
  transition: all 0.2s;
}
.nav-item:hover {
  background: var(--bg-soft);
  color: var(--brand);
}
.nav-item.active {
  background: var(--brand);
  color: #fff;
}
.nav-item.active .el-icon {
  color: #fff;
}
.nav-label {
  white-space: nowrap;
}
.space-content {
  padding: 20px 24px 40px;
  min-width: 0;
}
.content-placeholder {
  padding: 40px 0;
}

@media (max-width: 900px) {
  .space-body {
    grid-template-columns: 1fr;
  }
  .space-nav {
    display: flex;
    overflow-x: auto;
    border-right: none;
    border-bottom: 1px solid var(--border);
    padding: 8px;
  }
  .nav-item {
    flex-shrink: 0;
    margin-bottom: 0;
  }
  .nav-label {
    font-size: 13px;
  }
  .space-content {
    padding: 16px 12px 32px;
  }
}
</style>
