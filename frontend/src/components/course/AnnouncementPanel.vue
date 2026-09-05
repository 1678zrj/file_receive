<template>
  <div class="announcement-panel">
    <!-- 工具栏 -->
    <div class="panel-toolbar">
      <span class="tip">共 {{ list.length }} 条公告</span>
      <el-button v-if="isTeacher" type="primary" class="btn-primary" :icon="Plus" @click="createVisible = true">
        发布公告
      </el-button>
    </div>

    <!-- 公告列表 -->
    <div v-loading="loading">
      <el-empty v-if="!loading && list.length === 0" description="暂无公告" :image-size="90" />
      <div v-else class="ann-list">
        <div v-for="a in list" :key="a.id" class="ann-card cc-card">
          <div class="ann-head">
            <span v-if="a.pinned" class="pin-tag">置顶</span>
            <h3 class="ann-title">{{ a.title }}</h3>
          </div>
          <p class="ann-content">{{ a.content }}</p>
          <div class="ann-footer">
            <span class="ann-author">{{ a.author_name }}</span>
            <span class="ann-time">{{ formatDateTime(a.created_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 发布公告对话框 -->
    <el-dialog v-model="createVisible" title="发布公告" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="公告标题" prop="title">
          <el-input v-model="form.title" placeholder="例如：作业截止提醒" maxlength="60" show-word-limit />
        </el-form-item>
        <el-form-item label="公告内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="5" placeholder="公告正文..." maxlength="1000" show-word-limit />
        </el-form-item>
        <el-form-item label="置顶">
          <el-switch v-model="form.pinned" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取 消</el-button>
        <el-button type="primary" class="btn-primary" :loading="creating" @click="createAnnouncement">发 布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { announcementApi } from '@/api'
import type { Announcement } from '@/api/types'
import { formatDateTime } from '@/utils/format'

const props = defineProps<{ courseId: number; isTeacher: boolean }>()

const list = ref<Announcement[]>([])
const loading = ref(false)
const createVisible = ref(false)
const creating = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({ title: '', content: '', pinned: false })

const rules: FormRules = {
  title: [{ required: true, message: '请输入公告标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入公告内容', trigger: 'blur' }],
}

onMounted(load)

async function load() {
  loading.value = true
  try {
    list.value = await announcementApi.listByCourse(props.courseId)
  } catch (e: any) {
    ElMessage.error(e?.message || '加载公告失败')
  } finally {
    loading.value = false
  }
}

async function createAnnouncement() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  creating.value = true
  try {
    await announcementApi.create({
      course_id: props.courseId,
      title: form.title,
      content: form.content,
      pinned: form.pinned,
    })
    ElMessage.success('公告发布成功')
    createVisible.value = false
    form.title = form.content = ''
    form.pinned = false
    await load()
  } catch (e: any) {
    ElMessage.error(e?.message || '发布失败')
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.panel-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.tip {
  font-size: 12.5px;
  color: var(--text-secondary);
}
.ann-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ann-card {
  padding: 16px 18px;
}
.ann-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.pin-tag {
  font-size: 11px;
  color: var(--orange);
  background: #fdf3e3;
  padding: 1px 8px;
  border-radius: 3px;
  flex-shrink: 0;
}
.ann-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.ann-content {
  margin: 0 0 12px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--text-regular);
  white-space: pre-wrap;
}
.ann-footer {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-faint);
  border-top: 1px solid var(--border);
  padding-top: 10px;
}
</style>
