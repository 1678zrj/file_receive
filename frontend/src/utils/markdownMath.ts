/**
 * Markdown 数学公式插件（KaTeX）
 *
 * 支持四种定界符：
 *  - 行内：`$...$`、`\(...\)`
 *  - 块级：`$$...$$`、`\[...\]`
 *
 * 几个刻意的设计（都是为了流式输出下的体验）：
 *  1. **未闭合就按原文显示**：模型是一边想一边吐 token 的，`$$\frac{a}{` 这种半截公式
 *     如果拿去渲染，KaTeX 只会抛错或显示一片红色。这里块级规则在找不到结束符时
 *     直接"不匹配"，于是那段内容仍按普通文本渲染，等闭合符到了再变成公式。
 *  2. **语法错误回退原文**：用 `throwOnError: true` 自己接住异常，然后输出转义后的原文，
 *     而不是把错误渲染进页面（避免红色报错在对话中途一闪一闪）。
 *  3. **行内定界符有防误判**：`$` 后不能紧跟空白、`$` 前不能是空白、行内公式不跨行。
 *     这样「$5 and $10」这类普通文本不会被当成公式。
 *  4. 代码块 / 行内代码里的 `$` 不受影响（markdown-it 的代码规则会先吃掉它们）。
 */
import type MarkdownIt from 'markdown-it'
import katex from 'katex'
import { escapeHtml } from './html'

function renderMath(latex: string, display: boolean): string {
  const source = latex.trim()
  if (!source) return ''
  try {
    const html = katex.renderToString(source, {
      displayMode: display,
      throwOnError: true,
      strict: false,
      trust: false,
      output: 'html',
    })
    return display
      ? `<div class="math-block">${html}</div>`
      : `<span class="math-inline">${html}</span>`
  } catch {
    // 语法还没完整（流式）/ 写法不支持 → 原样显示，等它变完整
    const raw = escapeHtml(latex)
    return display
      ? `<div class="math-block math-fallback">${raw}</div>`
      : `<span class="math-fallback">${raw}</span>`
  }
}

export function mathPlugin(md: MarkdownIt): void {
  // ---------------- 行内：$...$ 与 \(...\) ----------------
  md.inline.ruler.before('escape', 'math_inline', (state, silent) => {
    const start = state.pos
    const src = state.src
    const marker = src[start]

    let open: string
    let close: string
    if (marker === '$') {
      // `$$` 交给块级规则
      if (src[start + 1] === '$') return false
      open = '$'
      close = '$'
    } else if (marker === '\\') {
      // `\(...\)` 行内；`\[...\]` 常规是块级，但如果它出现在一行中间
      // （块级规则只在行首生效），这里也接住，按行内尺寸渲染，
      // 避免把块级元素塞进 <p> 里造成非法嵌套。
      if (src[start + 1] === '(') {
        open = '\\('
        close = '\\)'
      } else if (src[start + 1] === '[') {
        open = '\\['
        close = '\\]'
      } else {
        return false
      }
    } else {
      return false
    }

    const contentStart = start + open.length
    let pos = contentStart
    let found = -1
    while (pos < state.posMax) {
      const ch = src[pos]
      if (ch === '\\' && open === '$') {
        pos += 2 // 跳过转义字符，避免 `\$` 被当成结束
        continue
      }
      if (src.startsWith(close, pos)) {
        found = pos
        break
      }
      if (ch === '\n') return false // 行内公式不跨行
      pos++
    }
    if (found < 0) return false

    const content = src.slice(contentStart, found)
    if (!content.trim()) return false
    // 防误判：「$5 and $10」里的 `$5 and $` 会因为结尾是空白而被拒绝
    if (open === '$' && (/^\s/.test(content) || /\s$/.test(content))) return false

    if (!silent) {
      const token = state.push('math_inline', 'math', 0)
      token.markup = open
      token.content = content
    }
    state.pos = found + close.length
    return true
  })

  // ---------------- 块级：$$...$$ 与 \[...\] ----------------
  md.block.ruler.before('fence', 'math_block', (state, startLine, endLine, silent) => {
    const begin = state.bMarks[startLine] + state.tShift[startLine]
    const max = state.eMarks[startLine]
    const first = state.src.slice(begin, max)

    let open: string
    let close: string
    if (first.startsWith('$$')) {
      open = '$$'
      close = '$$'
    } else if (first.startsWith('\\[')) {
      open = '\\['
      close = '\\]'
    } else {
      return false
    }
    if (silent) return true

    const afterOpen = first.slice(open.length)
    let content: string
    let nextLine = startLine + 1

    const sameLine = afterOpen.lastIndexOf(close)
    if (sameLine >= 0) {
      // 单行写法：$$ a+b $$
      content = afterOpen.slice(0, sameLine)
    } else {
      // 多行写法：向下找结束符；**找不到就不匹配**（流式未闭合时按普通文本渲染）
      const lines: string[] = []
      let closed = false
      for (let i = startLine + 1; i < endLine; i++) {
        const lBegin = state.bMarks[i] + state.tShift[i]
        const lEnd = state.eMarks[i]
        const raw = state.src.slice(lBegin, lEnd)
        const idx = raw.indexOf(close)
        if (idx >= 0) {
          lines.push(raw.slice(0, idx))
          nextLine = i + 1
          closed = true
          break
        }
        lines.push(raw)
        nextLine = i + 1
      }
      if (!closed) return false
      content = lines.join('\n')
    }

    const token = state.push('math_block', 'math', 0)
    token.block = true
    token.markup = open
    token.content = content
    token.map = [startLine, nextLine]
    state.line = nextLine
    return true
  })

  md.renderer.rules.math_inline = (tokens, idx) => renderMath(tokens[idx].content, false)
  md.renderer.rules.math_block = (tokens, idx) => `${renderMath(tokens[idx].content, true)}\n`
}
