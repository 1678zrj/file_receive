<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">我的课程</h2>
        <p class="page-subtitle">{{ subtitle }}</p>
      </div>
      <el-button
        v-if="auth.isTeacherOrAdmin"
        type="primary"
        class="btn-primary"
        :icon="Plus"
        @click="createVisible = true"
      >
        创建课程
      </el-button>
    </div>

    <!-- 管理员：全部课程（全局视角） -->
    <template v-if="auth.isAdmin">
      <div class="section-head">
        <h3 class="section-title">全部课程 <span class="count">{{ courseStore.allList.length }}</span></h3>
      </div>
      <div v-loading="courseStore.loading" class="course-area">
        <el-empty v-if="!courseStore.loading && courseStore.allList.length === 0" description="暂无课程" :image-size="90">
          <el-button type="primary" class="btn-primary" @click="createVisible = true">创建课程</el-button>
        </el-empty>
        <div v-else class="course-grid">
          <CourseCard v-for="c in courseStore.allList" :key="c.id" :course="c" />
        </div>
      </div>
    </template>

    <!-- 教师：我教的课 + 我学的课 -->
    <template v-else-if="auth.isTeacher">
      <div class="section-head">
        <h3 class="section-title">我教的课 <span class="count">{{ courseStore.teaching.length }}</span></h3>
      </div>
      <div v-loading="courseStore.loading" class="course-area">
        <el-empty v-if="!courseStore.loading && courseStore.teaching.length === 0" description="还没有创建课程" :image-size="90">
          <el-button type="primary" class="btn-primary" @click="createVisible = true">创建课程</el-button>
        </el-empty>
        <div v-else class="course-grid">
          <CourseCard v-for="c in courseStore.teaching" :key="c.id" :course="c" />
        </div>
      </div>

      <div class="section-head mt-lg">
        <h3 class="section-title">我学的课 <span class="count">{{ courseStore.enrolled.length }}</span></h3>
      </div>
      <div v-loading="courseStore.loading" class="course-area">
        <el-empty v-if="!courseStore.loading && courseStore.enrolled.length === 0" description="还没有加入任何课程" :image-size="90">
          <el-button type="primary" class="btn-primary" @click="$router.push('/courses')">前往课程广场</el-button>
        </el-empty>
        <div v-else class="course-grid">
          <CourseCard v-for="c in courseStore.enrolled" :key="c.id" :course="c" />
        </div>
      </div>
    </template>

    <!-- 学生：我学的课 -->
    <template v-else>
      <div class="section-head">
        <h3 class="section-title">我学的课 <span class="count">{{ courseStore.enrolled.length }}</span></h3>
      </div>
      <div v-loading="courseStore.loading" class="course-area">
        <el-empty v-if="!courseStore.loading && courseStore.enrolled.length === 0" description="还没有加入任何课程" :image-size="90">
          <el-button type="primary" class="btn-primary" @click="$router.push('/courses')">前往课程广场</el-button>
        </el-empty>
        <div v-else class="course-grid">
          <CourseCard v-for="c in courseStore.enrolled" :key="c.id" :course="c" />
        </div>
      </div>
    </template>

    <!-- 创建课程对话框 -->
    <el-dialog v-model="createVisible" title="创建新课程" width="500px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="课程名称" prop="name">
          <el-input v-model="form.name" placeholder="例如：高级 Python 编程" maxlength="60" show-word-limit />
        </el-form-item>
        <el-form-item label="课程代码（选填）" prop="course_code">
          <el-input v-model="form.course_code" placeholder="例如：CS-201" maxlength="32" />
        </el-form-item>
        <el-form-item label="课程简介" prop="overview">
          <el-input v-model="form.overview" type="textarea" :rows="3" placeholder="简单介绍这门课程..." maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取 消</el-button>
        <el-button type="primary" class="btn-primary" :loading="creating" @click="createCourse">创建课程</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useCourseStore } from '@/stores/course'
import CourseCard from '@/components/CourseCard.vue'

const auth = useAuthStore()
const courseStore = useCourseStore()
const route = useRoute()
const router = useRouter()

const createVisible = ref(false)
const creating = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({ name: '', course_code: '', overview: '' })

const rules: FormRules = {
  name: [
    { required: true, message: '请输入课程名称', trigger: 'blur' },
    { min: 2, max: 60, message: '长度 2-60 个字符', trigger: 'blur' },
  ],
}

const subtitle = computed(() => {
  if (auth.isAdmin) return '管理平台全部课程（全局视角）'
  if (auth.isTeacher) return '你创建的课程与你加入的课程'
  return '你已加入的所有课程'
})

onMounted(() => {
  if (auth.user) courseStore.refreshMyCourses(auth.user.role)
  if (route.query.create === '1' && auth.isTeacherOrAdmin) createVisible.value = true
})

async function createCourse() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  creating.value = true
  try {
    const course = await courseStore.createCourse({
      name: form.name,
      course_code: form.course_code || null,
      overview: form.overview || '暂无简介',
    })
    ElMessage.success(`课程《${course.name}》创建成功`)
    createVisible.value = false
    form.name = form.course_code = form.overview = ''
    router.push({ name: 'course-detail', params: { id: course.id } })
  } catch (e: any) {
    ElMessage.error(e?.message || '创建课程失败')
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.section-head {
  margin: 6px 0 12px;
}
.section-head.mt-lg {
  margin-top: 28px;
}
.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}
.count {
  font-size: 12px;
  color: var(--brand);
  background: var(--brand-light);
  padding: 1px 9px;
  border-radius: 10px;
}
.course-area {
  min-height: 120px;
}
.course-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}
</style>
