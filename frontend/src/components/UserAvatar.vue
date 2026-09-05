<template>
  <span
    class="cc-avatar"
    :style="{
      width: `${size}px`,
      height: `${size}px`,
      fontSize: `${Math.round(size * 0.42)}px`,
      background: avatarGradient(name || '?'),
    }"
  >
    <img v-if="src" :src="src" :alt="name" class="cc-avatar-img" />
    <template v-else>{{ initial }}</template>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { avatarGradient } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    name?: string
    src?: string | null
    size?: number
  }>(),
  { name: '?', src: null, size: 40 },
)

const initial = computed(() => (props.name || '?').trim().charAt(0).toUpperCase())
</script>

<style scoped>
.cc-avatar-img {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  object-fit: cover;
}
</style>
