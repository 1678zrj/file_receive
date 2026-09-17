# 云课堂 · 前端

迷你学习通（云课堂）的前端项目，基于 **Vue 3 + Vite + TypeScript + Element Plus** 构建，
设计风格参考学习通 / 超星等成熟在线教学平台（严肃沉稳、信息密集、克制蓝色主色）。

## 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3（Composition API + `<script setup>`） |
| 构建 | Vite 5 |
| 语言 | TypeScript（严格模式） |
| UI | Element Plus + @element-plus/icons-vue |
| 状态 | Pinia |
| 路由 | Vue Router 4 |
| 请求 | Axios（Token 自动刷新 / 401 静默重放） |
| 文件 | js-sha256（分片断点续传 + 秒传）、markdown-it、highlight.js |

## 快速开始

```bash
cd frontend
npm install
npm run dev          # 启动开发服务器，默认 http://127.0.0.1:5173
```

> 开发服务器通过 Vite 代理把 `/api` 转发到 `http://127.0.0.1:8000`（FastAPI 后端），
> 因此需要**先启动后端**。

生产构建与验证：

```bash
npm run typecheck    # 仅类型检查
npm run build        # 类型检查 + 打包到 dist/
```

## 登录账号（后端 seed 数据）

| 账号 | 角色 | 密码 |
|------|------|------|
| `teacher_li` | 教师 | 123456 |
| `student_zhang` | 学生 | 123456 |
| `student_wang` | 学生 | 123456 |
| `admin` | 管理员 | 123456 |

## Mock 模式开关

后端目前**尚未提供部分接口**（课程列表/详情、作业、知识库列表、问答等）。
为了让界面立即可预览，前端内置了一套逼真的演示数据：

```ts
// src/config.ts
export const config = {
  USE_MOCK: true,   // true = 缺失接口返回演示数据；false = 全部走真实后端
  MOCK_DELAY: 250,  // 模拟网络延迟（毫秒）
}
```

- 后端补齐接口后，把 `USE_MOCK` 改为 `false`，前端**无需改动其他代码**即可切回真实数据。
- 缺失接口的完整契约见 [`docs/BACKEND_API.md`](./docs/BACKEND_API.md)（按模块划分，含每个接口的状态 ✅/❌）。
  早期版本 [`docs/MISSING_APIS.md`](./docs/MISSING_APIS.md) 已被它取代。

## 已对接的真实接口

- 鉴权：`POST /auth/login`、`POST /auth/refresh`、`GET /auth/me`
- 注册：`POST /user/register`
- 课程：`POST /course/register`（教师）
- 资源：`POST /course-resource/register`、`GET /course-resource/course/{id}`
- 选课：`POST /enrollment/register`、`POST /enrollment/{course_id}/students`
- 知识库：`POST /kb/course`（索引）
- 上传（分片断点续传）：`POST /upload/init` → `chunk` → `merge` → `status` 轮询
- Agent 问答：`POST /agent/thread`、`POST /agent/threads/{id}/run`、`POST .../resume`、`GET .../stream`（SSE）、
  `GET /agent/threads`（会话列表）、`GET /agent/threads/{id}/messages`（历史消息）、`DELETE /agent/threads/{id}`（删除会话）

## 功能概览

- 登录 / 注册（含演示账号一键填充）
- 工作台（站点概览 + 数据看板 + 待办 + 快捷入口）：
  - **统计看板**：作业提交率环形图 + 成绩分布柱状图（echarts）
  - **待办**：即将截止/待提交的作业提醒
- 课程广场（浏览 / 搜索 / 选课）
- 我的课程（教师我教的 · 学生我学的，教师可创建课程）
- **课程空间**（学习通式：左侧课程内导航 + 右侧内容区）：
  - **课程概述**：课程简介 + 最新公告 + 进度概览
  - **课程资源**：分片上传（断点续传/秒传/并发）+ 列表 + 预览 + 下载 + 删除
  - **作业**：发布 / 列表 / 提交 / 批改
  - **成绩**：教师看「学生 × 作业」二维成绩表；学生看「我的成绩」
  - **公告**：教师发布课程公告（置顶/普通）
  - **讨论**：发帖 / 回帖 / 点赞
  - **学生管理**：学生列表（仅教师可见）
- **知识库管理**（独立模块）：课程选择器 + 文档上传索引 + 状态展示 + 启停/删除 + **详情预览**
  - 详情抽屉三视图：**解析内容**（Markdown 渲染）/ **原始文档**（预览下载）/ **分块列表**
- **AI 问答**（独立全屏对话模块）：课程选择器（**首次进入默认选中第一门课**）+ 沉浸式对话 + 来源引用追溯
  - **多会话**：左侧会话列表（后端 `GET /agent/threads` 为准，按更新时间倒序），新建 / 切换 / 删除（删除走 `DELETE /agent/threads/{id}` 软删除）；支持**标题+内容搜索**与**今天/昨天/近 7 天/更早**分组
  - **会话深链**：URL 带 `?thread=<id>`，刷新 / 收藏 / 前后退都能精确回到同一会话
  - **多标签页同步**：删除会话、新建会话跨标签页同步；同一会话被另一页接管时自动让出，避免两条流互相覆盖
  - **多会话并发**：不同会话可同时提问，各自独立接流，切换会话不中断后台 SSE
  - **服务端历史**：切到某会话时懒加载 `GET /agent/threads/{id}/messages`，`tool_call` + `tool_result` 合并成一张工具卡片
  - **过程可视化**：思考 / 正文 / 工具调用按发生顺序交替渲染（与后端 `parts` 同构）
  - **流式性能**：token 级增量按帧合并后再写状态（实测组件渲染降 2~8 倍），流式期间关闭代码高亮、定稿后补一次完整渲染；正文渲染按内容长度分档节流，短回答按帧刷新，观感不打折
  - **断线续传**：记住 Redis Stream 事件 id，断线后带 `Last-Event-ID` 增量重连（指数退避），不重复也不丢内容；心跳作为存活信号，长时间无响应会如实提示
  - **运行状态如实展示**：排队中 / 思考中 / 等待你的回答 / 重连中 / 长时间无响应 / 已停止接收
  - **停止与继续**：可停止接收（前端断开，不丢已收内容）并随时继续接收
  - **刷新不丢**：localStorage 秒开 + 未完成的 run 重连 SSE 重放 + 终态后回拉服务端校正
  - **中断问答**：Agent 通过 `ask_user_question` 反问时，提问表单与「已回复」卡片都是 **parts 时间轴上的一个块**，留在原位（回答后模型继续输出的内容排在它后面）；**位置与回答都从服务端数据还原**（锚点是那个 `ask_user_question` 的 tool_call 块 + 配对的 tool_result），因此刷新/换设备后依然准确；若某轮正停在等回答，刷新后还能继续回答并自动接回后续输出
  - **失败重试**：发送失败可在消息上重试，**复用同一幂等键**，不会因为重试多出一轮对话
  - **复制与导出**：回答一键复制、代码块悬浮复制按钮、整段会话导出为 Markdown
- **消息通知中心**：顶栏铃铛 + 未读红点 + 分类消息（公告/批改/截止提醒/回复）
- 个人中心

### 后台上传任务中心

课程资源、知识库文档的上传已改为**后台多文件并发上传**：

- 选择文件后立即入队，**不必停留在上传页**，可继续浏览其他页面
- 右下角悬浮任务中心实时展示每个文件的进度、速度、已传大小
- 支持多文件并发（默认 2 个）、失败重试、手动取消
- 队列按「真正占用槽位的任务数」限流（`hashing/uploading/merging`），排队中的任务不占槽位；取消排队中的任务会落到「已取消」终态
- 上传完成后自动落地：课程资源自动绑定到课程、知识库文档自动弹出索引设置；**若完成时你已离开该页面，回到页面时会自动补上**
- 资源上传完成后**自动用文件名做标题绑定到课程**（无弹窗打扰）；知识库上传完成后自动进入「索引设置」
- 大文件仍走分片断点续传 + SHA-256 秒传

> 知识库相关功能已**独立成模块**，从左侧导航「AI 助手」分组进入，也可从课程详情页跳转（携带课程 id）。

## 目录结构

```
src/
├── config.ts              # 全局配置（Mock 开关）
├── api/
│   ├── http.ts            # Axios 封装（token 刷新）
│   ├── index.ts           # 接口层（真实 + mock 分支）
│   ├── types.ts           # 类型定义（对齐后端 schemas）
│   └── mock.ts            # 内置演示数据
├── stores/                # auth / course / knowledge
├── composables/           # useKnowledgeDocs / useKbChat 可复用逻辑
├── router/                # 路由 + 登录守卫
├── layouts/               # MainLayout 主框架（分组导航）
├── views/                 # 页面（含 KnowledgeView / QaView）
├── components/            # 通用组件 + 课程子面板
├── utils/                 # format / uploader（分片上传器）
└── styles/                # 全局设计系统
```

## 说明

- 本目录**仅包含前端代码**，后端位于项目根目录 `backend/`，前端不会改动后端。
- 文件上传的分片大小默认 5MB，与后端 `settings.chunk_size` 保持一致。
