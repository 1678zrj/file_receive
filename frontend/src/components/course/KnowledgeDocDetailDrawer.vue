<template>
  <el-drawer v-model="visible" :title="null" size="720px" destroy-on-close>
    <template v-if="doc">
      <!-- 头部 -->
      <div class="drawer-header">
        <h2 class="dh-title">{{ doc.title }}</h2>
        <div class="dh-meta">
          <el-tag :type="statusTagType(doc.status)" size="small" effect="light">{{ statusText(doc.status) }}</el-tag>
          <span class="dh-item">{{ doc.chunk_count }} 个分块</span>
          <span v-if="doc.markdown_char_count" class="dh-item">{{ formatSize(doc.markdown_char_count) }} 字符</span>
          <span class="dh-item">{{ formatDateTime(doc.updated_at || doc.created_at) }}</span>
        </div>
        <p v-if="doc.status === 'FAILED' && doc.error_msg" class="dh-error">{{ doc.error_msg }}</p>
      </div>

      <!-- Tab：解析内容 / 原始文档 / 分块 -->
      <el-tabs v-model="activeTab" class="detail-tabs">
        <!-- Markdown 解析内容 -->
        <el-tab-pane label="解析内容" name="markdown">
          <div v-if="canManage && !mdError" class="md-toolbar">
            <template v-if="!editing">
              <el-button size="small" :icon="Edit" @click="startEdit">编辑</el-button>
            </template>
            <template v-else>
              <el-button size="small" type="primary" class="btn-primary" :loading="saving" @click="saveMarkdown">保存</el-button>
              <el-button size="small" @click="cancelEdit">取消</el-button>
            </template>
          </div>
          <div v-loading="mdLoading" class="md-pane">
            <div v-if="mdError" class="pane-empty">
              <el-empty :description="mdError" :image-size="80" />
            </div>
            <el-input
              v-else-if="editing"
              v-model="markdownText"
              type="textarea"
              :rows="18"
              class="md-editor"
              placeholder="编辑 Markdown 内容..."
            />
            <div v-else class="md-body md-render" v-html="renderedMarkdown"></div>
          </div>
        </el-tab-pane>

        <!-- 原始文档 -->
        <el-tab-pane label="原始文档" name="source">
          <div class="source-pane">
            <div class="source-info">
              <FileIcon :file-name="doc.title" :size="32" />
              <span class="source-fname">file_record_id: {{ doc.file_record_id }}</span>
            </div>
            <div class="source-actions">
              <el-button type="primary" class="btn-primary" :icon="View" @click="previewSource">预览原始文档</el-button>
              <el-button :icon="Download" @click="downloadSource">下载</el-button>
            </div>
            <p class="source-tip">原始文档预览/下载接口待后端提供（GET /api/v1/file/preview/{file_record_id}），补齐后即可使用。</p>
          </div>
        </el-tab-pane>

        <!-- 分块列表 -->
        <el-tab-pane :label="`分块（${chunks.length}）`" name="chunks">
          <div v-loading="chunkLoading" class="chunks-pane">
            <el-empty v-if="!chunkLoading && chunks.length === 0" description="暂无分块数据" :image-size="80" />
            <div v-else class="chunk-list">
              <div v-for="c in chunks" :key="c.id" class="chunk-item" :class="{ 'is-disabled': !c.is_enabled }">
                <div class="chunk-head">
                  <span class="chunk-index">#{{ c.chunk_index + 1 }}</span>
                  <span class="chunk-meta">{{ c.token_count }} tokens</span>
                  <el-switch
                    v-if="canManage"
                    :model-value="c.is_enabled"
                    size="small"
                    :loading="chunkTogglingId === c.id"
                    @change="(v: boolean) => toggleChunk(c, v)"
                  />
                  <el-tag v-else :type="c.is_enabled ? 'success' : 'info'" size="small" effect="plain">
                    {{ c.is_enabled ? '启用' : '停用' }}
                  </el-tag>
                </div>
                <div class="chunk-text">{{ c.chunk_text }}</div>
              </div>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- 原始文档预览 -->
    <FilePreviewDialog v-model="previewVisible" :file-record-id="doc?.file_record_id ?? null" :file-name="doc?.title ?? ''" />
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { View, Download, Edit } from '@element-plus/icons-vue'
import { kbApi, resourceApi } from '@/api'
import type { KnowledgeDocChunkItem, KnowledgeDocItem } from '@/api/types'
import { statusText, statusTagType } from '@/composables/useKnowledgeDocs'
import { formatDateTime, formatSize } from '@/utils/format'
import FileIcon from '@/components/FileIcon.vue'
import FilePreviewDialog from '@/components/FilePreviewDialog.vue'

const props = defineProps<{
  modelValue: boolean
  doc: KnowledgeDocItem | null
  /** 是否可管理（教师/管理员），控制 Markdown 编辑与分块启停 */
  canManage?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean] }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const activeTab = ref('markdown')
const mdLoading = ref(false)
const mdError = ref('')
const markdownText = ref('')
const chunkLoading = ref(false)
const chunks = ref<KnowledgeDocChunkItem[]>([])
const previewVisible = ref(false)
const editing = ref(false)
const saving = ref(false)
const chunkTogglingId = ref<number | null>(null)

const md = new MarkdownIt({
  html: false,
  linkify: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(code, { language: lang }).value}</code></pre>`
      } catch {
        /* noop */
      }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(code)}</code></pre>`
  },
})

const renderedMarkdown = computed(() => md.render(markdownText.value))

watch(visible, (v) => {
  if (!v) return
  activeTab.value = 'markdown'
  loadMarkdown()
  loadChunks()
})

async function loadMarkdown() {
  if (!props.doc) return
  mdLoading.value = true
  mdError.value = ''
  try {
    markdownText.value = await kbApi.getMarkdown(props.doc.id)
  } catch (e: any) {
    if (e?.status === 404 || e?.status === 405) {
      mdError.value = '解析内容接口尚未提供（GET /api/v1/kb/doc/{id}/markdown），待后端补充'
    } else {
      mdError.value = e?.message || '加载解析内容失败'
    }
  } finally {
    mdLoading.value = false
  }
}

async function loadChunks() {
  if (!props.doc) return
  chunkLoading.value = true
  try {
    chunks.value = await kbApi.getChunks(props.doc.id)
  } catch (e: any) {
    chunks.value = []
    if (!(e?.status === 404 || e?.status === 405)) {
      ElMessage.error(e?.message || '加载分块失败')
    }
  } finally {
    chunkLoading.value = false
  }
}

// ---- Markdown 编辑 ----
function startEdit() {
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  loadMarkdown() // 重新加载，放弃本地修改
}

async function saveMarkdown() {
  if (!props.doc) return
  saving.value = true
  try {
    await kbApi.saveMarkdown(props.doc.id, markdownText.value)
    ElMessage.success('Markdown 已保存')
    editing.value = false
    await loadMarkdown()
  } catch (e: any) {
    ElMessage.error(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

// ---- 分块启停 ----
async function toggleChunk(c: KnowledgeDocChunkItem, v: boolean) {
  chunkTogglingId.value = c.id
  try {
    await kbApi.patchChunk(c.id, { is_enabled: v })
    c.is_enabled = v
    ElMessage.success(v ? '分块已启用' : '分块已停用')
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  } finally {
    chunkTogglingId.value = null
  }
}

function previewSource() {
  if (!props.doc) return
  previewVisible.value = true
}

async function downloadSource() {
  if (!props.doc) return
  try {
    const blob = await resourceApi.fetchBlob(props.doc.file_record_id, 'download')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = props.doc.title
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
</script>

<style scoped>
.drawer-header {
  margin-bottom: 16px;
}
.dh-title {
  margin: 0 0 10px;
  font-size: 19px;
  font-weight: 700;
}
.dh-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}
.dh-item {
  font-size: 12.5px;
  color: var(--text-secondary);
}
.dh-error {
  margin: 10px 0 0;
  font-size: 12.5px;
  color: var(--red);
  background: var(--red-light);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
}
.detail-tabs :deep(.el-tabs__item) {
  font-size: 14px;
}

/* Markdown 解析内容 */
.md-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 8px;
}
.md-pane {
  min-height: 300px;
  max-height: 62vh;
  overflow: auto;
  padding: 4px 2px;
}
.md-editor :deep(.el-textarea__inner) {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 13px;
  line-height: 1.7;
}
.md-render {
  font-size: 14px;
}
.pane-empty {
  padding: 40px 0;
}

/* 原始文档 */
.source-pane {
  min-height: 200px;
  padding: 12px 2px;
}
.source-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: var(--bg-soft);
  border-radius: var(--radius-md);
  margin-bottom: 16px;
}
.source-fname {
  font-size: 13px;
  color: var(--text-regular);
}
.source-actions {
  display: flex;
  gap: 10px;
}
.source-tip {
  margin-top: 16px;
  font-size: 12.5px;
  color: var(--text-secondary);
}

/* 分块列表 */
.chunks-pane {
  max-height: 62vh;
  overflow: auto;
}
.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.chunk-item {
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
}
.chunk-item.is-disabled {
  opacity: 0.65;
  background: var(--bg-soft);
}
.chunk-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.chunk-index {
  font-weight: 700;
  color: var(--brand);
  font-size: 13px;
}
.chunk-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-right: auto;
}
.chunk-text {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-regular);
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-soft);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
}
</style>
