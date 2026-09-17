/** 共享的 Markdown 渲染实例 */
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

/**
 * 自定义代码块渲染：外面包一层 `.md-code`，右上角放一个复制按钮。
 *
 * 按钮的点击**不做在这里**（这里只产出 HTML 字符串），而是由使用方在容器上做事件委托，
 * 点击时从同级的 `<code>` 里读 textContent 复制 —— 这样不用把代码内容重复塞进 data 属性。
 * 配套样式在 `styles/main.css`（`v-html` 注入的节点吃不到组件的 scoped 样式）。
 */
function installFence(instance: MarkdownIt, highlight: boolean) {
  instance.renderer.rules.fence = (tokens, idx) => {
    const token = tokens[idx]
    const lang = (token.info || '').trim().split(/\s+/)[0] || ''
    const code = token.content
    const esc = instance.utils.escapeHtml
    let body: string
    if (highlight && lang && hljs.getLanguage(lang)) {
      try {
        body = `<pre class="hljs"><code>${hljs.highlight(code, { language: lang }).value}</code></pre>`
      } catch {
        body = `<pre class="hljs"><code>${esc(code)}</code></pre>`
      }
    } else {
      // 流式期间（highlight=false）也保持同样的外层结构，只少了高亮 span，
      // 这样定稿时刻的重新渲染不会产生布局跳动
      body = `<pre class="hljs"><code>${esc(code)}</code></pre>`
    }
    const label = esc(lang || 'text')
    return (
      `<div class="md-code" data-lang="${label}">` +
      `<button type="button" class="md-code-copy" title="复制代码">复制</button>` +
      body +
      `</div>\n`
    )
  }
}

/** 完整渲染（带代码高亮）——用于定稿内容、知识库预览等 */
export const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})
installFence(md, true)

/**
 * 轻量渲染（不做代码高亮）——流式输出期间使用。
 *
 * highlight.js 是流式渲染里最贵的一步：内容每增长一点就要把整段代码块重新高亮一遍。
 * 流式过程中先用这个实例，等收到终态再做一次带高亮的完整渲染。
 */
const mdPlain: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})
installFence(mdPlain, false)

export interface RenderMarkdownOptions {
  /** 是否做代码高亮，默认 true。流式期间传 false */
  highlight?: boolean
}

export function renderMarkdown(text: string, options: RenderMarkdownOptions = {}): string {
  const instance = options.highlight === false ? mdPlain : md
  return instance.render(text || '')
}
