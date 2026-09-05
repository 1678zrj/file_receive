/**
 * 知识库问答对话逻辑（可复用组合式函数）
 * 供「AI 问答独立页」与「课程详情-问答 tab」共享。
 */
import { nextTick, ref } from 'vue'
import { kbApi } from '@/api'
import type { ChatMessage } from '@/api/types'

export function useKbChat(getCourseId: () => number | null) {
  const messages = ref<ChatMessage[]>([])
  const input = ref('')
  const answering = ref(false)
  const apiMissing = ref(false)
  const sessionId = ref<string | undefined>(undefined)
  const msgBox = ref<HTMLElement>()
  const atBottom = ref(true)
  const expandedSource = ref<string | null>(null)

  function onScroll() {
    const el = msgBox.value
    if (!el) return
    atBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 60
  }

  async function scrollToBottom(force = false) {
    await nextTick()
    const el = msgBox.value
    if (el && (force || atBottom.value)) el.scrollTop = el.scrollHeight
  }

  function ask(text: string) {
    input.value = text
    send()
  }

  let abortFlag = false

  async function send() {
    const courseId = getCourseId()
    const question = input.value.trim()
    if (!question || answering.value || courseId == null) return
    input.value = ''
    abortFlag = false

    messages.value.push({
      id: `u-${Date.now()}`,
      role: 'user',
      content: question,
      created_at: new Date().toISOString(),
    })
    const aiMsg: ChatMessage = {
      id: `a-${Date.now()}`,
      role: 'assistant',
      content: '',
      streaming: true,
      created_at: new Date().toISOString(),
    }
    messages.value.push(aiMsg)
    answering.value = true
    scrollToBottom()

    try {
      const res = await kbApi.chat({ course_id: courseId, question, session_id: sessionId.value })
      sessionId.value = res.session_id
      await typewrite(aiMsg, res.answer)
      aiMsg.sources = res.sources
    } catch (e: any) {
      if (e?.status === 404 || e?.status === 405) {
        apiMissing.value = true
        await typewrite(
          aiMsg,
          '**知识库问答接口尚未在后端提供**，我暂时无法真正检索课程内容。\n\n' +
            '建议后端补充以下接口后我就能正常工作：\n\n' +
            '- `POST /api/v1/kb/chat` — 知识库问答（推荐支持 SSE 流式输出）\n' +
            '- 请求体：`{ course_id, question, session_id? }`\n' +
            '- 响应：`{ answer, sources[], session_id }`',
        )
      } else {
        await typewrite(aiMsg, `出错了：${e?.message || '请求失败，请稍后重试'}`)
      }
    } finally {
      aiMsg.streaming = false
      answering.value = false
      scrollToBottom(true)
    }
  }

  async function typewrite(msg: ChatMessage, fullText: string) {
    const step = Math.max(2, Math.floor(fullText.length / 120))
    for (let i = 0; i < fullText.length; i += step) {
      if (abortFlag) {
        msg.content += '\n\n*（已停止生成）*'
        return
      }
      msg.content = fullText.slice(0, i + step)
      if (atBottom.value) scrollToBottom()
      await new Promise((r) => setTimeout(r, 16))
    }
    msg.content = fullText
  }

  function stop() {
    abortFlag = true
  }

  function clear() {
    messages.value = []
    sessionId.value = undefined
  }

  return {
    messages,
    input,
    answering,
    apiMissing,
    msgBox,
    atBottom,
    expandedSource,
    onScroll,
    scrollToBottom,
    ask,
    send,
    stop,
    clear,
  }
}
