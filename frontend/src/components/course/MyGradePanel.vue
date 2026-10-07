<template>
  <div class="my-grade-panel">
    <!-- 总分卡 -->
    <div class="total-card cc-card">
      <div class="tc-label">课程总评</div>
      <div class="tc-value" :class="scoreClass(grade?.total_score)">
        {{ grade?.total_score != null ? grade.total_score : '待评定' }}
      </div>
      <div class="tc-sub">综合各次作业成绩得出</div>
    </div>

    <!-- 各次作业成绩 -->
    <div v-loading="loading" class="assignments">
      <el-table :data="grade?.assignments ?? []" stripe class="grade-table">
        <el-table-column label="作业" min-width="240">
          <template #default="{ row }">{{ row.title }}</template>
        </el-table-column>
        <el-table-column label="分数" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.score != null" class="score-num" :class="scoreClass(row.score)">{{ row.score }}</span>
            <el-tag v-else type="info" size="small" effect="plain">待批改</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="160">
          <template #default="{ row }">
            <span class="dim-text">{{ row.submitted_at ? formatDateTime(row.submitted_at) : '未提交' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="教师评语" min-width="200">
          <template #default="{ row }">
            <span class="feedback">{{ row.feedback || '—' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { gradeApi } from '@/api'
import type { MyCourseGrade } from '@/api/types'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ courseId: number }>()

const grade = ref<MyCourseGrade | null>(null)
const loading = ref(false)

onMounted(load)

async function load() {
  loading.value = true
  try {
    grade.value = await gradeApi.myGrade(props.courseId)
  } catch (e: any) {
    ElMessage.error(e?.message || '加载成绩失败')
  } finally {
    loading.value = false
  }
}

function scoreClass(score: number | null | undefined) {
  if (score == null) return ''
  if (score >= 90) return 'score-excellent'
  if (score >= 80) return 'score-good'
  if (score >= 60) return 'score-pass'
  return 'score-fail'
}
</script>

<style scoped>
.total-card {
  padding: 20px 24px;
  margin-bottom: 16px;
  display: flex;
  align-items: baseline;
  gap: 16px;
  flex-wrap: wrap;
}
.tc-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.tc-value {
  font-size: 36px;
  font-weight: 800;
  line-height: 1;
}
.tc-sub {
  font-size: 12px;
  color: var(--text-faint);
}
.score-num {
  font-weight: 700;
  font-size: 14px;
}
.score-excellent { color: var(--green); }
.score-good { color: var(--brand); }
.score-pass { color: var(--orange); }
.score-fail { color: var(--red); }
.dim-text {
  color: var(--text-faint);
}
.feedback {
  font-size: 13px;
  color: var(--text-regular);
}
</style>
