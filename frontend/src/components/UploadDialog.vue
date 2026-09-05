<template>
  <el-dialog
    v-model="visible"
    :title="title"
    width="560px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="!uploading"
    @closed="onClosed"
  >
    <!-- 选择文件区 -->
    <div v-if="!file" class="upload-dropzone" :class="{ 'is-dragover': dragover }"
      @dragover.prevent="dragover = true"
      @dragleave="dragover = false"
      @drop.prevent="onDrop"
      @click="pickFile"
    >
      <el-icon :size="44" color="#2d6cdf"><UploadFilled /></el-icon>
      <p class="dz-text">点击选择文件，或拖拽到此处</p>
      <p class="dz-hint">支持大文件分片上传 · 断点续传 · 秒传</p>
    </div>

    <!-- 已选文件 + 进度 -->
    <div v-else class="upload-body">
      <div class="file-row">
        <FileIcon :file-name="file.name" :size="44" />
        <div class="file-meta">
          <div class="file-name" :title="file.name">{{ file.name }}</div>
          <div class="file-sub">{{ formatSize(file.size) }}<span v-if="progress.instant" class="instant-tag">· 秒传</span></div>
        </div>
        <el-button v-if="!uploading && progress.phase !== 'completed'" text type="danger" @click="reset">移除</el-button>
      </div>

      <div v-if="uploading || progress.phase === 'completed'" class="progress-area">
        <el-progress
          :percentage="progress.percent"
          :status="progress.phase === 'completed' ? 'success' : undefined"
          :stroke-width="10"
          striped
          :striped-flow="progress.phase !== 'completed'"
        />
        <div class="phase-text">{{ phaseText }}</div>
        <div v-if="progress.phase === 'uploading'" class="speed-line">
          <span>{{ formatSize(progress.uploadedBytes ?? 0) }} / {{ formatSize(progress.totalBytes ?? 0) }}</span>
          <span v-if="speedText">· {{ speedText }}</span>
        </div>
      </div>
    </div>

    <template #footer>
      <el-button :disabled="uploading" @click="visible = false">取 消</el-button>
      <el-button
        type="primary"
        class="btn-primary"
        :loading="uploading"
        :disabled="!file"
        @click="startUpload"
      >
        {{ progress.phase === 'completed' ? '完成' : '开始上传' }}
      </el-button>
    </template>

    <input ref="fileInput" type="file" hidden @change="onPick" />
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import FileIcon from './FileIcon.vue'
import { formatSize } from '@/utils/format'
import { uploadFile, type UploadProgress } from '@/utils/uploader'

const props = withDefaults(defineProps<{ modelValue: boolean; title?: string }>(), {
  title: '上传文件',
})
const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  success: [payload: { file_record_id: number; file_name: string; instant: boolean }]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const file = ref<File | null>(null)
const uploading = ref(false)
const dragover = ref(false)
const fileInput = ref<HTMLInputElement>()
const progress = ref<UploadProgress>({ phase: 'hashing', uploaded: 0, total: 0, percent: 0 })

const phaseText = computed(() => {
  const p = progress.value
  switch (p.phase) {
    case 'hashing':
      return '正在计算文件指纹 (SHA-256)...'
    case 'init':
      return '正在初始化上传会话...'
    case 'uploading':
      return `分片上传中 ${p.uploaded}/${p.total}`
    case 'merging':
      return '服务器正在合并文件...'
    case 'completed':
      return p.instant ? '命中秒传，无需传输' : '上传完成'
    case 'failed':
      return p.error || '上传失败'
    default:
      return ''
  }
})

watch(visible, (v) => {
  if (!v) return
  reset()
})

function pickFile() {
  fileInput.value?.click()
}
function onPick(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0]
  if (f) file.value = f
  ;(e.target as HTMLInputElement).value = ''
}
function onDrop(e: DragEvent) {
  dragover.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) file.value = f
}
function reset() {
  file.value = null
  uploading.value = false
  speedText.value = ''
  progress.value = { phase: 'hashing', uploaded: 0, total: 0, percent: 0 }
}

// 实时速度估算
const speedText = ref('')
let lastBytes = 0
let lastTime = 0

async function startUpload() {
  if (!file.value) return
  if (progress.value.phase === 'completed') {
    visible.value = false
    return
  }
  uploading.value = true
  lastBytes = 0
  lastTime = Date.now()
  try {
    const result = await uploadFile(file.value, (p) => {
      progress.value = p
      // 估算实时速度
      if (p.phase === 'uploading' && p.uploadedBytes != null) {
        const now = Date.now()
        const dt = (now - lastTime) / 1000
        if (dt > 0.5) {
          const speed = (p.uploadedBytes - lastBytes) / dt
          speedText.value = `${formatSize(speed)}/s`
          lastBytes = p.uploadedBytes
          lastTime = now
        }
      }
    })
    ElMessage.success(result.instant ? '秒传成功' : '文件上传成功')
    emit('success', {
      file_record_id: result.file_record_id,
      file_name: file.value.name,
      instant: result.instant,
    })
    uploading.value = false
    visible.value = false
  } catch (e: any) {
    uploading.value = false
    progress.value = { ...progress.value, phase: 'failed', error: e?.message || '上传失败' }
    ElMessage.error(e?.message || '上传失败，请重试')
  }
}

function onClosed() {
  reset()
}
</script>

<style scoped>
.upload-dropzone {
  border: 2px dashed #c9cdf0;
  border-radius: var(--radius-md);
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: var(--bg-soft);
}
.upload-dropzone:hover,
.upload-dropzone.is-dragover {
  border-color: var(--brand);
  background: var(--brand-light);
}
.dz-text {
  margin: 12px 0 4px;
  font-weight: 600;
  color: var(--text-main);
}
.dz-hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
}
.file-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.file-meta {
  flex: 1;
  min-width: 0;
}
.file-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-sub {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.instant-tag {
  margin-left: 8px;
  color: var(--orange);
  font-weight: 600;
}
.progress-area {
  margin-top: 16px;
}
.phase-text {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
}
.speed-line {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-faint);
  text-align: center;
}
</style>
