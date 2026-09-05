<template>
  <div class="discussion-panel">
    <!-- 工具栏 -->
    <div class="panel-toolbar">
      <span class="tip">共 {{ list.length }} 个主题帖</span>
      <el-button type="primary" class="btn-primary" :icon="Plus" @click="createVisible = true">
        发新帖
      </el-button>
    </div>

    <!-- 讨论列表 -->
    <div v-loading="loading">
      <el-empty v-if="!loading && list.length === 0" description="暂无讨论，来发第一帖吧" :image-size="90" />
      <div v-else class="post-list">
        <div v-for="p in list" :key="p.id" class="post-card cc-card">
          <div class="post-main" @click="toggleDetail(p)">
            <div class="post-title-row">
              <h3 class="post-title">{{ p.title }}</h3>
              <span class="post-author">{{ p.author_name }}</span>
            </div>
            <p class="post-content">{{ p.content }}</p>
            <div class="post-footer">
              <span class="pf-time">{{ fromNow(p.created_at) }}</span>
              <span class="pf-actions">
                <span class="pf-action" :class="{ liked: p.liked }" @click.stop="toggleLike(p)">
                  <el-icon :size="14"><Pointer /></el-icon>{{ p.like_count }}
                </span>
                <span class="pf-action">
                  <el-icon :size="14"><ChatLineRound /></el-icon>{{ p.reply_count }}
                </span>
              </span>
            </div>
          </div>

          <!-- 回复区（展开时显示） -->
          <div v-if="expandedId === p.id" class="replies">
            <div v-for="r in p.replies" :key="r.id" class="reply-item">
              <UserAvatar :name="r.author_name" :size="26" />
              <div class="reply-main">
                <div class="reply-head">
                  <span class="reply-author">{{ r.author_name }}</span>
                  <span class="reply-time">{{ fromNow(r.created_at) }}</span>
                </div>
                <p class="reply-content">{{ r.content }}</p>
              </div>
            </div>
            <!-- 回帖输入 -->
            <div class="reply-input">
              <el-input v-model="replyTexts[p.id]" placeholder="写下你的回复..." @keyup.enter="submitReply(p)" />
              <el-button type="primary" class="btn-primary" size="small" :loading="replyingId === p.id" @click="submitReply(p)">
                回复
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 发帖对话框 -->
    <el-dialog v-model="createVisible" title="发起新讨论" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="一句话描述你的问题或话题" maxlength="60" show-word-limit />
        </el-form-item>
        <el-form-item label="内容" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="5" placeholder="详细描述..." maxlength="2000" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取 消</el-button>
        <el-button type="primary" class="btn-primary" :loading="creating" @click="createPost">发 布</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { discussionApi } from '@/api'
import type { DiscussionPost } from '@/api/types'
import { fromNow } from '@/utils/format'
import UserAvatar from '@/components/UserAvatar.vue'

const props = defineProps<{ courseId: number }>()

const list = ref<DiscussionPost[]>([])
const loading = ref(false)
const expandedId = ref<number | null>(null)
const createVisible = ref(false)
const creating = ref(false)
const replyingId = ref<number | null>(null)
const replyTexts = reactive<Record<number, string>>({})
const formRef = ref<FormInstance>()
const form = reactive({ title: '', content: '' })

const rules: FormRules = {
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入内容', trigger: 'blur' }],
}

onMounted(load)

async function load() {
  loading.value = true
  try {
    list.value = await discussionApi.listByCourse(props.courseId)
  } catch (e: any) {
    ElMessage.error(e?.message || '加载讨论失败')
  } finally {
    loading.value = false
  }
}

function toggleDetail(p: DiscussionPost) {
  expandedId.value = expandedId.value === p.id ? null : p.id
}

async function toggleLike(p: DiscussionPost) {
  try {
    const res = await discussionApi.toggleLike(p.id)
    // 用返回值更新本地显示（mock 与真实接口均返回 {liked, like_count}）
    if (res && typeof res.liked === 'boolean') {
      p.liked = res.liked
      p.like_count = res.like_count
    }
  } catch {
    /* 点赞失败静默 */
  }
}

async function submitReply(p: DiscussionPost) {
  const content = (replyTexts[p.id] || '').trim()
  if (!content) return
  replyingId.value = p.id
  try {
    await discussionApi.reply(p.id, content)
    ElMessage.success('回复成功')
    replyTexts[p.id] = ''
    await load()
    expandedId.value = p.id
  } catch (e: any) {
    ElMessage.error(e?.message || '回复失败')
  } finally {
    replyingId.value = null
  }
}

async function createPost() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  creating.value = true
  try {
    await discussionApi.create({ course_id: props.courseId, title: form.title, content: form.content })
    ElMessage.success('发帖成功')
    createVisible.value = false
    form.title = form.content = ''
    await load()
  } catch (e: any) {
    ElMessage.error(e?.message || '发帖失败')
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
.post-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.post-card {
  padding: 0;
  overflow: hidden;
}
.post-main {
  padding: 16px 18px;
  cursor: pointer;
}
.post-main:hover .post-title { color: var(--brand); }
.post-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}
.post-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.post-author {
  font-size: 12.5px;
  color: var(--brand);
  flex-shrink: 0;
}
.post-content {
  margin: 0 0 12px;
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--text-regular);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.post-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.pf-time {
  font-size: 12px;
  color: var(--text-faint);
}
.pf-actions {
  display: flex;
  gap: 16px;
}
.pf-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12.5px;
  color: var(--text-secondary);
  cursor: pointer;
}
.pf-action.liked { color: var(--brand); }

.replies {
  border-top: 1px solid var(--border);
  background: var(--bg-soft);
  padding: 14px 18px;
}
.reply-item {
  display: flex;
  gap: 10px;
  margin-bottom: 12px;
}
.reply-main {
  flex: 1;
  min-width: 0;
}
.reply-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}
.reply-author {
  font-size: 13px;
  font-weight: 600;
}
.reply-time {
  font-size: 11.5px;
  color: var(--text-faint);
}
.reply-content {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-regular);
}
.reply-input {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
</style>
