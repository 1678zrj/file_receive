<template>
  <el-dropdown trigger="click" @command="onCommand" @visible-change="onVisible">
    <div class="notif-trigger">
      <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
        <el-icon :size="18" class="bell-icon"><Bell /></el-icon>
      </el-badge>
    </div>
    <template #dropdown>
      <el-dropdown-menu>
        <div class="notif-panel">
          <div class="notif-head">
            <span class="notif-title">消息通知</span>
            <el-button v-if="unreadCount > 0" link type="primary" size="small" @click="markAllRead">
              全部已读
            </el-button>
          </div>
          <div class="notif-body" v-loading="loading">
            <el-empty v-if="!loading && list.length === 0" description="暂无消息" :image-size="60" />
            <div
              v-for="n in list"
              :key="n.id"
              class="notif-item"
              :class="{ unread: !n.read }"
              @click="onClickItem(n)"
            >
              <el-icon class="notif-icon" :size="16" :color="typeColor(n.type)">
                <component :is="typeIcon(n.type)" />
              </el-icon>
              <div class="notif-main">
                <div class="notif-item-title">{{ n.title }}</div>
                <div class="notif-item-content">{{ n.content }}</div>
                <div class="notif-item-time">{{ fromNow(n.created_at) }}</div>
              </div>
              <span v-if="!n.read" class="unread-dot"></span>
            </div>
          </div>
        </div>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { notificationApi } from '@/api'
import type { NotificationItem } from '@/api/types'
import { NotificationType } from '@/api/types'
import { fromNow } from '@/utils/format'

const router = useRouter()
const list = ref<NotificationItem[]>([])
const loading = ref(false)

const unreadCount = computed(() => list.value.filter((n) => !n.read).length)

onMounted(load)

async function load() {
  loading.value = true
  try {
    list.value = await notificationApi.list()
  } catch {
    list.value = []
  } finally {
    loading.value = false
  }
}

function onVisible(visible: boolean) {
  if (visible) load()
}

async function markAllRead() {
  try {
    await notificationApi.markAllRead()
    list.value.forEach((n) => (n.read = true))
  } catch {
    /* 静默 */
  }
}

async function onClickItem(n: NotificationItem) {
  if (!n.read) {
    try {
      await notificationApi.markRead(n.id)
      n.read = true
    } catch {
      /* 静默 */
    }
  }
  if (n.course_id) {
    router.push({ name: 'course-detail', params: { id: n.course_id } })
  }
}

function onCommand() {
  /* 保留 */
}

function typeIcon(type: NotificationType) {
  const map: Record<string, string> = {
    [NotificationType.ANNOUNCEMENT]: 'Bell',
    [NotificationType.GRADED]: 'DataAnalysis',
    [NotificationType.DEADLINE]: 'Clock',
    [NotificationType.REPLY]: 'ChatDotRound',
    [NotificationType.SYSTEM]: 'InfoFilled',
  }
  return map[type] || 'Bell'
}

function typeColor(type: NotificationType) {
  const map: Record<string, string> = {
    [NotificationType.ANNOUNCEMENT]: 'var(--brand)',
    [NotificationType.GRADED]: 'var(--green)',
    [NotificationType.DEADLINE]: 'var(--orange)',
    [NotificationType.REPLY]: 'var(--purple)',
    [NotificationType.SYSTEM]: 'var(--text-secondary)',
  }
  return map[type] || 'var(--text-secondary)'
}
</script>

<style scoped>
.notif-trigger {
  cursor: pointer;
  display: flex;
  align-items: center;
  padding: 4px;
  border-radius: 4px;
  color: var(--text-secondary);
  outline: none;
}
.notif-trigger:hover {
  color: var(--brand);
}
.notif-panel {
  width: 340px;
  max-height: 480px;
  display: flex;
  flex-direction: column;
}
.notif-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.notif-title {
  font-weight: 600;
  font-size: 14px;
}
.notif-body {
  overflow-y: auto;
  max-height: 400px;
  padding: 4px;
}
.notif-item {
  display: flex;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  position: relative;
}
.notif-item:hover {
  background: var(--bg-soft);
}
.notif-item.unread {
  background: var(--brand-light);
}
.notif-icon {
  flex-shrink: 0;
  margin-top: 2px;
}
.notif-main {
  flex: 1;
  min-width: 0;
}
.notif-item-title {
  font-size: 13px;
  font-weight: 600;
}
.notif-item-content {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.notif-item-time {
  font-size: 11px;
  color: var(--text-faint);
  margin-top: 4px;
}
.unread-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--red);
  flex-shrink: 0;
  margin-top: 6px;
}
</style>
