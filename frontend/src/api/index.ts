/**
 * API 层
 *  - 已对接的真实接口：auth / user / course / course-resource / enrollment / upload / kb(索引)
 *  - 带 [TODO-API] 标记的：后端尚未提供，调用会走真实 HTTP（后端补齐后自动生效），
 *    页面层已做 404/405 兜底展示。
 */
import http from './http'
import { config } from '@/config'
import { mockDelay } from './mockUtil'
import {
  advanceMockDocStatus,
  mockAnnouncements,
  mockAssignments,
  mockChatReply,
  mockCourseGrades,
  mockCourses,
  mockDiscussions,
  mockDocChunks,
  mockDocMarkdown,
  mockEnrolled,
  mockKnowledgeDocs,
  mockMyGrade,
  mockNotifications,
  mockResources,
  mockStats,
  mockStudents,
  mockSubmissions,
  mockTeaching,
  mockUpcomingAssignments,
} from './mock'
import type {
  AccessToken,
  Announcement,
  AnnouncementCreate,
  Assignment,
  AssignmentCreate,
  CourseCreate,
  CourseFileIndexRequest,
  CourseFileIndexResponse,
  CourseGradeRow,
  CourseResource,
  CourseResourceCreate,
  CourseResponse,
  CourseStudent,
  DiscussionCreate,
  DiscussionPost,
  DiscussionReply,
  EnrollmentCreate,
  EnrollmentResponse,
  InitUploadRequest,
  InitUploadResponse,
  KBChatRequest,
  KBChatResponse,
  KnowledgeDocChunkItem,
  KnowledgeDocItem,
  MergeTriggerResponse,
  MyCourseGrade,
  NotificationItem,
  PageResponse,
  StatsOverview,
  Submission,
  SubmissionCreate,
  SubmissionGrade,
  SubmissionWithStudent,
  Token,
  UploadStatusResponse,
  UserCreate,
  UserInfo,
  UserLogin,
  UserOut,
} from './types'
import { DocumentStatus } from './types'

// ============================================================
// 鉴权
// ============================================================
export const authApi = {
  /** POST /auth/login（后端会同时种下 refresh_token HttpOnly Cookie） */
  login(data: UserLogin) {
    return http.post<Token>('/auth/login', data).then((r) => r.data)
  },
  /** POST /auth/refresh */
  refresh() {
    return http.post<AccessToken>('/auth/refresh').then((r) => r.data)
  },
  /** GET /auth/me */
  me() {
    return http.get<UserInfo>('/auth/me').then((r) => r.data)
  },
}

// ============================================================
// 用户
// ============================================================
export const userApi = {
  /** POST /user/register */
  register(data: UserCreate) {
    return http.post<UserOut>('/user/register', data).then((r) => r.data)
  },
}

// ============================================================
// 课程
// ============================================================
export const courseApi = {
  /** POST /course/register 教师创建课程 */
  create(data: CourseCreate) {
    return http.post<CourseResponse>('/course/register', data).then((r) => r.data)
  },

  // ---------------- 以下为 [TODO-API]，后端尚未提供 ----------------
  /** GET /course/list 课程广场（全部课程，分页） */
  async list(params: { page: number; size: number; keyword?: string }) {
    if (config.USE_MOCK) {
      let items = [...mockCourses]
      const kw = params.keyword?.trim()
      if (kw) {
        items = items.filter(
          (c) => c.name.includes(kw) || (c.course_code && c.course_code.includes(kw)),
        )
      }
      const total = items.length
      const start = (params.page - 1) * params.size
      items = items.slice(start, start + params.size)
      const res: PageResponse<CourseResponse> = {
        total,
        page: params.page,
        size: params.size,
        items,
      }
      return mockDelay(res)
    }
    return http.get<PageResponse<CourseResponse>>('/course/list', { params }).then((r) => r.data)
  },
  /** GET /course/my 我教的课（教师） */
  myTeaching() {
    if (config.USE_MOCK) return mockDelay(mockTeaching)
    return http.get<CourseResponse[]>('/course/my').then((r) => r.data)
  },
  /** GET /course/enrolled 我学的课（学生） */
  myEnrolled() {
    if (config.USE_MOCK) return mockDelay(mockEnrolled)
    return http.get<CourseResponse[]>('/course/enrolled').then((r) => r.data)
  },
  /** GET /course/{id} 课程详情（mock 时也作为资源/作业等面板回退来源） */
  detail(id: number) {
    if (config.USE_MOCK) {
      const found = mockCourses.find((c) => c.id === id)
      return found ? mockDelay(found) : Promise.reject(new Error(`课程 ${id} 不存在`))
    }
    return http.get<CourseResponse>(`/course/${id}`).then((r) => r.data)
  },
  /** [TODO-API] PUT /course/{id} 更新课程 */
  update(id: number, data: Partial<CourseCreate>) {
    return http.put<CourseResponse>(`/course/${id}`, data).then((r) => r.data)
  },
  /** [TODO-API] DELETE /course/{id} 删除课程 */
  remove(id: number) {
    return http.delete(`/course/${id}`).then((r) => r.data)
  },
}

// ============================================================
// 选课
// ============================================================
export const enrollmentApi = {
  /** POST /enrollment/register 学生选课 */
  enroll(data: EnrollmentCreate) {
    return http.post<EnrollmentResponse>('/enrollment/register', data).then((r) => r.data)
  },
  /** 注意：后端此接口定义为 POST，path 为 /enrollment/{course_id}/students */
  async courseStudents(courseId: number, page = 1, size = 10) {
    if (config.USE_MOCK) {
      const items = mockStudents.filter((_, i) => i >= (page - 1) * size && i < page * size)
      const res: PageResponse<CourseStudent> = {
        total: mockStudents.length,
        page,
        size,
        items,
      }
      return mockDelay(res)
    }
    return http
      .post<PageResponse<CourseStudent>>(`/enrollment/${courseId}/students`, null, {
        params: { page, size },
      })
      .then((r) => r.data)
  },
  /** [TODO-API] DELETE /enrollment/{course_id} 退课 */
  unenroll(courseId: number) {
    return http.delete(`/enrollment/${courseId}`).then((r) => r.data)
  },
}

// ============================================================
// 课程资源
// ============================================================
export const resourceApi = {
  /** GET /course-resource/course/{course_id} 课程资源列表 */
  async listByCourse(courseId: number, skip = 0, limit = 100) {
    if (config.USE_MOCK) {
      return mockDelay(mockResources.filter((r) => r.course_id === courseId))
    }
    return http
      .get<CourseResource[]>(`/course-resource/course/${courseId}`, {
        params: { skip, limit },
      })
      .then((r) => r.data)
  },
  /** POST /course-resource/register 教师绑定课程资源（mock 下同步落到本地演示数据） */
  async create(data: CourseResourceCreate) {
    if (config.USE_MOCK) {
      const now = new Date().toISOString()
      const r: CourseResource = {
        ...data,
        id: Math.floor(Math.random() * 10000) + 1000,
        uploaded_by: 2,
        created_at: now,
        total_size: Math.floor(Math.random() * 5_000_000) + 10_000,
      }
      mockResources.unshift(r)
      return mockDelay(r)
    }
    return http.post<CourseResource>('/course-resource/register', data).then((r) => r.data)
  },

  // ---------------- [TODO-API] ----------------
  /** [TODO-API] GET /file/download/{file_record_id} 文件下载（返回二进制流） */
  downloadUrl(fileRecordId: number) {
    return `/api/v1/file/download/${fileRecordId}`
  },
  /** [TODO-API] GET /file/preview/{file_record_id} 文件预览（inline 流） */
  previewUrl(fileRecordId: number) {
    return `/api/v1/file/preview/${fileRecordId}`
  },
  /** 带鉴权拉取文件 Blob（用于预览/下载，token 无法通过 <img>/<a> 直接携带） */
  fetchBlob(fileRecordId: number, mode: 'download' | 'preview' = 'preview') {
    return http
      .get<Blob>(`/file/${mode}/${fileRecordId}`, { responseType: 'blob', timeout: 120000 })
      .then((r) => r.data)
  },
  /** [TODO-API] DELETE /course-resource/{id} 删除课程资源 */
  remove(id: number) {
    return http.delete(`/course-resource/${id}`).then((r) => r.data)
  },
}

// ============================================================
// 文件分片上传
// ============================================================
export const uploadApi = {
  /** POST /upload/init */
  init(data: InitUploadRequest) {
    return http.post<InitUploadResponse>('/upload/init', data).then((r) => r.data)
  },
  /** POST /upload/{upload_id}/chunk?chunk_index=N （原始字节流） */
  uploadChunk(uploadId: string, chunkIndex: number, blob: Blob) {
    return http
      .post(`/upload/${uploadId}/chunk`, blob, {
        params: { chunk_index: chunkIndex },
        headers: { 'Content-Type': 'application/octet-stream' },
        timeout: 120000,
      })
      .then((r) => r.data)
  },
  /** GET /upload/{upload_id}/status */
  getStatus(uploadId: string) {
    return http.get<UploadStatusResponse>(`/upload/${uploadId}/status`).then((r) => r.data)
  },
  /** POST /upload/{upload_id}/merge (202) */
  merge(uploadId: string) {
    return http.post<MergeTriggerResponse>(`/upload/${uploadId}/merge`).then((r) => r.data)
  },
}

// ============================================================
// 知识库
// ============================================================
export const kbApi = {
  /** POST /kb/course 将已上传文件索引进课程知识库 */
  indexCourseFile(data: CourseFileIndexRequest) {
    return http.post<CourseFileIndexResponse>('/kb/course', data).then((r) => r.data)
  },

  // ---------------- [TODO-API] ----------------
  /** GET /kb/course/{course_id}/docs 课程知识库文档列表 */
  listDocs(courseId: number) {
    if (config.USE_MOCK) return mockDelay(mockKnowledgeDocs)
    return http
      .get<KnowledgeDocItem[]>(`/kb/course/${courseId}/docs`)
      .then((r) => r.data)
  },
  /** GET /kb/doc/{doc_id} 单个文档详情（用于状态轮询） */
  docDetail(docId: number) {
    if (config.USE_MOCK) {
      const advanced = advanceMockDocStatus(docId)
      return advanced ? mockDelay(advanced) : Promise.reject(new Error(`文档 ${docId} 不存在`))
    }
    return http.get<KnowledgeDocItem>(`/kb/doc/${docId}`).then((r) => r.data)
  },
  /** DELETE /kb/doc/{doc_id} 删除知识库文档 */
  removeDoc(docId: number) {
    if (config.USE_MOCK) return mockDelay({ ok: true })
    return http.delete(`/kb/doc/${docId}`).then((r) => r.data)
  },
  /** PATCH /kb/doc/{doc_id} 启用/停用文档检索 */
  toggleDoc(docId: number, isEnabled: boolean) {
    if (config.USE_MOCK) return mockDelay({ id: docId, is_enabled: isEnabled })
    return http.patch(`/kb/doc/${docId}`, { is_enabled: isEnabled }).then((r) => r.data)
  },
  /** POST /kb/chat 知识库问答（非流式） */
  chat(data: KBChatRequest) {
    if (config.USE_MOCK) return mockDelay(mockChatReply(data.question))
    return http.post<KBChatResponse>('/kb/chat', data).then((r) => r.data)
  },
  /** GET /kb/doc/{doc_id}/markdown 获取解析后的 Markdown 内容 */
  getMarkdown(docId: number) {
    if (config.USE_MOCK) {
      return mockDelay(mockDocMarkdown[docId] ?? '# 暂无解析内容')
    }
    return http.get<string>(`/kb/doc/${docId}/markdown`).then((r) => r.data)
  },
  /** GET /kb/doc/{doc_id}/chunks 获取文档分块列表 */
  getChunks(docId: number) {
    if (config.USE_MOCK) {
      return mockDelay(mockDocChunks[docId] ?? [])
    }
    return http.get<KnowledgeDocChunkItem[]>(`/kb/doc/${docId}/chunks`).then((r) => r.data)
  },
  /** PATCH /kb/chunk/{chunk_id} 启用/停用/编辑单个分块 */
  patchChunk(chunkId: number, data: { is_enabled?: boolean; chunk_text?: string }) {
    if (config.USE_MOCK) {
      for (const chunks of Object.values(mockDocChunks)) {
        const c = chunks.find((x) => x.id === chunkId)
        if (c) {
          if (data.is_enabled !== undefined) c.is_enabled = data.is_enabled
          if (data.chunk_text !== undefined) c.chunk_text = data.chunk_text
          return mockDelay(c)
        }
      }
      return Promise.reject(new Error(`分块 ${chunkId} 不存在`))
    }
    return http.patch<KnowledgeDocChunkItem>(`/kb/chunk/${chunkId}`, data).then((r) => r.data)
  },
  /** POST /kb/doc/{doc_id}/retry 失败文档重新索引 */
  retryDoc(docId: number) {
    if (config.USE_MOCK) {
      const doc = mockKnowledgeDocs.find((d) => d.id === docId)
      if (doc) {
        doc.status = DocumentStatus.PARSING
        doc.error_msg = null
      }
      return mockDelay(doc as KnowledgeDocItem)
    }
    return http.post<KnowledgeDocItem>(`/kb/doc/${docId}/retry`).then((r) => r.data)
  },
  /** PUT /kb/doc/{doc_id}/markdown 保存 Markdown 编辑 */
  saveMarkdown(docId: number, content: string) {
    if (config.USE_MOCK) {
      mockDocMarkdown[docId] = content
      const doc = mockKnowledgeDocs.find((d) => d.id === docId)
      if (doc) doc.markdown_char_count = content.length
      return mockDelay({ ok: true })
    }
    return http.put(`/kb/doc/${docId}/markdown`, { content }).then((r) => r.data)
  },
}

// ============================================================
// 作业（全部 [TODO-API]，后端仅有数据模型）
// ============================================================
export const assignmentApi = {
  /** POST /assignment 教师发布作业 */
  async create(data: AssignmentCreate) {
    if (config.USE_MOCK) {
      const now = new Date().toISOString()
      const a: Assignment = {
        id: mockAssignments.length + 1 + Math.floor(Math.random() * 100),
        course_id: data.course_id,
        title: data.title,
        description: data.description,
        deadline: data.deadline,
        created_at: now,
        attachments: (data.attachment_file_ids || []).map((id, i) => ({
          id: i + 1,
          assignment_id: 0,
          file_record_id: id,
          file_name: `附件${i + 1}`,
          uploaded_by: 0,
        })),
        my_submission: null,
        stats: { total_students: 0, submitted_count: 0, graded_count: 0 },
      }
      mockAssignments.unshift(a)
      return mockDelay(a)
    }
    return http.post<Assignment>('/assignment', data).then((r) => r.data)
  },
  /** GET /assignment/course/{course_id} 课程作业列表 */
  listByCourse(courseId: number) {
    if (config.USE_MOCK) {
      return mockDelay(mockAssignments.filter((a) => a.course_id === courseId))
    }
    return http.get<Assignment[]>(`/assignment/course/${courseId}`).then((r) => r.data)
  },
  /** [TODO-API] GET /assignment/upcoming 我即将截止/待提交的作业 */
  upcoming() {
    if (config.USE_MOCK) return mockDelay(mockUpcomingAssignments)
    return http.get<Assignment[]>('/assignment/upcoming').then((r) => r.data)
  },
  /** GET /assignment/{id} 作业详情 */
  detail(id: number) {
    if (config.USE_MOCK) {
      const found = mockAssignments.find((a) => a.id === id)
      return found ? mockDelay(found) : Promise.reject(new Error(`作业 ${id} 不存在`))
    }
    return http.get<Assignment>(`/assignment/${id}`).then((r) => r.data)
  },
  /** DELETE /assignment/{id} 删除作业 */
  remove(id: number) {
    if (config.USE_MOCK) {
      const idx = mockAssignments.findIndex((a) => a.id === id)
      if (idx >= 0) mockAssignments.splice(idx, 1)
      return mockDelay({ ok: true })
    }
    return http.delete(`/assignment/${id}`).then((r) => r.data)
  },
  /** POST /submission 学生提交作业 */
  submit(data: SubmissionCreate) {
    if (config.USE_MOCK) {
      const s: Submission = {
        id: Math.floor(Math.random() * 1000) + 100,
        student_id: 11,
        assignment_id: data.assignment_id,
        score: null,
        submitted_at: new Date().toISOString(),
        feedback: null,
        attempt: 1,
      }
      return mockDelay(s)
    }
    return http.post<Submission>('/submission', data).then((r) => r.data)
  },
  /** GET /assignment/{id}/submissions 某作业全部提交（教师） */
  listSubmissions(assignmentId: number) {
    if (config.USE_MOCK) {
      return mockDelay(mockSubmissions.filter((s) => s.assignment_id === assignmentId))
    }
    return http
      .get<SubmissionWithStudent[]>(`/assignment/${assignmentId}/submissions`)
      .then((r) => r.data)
  },
  /** POST /submission/{id}/grade 教师批改 */
  grade(submissionId: number, data: SubmissionGrade) {
    if (config.USE_MOCK) {
      const target = mockSubmissions.find((s) => s.id === submissionId)
      if (target) {
        target.score = data.score
        target.feedback = data.feedback || null
      }
      return mockDelay(target as Submission)
    }
    return http.post<Submission>(`/submission/${submissionId}/grade`, data).then((r) => r.data)
  },
}

// ============================================================
// 成绩（后端已有 Enrollment.score / Submission.score 模型，接口待提供）
// ============================================================
export const gradeApi = {
  /** [TODO-API] GET /course/{id}/grades 教师查看课程成绩表 */
  courseGrades(courseId: number) {
    if (config.USE_MOCK) return mockDelay(mockCourseGrades)
    return http.get<CourseGradeRow[]>(`/course/${courseId}/grades`).then((r) => r.data)
  },
  /** [TODO-API] GET /course/{id}/my-grade 学生查看自己成绩 */
  myGrade(courseId: number) {
    if (config.USE_MOCK) return mockDelay(mockMyGrade)
    return http.get<MyCourseGrade>(`/course/${courseId}/my-grade`).then((r) => r.data)
  },
}

// ============================================================
// 统计（工作台看板，接口待提供）
// ============================================================
export const statsApi = {
  /** [TODO-API] GET /stats/overview 工作台统计概览 */
  overview() {
    if (config.USE_MOCK) return mockDelay(mockStats)
    return http.get<StatsOverview>('/stats/overview').then((r) => r.data)
  },
}

// ============================================================
// 通知公告（后端暂无模型，前端先行设计）
// ============================================================
export const announcementApi = {
  /** [TODO-API] GET /course/{id}/announcements 课程公告列表 */
  listByCourse(courseId: number) {
    if (config.USE_MOCK) return mockDelay(mockAnnouncements.filter((a) => a.course_id === courseId))
    return http.get<Announcement[]>(`/course/${courseId}/announcements`).then((r) => r.data)
  },
  /** [TODO-API] POST /announcement 发布公告（教师） */
  create(data: AnnouncementCreate) {
    if (config.USE_MOCK) {
      const a: Announcement = {
        id: mockAnnouncements.length + 1,
        course_id: data.course_id,
        title: data.title,
        content: data.content,
        pinned: data.pinned ?? false,
        created_by: 2,
        author_name: '李老师',
        created_at: new Date().toISOString(),
      }
      mockAnnouncements.unshift(a)
      return mockDelay(a)
    }
    return http.post<Announcement>('/announcement', data).then((r) => r.data)
  },
}

// ============================================================
// 讨论区（后端暂无模型，前端先行设计）
// ============================================================
export const discussionApi = {
  /** [TODO-API] GET /course/{id}/discussions 课程讨论帖列表 */
  listByCourse(courseId: number) {
    if (config.USE_MOCK) return mockDelay(mockDiscussions.filter((d) => d.course_id === courseId))
    return http.get<DiscussionPost[]>(`/course/${courseId}/discussions`).then((r) => r.data)
  },
  /** [TODO-API] POST /discussion 发帖 */
  create(data: DiscussionCreate) {
    if (config.USE_MOCK) {
      const p: DiscussionPost = {
        id: mockDiscussions.length + 1,
        course_id: data.course_id,
        title: data.title,
        content: data.content,
        author_id: 11,
        author_name: '张同学',
        reply_count: 0,
        like_count: 0,
        liked: false,
        created_at: new Date().toISOString(),
        replies: [],
      }
      mockDiscussions.unshift(p)
      return mockDelay(p)
    }
    return http.post<DiscussionPost>('/discussion', data).then((r) => r.data)
  },
  /** [TODO-API] POST /discussion/{id}/reply 回帖 */
  reply(postId: number, content: string) {
    if (config.USE_MOCK) {
      const post = mockDiscussions.find((p) => p.id === postId)
      if (post) {
        const r: DiscussionReply = {
          id: Date.now(),
          post_id: postId,
          content,
          author_id: 11,
          author_name: '张同学',
          created_at: new Date().toISOString(),
        }
        post.replies = post.replies || []
        post.replies.push(r)
        post.reply_count = post.replies.length
      }
      return mockDelay({ ok: true })
    }
    return http.post(`/discussion/${postId}/reply`, { content }).then((r) => r.data)
  },
  /** [TODO-API] POST /discussion/{id}/like 点赞/取消点赞 */
  toggleLike(postId: number) {
    if (config.USE_MOCK) {
      const post = mockDiscussions.find((p) => p.id === postId)
      if (post) {
        post.liked = !post.liked
        post.like_count += post.liked ? 1 : -1
      }
      return mockDelay({ liked: post?.liked, like_count: post?.like_count })
    }
    return http.post(`/discussion/${postId}/like`).then((r) => r.data)
  },
}

// ============================================================
// 消息通知中心（后端暂无模型，前端先行设计）
// ============================================================
export const notificationApi = {
  /** [TODO-API] GET /notifications 我的消息列表 */
  list() {
    if (config.USE_MOCK) return mockDelay(mockNotifications)
    return http.get<NotificationItem[]>('/notifications').then((r) => r.data)
  },
  /** [TODO-API] POST /notifications/read 标记已读 */
  markRead(id: number) {
    if (config.USE_MOCK) {
      const n = mockNotifications.find((x) => x.id === id)
      if (n) n.read = true
      return mockDelay({ ok: true })
    }
    return http.post(`/notifications/${id}/read`).then((r) => r.data)
  },
  /** [TODO-API] POST /notifications/read-all 全部已读 */
  markAllRead() {
    if (config.USE_MOCK) {
      mockNotifications.forEach((n) => (n.read = true))
      return mockDelay({ ok: true })
    }
    return http.post('/notifications/read-all').then((r) => r.data)
  },
}

export * from './types'
