/** 共享的 Markdown 渲染实例 */
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

export const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight(code: string, lang: string): string {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(code, { language: lang }).value}</code></pre>`
      } catch {
        /* noop */
      }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(code)}</code></pre>`
  },
})

export function renderMarkdown(text: string): string {
  return md.render(text || '')
}
