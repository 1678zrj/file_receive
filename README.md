# 云课堂

一个迷你在线教学平台，对标学习通。功能上想做的是「课程 → 资源 → 作业 → 知识库 → AI 问答」这条完整链路。

后端是我自己一行行手敲的，前端基本是 vibe coding 出来的 —— 所以后端结构上比较讲究，前端只求好用好看，两边风格不太统一，见谅。

## 技术栈

**后端**：FastAPI · SQLModel + PostgreSQL · Redis · Milvus · TaskIQ · LangGraph / LangChain · python-jose + passlib · orjson

**前端**：Vue 3 + Vite + TypeScript · Pinia · Vue Router · Element Plus · echarts · markdown-it + highlight.js + KaTeX · js-sha256

## 已经实现的

后端真接口、前端真对接的部分：

- 鉴权：JWT（access + refresh），refresh token 走 HttpOnly Cookie，401 自动刷新并重放原请求
- 权限：学生 / 教师 / 管理员三级 RBAC
- 文件上传：分片上传 init → chunk → merge → status，带 SHA-256 秒传和断点续传，文件合并在独立的 TaskIQ worker 里跑
- 课程 / 选课 / 课程资源：创建课程、选课、查课程学生列表、资源绑定与按课程查询
- 知识库：文档解析 → 分块 → 向量化入 Milvus，按课程隔离检索
- AI 问答：LangGraph 状态机，TaskIQ 异步执行，Redis Stream 推 SSE 流式输出，支持反问中断和恢复

前端界面这块是完整的：

- 登录注册、工作台（echarts 数据看板）、课程广场、我的课程
- 课程空间：概述 / 资源 / 作业 / 成绩 / 公告 / 讨论 / 学生管理
- 知识库管理：上传索引 + 状态展示 + 详情三视图（解析内容 / 原始文档 / 分块）
- AI 问答：全屏沉浸式对话，多会话并发、刷新不丢、SSE 断线续传、会话深链、导出 Markdown、公式与代码高亮
- 浅色 / 深色主题

## 还没实现的

后端只做了上面那几块，**常规业务接口大部分还空着**：

- 作业：发布 / 列表 / 详情 / 删除 / 提交 / 批改 / 待办提醒（数据表建了，接口没写）
- 成绩：教师成绩表、学生我的成绩
- 课程：课程列表、我教的课、我学的课、课程详情、改和删
- 选课：退课
- 文件：统一下载、统一预览；课程资源删除
- 知识库管理：文档列表 / 详情 / 删除 / 启停 / 分块编辑 / 重新索引
- 公告、讨论、消息通知、工作台统计：连数据表都还没建

所以界面上看着很全，但**不少页面是前端 mock 出来的**。`frontend/src/config.ts` 里有个 `USE_MOCK` 开关，默认 `true`：未实现的接口返回演示数据；改成 `false` 就全走真实后端，缺的接口会显示「接口尚未提供」的占位。后端补齐后不用改页面代码。

## 跑起来

需要 PostgreSQL、Redis、Milvus（Milvus 只有知识库和问答用得上，不启也能跑其余功能）。

```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 另开两个终端，跑两个队列的 worker
taskiq worker app.core.broker:merge_broker
taskiq worker app.core.broker:agent_broker

# 前端
cd frontend
npm install
npm run dev        # http://127.0.0.1:5173，/api 已代理到 127.0.0.1:8000
```

配置写在 `backend/.env`，键名统一以 `FR_` 开头（`FR_DATABASE_URL`、`FR_MILVUS_URI`、`FR_API_KEY` 等），这个文件不入库。

演示账号密码都是 `123456`：`teacher_li`（教师）、`student_zhang` / `student_wang`（学生）、`admin`。

## 说明

- 后端是手写的；前端是 vibe coding 的，重心在界面和交互体验。
- 目前算是个练手项目。
