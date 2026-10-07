/**
 * 内置 Mock 数据（用于后端接口尚未提供时的界面预览）
 * 所有字段严格对齐 src/api/types.ts 的类型定义，保证切回真实接口时无缝。
 */
import type {
  Announcement,
  Assignment,
  CourseGradeRow,
  CourseResource,
  CourseResponse,
  CourseStudent,
  DiscussionPost,
  DiscussionReply,
  KnowledgeDocChunkItem,
  KnowledgeDocItem,
  KBChatResponse,
  KBSource,
  MyCourseGrade,
  NotificationItem,
  StatsOverview,
  SubmissionWithStudent,
} from '@/api/types'
import { DocumentStatus, NotificationType } from '@/api/types'

// ------------------------------------------------------------
// 课程
// ------------------------------------------------------------
/** 课程（附加 teacher_name 供前端展示，真实接口后续也应返回） */
export type CourseWithTeacher = CourseResponse & { teacher_name?: string }

export const mockCourses: CourseWithTeacher[] = [
  {
    id: 1,
    name: '高级 Python 编程',
    course_code: 'CS-201',
    teacher_id: 2,
    overview: '深入理解 Python 异步编程与 Web 框架，涵盖 asyncio、aiohttp、FastAPI 等核心内容，配合大量工程实践。',
    created_at: '2025-02-18T09:30:00Z',
    teacher_name: '李老师',
  },
  {
    id: 2,
    name: '数据库系统原理',
    course_code: 'CS-301',
    teacher_id: 2,
    overview: '从关系模型到 NoSQL，系统讲解 SQL 优化、事务与并发控制，以及 Redis、Milvus 等新兴存储引擎。',
    created_at: '2025-02-20T14:00:00Z',
    teacher_name: '李老师',
  },
  {
    id: 3,
    name: '机器学习导论',
    course_code: 'CS-401',
    teacher_id: 3,
    overview: '机器学习基础理论与实践，覆盖线性模型、决策树、神经网络，配套 Python 与 scikit-learn 实现。',
    created_at: '2025-03-01T10:00:00Z',
    teacher_name: '王老师',
  },
  {
    id: 4,
    name: '操作系统',
    course_code: 'CS-202',
    teacher_id: 3,
    overview: '进程与线程、内存管理、文件系统、IO 模型等操作系统核心原理，结合 Linux 源码与实践分析。',
    created_at: '2025-03-05T08:30:00Z',
    teacher_name: '王老师',
  },
  {
    id: 5,
    name: '计算机网络',
    course_code: 'CS-303',
    teacher_id: 4,
    overview: '自顶向下讲解 TCP/IP 协议栈、HTTP/HTTPS、路由与交换，配套 Wireshark 抓包实验。',
    created_at: '2025-03-08T15:20:00Z',
    teacher_name: '陈老师',
  },
  {
    id: 6,
    name: '大学英语（二）',
    course_code: 'EN-102',
    teacher_id: 5,
    overview: '重点提升阅读与写作能力，结合四六级考点与学术英语表达训练。',
    created_at: '2025-03-10T09:00:00Z',
    teacher_name: '刘老师',
  },
]

/** 教师角色的"我教的课"（teacher_id = 2 是李老师） */
export const mockTeaching: CourseWithTeacher[] = mockCourses.filter((c) => c.teacher_id === 2)
/** 学生角色的"我学的课" */
export const mockEnrolled: CourseWithTeacher[] = mockCourses.filter((c) => [1, 3, 5].includes(c.id))

// ------------------------------------------------------------
// 学生列表
// ------------------------------------------------------------
export const mockStudents: CourseStudent[] = [
  { student_id: 11, username: 'student_zhang', real_name: '张同学', score: 92.5 },
  { student_id: 12, username: 'student_wang', real_name: '王同学', score: 88 },
  { student_id: 13, username: 'li_xiaoming', real_name: '李小明', score: 76.5 },
  { student_id: 14, username: 'chen_jing', real_name: '陈静', score: 95 },
  { student_id: 15, username: 'zhao_lei', real_name: '赵磊', score: null },
  { student_id: 16, username: 'sun_yue', real_name: '孙悦', score: 81 },
  { student_id: 17, username: 'zhou_ming', real_name: '周明', score: 69 },
  { student_id: 18, username: 'wu_hang', real_name: '吴航', score: null },
]

// ------------------------------------------------------------
// 作业
// ------------------------------------------------------------
export const mockAssignments: Assignment[] = [
  {
    id: 1,
    course_id: 1,
    title: '第一次作业：实现异步爬虫',
    description:
      '请使用 asyncio 与 aiohttp 抓取指定网站的前 100 条新闻标题，要求：\n\n1. 控制并发数不超过 10\n2. 实现异常重试与超时处理\n3. 结果序列化为 JSON 并保存\n\n**评分标准**：代码规范 20%、功能完整 50%、异常处理 20%、文档注释 10%。',
    deadline: '2025-09-15T18:00:00Z',
    created_at: '2025-09-01T08:00:00Z',
    attachments: [
      { id: 1, assignment_id: 1, file_record_id: 101, file_name: '作业说明.pdf', uploaded_by: 2 },
      { id: 2, assignment_id: 1, file_record_id: 102, file_name: '示例代码.zip', uploaded_by: 2 },
    ],
    my_submission: {
      id: 11,
      student_id: 11,
      assignment_id: 1,
      score: 90,
      submitted_at: '2025-09-14T20:15:00Z',
      feedback: '完成度很高，异常处理部分可以再补充对连接池复用的说明。',
      attempt: 1,
    },
    stats: { total_students: 18, submitted_count: 14, graded_count: 10 },
  },
  {
    id: 2,
    course_id: 1,
    title: '第二次作业：实现 RAG 检索问答',
    description: '基于课程知识库，使用向量检索 + LLM 实现一个课程问答命令行小工具，要求输出来源引用。',
    deadline: '2025-09-22T23:59:00Z',
    created_at: '2025-09-10T08:00:00Z',
    attachments: [],
    my_submission: null,
    stats: { total_students: 18, submitted_count: 5, graded_count: 0 },
  },
  {
    id: 3,
    course_id: 1,
    title: '第三次作业：并发安全实践',
    description: '使用 Redis 分布式锁实现一个幂等的下单接口，并写测试用例验证并发安全性。',
    deadline: '2025-08-30T18:00:00Z',
    created_at: '2025-08-20T08:00:00Z',
    attachments: [],
    my_submission: {
      id: 12,
      student_id: 11,
      assignment_id: 3,
      score: 96,
      submitted_at: '2025-08-29T22:00:00Z',
      feedback: '很好，Lua 脚本保证原子性的思路清晰。',
      attempt: 2,
    },
    stats: { total_students: 18, submitted_count: 17, graded_count: 17 },
  },
]

// ------------------------------------------------------------
// 课程资源（mock 演示数据）
// ------------------------------------------------------------
export const mockResources: CourseResource[] = [
  { id: 1, course_id: 1, file_record_id: 301, uploaded_by: 2, file_name: '第1讲_异步编程概述.pdf', title: '第1讲：异步编程概述', created_at: '2025-09-01T09:00:00Z', total_size: 2_548_230 },
  { id: 2, course_id: 1, file_record_id: 302, uploaded_by: 2, file_name: '课件_asyncio核心.md', title: '课件：asyncio 核心概念', created_at: '2025-09-01T09:10:00Z', total_size: 48_120 },
  { id: 3, course_id: 1, file_record_id: 303, uploaded_by: 2, file_name: '示例代码_异步爬虫.zip', title: '示例代码：异步爬虫', created_at: '2025-09-03T14:20:00Z', total_size: 890_400 },
  { id: 4, course_id: 1, file_record_id: 304, uploaded_by: 2, file_name: '实验指导.docx', title: '实验指导书', created_at: '2025-09-05T10:30:00Z', total_size: 356_700 },
  { id: 5, course_id: 1, file_record_id: 305, uploaded_by: 2, file_name: 'FastAPI入门视频.mp4', title: 'FastAPI 快速入门视频', created_at: '2025-09-08T16:00:00Z', total_size: 58_600_000 },
  { id: 6, course_id: 1, file_record_id: 306, uploaded_by: 2, file_name: '期末复习提纲.xlsx', title: '期末复习提纲', created_at: '2025-09-12T11:00:00Z', total_size: 120_500 },
  { id: 7, course_id: 1, file_record_id: 307, uploaded_by: 2, file_name: '参考论文_RAG综述.pdf', title: '参考论文：RAG 综述', created_at: '2025-09-14T20:00:00Z', total_size: 4_100_200 },
]

// ------------------------------------------------------------
// 知识库文档
// ------------------------------------------------------------
export const mockKnowledgeDocs: KnowledgeDocItem[] = [
  {
    id: 1,
    title: 'FastAPI 异步编程实践',
    file_record_id: 201,
    markdown_char_count: 18430,
    scope: 'course',
    scope_id: 'course_1',
    status: DocumentStatus.SUCCESS,
    error_msg: null,
    chunk_count: 24,
    is_enabled: true,
    created_by: 2,
    created_at: '2025-09-05T10:00:00Z',
    updated_at: '2025-09-05T10:02:00Z',
  },
  {
    id: 2,
    title: 'Redis 缓存与分布式锁',
    file_record_id: 202,
    markdown_char_count: 22110,
    scope: 'course',
    scope_id: 'course_1',
    status: DocumentStatus.SUCCESS,
    error_msg: null,
    chunk_count: 31,
    is_enabled: true,
    created_by: 2,
    created_at: '2025-09-06T14:30:00Z',
    updated_at: '2025-09-06T14:32:00Z',
  },
  {
    id: 3,
    title: 'SQLModel 与数据库建模',
    file_record_id: 203,
    markdown_char_count: 9800,
    scope: 'course',
    scope_id: 'course_1',
    status: DocumentStatus.SUCCESS,
    error_msg: null,
    chunk_count: 15,
    is_enabled: false,
    created_by: 2,
    created_at: '2025-09-08T16:00:00Z',
    updated_at: '2025-09-08T16:01:00Z',
  },
  {
    id: 4,
    title: 'Milvus 向量库部署指南',
    file_record_id: 204,
    markdown_char_count: null,
    scope: 'course',
    scope_id: 'course_1',
    status: DocumentStatus.INDEXING,
    error_msg: null,
    chunk_count: 0,
    is_enabled: true,
    created_by: 2,
    created_at: '2025-09-12T09:20:00Z',
    updated_at: '2025-09-12T09:20:00Z',
  },
]

// ------------------------------------------------------------
// 知识库文档解析后的 Markdown 内容（mock，供预览）
// ------------------------------------------------------------
export const mockDocMarkdown: Record<number, string> = {
  1: `# FastAPI 异步编程实践

## 概述

FastAPI 是基于 Starlette 与 Pydantic 构建的现代 Web 框架，原生支持 \`async/await\` 异步语法。

## 核心要点

1. **异步路由**：使用 \`async def\` 声明即可获得异步支持
2. **阻塞代码处理**：CPU 密集型或同步阻塞 IO 应放入线程池，避免阻塞事件循环
3. **依赖注入**：\`Depends\` 提供了优雅的依赖管理与复用

## 示例代码

\`\`\`python
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}
\`\`\`

## 注意事项

- 区分「I/O 密集型」与「CPU 密集型」任务
- 同步阻塞函数使用 \`run_in_threadpool\` 包装

> 详见课程第 3 讲与实验指导书。
`,
  2: `# Redis 缓存与分布式锁

## 缓存策略

Redis 作为缓存中间件，可显著降低数据库压力，常用的模式包括 Cache-Aside、Write-Through 等。

## 分布式锁

- 使用 \`SET key value NX EX\` 实现加锁与过期
- 配合 Lua 脚本保证「判断 + 加锁 + 设过期」的原子性
- 释放锁时需校验锁归属，避免误删他人锁

## 幂等与并发

分布式场景下，幂等与分布式锁是保证并发安全的两道防线。

\`\`\`python
import redis
r = redis.Redis()
r.set("lock:order", "token", nx=True, ex=30)
\`\`\`
`,
  3: `# SQLModel 与数据库建模

SQLModel 结合了 Pydantic 与 SQLAlchemy 的优点，用于类型安全的数据库建模。

## 关键点

- 使用 \`Field\` 声明主键、索引与约束
- 唯一约束通过 \`UniqueConstraint\` 定义
- 枚举字段使用 \`sa_column=Column(Enum(...))\`

## 示例

\`\`\`python
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
\`\`\`
`,
}

// ------------------------------------------------------------
// 知识库文档分块（mock，供详情页预览）
// ------------------------------------------------------------
function buildChunks(docId: number, title: string, texts: string[]): KnowledgeDocChunkItem[] {
  return texts.map((text, i) => ({
    id: docId * 100 + i,
    knowledge_doc_id: docId,
    vector_id: `vec_${docId}_${i}`,
    chunk_text: text,
    chunk_index: i,
    token_count: Math.round(text.length / 3),
    // 让部分分块默认停用，演示「分块级启停」效果
    is_enabled: !(docId === 1 && i === 1),
    created_at: '2025-09-05T10:00:00Z',
  }))
}

export const mockDocChunks: Record<number, KnowledgeDocChunkItem[]> = {
  1: buildChunks(1, 'FastAPI 异步编程实践', [
    '# FastAPI 异步编程实践\n\n## 概述\n\nFastAPI 是基于 Starlette 与 Pydantic 构建的现代 Web 框架，原生支持 async/await 异步语法。',
    '## 核心要点\n\n1. 异步路由：使用 async def 声明即可获得异步支持\n2. 阻塞代码处理：CPU 密集型或同步阻塞 IO 应放入线程池\n3. 依赖注入：Depends 提供优雅的依赖管理',
    '## 示例代码\n\n```python\nfrom fastapi import FastAPI\napp = FastAPI()\n@app.get("/health")\nasync def health():\n    return {"status": "ok"}\n```',
    '## 注意事项\n\n- 区分「I/O 密集型」与「CPU 密集型」任务\n- 同步阻塞函数使用 run_in_threadpool 包装',
  ]),
  2: buildChunks(2, 'Redis 缓存与分布式锁', [
    '## 缓存策略\n\nRedis 作为缓存中间件，可显著降低数据库压力，常用模式包括 Cache-Aside、Write-Through 等。',
    '## 分布式锁\n\n- 使用 SET key value NX EX 实现加锁与过期\n- 配合 Lua 脚本保证原子性',
    '## 幂等与并发\n\n分布式场景下，幂等与分布式锁是保证并发安全的两道防线。',
  ]),
  3: buildChunks(3, 'SQLModel 与数据库建模', [
    '## 关键点\n\n- 使用 Field 声明主键、索引与约束\n- 唯一约束通过 UniqueConstraint 定义',
    '## 示例\n\n```python\nclass User(SQLModel, table=True):\n    id: int | None = Field(primary_key=True)\n```',
  ]),
}

// ------------------------------------------------------------
// 作业提交（教师视角）
// ------------------------------------------------------------
export const mockSubmissions: SubmissionWithStudent[] = [
  { id: 11, student_id: 11, username: 'student_zhang', real_name: '张同学', assignment_id: 1, score: 90, submitted_at: '2025-09-14T20:15:00Z', feedback: null, attempt: 1 },
  { id: 21, student_id: 12, username: 'student_wang', real_name: '王同学', assignment_id: 1, score: 85, submitted_at: '2025-09-14T21:00:00Z', feedback: null, attempt: 1 },
  { id: 31, student_id: 13, username: 'li_xiaoming', real_name: '李小明', assignment_id: 1, score: null, submitted_at: '2025-09-15T10:00:00Z', feedback: null, attempt: 1 },
  { id: 41, student_id: 14, username: 'chen_jing', real_name: '陈静', assignment_id: 1, score: 95, submitted_at: '2025-09-14T19:30:00Z', feedback: null, attempt: 1 },
]

// ------------------------------------------------------------
// 成绩（mock，供成绩管理）
// ------------------------------------------------------------
export const mockCourseGrades: CourseGradeRow[] = [
  {
    student_id: 11, username: 'student_zhang', real_name: '张同学', total_score: 90.5,
    assignments: [
      { assignment_id: 1, title: '第一次作业：实现异步爬虫', score: 90, submitted: true },
      { assignment_id: 2, title: '第二次作业：实现 RAG 检索问答', score: 88, submitted: true },
      { assignment_id: 3, title: '第三次作业：并发安全实践', score: 96, submitted: true },
    ],
  },
  {
    student_id: 12, username: 'student_wang', real_name: '王同学', total_score: 85,
    assignments: [
      { assignment_id: 1, title: '第一次作业：实现异步爬虫', score: 85, submitted: true },
      { assignment_id: 2, title: '第二次作业：实现 RAG 检索问答', score: 82, submitted: true },
      { assignment_id: 3, title: '第三次作业：并发安全实践', score: 88, submitted: true },
    ],
  },
  {
    student_id: 13, username: 'li_xiaoming', real_name: '李小明', total_score: 76.5,
    assignments: [
      { assignment_id: 1, title: '第一次作业：实现异步爬虫', score: 70, submitted: true },
      { assignment_id: 2, title: '第二次作业：实现 RAG 检索问答', score: 74, submitted: true },
      { assignment_id: 3, title: '第三次作业：并发安全实践', score: 80, submitted: true },
    ],
  },
  {
    student_id: 14, username: 'chen_jing', real_name: '陈静', total_score: 95,
    assignments: [
      { assignment_id: 1, title: '第一次作业：实现异步爬虫', score: 95, submitted: true },
      { assignment_id: 2, title: '第二次作业：实现 RAG 检索问答', score: 97, submitted: true },
      { assignment_id: 3, title: '第三次作业：并发安全实践', score: 93, submitted: true },
    ],
  },
  {
    student_id: 15, username: 'zhao_lei', real_name: '赵磊', total_score: null,
    assignments: [
      { assignment_id: 1, title: '第一次作业：实现异步爬虫', score: null, submitted: false },
      { assignment_id: 2, title: '第二次作业：实现 RAG 检索问答', score: null, submitted: false },
      { assignment_id: 3, title: '第三次作业：并发安全实践', score: 60, submitted: true },
    ],
  },
  {
    student_id: 16, username: 'sun_yue', real_name: '孙悦', total_score: 81,
    assignments: [
      { assignment_id: 1, title: '第一次作业：实现异步爬虫', score: 82, submitted: true },
      { assignment_id: 2, title: '第二次作业：实现 RAG 检索问答', score: 79, submitted: true },
      { assignment_id: 3, title: '第三次作业：并发安全实践', score: 83, submitted: true },
    ],
  },
]

export const mockMyGrade: MyCourseGrade = {
  course_id: 1,
  total_score: 90.5,
  assignments: [
    { assignment_id: 1, title: '第一次作业：实现异步爬虫', score: 90, feedback: '完成度很高，异常处理部分可以再补充对连接池复用的说明。', submitted_at: '2025-09-14T20:15:00Z' },
    { assignment_id: 2, title: '第二次作业：实现 RAG 检索问答', score: 88, feedback: '来源引用准确，检索策略可以再优化。', submitted_at: '2025-09-21T22:00:00Z' },
    { assignment_id: 3, title: '第三次作业：并发安全实践', score: 96, feedback: '很好，Lua 脚本保证原子性的思路清晰。', submitted_at: '2025-08-29T22:00:00Z' },
  ],
}

// ------------------------------------------------------------
// 统计概览（mock，供工作台看板）
// ------------------------------------------------------------
export const mockStats: StatsOverview = {
  course_count: 6,
  student_count: 18,
  assignment_count: 3,
  submission_rate: 82,
  score_distribution: [
    { range: '90-100', count: 4 },
    { range: '80-89', count: 7 },
    { range: '70-79', count: 4 },
    { range: '60-69', count: 2 },
    { range: '0-59', count: 1 },
  ],
}

// ------------------------------------------------------------
// 即将截止的作业（mock，供工作台待办）
// ------------------------------------------------------------
export const mockUpcomingAssignments: Assignment[] = [
  {
    id: 2, course_id: 1, title: '第二次作业：实现 RAG 检索问答',
    description: '基于课程知识库，使用向量检索 + LLM 实现课程问答工具。',
    deadline: '2025-09-22T23:59:00Z', created_at: '2025-09-10T08:00:00Z',
    my_submission: null, stats: { total_students: 18, submitted_count: 5, graded_count: 0 },
  },
  {
    id: 101, course_id: 3, title: '第一次作业：线性回归实现',
    description: '从零实现线性回归并分析梯度下降收敛性。',
    deadline: '2025-09-25T18:00:00Z', created_at: '2025-09-12T08:00:00Z',
    my_submission: null, stats: { total_students: 30, submitted_count: 8, graded_count: 0 },
  },
  {
    id: 102, course_id: 5, title: '实验一：Wireshark 抓包分析',
    description: '抓取 HTTP 请求并分析三次握手与报文结构。',
    deadline: '2025-09-20T12:00:00Z', created_at: '2025-09-13T09:00:00Z',
    my_submission: null, stats: { total_students: 25, submitted_count: 12, graded_count: 5 },
  },
]

// ------------------------------------------------------------
// 知识库问答
// ------------------------------------------------------------
const kbSources: KBSource[] = [
  {
    knowledge_doc_id: 1,
    title: 'FastAPI 异步编程实践',
    chunk_index: 3,
    chunk_text: '在 FastAPI 中，使用 async def 声明路由处理函数即可获得异步支持，但需注意：同步阻塞代码应放入线程池，避免阻塞事件循环。',
    score: 0.92,
  },
  {
    knowledge_doc_id: 2,
    title: 'Redis 缓存与分布式锁',
    chunk_index: 7,
    chunk_text: '分布式锁通常借助 Redis 的 SET NX EX 命令实现，配合 Lua 脚本可保证「判断+加锁+设过期」的原子性。',
    score: 0.87,
  },
]

export function mockChatReply(question: string): KBChatResponse {
  return {
    session_id: 'mock-session-1',
    answer:
      `根据课程知识库中的资料，关于「${question.slice(0, 20)}」这个问题，我的理解如下：\n\n` +
      '**核心要点**\n\n' +
      '1. 异步编程的关键在于合理区分「I/O 密集型」与「CPU 密集型」任务，前者交给事件循环，后者放入线程池。\n' +
      '2. 分布式场景下的并发安全，通常需要结合「幂等 + 分布式锁」两道防线共同保证。\n\n' +
      '**示例**\n\n' +
      '```python\n' +
      'async def fetch(url):\n' +
      '    async with aiohttp.ClientSession() as session:\n' +
      '        return await session.get(url)\n' +
      '```\n\n' +
      '以上内容来自本课程知识库，详见下方来源引用。',
    sources: kbSources,
  }
}

/**
 * Mock：模拟文档处理状态推进（供状态轮询演示）
 * 处理中的文档（PARSING/CHUNKING/INDEXING）每次被轮询调用时推进一个阶段，
 * 最终到达 SUCCESS，让前端轮询体验真实可见。
 */
const STAGE_ORDER = [DocumentStatus.PARSING, DocumentStatus.CHUNKING, DocumentStatus.INDEXING, DocumentStatus.SUCCESS]

export function advanceMockDocStatus(docId: number): KnowledgeDocItem | null {
  const doc = mockKnowledgeDocs.find((d) => d.id === docId)
  if (!doc) return null
  const pending = [DocumentStatus.PENDING, DocumentStatus.PARSING, DocumentStatus.CHUNKING, DocumentStatus.INDEXING]
  if (pending.includes(doc.status)) {
    const idx = STAGE_ORDER.indexOf(doc.status)
    const next = STAGE_ORDER[idx + 1]
    if (next === DocumentStatus.SUCCESS) {
      doc.status = DocumentStatus.SUCCESS
      doc.chunk_count = Math.floor(Math.random() * 20) + 8
      doc.markdown_char_count = Math.floor(Math.random() * 20000) + 5000
    } else {
      doc.status = next
    }
    doc.updated_at = new Date().toISOString()
  }
  return { ...doc }
}

// ------------------------------------------------------------
// 课程公告（mock）
// ------------------------------------------------------------
export const mockAnnouncements: Announcement[] = [
  {
    id: 1, course_id: 1, title: '第一次作业截止提醒',
    content: '各位同学，第一次作业《实现异步爬虫》将于本周五 18:00 截止，请尚未提交的同学抓紧时间。提交前请仔细阅读评分标准，注意异常处理与文档注释。',
    pinned: true, created_by: 2, author_name: '李老师', created_at: '2025-09-12T09:00:00Z',
  },
  {
    id: 2, course_id: 1, title: '实验课调课通知',
    content: '本周四下午的实验课调整到周五上午 9:00，地点不变（实验楼 302），请同学们相互转告。',
    pinned: false, created_by: 2, author_name: '李老师', created_at: '2025-09-10T14:30:00Z',
  },
  {
    id: 3, course_id: 1, title: '课程知识库已上线',
    content: '本课程知识库已支持 AI 问答，同学们可以在「AI 问答」模块就课程内容提问，系统会基于课件与资料给出带来源引用的回答。欢迎体验！',
    pinned: false, created_by: 2, author_name: '李老师', created_at: '2025-09-05T10:00:00Z',
  },
]

// ------------------------------------------------------------
// 讨论区（mock）
// ------------------------------------------------------------
export const mockDiscussions: DiscussionPost[] = [
  {
    id: 1, course_id: 1, title: '异步爬虫的并发数设置多少比较合适？',
    content: '作业要求并发数不超过 10，但我在本地测试时发现并发太高会被目标网站限流，大家一般设置多少？',
    author_id: 11, author_name: '张同学', reply_count: 3, like_count: 5, liked: false,
    created_at: '2025-09-13T15:00:00Z',
    replies: [
      { id: 1, post_id: 1, content: '我一般设置 5，配合超时和重试，比较稳。', author_id: 12, author_name: '王同学', created_at: '2025-09-13T16:00:00Z' },
      { id: 2, post_id: 1, content: '可以加一个简单的限速器，配合 asyncio.Semaphore 控制并发。', author_id: 14, author_name: '陈静', created_at: '2025-09-13T17:30:00Z' },
      { id: 3, post_id: 1, content: '建议参考课程里讲的指数退避策略。', author_id: 2, author_name: '李老师', created_at: '2025-09-13T20:00:00Z' },
    ],
  },
  {
    id: 2, course_id: 1, title: 'RAG 检索问答的向量库选择',
    content: '作业二里向量库用 Milvus 还是用 FAISS 更好？两者在部署和检索效果上有什么区别？',
    author_id: 13, author_name: '李小明', reply_count: 2, like_count: 3, liked: true,
    created_at: '2025-09-14T10:00:00Z',
    replies: [
      { id: 4, post_id: 2, content: 'Milvus 适合生产环境，支持分布式；FAISS 轻量，适合本地实验。', author_id: 2, author_name: '李老师', created_at: '2025-09-14T11:00:00Z' },
      { id: 5, post_id: 2, content: '课程实验环境已经配好 Milvus，建议直接用 Milvus。', author_id: 14, author_name: '陈静', created_at: '2025-09-14T12:00:00Z' },
    ],
  },
  {
    id: 3, course_id: 1, title: '第三次作业成绩出来了，大家多少分？',
    content: '看到成绩了，96 分，分布式锁那部分老师给了很详细的评语。',
    author_id: 11, author_name: '张同学', reply_count: 1, like_count: 2, liked: false,
    created_at: '2025-08-30T09:00:00Z',
    replies: [
      { id: 6, post_id: 3, content: '88 分，Lua 脚本那块我写复杂了。', author_id: 12, author_name: '王同学', created_at: '2025-08-30T10:00:00Z' },
    ],
  },
]

// ------------------------------------------------------------
// 消息通知（mock）
// ------------------------------------------------------------
export const mockNotifications: NotificationItem[] = [
  { id: 1, type: NotificationType.ANNOUNCEMENT, title: '新公告：第一次作业截止提醒', content: '《高级 Python 编程》发布了新公告', read: false, course_id: 1, created_at: '2025-09-12T09:00:00Z' },
  { id: 2, type: NotificationType.GRADED, title: '作业已批改', content: '《第三次作业：并发安全实践》已批改，得分 96', read: false, course_id: 1, created_at: '2025-08-30T08:00:00Z' },
  { id: 3, type: NotificationType.DEADLINE, title: '作业即将截止', content: '《第二次作业：实现 RAG 检索问答》将于 9-22 截止', read: true, course_id: 1, created_at: '2025-09-20T10:00:00Z' },
  { id: 4, type: NotificationType.REPLY, title: '收到新回复', content: '李老师回复了你的帖子《异步爬虫的并发数设置多少比较合适？》', read: true, course_id: 1, created_at: '2025-09-13T20:00:00Z' },
]
