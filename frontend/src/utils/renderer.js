import MarkdownIt from 'markdown-it'
import mk from '@iktakahiro/markdown-it-katex'
import mermaid from 'mermaid'
import 'katex/dist/katex.min.css'
import renderMathInElement from 'katex/dist/contrib/auto-render'
import { buildApiUrl } from '../api/client'
import { normalizeMathDelimiters } from './mathDelimiters'
export { deserializeMessages, serializeMessages } from './chatMessages.js'

mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict',
    theme: 'default'
})

const md = new MarkdownIt({ html: false, linkify: true, typographer: true })
md.use(mk, {
    throwOnError: false,
    errorColor: '#cc0000'
})

const defaultFence = md.renderer.rules.fence || ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))

md.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const token = tokens[idx]
    const info = token.info.trim()
    if (info === 'mermaid') {
        const encoded = md.utils.escapeHtml(token.content)
        return `<pre class="mermaid">${encoded}</pre>`
    }
    return defaultFence(tokens, idx, options, env, self)
}

export const renderMarkdown = (content, book) => {
    let html = md.render(normalizeMathDelimiters(content || ''))
    
    if (book) {
        const rawUuid = typeof book.uuid === 'string' ? book.uuid.trim() : ''
        const safeUuid = encodeURIComponent(rawUuid)
        const baseUrl = safeUuid 
          ? buildApiUrl(`/static/${safeUuid}/images/`)
          : buildApiUrl('/static/images/')
        html = html.replace(/src="images\//g, `src="${baseUrl}`)
    }
    
    return html
}

export const renderMath = (element) => {
    const mathOptions = {
        delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false},
            {left: '\\(', right: '\\)', display: false},
            {left: '\\[', right: '\\]', display: true}
        ],
        throwOnError: false
    }
    renderMathInElement(element, mathOptions)
}
