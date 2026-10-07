<template>
  <div class="resource-panel">
    <!-- 工具栏 -->
    <div class="panel-toolbar">
      <el-input
        v-model="keyword"
        placeholder="搜索资源标题或文件名"
        :prefix-icon="Search"
        clearable
        style="width: 260px"
      />
      <div class="toolbar-right">
        <span class="count-tip">共 {{ list.length }} 个资源</span>
        <el-button :icon="Refresh" circle size="small" @click="load" title="刷新" />
        <el-button v-if="isTeacher" type="primary" class="btn-primary" :icon="Upload" @click="triggerPick">
          上传资源
        </el-button>
      </div>
    </div>

    <!-- 资源表格（学习通式紧凑表格） -->
    <el-table
      v-loading="loading"
      :data="filtered"
      stripe
      class="resource-table"
      :empty-text="keyword ? '没有匹配的资源' : '暂无课程资源，教师可点击右上角上传'"
    >
      <el-table-column label="资源名称" min-width="300">
        <template #default="{ row }">
          <div class="name-cell">
            <FileIcon :file-name="row.file_name" :size="32" />
            <div class="name-text">
              <div class="name-title" :title="row.title">{{ row.title }}</div>
              <div class="name-file" :title="row.file_name">{{ row.file_name }}</div>
            </div>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <span class="type-label">{{ fileTypeLabel(row.file_name) }}</span>
        </template>
      </el-table-column>

      <el-table-column label="大小" width="110" align="right">
        <template #default="{ row }">
          <span class="size-text">{{ row.total_size != null ? formatSize(row.total_size) : '—' }}</span>
        </template>
      </el-table-column>

      <el-table-column label="上传时间" width="150">
        <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
      </el-table-column>

      <el-table-column label="操作" width="170" align="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" :disabled="!previewable(row.file_name)" @click="preview(row)">
            预览
          </el-button>
          <el-button link type="primary" size="small" @click="download(row)">下载</el-button>
          <el-popconfirm v-if="isTeacher" title="确定删除该资源吗？" width="200" @confirm="remove(row)">
            <template #reference>
              <el-button link type="danger" size="small">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- 预览 -->
    <FilePreviewDialog v-model="previewVisible" :file-record-id="previewFile?.file_record_id ?? null" :file-name="previewFile?.file_name ?? ''" />

    <!-- 隐藏的多文件选择框 -->
    <input ref="fileInput" type="file" multiple hidden @change="onFilesPicked" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Refresh, Upload } from '@element-plus/icons-vue'
import { resourceApi } from '@/api'
import type { CourseResource } from '@/api/types'
import { formatDateTime, formatSize, canPreview, fileTypeLabel } from '@/utils/format'
import { useUploadTaskStore } from '@/stores/uploadTask'
import FileIcon from '@/components/FileIcon.vue'
import FilePreviewDialog from '@/components/FilePreviewDialog.vue'

const props = defineProps<{ courseId: number; isTeacher: boolean }>()

const list = ref<CourseResource[]>([])
const loading = ref(false)
const keyword = ref('')
const previewVisible = ref(false)
const previewFile = ref<CourseResource | null>(null)

const fileInput = ref<HTMLInputElement>()
const uploadStore = useUploadTaskStore()
/** 已处理（自动绑定）过的任务 id，防止重复绑定 */
const handledIds = new Set<string>()

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return list.value
  return list.value.filter(
    (r) => r.title.toLowerCase().includes(k) || r.file_name.toLowerCase().includes(k),
  )
})

onMounted(load)

function triggerPick() {
  fileInput.value?.click()
}

function onFilesPicked(e: Event) {
  const files = Array.from((e.target as HTMLInputElement).files || [])
  ;(e.target as HTMLInputElement).value = ''
  if (files.length === 0) return
  for (const f of files) {
    uploadStore.enqueue({ file: f, source: 'course_resource', courseId: props.courseId })
  }
  ElMessage.success(`已添加 ${files.length} 个文件到上传队列，上传完成后将自动添加到课程资源`)
}

/**
 * 监听本课程资源上传完成，自动用「文件名（去扩展名）」作为标题绑定到课程，
 * 无需弹窗确认，全程后台。
 *
 * `immediate: true` 是必须的：上传是后台任务，老师完全可能在上传完成前就离开本页
 * （上传中心的提示就是「不必停留在上传页」）。若只在任务变化时触发，
 * 回来时既不会补绑（挂载不触发 watcher），那些文件就会「传上去了但没进课程资源」。
 * 加上 immediate 后，每次进入本页都会先把「已完成但未绑定」的任务补绑一次。
 */
watch(
  () =>
    uploadStore.tasks.map((t) => ({
      id: t.id,
      status: t.status,
      source: t.source,
      courseId: t.courseId,
      fileRecordId: t.fileRecordId,
      fileName: t.fileName,
    })),
  async () => {
    // 先收集本次需要处理的完成项（filter 出新数组，避免遍历中 splice）
    const completed = uploadStore.tasks.filter(
      (t) =>
        t.source === 'course_resource' &&
        t.courseId === props.courseId &&
        t.status === 'completed' &&
        t.fileRecordId != null &&
        !handledIds.has(t.id),
    )
    if (completed.length === 0) return
    for (const t of completed) {
      try {
        await resourceApi.create({
          course_id: props.courseId,
          file_record_id: t.fileRecordId!,
          file_name: t.fileName,
          title: t.fileName.replace(/\.[^.]+$/, ''),
        })
        // 绑定成功才移出队列并标记已处理
        handledIds.add(t.id)
        uploadStore.remove(t.id)
        ElMessage.success(`「${t.fileName}」已添加到课程资源`)
      } catch (e: any) {
        /*
         * 文件本身已经上传成功（有 fileRecordId），只是「绑定成课程资源」失败了。
         * 这里**不能**把任务移出队列，否则这个文件就再也没机会被绑定了；
         * 保留它，下次任务变化或重新进入本页时会自动重试。
         * （失败不会自我循环：绑定失败并不改动 uploadStore.tasks，watcher 不会再被触发。）
         */
        ElMessage.error(`「${t.fileName}」添加失败：${e?.message || '未知错误'}（稍后会自动重试）`)
      }
    }
    await load()
  },
  { deep: true, immediate: true },
)

function previewable(name: string) {
  return canPreview(name)
}

function preview(r: CourseResource) {
  previewFile.value = r
  previewVisible.value = true
}

async function load() {
  loading.value = true
  try {
    list.value = await resourceApi.listByCourse(props.courseId)
  } catch (e: any) {
    ElMessage.error(e?.message || '加载课程资源失败')
  } finally {
    loading.value = false
  }
}

async function download(r: CourseResource) {
  try {
    const blob = await resourceApi.fetchBlob(r.file_record_id, 'download')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = r.file_name
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    if (e?.status === 404 || e?.status === 405) {
      ElMessage.warning('下载接口尚未提供（GET /api/v1/file/download/{file_record_id}），待后端补充')
    } else {
      ElMessage.error(e?.message || '下载失败')
    }
  }
}

async function remove(r: CourseResource) {
  try {
    await resourceApi.remove(r.id)
    ElMessage.success('资源已删除')
    list.value = list.value.filter((x) => x.id !== r.id)
  } catch (e: any) {
    if (e?.status === 404 || e?.status === 405) {
      ElMessage.warning('删除资源接口尚未提供（DELETE /api/v1/course-resource/{id}），待后端补充')
    } else {
      ElMessage.error(e?.message || '删除失败')
    }
  }
}
</script>

<style scoped>
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.toolbar-right {
  display: flex;
  gap: 10px;
  align-items: center;
}
.count-tip {
  font-size: 12.5px;
  color: var(--text-secondary);
}
.resource-table :deep(.el-table__cell) {
  padding: 8px 0;
}
.name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.name-text {
  min-width: 0;
}
.name-title {
  font-weight: 600;
  font-size: 13.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.name-file {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.type-label {
  font-size: 12.5px;
  color: var(--text-regular);
}
.size-text {
  font-size: 12.5px;
  color: var(--text-secondary);
}
</style>
