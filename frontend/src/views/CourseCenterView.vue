<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">课程广场</h2>
        <p class="page-subtitle">浏览全部开放课程，选择感兴趣的课程加入学习</p>
      </div>
      <el-input
        v-model="keyword"
        placeholder="搜索课程名称 / 课程代码"
        :prefix-icon="Search"
        clearable
        style="width: 280px"
        @keyup.enter="load(1)"
        @clear="load(1)"
      />
    </div>

    <div v-loading="loading" class="course-area">
      <el-empty v-if="!loading && courses.length === 0" description="暂无匹配课程" />
      <div v-else class="course-grid">
        <CourseCard v-for="c in courses" :key="c.id" :course="c">
          <template #actions>
            <el-button
              v-if="auth.isStudent"
              type="primary"
              size="small"
              :loading="enrollingId === c.id"
              :disabled="enrolledIds.has(c.id)"
              @click.stop="enroll(c)"
            >
              {{ enrolledIds.has(c.id) ? '已加入' : '加入课程' }}
            </el-button>
            <el-tag v-else-if="isMyCourse(c.id)" size="small" type="success" effect="plain">我教的</el-tag>
          </template>
        </CourseCard>
      </div>
    </div>

    <div v-if="total > size" class="pager-box">
      <el-pagination
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="total, prev, pager, next"
        background
        @current-change="load()"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { courseApi } from '@/api'
import type { CourseResponse } from '@/api/types'
import { useAuthStore } from '@/stores/auth'
import { useCourseStore } from '@/stores/course'
import CourseCard from '@/components/CourseCard.vue'

const auth = useAuthStore()
const courseStore = useCourseStore()

const keyword = ref('')
const page = ref(1)
const size = ref(12)
const total = ref(0)
const courses = ref<CourseResponse[]>([])
const loading = ref(false)
const enrollingId = ref<number | null>(null)
const enrolledIds = ref<Set<number>>(new Set())

onMounted(async () => {
  await load()
  if (auth.user) {
    await courseStore.refreshMyCourses(auth.user.role)
    enrolledIds.value = new Set(courseStore.enrolled.map((c) => c.id))
  }
})

function isMyCourse(id: number) {
  return courseStore.teaching.some((c) => c.id === id)
}

async function load(p?: number) {
  if (p) page.value = p
  loading.value = true
  try {
    const res = await courseApi.list({
      page: page.value,
      size: size.value,
      keyword: keyword.value || undefined,
    })
    courses.value = res.items
    total.value = res.total
  } catch (e: any) {
    ElMessage.error(e?.message || '加载课程失败')
  } finally {
    loading.value = false
  }
}

async function enroll(course: CourseResponse) {
  enrollingId.value = course.id
  try {
    await courseStore.enroll(course.id)
    enrolledIds.value.add(course.id)
    ElMessage.success(`已加入《${course.name}》`)
  } catch (e: any) {
    ElMessage.error(e?.message || '选课失败')
  } finally {
    enrollingId.value = null
  }
}
</script>

<style scoped>
.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}
.course-area {
  min-height: 200px;
}
.pager-box {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}
</style>
