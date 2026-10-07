/** 共享的 Markdown 渲染实例 */
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import { mathPlugin } from './markdownMath'
import { escapeHtml } from './html'

export { escapeHtml }

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
    /*
     * 结构：外层卡片 + 顶部信息条（语言 + 复制按钮）+ 代码本体。
     * 以前是把语言和复制按钮**绝对定位浮在代码上**，会和第一行代码重叠；
     * 改成信息条后既不会压字，复制按钮也不用靠 hover 才出现。
     */
    return (
      `<div class="md-code">` +
      `<div class="md-code-bar">` +
      `<span class="md-code-lang">${label}</span>` +
      `<button type="button" class="md-code-copy" title="复制代码">复制</button>` +
      `</div>` +
      body +
      `</div>\n`
    )
  }
}

export interface MarkdownRendererOptions {
  /** 是否做代码高亮，默认 true */
  highlight?: boolean
  /**
   * 单个换行是否渲染成 <br>，默认 true（聊天场景模型输出更依赖这个）。
   * 文档类内容建议传 false —— 标准 Markdown 里段内换行不该变成硬换行。
   */
  breaks?: boolean
}

/**
 * 创建一个带「代码块复制按钮 + 数学公式」的 Markdown 渲染实例。
 * 需要自行渲染 markdown 的地方都从这里取，保证各处行为一致。
 */
export function createMarkdownRenderer(options: MarkdownRendererOptions = {}): MarkdownIt {
  const { highlight = true, breaks = true } = options
  const instance = new MarkdownIt({
    html: false,
    linkify: true,
    breaks,
  })
  installFence(instance, highlight)
  instance.use(mathPlugin)
  return instance
}

/** 完整渲染（带代码高亮）——用于定稿内容、知识库预览等 */
export const md: MarkdownIt = createMarkdownRenderer({ highlight: true })

/**
 * 轻量渲染（不做代码高亮）——流式输出期间使用。
 *
 * highlight.js 是流式渲染里最贵的一步：内容每增长一点就要把整段代码块重新高亮一遍。
 * 流式过程中先用这个实例，等收到终态再做一次带高亮的完整渲染。
 */
const mdPlain: MarkdownIt = createMarkdownRenderer({ highlight: false })

/** 文档类内容（段内换行不硬断）的实例 */
const mdDoc: MarkdownIt = createMarkdownRenderer({ highlight: true, breaks: false })
const mdDocPlain: MarkdownIt = createMarkdownRenderer({ highlight: false, breaks: false })

/** 一次性渲染的辅助函数：优先用共享实例，参数不同时才新建 */
export function renderMarkdown(
  text: string,
  options: MarkdownRendererOptions = {},
): string {
  const instance =
    options.breaks === false
      ? options.highlight === false
        ? mdDocPlain
        : mdDoc
      : options.highlight === false
        ? mdPlain
        : md
  return instance.render(text || '')
}
