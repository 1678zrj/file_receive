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
- 缺失接口的完整契约见 [`docs/MISSING_APIS.md`](./docs/MISSING_APIS.md)。

## 已对接的真实接口

- 鉴权：`POST /auth/login`、`POST /auth/refresh`、`GET /auth/me`
- 注册：`POST /user/register`
- 课程：`POST /course/register`（教师）
- 资源：`POST /course-resource/register`、`GET /course-resource/course/{id}`
- 选课：`POST /enrollment/register`、`POST /enrollment/{course_id}/students`
- 知识库：`POST /kb/course`（索引）
- 上传（分片断点续传）：`POST /upload/init` → `chunk` → `merge` → `status` 轮询

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
- **AI 问答**（独立全屏对话模块）：课程选择器 + 沉浸式对话 + 来源引用追溯
- **消息通知中心**：顶栏铃铛 + 未读红点 + 分类消息（公告/批改/截止提醒/回复）
- 个人中心

### 后台上传任务中心

课程资源、知识库文档的上传已改为**后台多文件并发上传**：

- 选择文件后立即入队，**不必停留在上传页**，可继续浏览其他页面
- 右下角悬浮任务中心实时展示每个文件的进度、速度、已传大小
- 支持多文件并发（默认 2 个）、失败重试、手动取消
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
