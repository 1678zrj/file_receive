<template>
  <span class="file-icon" :style="{ width: `${size}px`, height: `${size}px`, borderRadius: '8px', background: meta.bg, color: meta.color }">
    <el-icon :size="Math.round(size * 0.55)">
      <component :is="meta.icon" />
    </el-icon>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { fileCategory } from '@/utils/format'

const props = withDefaults(defineProps<{ fileName: string; size?: number }>(), { size: 40 })

const meta = computed(() => {
  const cat = fileCategory(props.fileName)
  const map: Record<string, { icon: string; bg: string; color: string }> = {
    image: { icon: 'Picture', bg: '#e8f7ee', color: '#16a34a' },
    pdf: { icon: 'Document', bg: '#fdeaea', color: '#dc2626' },
    word: { icon: 'Document', bg: '#e8f0fe', color: '#2563eb' },
    excel: { icon: 'Grid', bg: '#e8f7ee', color: '#059669' },
    ppt: { icon: 'DataAnalysis', bg: '#fef3e5', color: '#ea580c' },
    video: { icon: 'VideoPlay', bg: '#f3e8fd', color: '#9333ea' },
    audio: { icon: 'Headset', bg: '#fdf0f7', color: '#db2777' },
    code: { icon: 'Monitor', bg: '#e8f4fa', color: '#0284c7' },
    archive: { icon: 'Box', bg: '#f2f3f7', color: '#64748b' },
    text: { icon: 'Tickets', bg: '#f2f3f7', color: '#64748b' },
    markdown: { icon: 'Notebook', bg: '#e8f4fa', color: '#0284c7' },
    other: { icon: 'Document', bg: '#f2f3f7', color: '#64748b' },
  }
  return map[cat] || map.other
})
</script>

<style scoped>
.file-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
</style>
