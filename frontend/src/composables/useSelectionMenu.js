import { onMounted, onUnmounted, ref } from 'vue'
import { copySelectionAsLatex, selectionStartsInElement, selectionTextWithLatex } from '../utils/latexCopy'

export function useSelectionMenu(viewportRef, onAction) {
  const menuVisible = ref(false)
  const menuX = ref(0)
  const menuY = ref(0)
  const selectedText = ref('')
  const selectedContentTarget = ref('translated')

  const closeMenu = () => {
    menuVisible.value = false
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

    return element?.closest('.source-pane') ? 'raw' : 'translated'
  }

  const handleMenuAction = async (action) => {
    closeMenu()
    const text = selectedText.value.trim()
    if (!text) return
    await onAction(action, text, { contentTarget: selectedContentTarget.value })
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

    selectedText.value = text
    selectedContentTarget.value = getSelectionContentTarget(selection)
    const rect = selection.getRangeAt(0).getBoundingClientRect()
    menuX.value = rect.left
    menuY.value = rect.bottom + 8
    menuVisible.value = true
  }

  const handleCopy = (event) => {
    const selection = window.getSelection()
    if (!isSelectionFromReader(selection)) return
    copySelectionAsLatex(event, viewportRef.value)
  }

  const handleDocumentClick = (event) => {
    if (event.target.closest('.context-menu')) return

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
    handleMenuAction,
    menuVisible,
    menuX,
    menuY,
    selectedContentTarget,
    selectedText
  }
}
