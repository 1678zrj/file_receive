<template>
  <el-drawer v-model="visible" :title="null" size="620px" destroy-on-close>
    <template v-if="assignment">
      <!-- 头部 -->
      <div class="drawer-header">
        <h2 class="dh-title">{{ assignment.title }}</h2>
        <div class="dh-meta">
          <el-tag :type="deadlineInfo(assignment.deadline).overdue ? 'info' : 'warning'" round size="small">
            {{ deadlineInfo(assignment.deadline).text }}
          </el-tag>
          <span class="dh-time">截止：{{ formatDateTime(assignment.deadline) }}</span>
        </div>
      </div>

      <!-- 描述 -->
      <div class="drawer-section">
        <h4 class="ds-title">作业要求</h4>
        <div class="md-body" v-html="renderedDesc"></div>
      </div>

      <!-- 附件 -->
      <div v-if="assignment.attachments?.length" class="drawer-section">
        <h4 class="ds-title">作业附件</h4>
        <div class="attach-list">
          <div v-for="f in assignment.attachments" :key="f.id" class="attach-row">
            <FileIcon :file-name="f.file_name" :size="30" />
            <span class="attach-row-name">{{ f.file_name }}</span>
            <el-button size="small" text type="primary" @click="downloadFile(f.file_record_id, f.file_name)">下载</el-button>
          </div>
        </div>
      </div>

      <!-- 学生视角：我的提交 -->
      <div v-if="!isTeacher" class="drawer-section">
        <h4 class="ds-title">我的提交</h4>
        <template v-if="assignment.my_submission">
          <div class="my-sub">
            <div class="ms-row">
              <span class="ms-label">提交时间</span>
              <span>{{ formatDateTime(assignment.my_submission.submitted_at) }}</span>
            </div>
            <div class="ms-row">
              <span class="ms-label">第几次提交</span>
              <span>第 {{ assignment.my_submission.attempt }} 次</span>
            </div>
            <div class="ms-row">
              <span class="ms-label">成绩</span>
              <el-tag v-if="assignment.my_submission.score != null" type="success" round>{{ assignment.my_submission.score }} 分</el-tag>
              <el-tag v-else type="info" round>待批改</el-tag>
            </div>
            <div v-if="assignment.my_submission.feedback" class="ms-feedback">
              <span class="ms-label">教师评语</span>
              <p>{{ assignment.my_submission.feedback }}</p>
            </div>
          </div>
        </template>
        <el-empty v-else description="还未提交作业" :image-size="70" />

        <div class="submit-area">
          <div v-for="(f, i) in submitFiles" :key="i" class="attach-row">
            <FileIcon :file-name="f.file_name" :size="30" />
            <span class="attach-row-name">{{ f.file_name }}</span>
            <el-button size="small" text type="danger" @click="submitFiles.splice(i, 1)">移除</el-button>
          </div>
          <el-button :icon="Plus" plain @click="submitUploadVisible = true" :disabled="isOverdue">
            添加提交文件
          </el-button>
          <el-button
            type="primary"
            class="btn-primary"
            :disabled="submitFiles.length === 0 || isOverdue"
            :loading="submitting"
            @click="submit"
          >
            {{ assignment.my_submission ? '重新提交' : '提交作业' }}
          </el-button>
          <p v-if="isOverdue" class="overdue-tip">作业已截止，无法提交</p>
        </div>
      </div>

      <!-- 教师视角：提交管理 -->
      <div v-else class="drawer-section">
        <h4 class="ds-title">提交情况</h4>
        <el-alert type="info" :closable="false" show-icon class="todo-alert">
          <template #title>
            提交列表与批改接口待提供（GET /api/v1/assignment/{{ assignment.id }}/submissions · POST /api/v1/submission/{id}/grade），下方为界面预览。
          </template>
        </el-alert>
        <el-table :data="submissions" v-loading="subsLoading" empty-text="暂无提交记录">
          <el-table-column label="学生" min-width="120">
            <template #default="{ row }">
              <div class="stu-cell">
                <UserAvatar :name="row.real_name || row.username || '?'" :size="28" />
                <span>{{ row.real_name || row.username || `学生 #${row.student_id}` }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="提交时间" min-width="140">
            <template #default="{ row }">{{ formatDateTime(row.submitted_at) }}</template>
          </el-table-column>
          <el-table-column label="成绩" width="90" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.score != null" type="success" round size="small">{{ row.score }}</el-tag>
              <el-tag v-else type="info" round size="small">未批改</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button size="small" type="primary" plain @click="openGrade(row)">批改</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <!-- 提交上传 -->
    <UploadDialog v-model="submitUploadVisible" title="上传作业文件" @success="onSubmitUploaded" />

    <!-- 批改对话框 -->
    <el-dialog v-model="gradeVisible" title="批改作业" width="420px" append-to-body>
      <el-form label-position="top">
        <el-form-item label="分数">
          <el-input-number v-model="gradeForm.score" :min="0" :max="100" style="width: 100%" />
        </el-form-item>
        <el-form-item label="评语">
          <el-input v-model="gradeForm.feedback" type="textarea" :rows="4" placeholder="给学生的反馈..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="gradeVisible = false">取 消</el-button>
        <el-button type="primary" class="btn-primary" :loading="grading" @click="doGrade">确认批改</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { assignmentApi, resourceApi } from '@/api'
import type { Assignment, SubmissionWithStudent } from '@/api/types'
import { formatDateTime, deadlineInfo } from '@/utils/format'
import FileIcon from '@/components/FileIcon.vue'
import UploadDialog from '@/components/UploadDialog.vue'
import UserAvatar from '@/components/UserAvatar.vue'

const props = defineProps<{
  modelValue: boolean
  assignment: Assignment | null
  isTeacher: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean]; refresh: [] }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const md = new MarkdownIt({ html: false, linkify: true })
const renderedDesc = computed(() => (props.assignment ? md.render(props.assignment.description || '暂无描述') : ''))
const isOverdue = computed(() => (props.assignment ? deadlineInfo(props.assignment.deadline).overdue : false))

// ---- 学生提交 ----
const submitUploadVisible = ref(false)
const submitFiles = ref<{ file_record_id: number; file_name: string }[]>([])
const submitting = ref(false)

watch(visible, (v) => {
  if (v) submitFiles.value = []
  if (v && props.isTeacher) loadSubmissions()
})

function onSubmitUploaded(p: { file_record_id: number; file_name: string }) {
  submitFiles.value.push(p)
}

async function submit() {
  if (!props.assignment || submitFiles.value.length === 0) return
  submitting.value = true
  try {
    await assignmentApi.submit({
      assignment_id: props.assignment.id,
      file_record_ids: submitFiles.value.map((f) => f.file_record_id),
    })
    ElMessage.success('作业提交成功')
    emit('refresh')
  } catch (e: any) {
    if (e?.status === 404 || e?.status === 405) {
      ElMessage.warning('提交作业接口尚未提供（POST /api/v1/submission），待后端补充')
    } else {
      ElMessage.error(e?.message || '提交失败')
    }
  } finally {
    submitting.value = false
  }
}

// ---- 教师批改 ----
const submissions = ref<SubmissionWithStudent[]>([])
const subsLoading = ref(false)
const gradeVisible = ref(false)
const grading = ref(false)
const gradeTarget = ref<SubmissionWithStudent | null>(null)
const gradeForm = ref({ score: 0, feedback: '' })

async function loadSubmissions() {
  if (!props.assignment) return
  subsLoading.value = true
  try {
    submissions.value = await assignmentApi.listSubmissions(props.assignment.id)
  } catch {
    submissions.value = []
  } finally {
    subsLoading.value = false
  }
}

function openGrade(row: SubmissionWithStudent) {
  gradeTarget.value = row
  gradeForm.value = { score: row.score ?? 0, feedback: row.feedback ?? '' }
  gradeVisible.value = true
}

async function doGrade() {
  if (!gradeTarget.value) return
  grading.value = true
  try {
    await assignmentApi.grade(gradeTarget.value.id, gradeForm.value)
    ElMessage.success('批改完成')
    gradeVisible.value = false
    loadSubmissions()
    emit('refresh')
  } catch (e: any) {
    if (e?.status === 404 || e?.status === 405) {
      ElMessage.warning('批改接口尚未提供（POST /api/v1/submission/{id}/grade），待后端补充')
    } else {
      ElMessage.error(e?.message || '批改失败')
    }
  } finally {
    grading.value = false
  }
}

async function downloadFile(fileRecordId: number, fileName: string) {
  try {
    const blob = await resourceApi.fetchBlob(fileRecordId, 'download')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    ElMessage.warning('下载接口尚未提供，待后端补充')
  }
}
</script>

<style scoped>
.drawer-header {
  margin-bottom: 20px;
}
.dh-title {
  margin: 0 0 10px;
  font-size: 20px;
  font-weight: 700;
}
.dh-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}
.dh-time {
  font-size: 12.5px;
  color: var(--text-secondary);
}
.drawer-section {
  margin-bottom: 24px;
}
.ds-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
  padding-left: 10px;
  border-left: 3px solid var(--brand);
}
.attach-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.attach-row {
  display: flex;
  align-items: center;
  gap: 10px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
}
.attach-row-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.my-sub {
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  margin-bottom: 14px;
}
.ms-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 0;
  font-size: 13.5px;
}
.ms-label {
  color: var(--text-secondary);
  width: 88px;
  flex-shrink: 0;
}
.ms-feedback {
  margin-top: 8px;
}
.ms-feedback p {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.7;
}
.submit-area {
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: flex-start;
}
.overdue-tip {
  color: var(--orange);
  font-size: 12.5px;
  margin: 0;
}
.todo-alert {
  margin-bottom: 14px;
  border-radius: var(--radius-md);
}
.stu-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
