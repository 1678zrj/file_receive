<template>
  <div class="page-container profile-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">个人中心</h2>
        <p class="page-subtitle">查看和管理你的账号信息</p>
      </div>
    </div>

    <div class="profile-grid">
      <!-- 用户卡片 -->
      <div class="profile-card cc-card fade-in-up">
        <div class="pc-banner"></div>
        <div class="pc-body">
          <UserAvatar :name="auth.user?.real_name" :size="86" class="pc-avatar" />
          <h3 class="pc-name">{{ auth.user?.real_name }}</h3>
          <el-tag :type="roleTagType" round effect="light">{{ roleName(auth.user?.role ?? 0) }}</el-tag>
          <div class="pc-info">
            <div class="info-row">
              <el-icon><User /></el-icon>
              <span class="info-label">用户名</span>
              <span class="info-value">{{ auth.user?.username }}</span>
            </div>
            <div class="info-row">
              <el-icon><Message /></el-icon>
              <span class="info-label">邮箱</span>
              <span class="info-value">{{ auth.user?.email || '未绑定' }}</span>
            </div>
            <div class="info-row">
              <el-icon><Calendar /></el-icon>
              <span class="info-label">注册时间</span>
              <span class="info-value">{{ formatDate(auth.user?.created_at) }}</span>
            </div>
            <div class="info-row">
              <el-icon><Key /></el-icon>
              <span class="info-label">用户 ID</span>
              <span class="info-value">#{{ auth.user?.id }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 学习数据 -->
      <div class="right-column">
        <div class="cc-card stat-panel fade-in-up">
          <h4 class="panel-title">{{ auth.isAdmin ? '管理数据' : auth.isTeacher ? '教学数据' : '学习数据' }}</h4>
          <div class="mini-stat-grid">
            <div class="mini-stat">
              <div class="ms-value">{{ auth.isAdmin ? courseStore.allList.length : auth.isTeacher ? courseStore.teaching.length : courseStore.enrolled.length }}</div>
              <div class="ms-label">{{ auth.isAdmin ? '全部课程' : auth.isTeacher ? '我教的课' : '在学课程' }}</div>
            </div>
            <div class="mini-stat">
              <div class="ms-value">{{ courseStore.allCourses.length }}</div>
              <div class="ms-label">可见课程</div>
            </div>
            <div class="mini-stat">
              <div class="ms-value">—</div>
              <div class="ms-label">作业完成率</div>
            </div>
          </div>
        </div>

        <div class="cc-card about-panel fade-in-up">
          <h4 class="panel-title">关于云课堂</h4>
          <p class="about-text">
            云课堂是一个迷你版在线教学平台，支持课程管理、课程资源共享、作业发布与提交，
            并内置基于 RAG 的课程知识库智能问答。前端基于 Vue 3 + TypeScript + Element Plus 构建。
          </p>
          <el-button text type="danger" :icon="SwitchButton" @click="logout">退出登录</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { User, Message, Calendar, Key, SwitchButton } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { useCourseStore } from '@/stores/course'
import { formatDate, roleName } from '@/utils/format'
import UserAvatar from '@/components/UserAvatar.vue'

const auth = useAuthStore()
const courseStore = useCourseStore()
const router = useRouter()

const roleTagType = computed(() => {
  const r = auth.user?.role ?? 0
  return r === 2 ? 'danger' : r === 1 ? 'warning' : 'success'
})

onMounted(() => {
  if (auth.user) courseStore.refreshMyCourses(auth.user.role)
})

async function logout() {
  await ElMessageBox.confirm('确定要退出登录吗？', '提示', { type: 'warning', confirmButtonText: '退出', cancelButtonText: '取消' })
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 20px;
  align-items: start;
}
@media (max-width: 900px) {
  .profile-grid {
    grid-template-columns: 1fr;
  }
}
.profile-card {
  overflow: hidden;
}
.pc-banner {
  height: 90px;
  background: var(--brand-gradient);
}
.pc-body {
  padding: 0 24px 24px;
  text-align: center;
  margin-top: -43px;
}
.pc-avatar {
  border: 4px solid var(--surface);
  box-shadow: var(--shadow-md);
}
.pc-name {
  margin: 12px 0 8px;
  font-size: 20px;
  font-weight: 800;
}
.pc-info {
  margin-top: 20px;
  text-align: left;
  background: var(--bg-soft);
  border-radius: var(--radius-md);
  padding: 14px 16px;
}
.info-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 0;
  font-size: 13.5px;
  color: var(--text-regular);
}
.info-label {
  color: var(--text-secondary);
  width: 64px;
}
.info-value {
  font-weight: 600;
  margin-left: auto;
}
.right-column {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.stat-panel,
.about-panel {
  padding: 22px;
}
.panel-title {
  margin: 0 0 16px;
  font-size: 16px;
  font-weight: 700;
}
.mini-stat-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}
.mini-stat {
  background: var(--bg-soft);
  border-radius: var(--radius-md);
  padding: 18px;
  text-align: center;
}
.ms-value {
  font-size: 26px;
  font-weight: 800;
  background: var(--brand-gradient);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.ms-label {
  font-size: 12.5px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.about-text {
  color: var(--text-regular);
  font-size: 13.5px;
  line-height: 1.8;
  margin: 0 0 14px;
}
</style>
