/** 通用格式化工具 */
import dayjs from 'dayjs'

/** 格式化字节大小 */
export function formatSize(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined || bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const k = 1024
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), units.length - 1)
  return `${(bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

/** 格式化日期时间 */
export function formatDateTime(dt: string | null | undefined, fmt = 'YYYY-MM-DD HH:mm'): string {
  if (!dt) return '-'
  return dayjs(dt).format(fmt)
}

/** 格式化日期 */
export function formatDate(dt: string | null | undefined): string {
  if (!dt) return '-'
  return dayjs(dt).format('YYYY-MM-DD')
}

/** 相对时间（如：3天前、5小时前） */
export function fromNow(dt: string | null | undefined): string {
  if (!dt) return '-'
  const now = dayjs()
  const t = dayjs(dt)
  const diffMin = now.diff(t, 'minute')
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  const diffHour = now.diff(t, 'hour')
  if (diffHour < 24) return `${diffHour} 小时前`
  const diffDay = now.diff(t, 'day')
  if (diffDay < 30) return `${diffDay} 天前`
  return t.format('YYYY-MM-DD')
}

/** 距离截止时间的描述（用于作业） */
export function deadlineInfo(deadline: string): { text: string; urgent: boolean; overdue: boolean } {
  const now = dayjs()
  const t = dayjs(deadline)
  if (t.isBefore(now)) {
    return { text: `已截止 · ${t.format('MM-DD HH:mm')}`, urgent: false, overdue: true }
  }
  const diffHour = t.diff(now, 'hour')
  if (diffHour < 24) {
    return { text: `剩余 ${diffHour} 小时`, urgent: true, overdue: false }
  }
  const diffDay = t.diff(now, 'day')
  return { text: `剩余 ${diffDay} 天`, urgent: diffDay <= 2, overdue: false }
}

/** 用户角色名 */
export function roleName(role: number): string {
  return role === 2 ? '管理员' : role === 1 ? '教师' : '学生'
}

/** 头像/封面色调（沉稳教学蓝灰系，按名字 hash 取稳定色） */
const AVATAR_GRADIENTS = [
  ['#2d6cdf', '#4d8fe8'],
  ['#1a7a50', '#3aa37a'],
  ['#b7760a', '#d6902a'],
  ['#7a5cc4', '#9678d8'],
  ['#c04b54', '#d96b73'],
  ['#31859b', '#55a3b8'],
  ['#8a6642', '#a98a62'],
  ['#5a6b8a', '#7a8ba8'],
]
export function avatarGradient(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  const [a, b] = AVATAR_GRADIENTS[hash % AVATAR_GRADIENTS.length]
  return `linear-gradient(135deg, ${a}, ${b})`
}

/** 课程封面：按课程名生成沉稳的纯色渐变（学习通卡片风） */
const COURSE_COVERS: Array<[string, string]> = [
  ['#2d6cdf', '#1a52a8'],
  ['#31859b', '#23667a'],
  ['#7a5cc4', '#5b4294'],
  ['#1a7a50', '#12583a'],
  ['#b7760a', '#8a5a08'],
  ['#c04b54', '#8f353c'],
  ['#5a6b8a', '#3f4d64'],
  ['#8a6642', '#5f4730'],
]
export function courseCover(name: string): string {
  let hash = 0
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) >>> 0
  const [a, b] = COURSE_COVERS[hash % COURSE_COVERS.length]
  return `linear-gradient(135deg, ${a}, ${b})`
}

/** 文件扩展名图标类型 */
export function fileCategory(fileName: string): 'image' | 'pdf' | 'word' | 'excel' | 'ppt' | 'video' | 'audio' | 'code' | 'archive' | 'text' | 'markdown' | 'other' {
  const ext = (fileName.split('.').pop() || '').toLowerCase()
  const map: Record<string, ReturnType<typeof fileCategory>> = {
    jpg: 'image', jpeg: 'image', png: 'image', gif: 'image', webp: 'image', svg: 'image', bmp: 'image',
    pdf: 'pdf',
    doc: 'word', docx: 'word',
    xls: 'excel', xlsx: 'excel', csv: 'excel',
    ppt: 'ppt', pptx: 'ppt',
    mp4: 'video', avi: 'video', mkv: 'video', mov: 'video', webm: 'video',
    mp3: 'audio', wav: 'audio', flac: 'audio', ogg: 'audio',
    py: 'code', js: 'code', ts: 'code', java: 'code', cpp: 'code', c: 'code', go: 'code', rs: 'code', html: 'code', css: 'code', sql: 'code', sh: 'code',
    zip: 'archive', rar: 'archive', '7z': 'archive', tar: 'archive', gz: 'archive',
    txt: 'text', log: 'text',
    md: 'markdown',
  }
  return map[ext] || 'other'
}

/** 是否可直接预览 */
export function canPreview(fileName: string): boolean {
  return ['image', 'pdf', 'video', 'audio', 'text', 'markdown', 'code'].includes(fileCategory(fileName))
}

/** 文件类型中文标签（用于表格展示） */
export function fileTypeLabel(fileName: string): string {
  const map: Record<ReturnType<typeof fileCategory>, string> = {
    image: '图片',
    pdf: 'PDF',
    word: 'Word 文档',
    excel: 'Excel 表格',
    ppt: 'PPT 演示',
    video: '视频',
    audio: '音频',
    code: '代码',
    archive: '压缩包',
    text: '文本',
    markdown: 'Markdown',
    other: '其他',
  }
  return map[fileCategory(fileName)]
}
