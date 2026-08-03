const closestKatexElement = (node) => {
  const element = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement
  return element?.closest?.('.katex') || null
}

const rangeExpandedToKatexBoundaries = (range) => {
  const copyRange = range.cloneRange()
  const startKatex = closestKatexElement(range.startContainer)
  const endKatex = closestKatexElement(range.endContainer)
  const startTarget = startKatex?.closest('.katex-display') || startKatex
  const endTarget = endKatex?.closest('.katex-display') || endKatex

  if (startTarget) copyRange.setStartBefore(startTarget)
  if (endTarget) copyRange.setEndAfter(endTarget)

  return copyRange
}

export const selectionTextWithLatex = (selection) => {
  if (!selection || selection.rangeCount === 0) return ''

  const range = rangeExpandedToKatexBoundaries(selection.getRangeAt(0))
  const div = document.createElement('div')
  div.appendChild(range.cloneContents())
  div.querySelectorAll('.katex').forEach(element => {
    const annotation = element.querySelector('annotation[encoding="application/x-tex"]')
    if (!annotation) return

    const displayWrapper = element.closest('.katex-display')
    const replacement = displayWrapper
      ? document.createTextNode(`$$${annotation.textContent}$$`)
      : document.createTextNode(`$${annotation.textContent}$`)
    const target = displayWrapper || element
    target.parentNode.replaceChild(replacement, target)
  })

  return div.textContent || ''
}

export const selectionStartsInElement = (selection, rootElement) => {
  if (!selection || !selection.rangeCount || !rootElement) return false

  const range = selection.getRangeAt(0)
  const commonAncestor = range.commonAncestorContainer
  const element = commonAncestor.nodeType === Node.ELEMENT_NODE
    ? commonAncestor
    : commonAncestor.parentElement

  return Boolean(element && rootElement.contains(element))
}

export const copySelectionAsLatex = (event, rootElement) => {
  const selection = window.getSelection()
  const text = selectionTextWithLatex(selection).trim()
  if (!text || !selectionStartsInElement(selection, rootElement) || !event.clipboardData) return false

  event.clipboardData.setData('text/plain', text)
  event.preventDefault()
  return true
}
