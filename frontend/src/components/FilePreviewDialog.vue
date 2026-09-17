<template>
  <el-dialog
    v-model="visible"
    :title="fileName"
    width="80%"
    top="5vh"
    destroy-on-close
    class="preview-dialog"
  >
    <div v-loading="loading" class="preview-body">
      <template v-if="!loading">
        <!-- 加载失败 / 后端未提供接口 -->
        <el-result v-if="error" icon="warning" :title="errorTitle" :sub-title="error">
          <template #extra>
            <el-button type="primary" class="btn-primary" @click="retry">重 试</el-button>
          </template>
        </el-result>

        <!-- 图片 -->
        <div v-else-if="kind === 'image'" class="center-box">
          <img :src="blobUrl" class="preview-img" :alt="fileName" />
        </div>

        <!-- PDF -->
        <iframe v-else-if="kind === 'pdf'" :src="blobUrl" class="preview-frame" title="PDF 预览" />

        <!-- 视频 -->
        <div v-else-if="kind === 'video'" class="center-box">
          <video :src="blobUrl" controls class="preview-video">您的浏览器不支持视频播放</video>
        </div>

        <!-- 音频 -->
        <div v-else-if="kind === 'audio'" class="center-box">
          <audio :src="blobUrl" controls style="width: 100%">您的浏览器不支持音频播放</audio>
        </div>

        <!-- 文本 / Markdown / 代码 -->
        <div v-else-if="kind === 'text' || kind === 'markdown' || kind === 'code'" class="text-preview">
          <div v-if="kind === 'markdown'" class="md-body" v-html="renderedMarkdown"></div>
          <pre v-else class="code-pre"><code v-html="highlightedCode"></code></pre>
        </div>

        <!-- 不支持预览 -->
        <el-result v-else icon="document" title="该文件类型暂不支持在线预览">
          <template #sub-title>
            <p>你可以尝试下载后查看</p>
          </template>
          <template #extra>
            <el-button type="primary" class="btn-primary" @click="download">下 载</el-button>
          </template>
        </el-result>
      </template>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import hljs from 'highlight.js'
import { resourceApi } from '@/api'
import { fileCategory } from '@/utils/format'
import { escapeHtml, renderMarkdown } from '@/utils/markdown'

const props = defineProps<{
  modelValue: boolean
  fileRecordId: number | null
  fileName: string
}>()
const emit = defineEmits<{ 'update:modelValue': [v: boolean] }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const loading = ref(false)
const error = ref('')
const errorTitle = ref('加载失败')
const blobUrl = ref('')
const textContent = ref('')

const kind = computed(() => fileCategory(props.fileName || ''))
const codeLang = computed(() => (props.fileName.split('.').pop() || '').toLowerCase())

const renderedMarkdown = computed(() => renderMarkdown(textContent.value, { breaks: false }))
const highlightedCode = computed(() => {
  if (hljs.getLanguage(codeLang.value)) {
    try {
      return hljs.highlight(textContent.value, { language: codeLang.value }).value
    } catch {
      /* noop */
    }
  }
  return escapeHtml(textContent.value)
})

watch(visible, (v) => {
  if (v && props.fileRecordId != null) load()
})
onBeforeUnmount(() => {
  if (blobUrl.value) URL.revokeObjectURL(blobUrl.value)
})

async function load() {
  if (props.fileRecordId == null) return
  loading.value = true
  error.value = ''
  try {
    const blob = await resourceApi.fetchBlob(props.fileRecordId, 'preview')
    if (kind.value === 'text' || kind.value === 'markdown' || kind.value === 'code') {
      textContent.value = await blob.text()
    } else {
      blobUrl.value = URL.createObjectURL(blob)
    }
  } catch (e: any) {
    if (e?.status === 404 || e?.status === 405) {
      errorTitle.value = '预览接口尚未提供'
      error.value =
        '后端暂未提供文件预览/下载接口（建议：GET /api/v1/file/preview/{file_record_id} 以 inline 方式返回文件流），待补充后即可使用。'
    } else {
      errorTitle.value = '加载失败'
      error.value = e?.message || '文件加载失败'
    }
  } finally {
    loading.value = false
  }
}

function retry() {
  load()
}

async function download() {
  if (props.fileRecordId == null) return
  try {
    const blob = await resourceApi.fetchBlob(props.fileRecordId, 'download')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = props.fileName
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    errorTitle.value = '下载接口尚未提供'
    error.value =
      '后端暂未提供文件下载接口（建议：GET /api/v1/file/download/{file_record_id} 以 attachment 方式返回文件流），待补充后即可使用。'
  }
}
</script>

<style scoped>
.preview-body {
  min-height: 40vh;
}
.center-box {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
}
.preview-img {
  max-width: 100%;
  max-height: 70vh;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}
.preview-frame {
  width: 100%;
  height: 72vh;
  border: none;
  border-radius: var(--radius-md);
  background: #525659;
}
.preview-video {
  max-width: 100%;
  max-height: 70vh;
  border-radius: var(--radius-md);
  background: #000;
}
.text-preview {
  max-height: 68vh;
  overflow: auto;
  border-radius: var(--radius-md);
  background: var(--bg-soft);
  padding: 16px;
}
.code-pre {
  margin: 0;
  background: #282c34;
  color: #dcdfe4;
  padding: 16px;
  border-radius: var(--radius-md);
  font-size: 13px;
  line-height: 1.7;
  font-family: 'JetBrains Mono', Consolas, monospace;
  overflow-x: auto;
}
</style>
