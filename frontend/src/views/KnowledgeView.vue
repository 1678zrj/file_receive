<template>
  <div class="page-container">
    <div class="page-header">
      <div>
        <h2 class="page-title">知识库管理</h2>
        <p class="page-subtitle">管理课程知识库文档，文件将被解析、分块并向量化，供 AI 问答检索</p>
      </div>
      <div class="header-actions">
        <CourseSelector v-model="selectedCourseId" />
      </div>
    </div>

    <!-- 未选择课程 -->
    <div v-if="selectedCourseId == null" class="cc-card empty-card">
      <el-empty description="请先选择一门课程，查看或管理它的知识库" :image-size="120">
        <el-button type="primary" class="btn-primary" @click="$router.push('/my-courses')">前往我的课程</el-button>
      </el-empty>
    </div>

    <!-- 已选择课程 -->
    <template v-else>
      <!-- 统计概览 -->
      <div class="kb-stats">
        <div class="kb-stat-item">
          <div class="kb-stat-value">{{ stats.total }}</div>
          <div class="kb-stat-label">文档总数</div>
        </div>
        <div class="kb-stat-item">
          <div class="kb-stat-value" style="color:var(--green)">{{ stats.ready }}</div>
          <div class="kb-stat-label">已就绪</div>
        </div>
        <div class="kb-stat-item">
          <div class="kb-stat-value" style="color:var(--orange)">{{ stats.processing }}</div>
          <div class="kb-stat-label">处理中</div>
        </div>
        <div class="kb-stat-item">
          <div class="kb-stat-value" style="color:var(--red)">{{ stats.failed }}</div>
          <div class="kb-stat-label">失败</div>
        </div>
        <div class="kb-stat-item">
          <div class="kb-stat-value">{{ stats.totalChunks }}</div>
          <div class="kb-stat-label">总分块</div>
        </div>
        <div class="kb-stat-item">
          <div class="kb-stat-value">{{ formatSize(stats.totalChars) }}</div>
          <div class="kb-stat-label">总字符</div>
        </div>
      </div>

      <!-- 工具栏 -->
      <div class="panel-toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="keyword"
            placeholder="搜索文档标题"
            :prefix-icon="Search"
            clearable
            style="width: 220px"
          />
          <el-radio-group v-model="statusFilter" size="small">
            <el-radio-button value="all">全部</el-radio-button>
            <el-radio-button value="ready">已就绪</el-radio-button>
            <el-radio-button value="processing">处理中</el-radio-button>
            <el-radio-button value="failed">失败</el-radio-button>
            <el-radio-button value="disabled">已停用</el-radio-button>
          </el-radio-group>
          <span v-if="polling" class="polling-tag">
            <el-icon class="animate-pulse" :size="13"><Loading /></el-icon>
            同步状态中…
          </span>
        </div>
        <div class="toolbar-right">
          <el-button :icon="Refresh" @click="load">刷新</el-button>
          <el-button v-if="isTeacher" type="primary" class="btn-primary" :icon="Upload" @click="triggerPick">
            上传文档
          </el-button>
        </div>
      </div>

      <!-- 文档列表 -->
      <div v-loading="loading">
        <!-- 接口缺失 -->
        <div v-if="apiMissing && docs.length === 0" class="cc-card missing-box">
          <el-icon :size="40" color="var(--text-secondary)"><Collection /></el-icon>
          <h3>知识库列表接口尚未提供</h3>
          <p>后端暂未提供「知识库文档列表」接口（建议：GET /api/v1/kb/course/{course_id}/docs）。</p>
          <el-button v-if="isTeacher" type="primary" class="btn-primary" @click="triggerPick">上传文档</el-button>
        </div>

        <el-empty v-else-if="!loading && filteredDocs.length === 0" description="没有匹配的文档" :image-size="110">
          <el-button v-if="isTeacher && docs.length === 0" type="primary" class="btn-primary" @click="triggerPick">上传第一篇文档</el-button>
        </el-empty>

        <el-table
          v-else
          :data="filteredDocs"
          v-loading="loading"
          stripe
          class="doc-table"
          @row-click="openDetail"
        >
          <el-table-column label="文档" min-width="280">
            <template #default="{ row }">
              <div class="doc-cell">
                <FileIcon :file-name="row.title" :size="32" />
                <div class="doc-main">
                  <div class="doc-title" :title="row.title">{{ row.title }}</div>
                  <div v-if="row.error_msg" class="doc-error" :title="row.error_msg">{{ row.error_msg }}</div>
                </div>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="130" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)" size="small" effect="light">
                <span class="status-tag-inner">
                  <el-icon v-if="isProcessing(row.status)" class="animate-pulse" :size="12"><Loading /></el-icon>
                  {{ statusText(row.status) }}
                </span>
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="文本块" width="90" align="center">
            <template #default="{ row }">{{ row.chunk_count || '—' }}</template>
          </el-table-column>

          <el-table-column label="字符数" width="110" align="right">
            <template #default="{ row }">
              <span class="dim-text">{{ row.markdown_char_count ? formatSize(row.markdown_char_count) : '—' }}</span>
            </template>
          </el-table-column>

          <el-table-column label="更新时间" width="160">
            <template #default="{ row }">
              <span class="dim-text">{{ formatDateTime(row.updated_at || row.created_at) }}</span>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="280" align="right" fixed="right">
            <template #default="{ row }">
              <div class="doc-ops">
                <el-switch
                  v-if="row.status === 'SUCCESS'"
                  :model-value="row.is_enabled"
                  size="small"
                  :loading="togglingId === row.id"
                  @change="(v: boolean) => toggleDoc(row, v)"
                />
                <el-button
                  v-if="row.status === 'FAILED' && isTeacher"
                  link
                  type="warning"
                  size="small"
                  :icon="RefreshRight"
                  :loading="retryingId === row.id"
                  @click.stop="retryDoc(row)"
                >
                  重试
                </el-button>
                <el-button link type="primary" size="small" :icon="View" @click.stop="openDetail(row)">
                  详情
                </el-button>
                <el-button link type="primary" size="small" :icon="MagicStick" @click="goAsk(row)">
                  去提问
                </el-button>
                <el-popconfirm title="删除后该文档将不再参与问答检索，确定？" width="220" @confirm="removeDoc(row)">
                  <template #reference>
                    <el-button link type="danger" size="small" :icon="Delete" />
                  </template>
                </el-popconfirm>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <!-- 上传 + 索引向导 -->
    <el-dialog v-model="indexVisible" title="添加知识库文档" width="620px" :close-on-click-modal="false" :close-on-press-escape="false" destroy-on-close>
      <el-steps :active="0" align-center finish-status="success" class="kb-steps">
        <el-step title="上传文件" description="后台分片上传" />
        <el-step title="索引设置" description="分块策略与标题" />
      </el-steps>

      <div class="step-body">
        <el-alert type="success" :closable="false" class="file-ok">
          <template #title>文件已上传：{{ uploadedFile?.file_name }}（file_record_id: {{ uploadedFile?.file_record_id }}）</template>
        </el-alert>
        <el-form label-position="top" size="large">
          <el-form-item label="文档标题">
            <el-input v-model="indexForm.title" maxlength="80" show-word-limit />
          </el-form-item>
          <el-form-item label="分块策略">
            <el-radio-group v-model="indexForm.splitter_type">
              <el-radio value="markdown">Markdown 结构分块</el-radio>
              <el-radio value="recursive">递归字符分块</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item :label="`分块大小：${indexForm.chunk_size} 字符`">
            <el-slider v-model="indexForm.chunk_size" :min="256" :max="1536" :step="64" show-input />
          </el-form-item>
        </el-form>
      </div>

      <template #footer>
        <el-button @click="indexVisible = false">取 消</el-button>
        <el-button type="primary" class="btn-primary" :loading="indexing" @click="doIndex">开始索引</el-button>
      </template>
    </el-dialog>

    <!-- 隐藏的文件选择框（知识库上传，单选） -->
    <input ref="fileInput" type="file" hidden @change="onFilePicked" />

    <!-- 文档详情抽屉（Markdown / 原始文档 / 分块） -->
    <KnowledgeDocDetailDrawer v-model="detailVisible" :doc="currentDoc" :can-manage="isTeacher" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Upload, Delete, MagicStick, Collection, Loading, View, Search, RefreshRight } from '@element-plus/icons-vue'
import { kbApi } from '@/api'
import { useAuthStore } from '@/stores/auth'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useCourseStore } from '@/stores/course'
import { useUploadTaskStore } from '@/stores/uploadTask'
import { useKnowledgeDocs, statusText, statusTagType } from '@/composables/useKnowledgeDocs'
import { DocumentStatus, type KnowledgeDocItem } from '@/api/types'
import { formatDateTime, formatSize } from '@/utils/format'
import CourseSelector from '@/components/CourseSelector.vue'
import FileIcon from '@/components/FileIcon.vue'
import KnowledgeDocDetailDrawer from '@/components/course/KnowledgeDocDetailDrawer.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const knowledgeStore = useKnowledgeStore()
const courseStore = useCourseStore()
const uploadStore = useUploadTaskStore()

const selectedCourseId = ref<number | null>(
  route.query.courseId ? Number(route.query.courseId) : knowledgeStore.selectedCourseId,
)

/** 是否可管理当前课程的知识库（该课程教师或全局管理员）；学生仅可查看 */
const isTeacher = computed(() => {
  if (auth.isAdmin) return true
  if (!auth.isTeacher || selectedCourseId.value == null) return false
  // 从课程列表中找到当前课程，判断是否本人创建
  const course = courseStore.allCourses.find((c) => c.id === selectedCourseId.value)
  return course?.teacher_id === auth.user?.id
})

const fileInput = ref<HTMLInputElement>()

// 索引设置对话框状态
const indexVisible = ref(false)
const uploadedFile = ref<{ file_record_id: number; file_name: string } | null>(null)
const indexForm = reactive({ title: '', splitter_type: 'markdown', chunk_size: 1024 })

watch(selectedCourseId, (val) => {
  knowledgeStore.setCourseId(val)
  load()
})

const { docs, loading, apiMissing, togglingId, polling, indexing, load, indexDoc, toggleDoc, removeDoc } =
  useKnowledgeDocs(() => selectedCourseId.value)

// ---- 搜索 + 状态筛选 ----
const keyword = ref('')
const statusFilter = ref<'all' | 'ready' | 'processing' | 'failed' | 'disabled'>('all')
const retryingId = ref<number | null>(null)

/** 统计概览（基于文档列表实时计算） */
const stats = computed(() => {
  const total = docs.value.length
  const ready = docs.value.filter((d) => d.status === DocumentStatus.SUCCESS && d.is_enabled).length
  const processing = docs.value.filter((d) =>
    [DocumentStatus.PENDING, DocumentStatus.PARSING, DocumentStatus.CHUNKING, DocumentStatus.INDEXING].includes(d.status),
  ).length
  const failed = docs.value.filter((d) => d.status === DocumentStatus.FAILED).length
  const totalChunks = docs.value.reduce((sum, d) => sum + (d.chunk_count || 0), 0)
  const totalChars = docs.value.reduce((sum, d) => sum + (d.markdown_char_count || 0), 0)
  return { total, ready, processing, failed, totalChunks, totalChars }
})

/** 筛选后的文档列表 */
const filteredDocs = computed(() => {
  let list = docs.value
  const kw = keyword.value.trim().toLowerCase()
  if (kw) list = list.filter((d) => d.title.toLowerCase().includes(kw))
  switch (statusFilter.value) {
    case 'ready':
      list = list.filter((d) => d.status === DocumentStatus.SUCCESS && d.is_enabled)
      break
    case 'processing':
      list = list.filter((d) =>
        [DocumentStatus.PENDING, DocumentStatus.PARSING, DocumentStatus.CHUNKING, DocumentStatus.INDEXING].includes(d.status),
      )
      break
    case 'failed':
      list = list.filter((d) => d.status === DocumentStatus.FAILED)
      break
    case 'disabled':
      list = list.filter((d) => !d.is_enabled)
      break
  }
  return list
})

/** 失败文档重新索引 */
async function retryDoc(d: KnowledgeDocItem) {
  retryingId.value = d.id
  try {
    await kbApi.retryDoc(d.id)
    ElMessage.success(`「${d.title}」已重新提交解析`)
    await load()
  } catch (e: any) {
    ElMessage.error(e?.message || '重试失败')
  } finally {
    retryingId.value = null
  }
}

onMounted(() => {
  // 课程数据由 CourseSelector 统一刷新（子组件 onMounted 先于父组件执行）
  if (selectedCourseId.value != null) load()
})

/** 触发文件选择（知识库上传，单选，入队后台） */
function triggerPick() {
  fileInput.value?.click()
}

function onFilePicked(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  ;(e.target as HTMLInputElement).value = ''
  if (!f || selectedCourseId.value == null) return
  uploadStore.enqueue({ file: f, source: 'kb_doc', courseId: selectedCourseId.value })
  ElMessage.success(`「${f.name}」已进入后台上传队列，上传完成后会自动进入索引设置`)
}

/**
 * 监听本课程知识库文件上传完成，自动打开索引设置。
 *
 * `immediate: true`：上传在后台跑，用户可能中途离开本页；离开期间完成的上传
 * 若不在挂载时补一次检查，就永远不会弹出索引设置（文件传上去了却没进知识库）。
 * 每次进入本页都会先把「已完成但还没索引」的上传补上。
 */
watch(
  () => uploadStore.tasks.map((t) => ({ id: t.id, status: t.status, source: t.source, courseId: t.courseId, fileRecordId: t.fileRecordId, fileName: t.fileName })),
  () => {
    if (selectedCourseId.value == null) return
    for (const t of uploadStore.tasks) {
      if (t.source !== 'kb_doc' || t.courseId !== selectedCourseId.value) continue
      if (t.status !== 'completed' || t.fileRecordId == null) continue
      // 打开索引设置
      uploadedFile.value = { file_record_id: t.fileRecordId, file_name: t.fileName }
      indexForm.title = t.fileName.replace(/\.[^.]+$/, '')
      uploadStore.remove(t.id)
      indexVisible.value = true
      break
    }
  },
  { deep: true, immediate: true },
)

async function doIndex() {
  if (!uploadedFile.value) return
  try {
    await indexDoc({
      title: indexForm.title,
      fileRecordId: uploadedFile.value.file_record_id,
      fileName: uploadedFile.value.file_name,
      splitterType: indexForm.splitter_type,
      chunkSize: indexForm.chunk_size,
    })
    indexVisible.value = false
    uploadedFile.value = null
  } catch (e: any) {
    ElMessage.error(e?.message || '索引构建失败')
  }
}

function goAsk(d: { title: string }) {
  router.push({ name: 'qa', query: { courseId: selectedCourseId.value!, topic: d.title } })
}

// ---- 文档详情抽屉 ----
const detailVisible = ref(false)
const currentDoc = ref<KnowledgeDocItem | null>(null)

function openDetail(d: KnowledgeDocItem) {
  currentDoc.value = d
  detailVisible.value = true
}

function isProcessing(status: DocumentStatus | string): boolean {
  return [
    DocumentStatus.PENDING,
    DocumentStatus.PARSING,
    DocumentStatus.CHUNKING,
    DocumentStatus.INDEXING,
  ].includes(status as DocumentStatus)
}
</script>

<style scoped>
.header-actions {
  display: flex;
  align-items: center;
}
.empty-card {
  padding: 48px 0;
}
.kb-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.kb-stat-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  text-align: center;
}
.kb-stat-value {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--text-main);
}
.kb-stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.info-count {
  font-size: 13px;
  color: var(--text-secondary);
}
.info-count b {
  color: var(--brand);
  font-size: 15px;
}
.polling-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  color: var(--orange);
}
.status-tag-inner {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.toolbar-right {
  display: flex;
  gap: 10px;
}
.doc-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.doc-main {
  min-width: 0;
}
.doc-title {
  font-weight: 600;
  font-size: 13.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-error {
  margin: 2px 0 0;
  font-size: 12px;
  color: var(--red);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-ops {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: flex-end;
}
.doc-table :deep(.el-table__row) {
  cursor: pointer;
}
.dim-text {
  font-size: 12.5px;
  color: var(--text-secondary);
}
.kb-steps {
  margin-bottom: 24px;
}
.step-body {
  min-height: 220px;
}
.done-body {
  padding: 12px 0;
}
.file-ok {
  margin-bottom: 18px;
  border-radius: var(--radius-md);
}
.missing-box {
  text-align: center;
  padding: 44px 30px;
}
.missing-box h3 {
  margin: 12px 0 10px;
}
.missing-box p {
  color: var(--text-regular);
  line-height: 1.8;
}
</style>
