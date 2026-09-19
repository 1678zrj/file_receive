<template>
  <div class="login-page">
    <!-- 左侧品牌区（沉稳深蓝） -->
    <div class="brand-side">
      <div class="brand-content">
        <div class="brand-mark">
          <el-icon :size="30" color="#fff"><Reading /></el-icon>
        </div>
        <h1 class="brand-title">云课堂</h1>
        <p class="brand-sub">在线教学与管理一体化平台</p>
        <div class="feature-list">
          <div class="feature-item"><span class="fi-dot"></span>课程资源上传 · 分片断点续传</div>
          <div class="feature-item"><span class="fi-dot"></span>作业发布 · 提交 · 批改</div>
          <div class="feature-item"><span class="fi-dot"></span>课程知识库与智能问答</div>
        </div>
        <div class="brand-footer">贴近学习场景，服务课堂教学</div>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="form-side">
      <div class="form-card fade-in-up">
        <div class="form-tabs">
          <div class="tab-item" :class="{ active: isLogin }" @click="isLogin = true">登录</div>
          <div class="tab-item" :class="{ active: !isLogin }" @click="isLogin = false">注册</div>
        </div>

        <h2 class="form-title">{{ isLogin ? '账号登录' : '创建账号' }}</h2>

        <el-form ref="formRef" :model="form" :rules="rules" size="large" @submit.prevent="onSubmit">
          <el-form-item prop="username">
            <el-input v-model="form.username" placeholder="用户名 / 账号" :prefix-icon="User" clearable />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              :prefix-icon="Lock"
              show-password
              @keyup.enter="onSubmit"
            />
          </el-form-item>

          <template v-if="!isLogin">
            <el-form-item prop="real_name">
              <el-input v-model="form.real_name" placeholder="真实姓名" :prefix-icon="Postcard" clearable />
            </el-form-item>
            <el-form-item prop="email">
              <el-input v-model="form.email" placeholder="邮箱（选填）" :prefix-icon="Message" clearable />
            </el-form-item>
            <el-form-item prop="role">
              <el-radio-group v-model="form.role" class="role-radio">
                <el-radio :value="0">学生</el-radio>
                <el-radio :value="1">教师</el-radio>
              </el-radio-group>
            </el-form-item>
          </template>

          <el-button
            type="primary"
            size="large"
            class="submit-btn btn-primary"
            :loading="loading"
            native-type="submit"
          >
            {{ isLogin ? '登 录' : '注 册' }}
          </el-button>
        </el-form>

        <!-- 演示账号 -->
        <template v-if="isLogin">
          <el-divider><span class="demo-title">演示账号</span></el-divider>
          <div class="demo-accounts">
            <div
              v-for="d in demoAccounts"
              :key="d.username"
              class="demo-chip"
              @click="fillAccount(d.username)"
            >
              <span class="dc-role" :class="d.cls">{{ d.role }}</span>
              <span class="dc-name">{{ d.label }}</span>
            </div>
          </div>
          <p class="demo-hint">密码均为 123456，点击即可填充</p>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, Message, Postcard } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const isLogin = ref(true)
const loading = ref(false)
const formRef = ref<FormInstance>()

const demoAccounts = [
  { username: 'teacher_li', role: '教师', label: '李老师', cls: 't' },
  { username: 'student_zhang', role: '学生', label: '张同学', cls: 's' },
  { username: 'student_wang', role: '学生', label: '王同学', cls: 's' },
  { username: 'admin', role: '管理员', label: '系统管理员', cls: 'a' },
]

const form = reactive({
  username: '',
  password: '',
  real_name: '',
  email: '',
  role: 0 as 0 | 1,
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 32, message: '长度 3-32 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  real_name: [{ required: true, message: '请输入真实姓名', trigger: 'blur' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
}

function fillAccount(username: string) {
  form.username = username
  form.password = '123456'
}

async function onSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    if (isLogin.value) {
      await auth.login({ username: form.username, password: form.password })
      ElMessage.success(`欢迎回来，${auth.user?.real_name}！`)
      const redirect = (route.query.redirect as string) || '/dashboard'
      router.push(redirect)
    } else {
      await auth.register({
        username: form.username,
        password: form.password,
        real_name: form.real_name,
        email: form.email || null,
        role: form.role,
      })
      ElMessage.success('注册成功，请登录')
      isLogin.value = true
      form.password = ''
    }
  } catch (e: any) {
    ElMessage.error(e?.message || (isLogin.value ? '登录失败' : '注册失败'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: flex;
  min-height: 100vh;
}

/* ---------- 左侧 ---------- */
.brand-side {
  flex: 1.1;
  background: linear-gradient(160deg, #1a3a5c 0%, #1f2d3d 70%, #18242f 100%);
  position: relative;
  overflow: hidden;
  display: none;
  align-items: center;
  justify-content: center;
}
@media (min-width: 900px) {
  .brand-side {
    display: flex;
  }
}
.brand-content {
  color: #fff;
  padding: 40px;
  max-width: 420px;
}
.brand-mark {
  width: 54px;
  height: 54px;
  border-radius: 10px;
  background: var(--brand);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}
.brand-title {
  font-size: 34px;
  font-weight: 700;
  margin: 0;
  letter-spacing: 3px;
}
.brand-sub {
  font-size: 15px;
  opacity: 0.75;
  margin: 8px 0 36px;
}
.feature-list {
  border-top: 1px solid rgba(255, 255, 255, 0.12);
  padding-top: 24px;
}
.feature-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  font-size: 14px;
  opacity: 0.88;
}
.fi-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #4d8fe8;
  flex-shrink: 0;
}
.brand-footer {
  margin-top: 40px;
  font-size: 12px;
  opacity: 0.45;
}

/* ---------- 右侧 ---------- */
.form-side {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 20px;
  background: var(--bg-page);
}
.form-card {
  width: 100%;
  max-width: 400px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-md);
  padding: 32px 34px 28px;
}
.form-tabs {
  display: flex;
  border-bottom: 1px solid var(--border);
  margin-bottom: 22px;
}
.tab-item {
  flex: 1;
  text-align: center;
  padding: 10px 0;
  font-size: 15px;
  cursor: pointer;
  color: var(--text-secondary);
  position: relative;
  user-select: none;
}
.tab-item.active {
  color: var(--brand);
  font-weight: 600;
}
.tab-item.active::after {
  content: '';
  position: absolute;
  left: 30%;
  right: 30%;
  bottom: -1px;
  height: 2px;
  background: var(--brand);
}
.form-title {
  margin: 0 0 20px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-main);
}
.submit-btn {
  width: 100%;
  margin-top: 4px;
  font-size: 15px;
  letter-spacing: 6px;
}
.role-radio {
  width: 100%;
  display: flex;
  gap: 24px;
}
.demo-title {
  font-size: 12px;
  color: var(--text-secondary);
}
.demo-accounts {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.demo-chip {
  flex: 1;
  min-width: 90px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 9px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}
.demo-chip:hover {
  border-color: var(--brand);
  background: var(--brand-light);
}
.dc-role {
  font-size: 11px;
  padding: 1px 7px;
  border-radius: 3px;
}
.dc-role.t { background: var(--warn-bg); color: var(--warn-text); }
.dc-role.s { background: var(--success-bg); color: var(--success-text); }
.dc-role.a { background: var(--red-light); color: var(--red); }
.dc-name {
  font-size: 12.5px;
  color: var(--text-main);
  font-weight: 500;
}
.demo-hint {
  text-align: center;
  font-size: 12px;
  color: var(--text-faint);
  margin: 12px 0 0;
}
</style>
