<template>
  <div class="students-panel">
    <!-- 工具栏 -->
    <div class="panel-toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索学生姓名或用户名..."
        :prefix-icon="Search"
        clearable
        style="max-width: 300px"
      />
      <el-button :icon="Refresh" circle @click="load()" title="刷新" />
    </div>

    <el-table :data="filtered" v-loading="loading" stripe class="students-table">
      <el-table-column label="学生" min-width="180">
        <template #default="{ row }">
          <div class="stu-cell">
            <UserAvatar :name="row.real_name" :size="36" />
            <div>
              <div class="stu-name">{{ row.real_name }}</div>
              <div class="stu-username">@{{ row.username }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="学生 ID" prop="student_id" width="110" align="center" />
      <el-table-column label="课程成绩" width="130" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.score != null" :type="row.score >= 60 ? 'success' : 'danger'" round size="small">
            {{ row.score }} 分
          </el-tag>
          <span v-else class="no-score">未录入</span>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager-box">
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
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { enrollmentApi } from '@/api'
import type { CourseStudent } from '@/api/types'
import UserAvatar from '@/components/UserAvatar.vue'

const props = defineProps<{ courseId: number }>()

const list = ref<CourseStudent[]>([])
const loading = ref(false)
const keyword = ref('')
const page = ref(1)
const size = ref(10)
const total = ref(0)

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return list.value
  return list.value.filter((s) => s.real_name.toLowerCase().includes(k) || s.username.toLowerCase().includes(k))
})

onMounted(() => load())

async function load(p?: number) {
  if (p) page.value = p
  loading.value = true
  try {
    const res = await enrollmentApi.courseStudents(props.courseId, page.value, size.value)
    list.value = res.items
    total.value = res.total
  } catch (e: any) {
    ElMessage.error(e?.message || '加载学生列表失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.students-table {
  border-radius: var(--radius-md);
}
.stu-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stu-name {
  font-weight: 600;
}
.stu-username {
  font-size: 12px;
  color: var(--text-secondary);
}
.no-score {
  color: var(--text-secondary);
  font-size: 12.5px;
}
.pager-box {
  display: flex;
  justify-content: center;
  margin-top: 18px;
}
</style>
