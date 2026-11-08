import { describe, expect, it } from 'vitest'

import { renderMarkdownRaw } from './markdown'

describe('renderMarkdownRaw', () => {
  it('把模型常见的加粗与列表渲染成标签', () => {
    const html = renderMarkdownRaw('**第一档**\n\n- 3 元/瓶\n- 4 元/瓶')
    expect(html).toContain('<strong>第一档</strong>')
    expect(html).toContain('<li>3 元/瓶</li>')
  })

  it('单个换行也换行（模型回复常这么写）', () => {
    expect(renderMarkdownRaw('第一行\n第二行')).toContain('<br>')
  })

  it('代码块保留原样，不被当成 HTML', () => {
    const html = renderMarkdownRaw('```python\nprint("<b>")\n```')
    expect(html).toContain('<pre><code class="language-python">')
    expect(html).toContain('&lt;b&gt;')
  })

  it('原文里的 HTML 标签按文本处理，不进入标签层', () => {
    const html = renderMarkdownRaw('<img src=x onerror=alert(1)>')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
  })

  it('链接自动识别并带上新标签与 rel', () => {
    const html = renderMarkdownRaw('见 https://example.com/docs')
    expect(html).toContain('href="https://example.com/docs"')
    expect(html).toContain('target="_blank"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('空内容返回空串', () => {
    expect(renderMarkdownRaw('')).toBe('')
  })
})
