<template>
  <el-container class="main-layout">
    <!-- ============ 侧边栏（深色·学习通式） ============ -->
    <el-aside :width="asideWidth" class="sidebar">
      <div class="logo-box" @click="$router.push('/dashboard')">
        <div class="logo-icon">
          <el-icon :size="20" color="#fff"><Reading /></el-icon>
        </div>
        <transition name="fade">
          <span v-show="!menuCollapsed" class="logo-text">云课堂</span>
        </transition>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="menuCollapsed"
        :collapse-transition="false"
        class="side-menu"
        router
      >
        <!-- 教学分组 -->
        <div class="menu-group-title" v-show="!menuCollapsed">教学</div>
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <template #title>工作台</template>
        </el-menu-item>
        <el-menu-item index="/courses">
          <el-icon><Search /></el-icon>
          <template #title>课程广场</template>
        </el-menu-item>
        <el-menu-item index="/my-courses">
          <el-icon><Notebook /></el-icon>
          <template #title>我的课程</template>
        </el-menu-item>

        <!-- AI 助手分组 -->
        <div class="menu-group-title" v-show="!menuCollapsed">AI 助手</div>
        <el-menu-item index="/knowledge">
          <el-icon><Collection /></el-icon>
          <template #title>知识库管理</template>
        </el-menu-item>
        <el-menu-item index="/qa">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>AI 问答</template>
        </el-menu-item>

        <!-- 通用分组 -->
        <div class="menu-group-title" v-show="!menuCollapsed">通用</div>
        <el-menu-item index="/profile">
          <el-icon><User /></el-icon>
          <template #title>个人中心</template>
        </el-menu-item>
      </el-menu>

      <div v-if="config.USE_MOCK" class="mock-badge" :title="'当前为 Mock 预览模式，修改 src/config.ts 的 USE_MOCK 可切换真实接口'">
        <el-icon><DataLine /></el-icon>
        <span v-show="!menuCollapsed">演示数据</span>
      </div>
    </el-aside>

    <!-- ============ 主区域 ============ -->
    <el-container class="right-area">
      <el-header class="topbar" height="52px">
        <div class="topbar-left">
          <el-icon v-if="!isMobile" class="collapse-icon" @click="collapsed = !collapsed">
            <Fold v-if="!collapsed" /><Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="topbar-right">
          <!-- 主题切换：浅色 ⇄ 深色（图标表示「当前已是该模式」的反面，即点击后会切到的模式） -->
          <el-button
            text
            circle
            size="small"
            class="theme-toggle"
            :icon="theme.isDark ? Sunny : Moon"
            :title="theme.isDark ? '切换到浅色模式' : '切换到深色模式'"
            @click="theme.toggle()"
          />
          <!-- 消息通知中心 -->
          <NotificationCenter />
          <el-tag size="small" effect="plain" :type="roleTagType" class="role-tag">
            {{ roleName(auth.user?.role ?? 0) }}
          </el-tag>
          <el-dropdown trigger="click" @command="onCommand">
            <div class="user-chip">
              <UserAvatar :name="auth.user?.real_name" :size="30" />
              <span class="username">{{ auth.user?.real_name }}</span>
              <el-icon class="arrow" :size="12"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="content-area">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>

    <!-- 全局上传任务中心（后台多文件并发上传） -->
    <UploadCenter />
  </el-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'
import { roleName } from '@/utils/format'
import { config } from '@/config'
import { Moon, Sunny } from '@element-plus/icons-vue'
import UserAvatar from '@/components/UserAvatar.vue'
import UploadCenter from '@/components/UploadCenter.vue'
import NotificationCenter from '@/components/NotificationCenter.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const theme = useThemeStore()

const collapsed = ref(false)
/** 是否移动端窄屏 */
const isMobile = ref(false)
let mql: MediaQueryList | null = null

onMounted(() => {
  mql = window.matchMedia('(max-width: 768px)')
  isMobile.value = mql.matches
  mql.addEventListener('change', (e) => (isMobile.value = e.matches))
})
onBeforeUnmount(() => {
  mql?.removeEventListener('change', () => {})
})

/** 实际侧边栏宽度：窄屏强制图标模式 */
const asideWidth = computed(() => {
  if (isMobile.value) return '62px'
  return collapsed.value ? '62px' : '220px'
})
/** 窄屏时菜单始终处于 collapse（图标）状态 */
const menuCollapsed = computed(() => isMobile.value || collapsed.value)

// 移动端点击菜单后无需处理（无抽屉），保持简洁
watch(
  () => route.path,
  () => {
    // 路由变化时无需额外处理
  },
)

const activeMenu = computed(() => {
  if (route.name === 'course-detail') return '/my-courses'
  return route.path
})

const roleTagType = computed(() => {
  const r = auth.user?.role ?? 0
  return r === 2 ? 'danger' : r === 1 ? 'warning' : 'success'
})

async function onCommand(cmd: string) {
  if (cmd === 'profile') {
    router.push('/profile')
  } else if (cmd === 'logout') {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '退出',
      cancelButtonText: '取消',
      type: 'warning',
    })
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}

/* ---------- 侧边栏：深色学习通式 ---------- */
.sidebar {
  background: var(--sidebar-bg);
  display: flex;
  flex-direction: column;
  transition: width 0.25s ease;
  overflow: hidden;
}
.logo-box {
  height: 52px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  cursor: pointer;
  flex-shrink: 0;
}
.logo-icon {
  width: 30px;
  height: 30px;
  border-radius: 6px;
  background: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--sidebar-text-strong);
  white-space: nowrap;
  letter-spacing: 1px;
}
.side-menu {
  border-right: none;
  flex: 1;
  background: transparent;
}
.side-menu :deep(.el-menu-item) {
  color: var(--sidebar-text);
  height: 44px;
  margin: 2px 8px;
  border-radius: 4px;
}
.side-menu :deep(.el-menu-item:hover) {
  background: var(--sidebar-hover-bg);
  color: var(--sidebar-text-strong);
}
.side-menu :deep(.el-menu-item.is-active) {
  background: var(--brand);
  /* 主色底上的文字：两套主题都保持白色 */
  color: #fff;
}
.side-menu :deep(.el-menu-item .el-icon) {
  color: inherit;
}
.menu-group-title {
  padding: 14px 16px 6px;
  font-size: 11px;
  color: var(--sidebar-group-text);
  letter-spacing: 1px;
  user-select: none;
}
.mock-badge {
  margin: 8px;
  padding: 8px 12px;
  border-radius: 4px;
  background: rgba(232, 147, 12, 0.15);
  color: var(--warn-text);
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  overflow: hidden;
  flex-shrink: 0;
}

/* ---------- 顶栏 ---------- */
.right-area {
  display: flex;
  flex-direction: column;
}
.topbar {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
}
.topbar-left {
  display: flex;
  align-items: center;
  gap: 14px;
}
.collapse-icon {
  cursor: pointer;
  font-size: 18px;
  color: var(--text-secondary);
}
.collapse-icon:hover {
  color: var(--brand);
}
.topbar-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.user-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
  outline: none;
}
.user-chip:hover {
  background: var(--bg-soft);
}
.username {
  font-weight: 500;
  font-size: 13.5px;
}
.arrow {
  color: var(--text-secondary);
}

/* ---------- 内容 ---------- */
.content-area {
  padding: 0;
  overflow-y: auto;
  background: var(--bg-page);
}

/* ---------- 过渡动画 ---------- */
.page-enter-active,
.page-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(6px);
}
.page-leave-to {
  opacity: 0;
}
.fade-enter-active {
  transition: opacity 0.2s;
}
.fade-enter-from {
  opacity: 0;
}

@media (max-width: 768px) {
  .username,
  .role-tag {
    display: none;
  }
}
</style>
