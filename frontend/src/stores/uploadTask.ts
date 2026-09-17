/**
 * 全局文件上传任务中心（Pinia）
 * 支持多文件并发上传队列，上传全程在后台运行，不影响用户浏览其它页面。
 * 任务状态：pending → hashing → uploading → merging → completed(秒传/成功) 或 failed
 */
import { defineStore } from 'pinia'
import { markRaw } from 'vue'
import { uploadFile, type UploadProgress } from '@/utils/uploader'

export interface UploadTask {
  id: string
  fileName: string
  size: number
  source: string
  courseId?: number
  status: 'pending' | 'hashing' | 'uploading' | 'merging' | 'completed' | 'failed'
  instant?: boolean
  percent: number
  uploadedBytes: number
  speed: number
  fileRecordId?: number
  error?: string
  controller?: AbortController
  /** 保留 File 引用，便于重试 */
  file?: File
}

let _idSeq = 0
function nextId() {
  return `upload-${Date.now()}-${_idSeq++}`
}

/** 最大并发上传任务数 */
const MAX_CONCURRENT = 2
/** 尚未结束的状态（含排队中）—— 用于「上传中心」徽章 */
const ACTIVE_STATUSES = ['pending', 'hashing', 'uploading', 'merging']
/**
 * 真正占用上传槽位的状态。
 * `pending` 只是「已入队、还没轮到」，不占槽位 —— 并发闸门必须只看这几个，
 * 否则排队中的任务会把自己算进"进行中"，把计数永久顶在上限之上（见 _run 里的说明）。
 */
const RUNNING_STATUSES = ['hashing', 'uploading', 'merging']
/** 排队等待空槽时的轮询间隔 */
const SLOT_POLL_INTERVAL = 200

export const useUploadTaskStore = defineStore('uploadTask', {
  state: () => ({
    tasks: [] as UploadTask[],
    expanded: false,
  }),
  getters: {
    /** 未结束任务数（含排队中），给上传中心徽章用 */
    activeCount: (s) => s.tasks.filter((t) => ACTIVE_STATUSES.includes(t.status)).length,
    /** 正在占用上传槽位的任务数 —— 并发闸门只看它 */
    runningCount: (s) => s.tasks.filter((t) => RUNNING_STATUSES.includes(t.status)).length,
    /** 折叠徽章展示的总览进度（进行中任务平均进度） */
    overall(state): number {
      const active = state.tasks.filter((t) => ['hashing', 'uploading', 'merging'].includes(t.status))
      if (active.length === 0) return 0
      return Math.round(active.reduce((sum, t) => sum + t.percent, 0) / active.length)
    },
  },
  actions: {
    /** 入队一个文件并异步启动上传，返回任务 id */
    enqueue(opts: { file: File; source: string; courseId?: number; fileName?: string }): string {
      const id = nextId()
      const controller = new AbortController()
      const task: UploadTask = {
        id,
        fileName: opts.fileName || opts.file.name,
        size: opts.file.size,
        source: opts.source,
        courseId: opts.courseId,
        status: 'pending',
        percent: 0,
        uploadedBytes: 0,
        speed: 0,
        // markRaw 防止 File / AbortController 被 reactive 化，
        // 否则 reactive(File).slice() 会抛 "Illegal invocation"
        controller: markRaw(controller),
        file: markRaw(opts.file),
      }
      this.tasks.unshift(task)
      this.expanded = true
      // 关键：传 id，让 _run 从 reactive 数组里取回 proxy 对象，
      // 避免修改「原始对象」导致响应式断裂（进度不刷新）。
      this._run(id)
      return id
    },

    /** 后台执行上传（并发受控）。taskId 用于从 reactive 数组取回响应式对象。 */
    async _run(taskId: string) {
      const task = this.tasks.find((t) => t.id === taskId)
      const file = task?.file
      if (!task || !file) return

      /*
       * 并发控制：等待「正在跑的任务数」降到上限以下。
       *
       * ⚠️ 这里踩过坑（老师批量上传时「只有前两个成功、其它一直不动」）：
       * 原来用的是 `activeCount > MAX_CONCURRENT`，而 activeCount 把 status='pending'
       * 的排队任务也算成进行中。于是：前 2 个传完后，剩下 3 个全是 pending，
       * activeCount 恒为 3，而它们等的正是「activeCount 降到 2 以下」——
       * 它们自己构成了这个 3，永远等不到 → 队列死锁。
       * 正确做法是只统计真正占槽位的状态，并且用 `>=` 判断。
       */
      while (this.runningCount >= MAX_CONCURRENT) {
        if (task.controller?.signal.aborted) {
          // 在排队期间被取消：必须落到终态，否则它会永远停在 pending，
          // 既占着「未结束」的计数，上传中心也只有「取消」按钮（没有「移除」），无法清理。
          task.status = 'failed'
          task.error = '已取消'
          return
        }
        await new Promise((r) => setTimeout(r, SLOT_POLL_INTERVAL))
      }
      if (task.controller?.signal.aborted) {
        task.status = 'failed'
        task.error = '已取消'
        return
      }
      // 占位：从上面判断到这里没有 await，多出来的等待者不会抢到同一个槽
      task.status = 'hashing'

      let lastBytes = 0
      let lastTime = Date.now()
      try {
        const result = await uploadFile(
          file,
          (p: UploadProgress) => {
            const ctrl = task.controller
            if (ctrl?.signal.aborted) throw new DOMException('已取消', 'AbortError')
            task.percent = p.percent
            if (p.uploadedBytes != null) task.uploadedBytes = p.uploadedBytes
            if (p.phase === 'uploading') {
              const now = Date.now()
              const dt = (now - lastTime) / 1000
              if (dt > 0.5) {
                task.speed = (task.uploadedBytes - lastBytes) / dt
                lastBytes = task.uploadedBytes
                lastTime = now
              }
            }
            // 映射 uploader 阶段到任务状态（init 归入 hashing 展示）
            if (p.phase === 'completed') task.status = 'completed'
            else if (p.phase === 'init') task.status = 'hashing'
            else if (['hashing', 'uploading', 'merging'].includes(p.phase)) task.status = p.phase as UploadTask['status']
          },
          task.controller?.signal,
        )
        task.status = 'completed'
        task.instant = result.instant
        task.fileRecordId = result.file_record_id
        task.percent = 100
        task.uploadedBytes = task.size
      } catch (e: any) {
        if (e?.name === 'AbortError') {
          task.status = 'failed'
          task.error = '已取消'
        } else {
          task.status = 'failed'
          task.error = e?.message || '上传失败'
        }
      }
    },

    /** 取消任务 */
    cancel(id: string) {
      const t = this.tasks.find((x) => x.id === id)
      if (t) t.controller?.abort()
    },

    /** 重试失败任务 */
    retry(id: string) {
      const t = this.tasks.find((x) => x.id === id)
      if (!t || !t.file) return
      // 重置并重新执行
      t.status = 'pending'
      t.percent = 0
      t.uploadedBytes = 0
      t.speed = 0
      t.error = undefined
      t.controller = markRaw(new AbortController())
      this._run(t.id)
    },

    /** 移除任务 */
    remove(id: string) {
      const idx = this.tasks.findIndex((x) => x.id === id)
      if (idx >= 0) this.tasks.splice(idx, 1)
    },

    /** 清除所有已完成/失败任务 */
    clearFinished() {
      this.tasks = this.tasks.filter((t) => ACTIVE_STATUSES.includes(t.status))
    },

    toggle() {
      this.expanded = !this.expanded
    },
  },
})
