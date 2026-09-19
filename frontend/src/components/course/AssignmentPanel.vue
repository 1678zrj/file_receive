<template>
  <div class="assignment-panel">
    <!-- 工具栏 -->
    <div class="panel-toolbar">
      <div class="filter-tabs">
        <el-radio-group v-model="filter" size="default">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="ongoing">进行中</el-radio-button>
          <el-radio-button value="ended">已截止</el-radio-button>
        </el-radio-group>
      </div>
      <el-button v-if="isTeacher" type="primary" class="btn-primary" :icon="Plus" @click="createVisible = true">
        发布作业
      </el-button>
    </div>

    <!-- 接口缺失占位（仅在关闭 Mock 的真实接口模式下出现） -->
    <div v-if="apiMissing" class="missing-box">
      <el-icon :size="40" color="var(--text-secondary)"><Document /></el-icon>
      <h3>作业接口尚未提供</h3>
      <p>后端已建好作业数据模型（Assignment / Submission），但尚未提供 REST 接口，待补充后即可体验完整流程。</p>
      <div class="missing-apis">
        <code>POST /api/v1/assignment</code>
        <code>GET /api/v1/assignment/course/{id}</code>
        <code>POST /api/v1/submission</code>
        <code>POST /api/v1/submission/{id}/grade</code>
      </div>
      <el-button v-if="isTeacher" type="primary" class="btn-primary" @click="createVisible = true">
        预览发布作业表单
      </el-button>
    </div>

    <!-- 作业列表 -->
    <div v-else v-loading="loading">
      <el-empty v-if="!loading && filtered.length === 0" description="暂无作业" :image-size="110" />
      <el-table
        v-else
        :data="filtered"
        v-loading="loading"
        stripe
        class="assignment-table"
        @row-click="openDetail"
      >
        <el-table-column label="作业" min-width="300">
          <template #default="{ row }">
            <div class="a-cell">
              <div class="a-status" :class="statusClass(row)">
                <el-icon :size="18"><component :is="statusIcon(row)" /></el-icon>
              </div>
              <div class="a-main">
                <div class="a-title">{{ row.title }}</div>
                <div class="a-desc">{{ row.description || '暂无描述' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="截止时间" width="180">
          <template #default="{ row }">
            <div class="deadline-cell">
              <div>{{ formatDateTime(row.deadline) }}</div>
              <span class="deadline-tag" :class="{ urgent: deadlineInfo(row.deadline).urgent, overdue: deadlineInfo(row.deadline).overdue }">
                {{ deadlineInfo(row.deadline).text }}
              </span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="提交状态" width="130" align="center">
          <template #default="{ row }">
            <template v-if="!isTeacher">
              <el-tag v-if="row.my_submission?.score != null" type="success" round size="small">{{ row.my_submission.score }} 分</el-tag>
              <el-tag v-else-if="row.my_submission" type="info" round size="small">已提交</el-tag>
              <el-tag v-else type="warning" round size="small">待提交</el-tag>
            </template>
            <template v-else>
              <span class="submitted-count">{{ row.stats?.submitted_count ?? 0 }} 人已交</span>
            </template>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="90" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="openDetail(row)">
              {{ isTeacher ? '批改/查看' : '查看' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 发布作业对话框 -->
    <el-dialog v-model="createVisible" title="发布新作业" width="640px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" size="large">
        <el-form-item label="作业标题" prop="title">
          <el-input v-model="form.title" placeholder="例如：第二次作业：实现 RAG 检索" maxlength="80" show-word-limit />
        </el-form-item>
        <el-form-item label="作业描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="5" placeholder="详细描述作业要求、评分标准等（支持 Markdown）" maxlength="2000" show-word-limit />
        </el-form-item>
        <el-form-item label="截止时间" prop="deadline">
          <el-date-picker
            v-model="form.deadline"
            type="datetime"
            placeholder="选择截止时间"
            style="width: 100%"
            :disabled-date="(d: Date) => d.getTime() < Date.now() - 86400000"
          />
        </el-form-item>
        <el-form-item label="附件（选填，最多 5 个）">
          <div class="attach-area">
            <div v-for="(f, i) in form.attachments" :key="i" class="attach-chip">
              <FileIcon :file-name="f.file_name" :size="26" />
              <span class="attach-name">{{ f.file_name }}</span>
              <el-icon class="attach-del" @click="form.attachments.splice(i, 1)"><Close /></el-icon>
            </div>
            <el-button v-if="form.attachments.length < 5" :icon="Plus" plain size="small" @click="attachUploadVisible = true">
              上传附件
            </el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取 消</el-button>
        <el-button type="primary" class="btn-primary" :loading="creating" @click="createAssignment">发布作业</el-button>
      </template>
    </el-dialog>

    <!-- 附件上传 -->
    <UploadDialog v-model="attachUploadVisible" title="上传作业附件" @success="onAttachUploaded" />

    <!-- 作业详情抽屉 -->
    <AssignmentDetailDrawer
      v-model="detailVisible"
      :assignment="current"
      :is-teacher="isTeacher"
      @refresh="load"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Close, Document } from '@element-plus/icons-vue'
import { assignmentApi } from '@/api'
import type { Assignment } from '@/api/types'
import { formatDateTime, deadlineInfo } from '@/utils/format'
import FileIcon from '@/components/FileIcon.vue'
import UploadDialog from '@/components/UploadDialog.vue'
import AssignmentDetailDrawer from './AssignmentDetailDrawer.vue'

const props = defineProps<{ courseId: number; isTeacher: boolean }>()

const list = ref<Assignment[]>([])
const loading = ref(false)
const apiMissing = ref(false)
const filter = ref('all')

const createVisible = ref(false)
const attachUploadVisible = ref(false)
const creating = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  title: '',
  description: '',
  deadline: null as Date | null,
  attachments: [] as { file_record_id: number; file_name: string }[],
})
const formRules: FormRules = {
  title: [{ required: true, message: '请输入作业标题', trigger: 'blur' }],
  description: [{ required: true, message: '请输入作业描述', trigger: 'blur' }],
  deadline: [{ required: true, message: '请选择截止时间', trigger: 'change' }],
}

const detailVisible = ref(false)
const current = ref<Assignment | null>(null)

const filtered = computed(() => {
  if (filter.value === 'all') return list.value
  return list.value.filter((a) => {
    const overdue = deadlineInfo(a.deadline).overdue
    return filter.value === 'ended' ? overdue : !overdue
  })
})

onMounted(load)

async function load() {
  loading.value = true
  try {
    list.value = await assignmentApi.listByCourse(props.courseId)
    apiMissing.value = false
  } catch (e: any) {
    if (e?.status === 404 || e?.status === 405) apiMissing.value = true
    else ElMessage.error(e?.message || '加载作业失败')
  } finally {
    loading.value = false
  }
}

function statusClass(a: Assignment) {
  const info = deadlineInfo(a.deadline)
  if (info.overdue) return 'is-ended'
  if (!props.isTeacher && a.my_submission) return 'is-done'
  return 'is-active'
}
function statusIcon(a: Assignment) {
  const info = deadlineInfo(a.deadline)
  if (info.overdue) return 'CircleClose'
  if (!props.isTeacher && a.my_submission) return 'CircleCheck'
  return 'EditPen'
}

function onAttachUploaded(p: { file_record_id: number; file_name: string }) {
  form.attachments.push(p)
}

async function createAssignment() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  creating.value = true
  try {
    await assignmentApi.create({
      course_id: props.courseId,
      title: form.title,
      description: form.description,
      deadline: form.deadline!.toISOString(),
      attachment_file_ids: form.attachments.map((f) => f.file_record_id),
    })
    ElMessage.success('作业发布成功')
    createVisible.value = false
    form.title = form.description = ''
    form.deadline = null
    form.attachments = []
    await load()
  } catch (e: any) {
    if (e?.status === 404 || e?.status === 405) {
      ElMessage.warning('发布作业接口尚未提供（POST /api/v1/assignment），待后端补充')
    } else {
      ElMessage.error(e?.message || '发布失败')
    }
  } finally {
    creating.value = false
  }
}

function openDetail(a: Assignment) {
  current.value = a
  detailVisible.value = true
}
</script>

<style scoped>
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.assignment-table :deep(.el-table__row) {
  cursor: pointer;
}
.a-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}
.a-status {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.a-status.is-active { background: var(--brand-light); color: var(--brand); }
.a-status.is-done { background: var(--success-bg); color: var(--success-text); }
.a-status.is-ended { background: var(--surface-hover); color: var(--text-secondary); }
.a-main { min-width: 0; }
.a-title { font-weight: 600; font-size: 14px; }
.a-desc {
  font-size: 12.5px;
  color: var(--text-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.deadline-cell {
  font-size: 13px;
  line-height: 1.5;
}
.deadline-cell > div {
  color: var(--text-regular);
}
.deadline-tag { font-weight: 600; font-size: 12px; }
.deadline-tag.urgent { color: var(--orange); }
.deadline-tag.overdue { color: var(--text-secondary); }
.submitted-count {
  font-size: 12.5px;
  color: var(--brand);
}

.attach-area {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.attach-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 5px 10px;
}
.attach-name {
  font-size: 12.5px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attach-del {
  cursor: pointer;
  color: var(--text-secondary);
}
.attach-del:hover { color: var(--red); }

.missing-box {
  text-align: center;
  padding: 48px 30px;
  background: var(--bg-soft);
  border-radius: var(--radius-md);
  border: 1px dashed var(--brand-border);
}
.missing-box h3 { margin: 12px 0 10px; }
.missing-box p { color: var(--text-regular); line-height: 1.8; }
.missing-apis {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
  margin: 16px 0 22px;
}
.missing-apis code {
  background: var(--code-inline-bg);
  color: var(--code-inline-text);
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
}
</style>
