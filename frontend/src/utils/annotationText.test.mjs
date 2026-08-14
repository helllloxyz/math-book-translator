import assert from 'node:assert/strict'
import { normalizeLegacyAnnotationText } from './annotationText.js'

const legacySelection = '与向量场的定义类似，Rn\\mathbb{R}^nRn 的开子集 UUU 上的余向量场或微分1-形式是一个函数，它给 UUU 中的每一点 ppp 分配一个余向量 ωp∈Tp∗(Rn)\\omega_p \\in T_p^*(\\mathbb{R}^n)ωp​∈Tp∗​(Rn)，'
const normalizedSelection = '与向量场的定义类似，$\\mathbb{R}^n$ 的开子集 $U$ 上的余向量场或微分1-形式是一个函数，它给 $U$ 中的每一点 $p$ 分配一个余向量 $\\omega_p \\in T_p^*(\\mathbb{R}^n)$，'

assert.equal(normalizeLegacyAnnotationText(legacySelection), normalizedSelection)
assert.equal(
  normalizeLegacyAnnotationText('我们互换使用术语 “光滑” 与 “ C∞C ^ { \\infty }C∞ ”'),
  '我们互换使用术语 “光滑” 与 “ $C ^ { \\infty }$ ”'
)
assert.equal(normalizeLegacyAnnotationText('$\\mathbb{R}^n$ 上的 U'), '$\\mathbb{R}^n$ 上的 U')
assert.equal(normalizeLegacyAnnotationText('普通标记文本'), '普通标记文本')

console.log('legacy annotation LaTeX normalization ok')
