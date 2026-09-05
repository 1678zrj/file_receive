/**
 * 全局 API 类型定义
 * 与后端 FastAPI schemas 严格对应（backend/app/schemas/*）
 * 带有 [TODO-API] 标记的类型表示后端尚未提供对应接口，前端已先行建模
 */

// ============================================================
// 通用
// ============================================================

/** 通用分页响应，对应后端 PageResponse[T] */
export interface PageResponse<T> {
  total: number
  page: number
  size: number
  items: T[]
}

// ============================================================
// 用户与鉴权
// ============================================================

/** 用户角色，对应后端 UserRole 枚举 */
export enum UserRole {
  STUDENT = 0,
  TEACHER = 1,
  ADMIN = 2,
}

/** POST /auth/login 请求体 */
export interface UserLogin {
  username: string
  password: string
}

/** POST /auth/login 响应 */
export interface Token {
  access_token: string
  refresh_token: string
}

/** POST /auth/refresh 响应 */
export interface AccessToken {
  access_token: string
}

/** GET /auth/me 响应（后端直接返回 User 表模型） */
export interface UserInfo {
  id: number
  role: UserRole
  username: string
  real_name: string
  email: string | null
  avatar: string | null
  created_at: string
}

/** POST /user/register 请求体 */
export interface UserCreate {
  role?: UserRole
  username: string
  password: string
  real_name: string
  email?: string | null
  avatar?: string | null
}

/** POST /user/register 响应 */
export interface UserOut {
  id: number
  role: UserRole
  username: string
  real_name: string
  email: string | null
  avatar: string | null
  created_at: string
}

// ============================================================
// 课程
// ============================================================

/** POST /course/register 请求体 */
export interface CourseCreate {
  name: string
  course_code?: string | null
  overview?: string
}

/** POST /course/register 响应 */
export interface CourseResponse {
  id: number
  name: string
  course_code: string | null
  teacher_id: number
  overview: string
  created_at: string
}

// ============================================================
// 课程资源
// ============================================================

/** POST /course-resource/register 请求体 */
export interface CourseResourceCreate {
  course_id: number
  file_record_id: number
  file_name: string
  title: string
}

/** GET /course-resource/course/{course_id} 响应元素 */
export interface CourseResource {
  id: number
  course_id: number
  file_record_id: number
  uploaded_by: number
  file_name: string
  title: string
  created_at: string
  /** 文件大小（字节），建议后端在返回课程资源时联表带上 FileRecord.total_size */
  total_size?: number
}

// ============================================================
// 选课
// ============================================================

/** POST /enrollment/register 请求体 */
export interface EnrollmentCreate {
  course_id: number
}

/** POST /enrollment/register 响应 */
export interface EnrollmentResponse {
  id: number
  student_id: number
  course_id: number
  score: number | null
}

/** GET /enrollment/{course_id}/students 响应元素 */
export interface CourseStudent {
  student_id: number
  username: string
  real_name: string
  score: number | null
}

// ============================================================
// 文件分片上传
// ============================================================

/** 上传状态，对应后端 UploadStatus 枚举 */
export enum UploadStatus {
  UPLOADING = 'uploading',
  MERGING = 'merging',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

/** POST /upload/init 请求体 */
export interface InitUploadRequest {
  file_name: string
  file_hash: string
  file_ext: string
  mime_type: string
  total_size: number
  chunk_size: number
  total_chunks: number
}

/** POST /upload/init 响应 */
export interface InitUploadResponse {
  /** true 表示秒传成功，无需传输分片 */
  instant_upload: boolean
  upload_id: string | null
  file_record_id: number | null
  uploaded_chunks: number[]
}

/** GET /upload/{upload_id}/status 响应 */
export interface UploadStatusResponse {
  upload_id: string
  status: UploadStatus
  uploaded_chunks: number[]
  total_chunks: number
  file_record_id: number | null
  error_msg: string | null
}

/** POST /upload/{upload_id}/merge 响应 (202) */
export interface MergeTriggerResponse {
  upload_id: string
  task_id: string | null
  status: UploadStatus
}

// ============================================================
// 知识库
// ============================================================

/** POST /kb/course 请求体 */
export interface CourseFileIndexRequest {
  title: string
  file_record_id: number
  course_id: number
  scope?: string
  splitter_type?: string
  chunk_size?: number
}

/** POST /kb/course 响应 */
export interface CourseFileIndexResponse {
  id: number
  title: string
  file_record_id: number
  scope: string
  scope_id: string
  chunk_count: number
  created_at: string
  updated_at: string
}

/** 知识库文档状态，对应后端 DocumentStatus 枚举 */
export enum DocumentStatus {
  PENDING = 'PENDING',
  PARSING = 'PARSING',
  CHUNKING = 'CHUNKING',
  INDEXING = 'INDEXING',
  SUCCESS = 'SUCCESS',
  FAILED = 'FAILED',
}

/** [TODO-API] 知识库文档列表项（对应后端 KnowledgeDoc 模型，暂无列表接口） */
export interface KnowledgeDocItem {
  id: number
  title: string
  file_record_id: number
  markdown_char_count: number | null
  scope: string
  scope_id: string
  status: DocumentStatus
  error_msg: string | null
  chunk_count: number
  is_enabled: boolean
  created_by: number
  created_at: string
  updated_at: string
}

/** [TODO-API] 知识库文档分块（对应后端 KnowledgeDocChunk 模型） */
export interface KnowledgeDocChunkItem {
  id: number
  knowledge_doc_id: number
  vector_id: string
  chunk_text: string
  chunk_index: number
  token_count: number
  is_enabled: boolean
  created_at: string
}

// ============================================================
// 作业（后端仅有数据模型，全部接口待提供）
// ============================================================

/** [TODO-API] 作业信息 */
export interface Assignment {
  id: number
  course_id: number
  title: string
  description: string
  deadline: string
  created_at: string
  /** 教师上传的附件 */
  attachments?: AssignmentFile[]
  /** 当前登录学生的提交信息（学生视角） */
  my_submission?: Submission | null
  /** 教师视角的统计信息 */
  stats?: {
    total_students: number
    submitted_count: number
    graded_count: number
  }
}

/** [TODO-API] 作业附件 */
export interface AssignmentFile {
  id: number
  assignment_id: number
  file_record_id: number
  file_name: string
  uploaded_by: number
}

/** [TODO-API] 作业提交记录 */
export interface Submission {
  id: number
  student_id: number
  assignment_id: number
  score: number | null
  submitted_at: string
  feedback: string | null
  attempt: number
  files?: SubmissionFile[]
}

/** [TODO-API] 作业提交文件 */
export interface SubmissionFile {
  id: number
  submission_id: number
  file_record_id: number
  file_name: string
  uploaded_by: number
}

/** [TODO-API] 发布作业请求 */
export interface AssignmentCreate {
  course_id: number
  title: string
  description: string
  deadline: string
  /** 附件 file_record_id 列表 */
  attachment_file_ids?: number[]
}

/** [TODO-API] 提交作业请求 */
export interface SubmissionCreate {
  assignment_id: number
  /** 提交文件的 file_record_id 列表 */
  file_record_ids: number[]
}

/** [TODO-API] 批改作业请求 */
export interface SubmissionGrade {
  score: number
  feedback?: string
}

/** [TODO-API] 某次作业的全部提交（教师视角） */
export interface SubmissionWithStudent extends Submission {
  username?: string
  real_name?: string
}

// ============================================================
// 成绩（后端已有 Enrollment.score / Submission.score 模型，接口待提供）
// ============================================================

/** [TODO-API] 教师视角：一门课的成绩表（学生 × 作业二维矩阵） */
export interface CourseGradeRow {
  student_id: number
  username: string
  real_name: string
  /** 课程总成绩（Enrollment.score） */
  total_score: number | null
  /** 各次作业成绩 */
  assignments: {
    assignment_id: number
    title: string
    score: number | null
    submitted: boolean
  }[]
}

/** [TODO-API] 学生视角：我在一门课的成绩 */
export interface MyCourseGrade {
  course_id: number
  /** 课程总成绩 */
  total_score: number | null
  assignments: {
    assignment_id: number
    title: string
    score: number | null
    feedback: string | null
    submitted_at: string | null
  }[]
}

/** [TODO-API] 工作台统计概览 */
export interface StatsOverview {
  course_count: number
  student_count: number
  assignment_count: number
  /** 作业提交率（0-100） */
  submission_rate: number
  /** 成绩分布（各分数段人数） */
  score_distribution: { range: string; count: number }[]
}

// ============================================================
// RAG 知识库问答（待提供）
// ============================================================

/** [TODO-API] 问答请求 */
export interface KBChatRequest {
  course_id: number
  question: string
  /** 可选：会话ID，用于多轮上下文 */
  session_id?: string
}

/** [TODO-API] 知识来源引用 */
export interface KBSource {
  knowledge_doc_id: number
  title: string
  chunk_index: number
  chunk_text: string
  score?: number
}

/** [TODO-API] 问答响应（非流式时） */
export interface KBChatResponse {
  answer: string
  sources: KBSource[]
  session_id: string
}

/** 前端本地的聊天消息模型 */
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: KBSource[]
  streaming?: boolean
  created_at: string
}

// ============================================================
// 通知公告（后端暂无模型，前端先行设计）
// ============================================================

/** [TODO-API] 课程公告 */
export interface Announcement {
  id: number
  course_id: number
  title: string
  content: string
  /** 是否置顶 */
  pinned: boolean
  created_by: number
  author_name: string
  created_at: string
}

/** [TODO-API] 发布公告请求 */
export interface AnnouncementCreate {
  course_id: number
  title: string
  content: string
  pinned?: boolean
}

// ============================================================
// 讨论区（后端暂无模型，前端先行设计）
// ============================================================

/** [TODO-API] 讨论帖 */
export interface DiscussionPost {
  id: number
  course_id: number
  title: string
  content: string
  author_id: number
  author_name: string
  /** 回复数 */
  reply_count: number
  /** 点赞数 */
  like_count: number
  /** 当前用户是否已点赞 */
  liked: boolean
  created_at: string
  replies?: DiscussionReply[]
}

/** [TODO-API] 讨论回复 */
export interface DiscussionReply {
  id: number
  post_id: number
  content: string
  author_id: number
  author_name: string
  created_at: string
}

/** [TODO-API] 发帖请求 */
export interface DiscussionCreate {
  course_id: number
  title: string
  content: string
}

// ============================================================
// 消息通知中心（后端暂无模型，前端先行设计）
// ============================================================

/** 消息类型 */
export enum NotificationType {
  /** 新公告 */
  ANNOUNCEMENT = 'announcement',
  /** 作业批改 */
  GRADED = 'graded',
  /** 作业截止提醒 */
  DEADLINE = 'deadline',
  /** 新讨论回复 */
  REPLY = 'reply',
  /** 系统通知 */
  SYSTEM = 'system',
}

/** [TODO-API] 消息通知 */
export interface NotificationItem {
  id: number
  type: NotificationType
  title: string
  content: string
  /** 是否已读 */
  read: boolean
  /** 关联的课程 id（可选） */
  course_id?: number
  created_at: string
}
