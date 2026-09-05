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
const ACTIVE_STATUSES = ['pending', 'hashing', 'uploading', 'merging']

export const useUploadTaskStore = defineStore('uploadTask', {
  state: () => ({
    tasks: [] as UploadTask[],
    expanded: false,
  }),
  getters: {
    activeCount: (s) => s.tasks.filter((t) => ACTIVE_STATUSES.includes(t.status)).length,
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
      // 并发控制：等待进行中的任务数降到上限以下
      while (this.activeCount > MAX_CONCURRENT) {
        await new Promise((r) => setTimeout(r, 400))
        if (task.controller?.signal.aborted) return
      }
      if (task.controller?.signal.aborted) return

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
