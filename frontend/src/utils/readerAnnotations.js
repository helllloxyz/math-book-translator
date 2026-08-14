const ANNOTATION_SELECTOR = '[data-reader-annotation-id]'

const safeNumber = (value, fallback = 0) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback
}

export const parseReaderAnnotation = (note = {}) => {
  let metadata = {}
  try {
    metadata = JSON.parse(note.note_content || '{}')
  } catch (_error) {
    metadata = {}
  }

  return {
    id: note.id,
    selectedText: metadata.anchor_text || note.selected_text || '',
    startIndex: safeNumber(note.start_index),
    style: metadata.style === 'underline' ? 'underline' : 'highlight',
    contentTarget: metadata.content_target === 'raw' ? 'raw' : 'translated'
  }
}

export const findClosestTextIndex = (content = '', selectedText = '', expectedIndex = 0) => {
  if (!selectedText) return -1
  const safeExpectedIndex = safeNumber(expectedIndex)
  if (content.slice(safeExpectedIndex, safeExpectedIndex + selectedText.length) === selectedText) {
    return safeExpectedIndex
  }

  let closestIndex = -1
  let closestDistance = Number.POSITIVE_INFINITY
  let matchIndex = content.indexOf(selectedText)
  while (matchIndex >= 0) {
    const distance = Math.abs(matchIndex - safeExpectedIndex)
    if (distance < closestDistance) {
      closestIndex = matchIndex
      closestDistance = distance
    }
    matchIndex = content.indexOf(selectedText, matchIndex + 1)
  }
  return closestIndex
}

export const selectionAnchorForRoot = (selection, root) => {
  if (!selection || !selection.rangeCount || !root) return null
  const range = selection.getRangeAt(0)
  if (!root.contains(range.startContainer) || !root.contains(range.endContainer)) return null

  const before = range.cloneRange()
  before.selectNodeContents(root)
  before.setEnd(range.startContainer, range.startOffset)

  return {
    anchorText: range.toString(),
    startIndex: before.toString().length
  }
}

const annotationRoot = (viewport, contentTarget) => {
  if (!viewport) return null
  const eligibleRoot = viewport.querySelector(
    `.markdown-body[data-content-target="${contentTarget}"][data-annotation-eligible="true"]`
  )
  if (eligibleRoot) return eligibleRoot
  if (contentTarget === 'raw') return viewport.querySelector('.source-pane .markdown-body')
  return viewport.querySelector('.target-pane .markdown-body')
    || viewport.querySelector('.single-layout .markdown-body')
    || viewport.querySelector('.markdown-body')
}

const textSegments = (root, selectedText, expectedIndex) => {
  if (!root || !selectedText) return []
  const content = root.textContent || ''
  const startIndex = findClosestTextIndex(content, selectedText, expectedIndex)
  if (startIndex < 0) return []
  const endIndex = startIndex + selectedText.length
  const nodeFilter = root.ownerDocument?.defaultView?.NodeFilter || globalThis.NodeFilter
  if (!nodeFilter) return []

  const walker = root.ownerDocument.createTreeWalker(root, nodeFilter.SHOW_TEXT)
  const segments = []
  let cursor = 0
  let node = walker.nextNode()
  while (node) {
    const length = node.textContent?.length || 0
    const nodeEnd = cursor + length
    if (length && startIndex < nodeEnd && endIndex > cursor) {
      segments.push({
        node,
        startOffset: Math.max(0, startIndex - cursor),
        endOffset: Math.min(length, endIndex - cursor)
      })
    }
    cursor = nodeEnd
    if (cursor >= endIndex) break
    node = walker.nextNode()
  }
  return segments
}

const wrapSegment = (segment, annotation) => {
  if (!segment?.node?.parentNode || segment.startOffset >= segment.endOffset) return null
  const document = segment.node.ownerDocument
  const range = document.createRange()
  range.setStart(segment.node, segment.startOffset)
  range.setEnd(segment.node, segment.endOffset)

  const marker = document.createElement('mark')
  marker.className = `reader-annotation reader-annotation--${annotation.style}`
  marker.dataset.readerAnnotationId = String(annotation.id)
  marker.dataset.contentTarget = annotation.contentTarget
  marker.title = '点击管理标注'
  range.surroundContents(marker)
  return marker
}

export const clearReaderAnnotations = (viewport) => {
  if (!viewport) return
  const markers = Array.from(viewport.querySelectorAll(ANNOTATION_SELECTOR)).reverse()
  markers.forEach((marker) => marker.replaceWith(...marker.childNodes))
  viewport.querySelectorAll('.markdown-body').forEach((root) => root.normalize())
}

export const applyReaderAnnotations = (viewport, notes = []) => {
  if (!viewport) return []
  clearReaderAnnotations(viewport)

  const appliedIds = new Set()
  notes.map(parseReaderAnnotation).forEach((annotation) => {
    if (!annotation.id || !annotation.selectedText) return
    const root = annotationRoot(viewport, annotation.contentTarget)
    const segments = textSegments(root, annotation.selectedText, annotation.startIndex)
    segments.reverse().forEach((segment) => {
      try {
        if (wrapSegment(segment, annotation)) appliedIds.add(annotation.id)
      } catch (_error) {
        // A stale or browser-normalized range should not block other annotations.
      }
    })
  })
  return [...appliedIds]
}
