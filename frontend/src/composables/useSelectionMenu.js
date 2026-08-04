import { onMounted, onUnmounted, ref } from 'vue'
import { copySelectionAsLatex, selectionStartsInElement, selectionTextWithLatex } from '../utils/latexCopy'
import { selectionAnchorForRoot } from '../utils/readerAnnotations'

export function useSelectionMenu(viewportRef, onAction) {
  const menuVisible = ref(false)
  const menuX = ref(0)
  const menuY = ref(0)
  const selectedText = ref('')
  const selectedContentTarget = ref('translated')
  const selectedAnchorText = ref('')
  const selectedStartIndex = ref(0)
  const annotationAllowed = ref(true)
  const activeAnnotationId = ref(null)

  const closeMenu = () => {
    menuVisible.value = false
    activeAnnotationId.value = null
  }

  const getSelectionText = () => {
    return selectionTextWithLatex(window.getSelection())
  }

  const isSelectionFromReader = (selection) => {
    if (!selection || !selection.rangeCount || !viewportRef.value) return false

    const range = selection.getRangeAt(0)
    const commonAncestor = range.commonAncestorContainer
    const element = commonAncestor.nodeType === Node.ELEMENT_NODE
      ? commonAncestor
      : commonAncestor.parentElement

    return Boolean(element?.closest('.markdown-body') && selectionStartsInElement(selection, viewportRef.value))
  }

  const getSelectionContentTarget = (selection) => {
    if (!selection || !selection.rangeCount) return 'translated'
    const range = selection.getRangeAt(0)
    const commonAncestor = range.commonAncestorContainer
    const element = commonAncestor.nodeType === Node.ELEMENT_NODE
      ? commonAncestor
      : commonAncestor.parentElement

    const root = element?.closest('.markdown-body')
    return root?.dataset.contentTarget || (element?.closest('.source-pane') ? 'raw' : 'translated')
  }

  const getSelectionRoot = (selection) => {
    if (!selection || !selection.rangeCount) return null
    const range = selection.getRangeAt(0)
    const startElement = range.startContainer.nodeType === Node.ELEMENT_NODE
      ? range.startContainer
      : range.startContainer.parentElement
    return startElement?.closest('.markdown-body') || null
  }

  const menuLeftForRect = (rect) => {
    const maximumLeft = Math.max(12, window.innerWidth - 500)
    return Math.max(12, Math.min(rect.left, maximumLeft))
  }

  const menuTopForRect = (rect) => {
    const below = rect.bottom + 10
    if (below + 52 <= window.innerHeight) return Math.max(12, below)
    return Math.max(12, rect.top - 52)
  }

  const openSelectionMenu = (selection) => {
    const text = selectionTextWithLatex(selection).trim()
    if (!text || !isSelectionFromReader(selection)) return false
    const root = getSelectionRoot(selection)
    const anchor = selectionAnchorForRoot(selection, root)
    if (!anchor?.anchorText.trim()) return false

    selectedText.value = text
    selectedAnchorText.value = anchor.anchorText
    selectedStartIndex.value = anchor.startIndex
    selectedContentTarget.value = getSelectionContentTarget(selection)
    const range = selection.getRangeAt(0)
    const startElement = range.startContainer.nodeType === Node.ELEMENT_NODE
      ? range.startContainer
      : range.startContainer.parentElement
    annotationAllowed.value = (
      root?.dataset.annotationEligible !== 'false'
      && !startElement?.closest('.mermaid, svg')
    )
    activeAnnotationId.value = null
    const rect = range.getBoundingClientRect()
    menuX.value = menuLeftForRect(rect)
    menuY.value = menuTopForRect(rect)
    menuVisible.value = true
    return true
  }

  const handleMenuAction = async (action) => {
    const annotationId = activeAnnotationId.value
    const options = {
      annotationId,
      anchorText: selectedAnchorText.value,
      startIndex: selectedStartIndex.value,
      contentTarget: selectedContentTarget.value
    }
    closeMenu()
    const text = selectedText.value.trim()
    if (!text && !annotationId) return
    await onAction(action, text, options)
  }

  const handleKeydown = async (event) => {
    if (!event.ctrlKey || (event.key !== 'q' && event.key !== 'Q')) return
    if (event.target?.closest('input, textarea, [contenteditable="true"]')) return

    const selection = window.getSelection()
    const text = getSelectionText().trim()
    event.preventDefault()

    if (!text || !isSelectionFromReader(selection)) {
      await onAction('chapter-note', '', { contentTarget: 'translated' })
      return
    }

    openSelectionMenu(selection)
  }

  const handleCopy = (event) => {
    const selection = window.getSelection()
    if (!isSelectionFromReader(selection)) return
    copySelectionAsLatex(event, viewportRef.value)
  }

  const handleDocumentClick = (event) => {
    if (event.target.closest('.context-menu')) return

    const annotation = event.target.closest('[data-reader-annotation-id]')
    if (annotation && viewportRef.value?.contains(annotation)) {
      const rect = annotation.getBoundingClientRect()
      activeAnnotationId.value = Number(annotation.dataset.readerAnnotationId)
      selectedText.value = annotation.textContent || ''
      selectedAnchorText.value = selectedText.value
      selectedStartIndex.value = 0
      selectedContentTarget.value = annotation.dataset.contentTarget || 'translated'
      annotationAllowed.value = true
      menuX.value = menuLeftForRect(rect)
      menuY.value = menuTopForRect(rect)
      menuVisible.value = true
      return
    }

    const selection = window.getSelection()
    if (getSelectionText().trim() && isSelectionFromReader(selection)) return

    closeMenu()
  }

  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
    document.addEventListener('click', handleDocumentClick)
    document.addEventListener('copy', handleCopy)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown)
    document.removeEventListener('click', handleDocumentClick)
    document.removeEventListener('copy', handleCopy)
  })

  return {
    closeMenu,
    activeAnnotationId,
    annotationAllowed,
    handleMenuAction,
    menuVisible,
    menuX,
    menuY,
    selectedContentTarget,
    selectedText
  }
}
