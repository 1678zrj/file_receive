/**
 * 把会话导出为 Markdown 文本（纯函数，便于复用与测试）
 */
import type { AgentChatMessage } from '@/api/types'

function pad(n: number): string {
  return n < 10 ? `0${n}` : `${n}`
}

function fmt(ts: string): string {
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ts
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes(),
  )}`
}

/** 助手消息里除正文以外的过程块（思考 / 工具调用）折叠成 <details>，导出后依然可读但不喧宾夺主 */
function renderAssistant(msg: AgentChatMessage): string {
  const out: string[] = []
  for (const part of msg.parts) {
    if (part.type === 'text') {
      if (part.content) out.push(part.content)
    } else if (part.type === 'thought') {
      if (part.content) {
        out.push(
          ['<details>', '<summary>思考过程</summary>', '', part.content, '', '</details>'].join('\n'),
        )
      }
    } else if (part.type === 'tool_call') {
      const name = part.name || 'tool'
      const head = `🔧 工具调用：${name}（${part.status || 'completed'}）`
      const body: string[] = []
      if (part.args && Object.keys(part.args).length) {
        body.push('参数：`' + JSON.stringify(part.args) + '`')
      }
      if (part.content) body.push('返回：\n\n```\n' + part.content + '\n```')
      out.push(['<details>', `<summary>${head}</summary>`, '', body.join('\n\n'), '', '</details>'].join('\n'))
    } else if (part.type === 'interrupt') {
      const lines: string[] = []
      if (part.interrupt?.questions?.length) {
        for (const q of part.interrupt.questions) {
          lines.push(`**❓ ${q.header || q.question}**`, '', q.question)
        }
      }
      if (part.answers?.length) {
        lines.push('', '已回复：')
        for (const a of part.answers) {
          lines.push(`- ${a.question} → ${a.selected.length ? a.selected.join('、') : '（空）'}`)
        }
      }
      if (lines.length) out.push(lines.join('\n'))
    } else if (part.content) {
      // 未知类型也保留内容，避免导出丢信息
      out.push(part.content)
    }
  }
  if (out.length === 0 && msg.content) out.push(msg.content)
  return out.join('\n\n')
}

export function sessionToMarkdown(title: string, messages: AgentChatMessage[]): string {
  const lines: string[] = []
  lines.push(`# ${title || '会话记录'}`)
  lines.push('')
  lines.push(`> 导出时间：${fmt(new Date().toISOString())}　共 ${messages.length} 条消息`)
  lines.push('')

  messages.forEach((m, i) => {
    if (m.role === 'user') {
      lines.push(`## ${i + 1}. 🙋 我`)
      if (m.scopeLabel) lines.push(`> 知识库：${m.scopeLabel}`)
      lines.push('')
      lines.push(m.content)
      lines.push('')
    } else {
      lines.push(`## ${i + 1}. 🤖 助手`)
      if (m.scopeLabel) lines.push(`> 知识库：${m.scopeLabel}`)
      lines.push('')
      lines.push(renderAssistant(m))
      lines.push('')
    }
  })

  return lines.join('\n').replace(/\n{3,}/g, '\n\n')
}

/** 触发浏览器下载 */
export function downloadText(filename: string, text: string, mime = 'text/markdown;charset=utf-8') {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  // 释放对象 URL（稍等，避免部分浏览器还没开始下载就失效）
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** 把标题转成安全的文件名 */
export function safeFileName(title: string): string {
  const base = (title || '会话记录').replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 40) || '会话记录'
  return `${base}.md`
}
