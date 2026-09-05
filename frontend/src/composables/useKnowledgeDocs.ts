/**
 * 知识库文档逻辑（可复用组合式函数）
 * 统一处理：文档列表加载、状态轮询、启停、删除、索引构建。
 * 上传部分已改为全局上传任务中心（uploadTask store），
 * 上传完成后由调用方调用 indexDoc() 发起索引。
 */
import { onUnmounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { kbApi } from '@/api'
import type { KnowledgeDocItem } from '@/api/types'
import { DocumentStatus } from '@/api/types'

/** 处理中的状态集合 */
const PROCESSING = [DocumentStatus.PENDING, DocumentStatus.PARSING, DocumentStatus.CHUNKING, DocumentStatus.INDEXING]
/** 轮询间隔（毫秒） */
const POLL_INTERVAL = 2500

export function statusText(s: DocumentStatus | string) {
  const map: Record<string, string> = {
    PENDING: '排队中',
    PARSING: '解析中',
    CHUNKING: '分块中',
    INDEXING: '向量化中',
    SUCCESS: '已就绪',
    FAILED: '失败',
  }
  return map[s] || s
}

export function statusTagType(s: DocumentStatus | string) {
  if (s === 'SUCCESS') return 'success'
  if (s === 'FAILED') return 'danger'
  if (s === 'PENDING') return 'info'
  return 'warning'
}

export function useKnowledgeDocs(getCourseId: () => number | null) {
  const docs = ref<KnowledgeDocItem[]>([])
  const loading = ref(false)
  const apiMissing = ref(false)
  const togglingId = ref<number | null>(null)
  const polling = ref(false)
  const indexing = ref(false)
  let pollTimer: ReturnType<typeof setTimeout> | null = null

  async function load() {
    const courseId = getCourseId()
    if (courseId == null) {
      docs.value = []
      stopPolling()
      return
    }
    loading.value = true
    try {
      docs.value = await kbApi.listDocs(courseId)
      apiMissing.value = false
      startPolling()
    } catch (e: any) {
      if (e?.status === 404 || e?.status === 405) apiMissing.value = true
      else ElMessage.error(e?.message || '加载知识库失败')
    } finally {
      loading.value = false
    }
  }

  function startPolling() {
    stopPolling()
    if (!docs.value.some((d) => PROCESSING.includes(d.status))) return
    polling.value = true
    pollTimer = setInterval(pollOnce, POLL_INTERVAL)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    polling.value = false
  }

  async function pollOnce() {
    const processing = docs.value.filter((d) => PROCESSING.includes(d.status))
    if (processing.length === 0) {
      stopPolling()
      return
    }
    await Promise.all(
      processing.map(async (d) => {
        try {
          const fresh = await kbApi.docDetail(d.id)
          Object.assign(d, fresh)
        } catch {
          /* 单文档轮询失败忽略 */
        }
      }),
    )
    if (!docs.value.some((d) => PROCESSING.includes(d.status))) {
      stopPolling()
    }
  }

  onUnmounted(stopPolling)

  /** 发起索引：title 文档标题、fileRecordId 已上传文件、splitter 分块策略 */
  async function indexDoc(opts: {
    title: string
    fileRecordId: number
    fileName: string
    splitterType: string
    chunkSize: number
  }): Promise<KnowledgeDocItem> {
    const courseId = getCourseId()
    if (courseId == null) throw new Error('未选择课程')
    indexing.value = true
    try {
      const doc = await kbApi.indexCourseFile({
        title: opts.title || opts.fileName,
        file_record_id: opts.fileRecordId,
        course_id: courseId,
        scope: 'course',
        splitter_type: opts.splitterType,
        chunk_size: opts.chunkSize,
      })
      const item: KnowledgeDocItem = {
        ...doc,
        markdown_char_count: null,
        error_msg: null,
        is_enabled: true,
        created_by: 0,
        status: DocumentStatus.PARSING,
      }
      docs.value.unshift(item)
      startPolling()
      ElMessage.success('知识库索引构建成功')
      return item
    } finally {
      indexing.value = false
    }
  }

  async function toggleDoc(d: KnowledgeDocItem, v: boolean) {
    togglingId.value = d.id
    try {
      await kbApi.toggleDoc(d.id, v)
      d.is_enabled = v
      ElMessage.success(v ? '已启用检索' : '已停用检索')
    } catch (e: any) {
      if (e?.status === 404 || e?.status === 405) {
        ElMessage.warning('文档启停接口尚未提供（PATCH /api/v1/kb/doc/{id}），待后端补充')
      } else {
        ElMessage.error(e?.message || '操作失败')
      }
    } finally {
      togglingId.value = null
    }
  }

  async function removeDoc(d: KnowledgeDocItem) {
    try {
      await kbApi.removeDoc(d.id)
      docs.value = docs.value.filter((x) => x.id !== d.id)
      ElMessage.success('已删除')
    } catch (e: any) {
      if (e?.status === 404 || e?.status === 405) {
        ElMessage.warning('删除知识库文档接口尚未提供（DELETE /api/v1/kb/doc/{id}），待后端补充')
      } else {
        ElMessage.error(e?.message || '删除失败')
      }
    }
  }

  return {
    docs,
    loading,
    apiMissing,
    togglingId,
    polling,
    indexing,
    load,
    indexDoc,
    toggleDoc,
    removeDoc,
  }
}
