/**
 * 文件分片上传器
 * 完整对接后端断点续传体系：
 *   1. 计算全量 SHA-256（分块流式计算，避免大文件 OOM）
 *   2. POST /upload/init 初始化（命中相同 hash 则秒传）
 *   3. 并发上传缺失分片（Content-Type: application/octet-stream 原始字节流）
 *   4. POST /upload/{upload_id}/merge 触发异步合并（202）
 *   5. 轮询 GET /upload/{upload_id}/status 直至 completed
 */
import { sha256 } from 'js-sha256'
import { uploadApi } from '@/api'
import { UploadStatus } from '@/api/types'

/** 与后端 settings.chunk_size 保持一致：5MB */
export const DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024
/** 并发上传分片数 */
const CONCURRENCY = 4
/** 单分片失败重试次数 */
const MAX_RETRY = 3

export interface UploadProgress {
  /** 当前阶段 */
  phase: 'hashing' | 'init' | 'uploading' | 'merging' | 'completed' | 'failed'
  /** 已上传分片数 */
  uploaded: number
  /** 总分片数 */
  total: number
  /** 0-100 百分比（含 hash 阶段估算） */
  percent: number
  /** 已上传字节数（用于计算实时速度） */
  uploadedBytes?: number
  /** 文件总字节数 */
  totalBytes?: number
  /** 实时上传速度（字节/秒，由 UI 层估算） */
  speed?: number
  /** 错误信息 */
  error?: string
  /** 秒传命中 */
  instant?: boolean
}

export interface UploadResult {
  file_record_id: number
  /** 是否秒传 */
  instant: boolean
}

/**
 * 分块计算文件 SHA-256（每次读 16MB，出让主线程，不卡 UI）
 */
export async function hashFile(file: File | Blob, onProgress?: (percent: number) => void): Promise<string> {
  const hasher = sha256.create()
  const SLICE = 16 * 1024 * 1024
  const total = file.size
  let offset = 0
  while (offset < total) {
    const buf = await file.slice(offset, offset + SLICE).arrayBuffer()
    hasher.update(new Uint8Array(buf))
    offset += SLICE
    onProgress?.(Math.round((Math.min(offset, total) / total) * 100))
    // 出让主线程，保持页面响应
    await new Promise((r) => setTimeout(r, 0))
  }
  return hasher.hex()
}

function fileExt(name: string): string {
  const idx = name.lastIndexOf('.')
  return idx >= 0 ? name.slice(idx + 1).toLowerCase() : ''
}

/**
 * 上传一个文件，返回 file_record_id
 * @param file     浏览器 File 对象
 * @param onProgress 进度回调
 * @param signal   可选：取消信号
 */
export async function uploadFile(
  file: File,
  onProgress?: (p: UploadProgress) => void,
  signal?: AbortSignal,
): Promise<UploadResult> {
  const totalSize = file.size
  if (totalSize === 0) throw new Error('不支持上传空文件（0 字节）')

  const chunkSize = DEFAULT_CHUNK_SIZE
  const totalChunks = Math.max(1, Math.ceil(totalSize / chunkSize))

  const report = (p: Partial<UploadProgress>) => {
    onProgress?.({
      phase: 'hashing',
      uploaded: 0,
      total: totalChunks,
      percent: 0,
      totalBytes: totalSize,
      uploadedBytes: 0,
      ...p,
    } as UploadProgress)
  }

  // ---- 1. 计算 Hash ----
  report({ phase: 'hashing', percent: 0 })
  const fileHash = await hashFile(file, (pct) =>
    report({ phase: 'hashing', percent: Math.round(pct * 0.15) }),
  )
  if (signal?.aborted) throw new DOMException('已取消', 'AbortError')

  // ---- 2. 初始化会话 ----
  report({ phase: 'init', percent: 15 })
  const initRes = await uploadApi.init({
    file_name: file.name,
    file_hash: fileHash,
    file_ext: fileExt(file.name),
    mime_type: file.type || 'application/octet-stream',
    total_size: totalSize,
    chunk_size: chunkSize,
    total_chunks: totalChunks,
  })

  // 秒传命中
  if (initRes.instant_upload && initRes.file_record_id != null) {
    report({ phase: 'completed', uploaded: totalChunks, percent: 100, instant: true })
    return { file_record_id: initRes.file_record_id, instant: true }
  }
  if (!initRes.upload_id) throw new Error('初始化上传失败：未返回 upload_id')

  const uploadId = initRes.upload_id
  const alreadyUploaded = new Set(initRes.uploaded_chunks || [])
  if (signal?.aborted) throw new DOMException('已取消', 'AbortError')

  // ---- 3. 并发上传缺失分片 ----
  const pendingIndexes: number[] = []
  for (let i = 0; i < totalChunks; i++) {
    if (!alreadyUploaded.has(i)) pendingIndexes.push(i)
  }
  let doneCount = alreadyUploaded.size
  let uploadedBytes = alreadyUploaded.size * chunkSize

  const reportUpload = () => {
    report({
      phase: 'uploading',
      uploaded: doneCount,
      uploadedBytes,
      percent: 15 + Math.round((doneCount / totalChunks) * 80),
    })
  }
  reportUpload()

  const uploadOne = async (index: number) => {
    const blob = file.slice(index * chunkSize, Math.min((index + 1) * chunkSize, totalSize))
    let lastErr: unknown = null
    for (let attempt = 0; attempt <= MAX_RETRY; attempt++) {
      if (signal?.aborted) throw new DOMException('已取消', 'AbortError')
      try {
        await uploadApi.uploadChunk(uploadId, index, blob)
        doneCount++
        uploadedBytes += blob.size
        reportUpload()
        return
      } catch (e: any) {
        // 分片已存在（400 "already been uploaded"）视为成功，直接跳过
        if (e?.status === 400 && /already/i.test(e?.detail || '')) {
          doneCount++
          uploadedBytes += blob.size
          reportUpload()
          return
        }
        lastErr = e
        // 指数退避
        await new Promise((r) => setTimeout(r, 500 * Math.pow(2, attempt)))
      }
    }
    throw lastErr
  }

  // 简易并发池
  const executing = new Set<Promise<void>>()
  for (const idx of pendingIndexes) {
    const p = uploadOne(idx).finally(() => executing.delete(p))
    executing.add(p)
    if (executing.size >= CONCURRENCY) await Promise.race(executing)
  }
  await Promise.all(executing)

  if (signal?.aborted) throw new DOMException('已取消', 'AbortError')

  // ---- 4. 触发合并 ----
  report({ phase: 'merging', uploaded: totalChunks, percent: 96 })
  await uploadApi.merge(uploadId)

  // ---- 5. 轮询合并结果 ----
  const deadline = Date.now() + 10 * 60 * 1000
  while (Date.now() < deadline) {
    if (signal?.aborted) throw new DOMException('已取消', 'AbortError')
    const status = await uploadApi.getStatus(uploadId)
    if (status.status === UploadStatus.COMPLETED && status.file_record_id != null) {
      report({ phase: 'completed', uploaded: totalChunks, percent: 100 })
      return { file_record_id: status.file_record_id, instant: false }
    }
    if (status.status === UploadStatus.FAILED) {
      throw new Error(status.error_msg || '文件合并失败')
    }
    await new Promise((r) => setTimeout(r, 1000))
  }
  throw new Error('等待文件合并超时，请稍后重试')
}
