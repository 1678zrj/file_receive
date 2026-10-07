<template>
  <div class="grade-panel">
    <!-- 工具栏 -->
    <div class="panel-toolbar">
      <span class="tip">成绩来源于各次作业评分与课程总评，未批改作业显示「—」</span>
      <el-button :icon="Refresh" circle size="small" @click="load" title="刷新" />
    </div>

    <!-- 成绩表：学生 × 作业 二维矩阵 -->
    <el-table v-loading="loading" :data="rows" stripe class="grade-table" border>
      <el-table-column label="学生" min-width="150" fixed="left">
        <template #default="{ row }">
          <div class="stu-cell">
            <UserAvatar :name="row.real_name" :size="30" />
            <div>
              <div class="stu-name">{{ row.real_name }}</div>
              <div class="stu-username">@{{ row.username }}</div>
            </div>
          </div>
        </template>
      </el-table-column>

      <!-- 动态作业列 -->
      <el-table-column
        v-for="a in assignmentTitles"
        :key="a.id"
        :label="a.title"
        min-width="130"
        align="center"
      >
        <template #default="{ row }">
          <span v-if="getAssignmentScore(row, a.id) != null" class="score-num" :class="scoreClass(getAssignmentScore(row, a.id)!)">
            {{ getAssignmentScore(row, a.id) }}
          </span>
          <span v-else class="dim-text">—</span>
        </template>
      </el-table-column>

      <!-- 总分列 -->
      <el-table-column label="总分" width="100" align="center" fixed="right">
        <template #default="{ row }">
          <span v-if="row.total_score != null" class="total-score" :class="scoreClass(row.total_score)">
            {{ row.total_score }}
          </span>
          <span v-else class="dim-text">—</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { gradeApi } from '@/api'
import type { CourseGradeRow } from '@/api/types'
import UserAvatar from '@/components/UserAvatar.vue'

const props = defineProps<{ courseId: number }>()

const rows = ref<CourseGradeRow[]>([])
const loading = ref(false)

/** 从第一行提取作业标题（动态列头） */
const assignmentTitles = computed(() => {
  if (rows.value.length === 0) return []
  return rows.value[0].assignments.map((a) => ({ id: a.assignment_id, title: a.title }))
})

onMounted(load)

async function load() {
  loading.value = true
  try {
    rows.value = await gradeApi.courseGrades(props.courseId)
  } catch (e: any) {
    ElMessage.error(e?.message || '加载成绩失败')
  } finally {
    loading.value = false
  }
}

function getAssignmentScore(row: CourseGradeRow, assignmentId: number): number | null {
  const a = row.assignments.find((x) => x.assignment_id === assignmentId)
  if (!a || !a.submitted) return null
  return a.score
}

function scoreClass(score: number) {
  if (score >= 90) return 'score-excellent'
  if (score >= 80) return 'score-good'
  if (score >= 60) return 'score-pass'
  return 'score-fail'
}
</script>

<style scoped>
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.tip {
  font-size: 12.5px;
  color: var(--text-secondary);
}
.stu-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stu-name {
  font-weight: 600;
  font-size: 13.5px;
}
.stu-username {
  font-size: 12px;
  color: var(--text-secondary);
}
.total-score {
  font-weight: 700;
  font-size: 15px;
}
.score-num {
  font-weight: 600;
  font-size: 13.5px;
}
.score-excellent { color: var(--green); }
.score-good { color: var(--brand); }
.score-pass { color: var(--orange); }
.score-fail { color: var(--red); }
.dim-text {
  color: var(--text-faint);
}
</style>
