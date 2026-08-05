import assert from 'node:assert/strict'
import MarkdownIt from 'markdown-it'
import mk from '@iktakahiro/markdown-it-katex'
import { normalizeMathDelimiters } from './mathDelimiters.js'

const normalized = normalizeMathDelimiters(String.raw`Inline \(x + y\), then display \[x^2 + y^2\].`)

assert.match(normalized, /Inline \$x \+ y\$/, 'LaTeX inline delimiters should become Markdown-It KaTeX delimiters')
assert.match(normalized, /\n\$\$\nx\^2 \+ y\^2\n\$\$\n/, 'LaTeX display delimiters should become a standalone KaTeX block')
assert.equal(
    normalizeMathDelimiters(String.raw`Literal \\(x\\) stays escaped.`),
    String.raw`Literal \\(x\\) stays escaped.`,
    'explicitly escaped delimiters should remain literal text'
)
assert.equal(normalizeMathDelimiters('$z$'), '$z$', 'existing dollar delimiters should remain unchanged')

const rendered = new MarkdownIt().use(mk, { throwOnError: false }).render(normalized)
assert.match(rendered, /class="katex"/, 'normalized LaTeX delimiters should render to KaTeX HTML without DOM auto-rendering')

console.log('math delimiter normalization ok')
