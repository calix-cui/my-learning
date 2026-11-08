import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'

/**
 * 模型返回的内容是 Markdown，这里统一渲染。
 *
 * 两条安全约束：
 * 1. `html: false` —— 原文里的 HTML 标签不参与渲染，只当普通文本；
 * 2. 渲染结果再过一遍 DOMPurify —— 防止「链接文本 / 自动链接」等路径把可执行内容带进来。
 */
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

/** 外链一律新标签打开，并切断 window.opener */
const defaultLinkOpen =
  md.renderer.rules.link_open ??
  ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

/** Markdown → HTML（未消毒，仅供单测与调试使用；界面必须用 renderMarkdown） */
export function renderMarkdownRaw(text: string): string {
  if (!text) return ''
  return md.render(text)
}

/** Markdown → 可安全插入 DOM 的 HTML */
export function renderMarkdown(text: string): string {
  if (!text) return ''
  return DOMPurify.sanitize(renderMarkdownRaw(text), {
    USE_PROFILES: { html: true },
    ADD_ATTR: ['target', 'rel'],
  })
}
