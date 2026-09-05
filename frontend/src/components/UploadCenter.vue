<template>
  <div class="upload-center">
    <!-- 折叠态：悬浮触发按钮 -->
    <div class="uc-fab" @click="store.toggle()">
      <el-badge :value="store.activeCount" :hidden="store.activeCount === 0" :max="99">
        <el-icon :size="22" class="uc-icon" :class="{ 'is-working': store.activeCount > 0 }">
          <Loading v-if="store.activeCount > 0" class="animate-pulse" />
          <UploadFilled v-else />
        </el-icon>
      </el-badge>
      <span v-if="store.activeCount > 0" class="uc-fab-label">{{ store.overall }}%</span>
    </div>

    <!-- 展开态：任务面板 -->
    <transition name="uc-panel">
      <div v-if="store.expanded" class="uc-panel cc-card">
        <div class="uc-head">
          <span class="uc-title">上传任务</span>
          <div class="uc-head-actions">
            <el-button v-if="hasFinished" text type="primary" size="small" @click="store.clearFinished()">
              清除已完成
            </el-button>
            <el-icon class="uc-close" @click="store.toggle()"><Close /></el-icon>
          </div>
        </div>

        <div class="uc-body">
          <el-empty v-if="store.tasks.length === 0" description="暂无上传任务" :image-size="60" />
          <div v-for="t in store.tasks" :key="t.id" class="uc-task">
            <div class="ut-icon">
              <el-icon v-if="isActive(t)" class="animate-pulse" color="#2d6cdf"><Loading /></el-icon>
              <el-icon v-else-if="t.status === 'completed'" color="#1fa06d"><CircleCheckFilled /></el-icon>
              <el-icon v-else-if="t.status === 'failed'" color="#e5484d"><CircleCloseFilled /></el-icon>
            </div>
            <div class="ut-main">
              <div class="ut-name" :title="t.fileName">{{ t.fileName }}</div>
              <div class="ut-sub">
                <span class="ut-status" :class="`st-${t.status}`">{{ statusText(t) }}</span>
                <span v-if="isActive(t) && t.percent > 0" class="ut-meta">
                  {{ formatSize(t.uploadedBytes) }} / {{ formatSize(t.size) }}
                  <template v-if="t.speed > 0"> · {{ formatSize(t.speed) }}/s</template>
                </span>
                <span v-if="t.instant" class="ut-instant">秒传</span>
              </div>
              <el-progress
                v-if="isActive(t)"
                :percentage="t.percent"
                :stroke-width="5"
                :show-text="false"
                class="ut-progress"
              />
              <div v-if="t.status === 'failed'" class="ut-error">{{ t.error }}</div>
            </div>
            <div class="ut-actions">
              <template v-if="t.status === 'failed' && t.file">
                <el-button text type="primary" size="small" @click="store.retry(t.id)">重试</el-button>
              </template>
              <template v-if="isActive(t)">
                <el-button text type="danger" size="small" @click="store.cancel(t.id)">取消</el-button>
              </template>
              <template v-if="t.status === 'completed' || (t.status === 'failed' && !t.file)">
                <el-button text size="small" @click="store.remove(t.id)">移除</el-button>
              </template>
              <!-- 完成后可执行后续动作（如资源绑定标题） -->
              <slot name="task-extra" :task="t" />
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatSize } from '@/utils/format'
import { useUploadTaskStore, type UploadTask } from '@/stores/uploadTask'

const store = useUploadTaskStore()

const hasFinished = computed(() => store.tasks.some((t) => t.status === 'completed' || t.status === 'failed'))

function isActive(t: UploadTask) {
  return ['pending', 'hashing', 'uploading', 'merging'].includes(t.status)
}

function statusText(t: UploadTask) {
  const map: Record<string, string> = {
    pending: '排队中',
    hashing: '计算指纹',
    uploading: '上传中',
    merging: '合并中',
    completed: '完成',
    failed: '失败',
  }
  return map[t.status] || ''
}
</script>

<style scoped>
.upload-center {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
}
.uc-fab {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 6px 20px rgba(45, 108, 223, 0.4);
  position: relative;
  transition: transform 0.2s;
}
.uc-fab:hover {
  transform: translateY(-2px);
}
.uc-icon.is-working {
  color: #fff;
}
.uc-fab-label {
  position: absolute;
  right: -4px;
  bottom: -6px;
  font-size: 11px;
  font-weight: 700;
  background: #fff;
  color: var(--brand);
  border-radius: 10px;
  padding: 1px 7px;
  box-shadow: var(--shadow-sm);
}
.uc-panel {
  width: 360px;
  max-height: 480px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.uc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.uc-title {
  font-weight: 600;
  font-size: 14px;
}
.uc-head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.uc-close {
  cursor: pointer;
  color: var(--text-secondary);
}
.uc-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.uc-task {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 8px;
  border-radius: var(--radius-sm);
  transition: background 0.2s;
}
.uc-task:hover {
  background: var(--bg-soft);
}
.ut-icon {
  flex-shrink: 0;
  display: flex;
}
.ut-main {
  flex: 1;
  min-width: 0;
}
.ut-name {
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ut-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin-top: 2px;
  flex-wrap: wrap;
}
.ut-status {
  font-weight: 500;
}
.st-uploading, .st-hashing, .st-merging { color: var(--brand); }
.st-completed { color: var(--green); }
.st-failed { color: var(--red); }
.st-pending { color: var(--text-secondary); }
.ut-meta {
  color: var(--text-faint);
}
.ut-instant {
  color: var(--orange);
  font-weight: 600;
}
.ut-progress {
  margin-top: 4px;
}
.ut-error {
  font-size: 11.5px;
  color: var(--red);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ut-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.uc-panel-enter-active,
.uc-panel-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.uc-panel-enter-from,
.uc-panel-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
