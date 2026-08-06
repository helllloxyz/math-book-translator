<template>
  <div
    class="reader-layout-wrapper"
    :class="{ 'sidebar-collapsed': !sidebarOpen, 'notes-collapsed': !notesPanelOpen }"
  >
    <Sidebar
      v-if="book && sidebarOpen"
      :book-tree="bookTree"
      :guide-tree="guideTree"
      :current-item-id="currentItem?.id"
      class="reader-sidebar"
      @select-item="handleItemSelect"
    />

    <div class="reader-main">
      <ReaderToolbar
        :book-title="book?.title || ''"
        :current-title="currentItem?.title || ''"
        :can-edit-chapter-status="currentItem?.type === 'chapter'"
        :can-toggle-view-mode="canUseChapterContent"
        :reading-status="chapterReadingStatus"
        :view-mode="viewMode"
        :sidebar-open="sidebarOpen"
        :notes-open="notesPanelOpen"
        :notes-count="askCards.length"
        :reading-percent="readingPercent"
        @update-reading-progress="updateChapterProgress"
        @update-reading-difficulty="updateChapterDifficulty"
        @set-view-mode="setViewMode"
        @open-quiz="openQuizDialog"
        @toggle-sidebar="sidebarOpen = !sidebarOpen"
        @toggle-notes="notesPanelOpen = !notesPanelOpen"
      />

      <ReaderPanes
        v-model:viewport-ref="viewportRef"
        :current-item="currentItem"
        :loading="loading"
        :next-item="nextReaderItem"
        :previous-item="previousReaderItem"
        :rendered-source="renderedSource"
        :rendered-guide="renderedGuide"
        :rendered-target="renderedTarget"
        :guide-item="currentChapterGuide"
        :guide-loading="guideLoading"
        :view-mode="viewMode"
        @scroll-progress="readingPercent = $event"
        @go-next="goToNextReaderItem"
        @go-previous="goToReaderItem(previousReaderItem)"
      />
    </div>

    <NotesPanel
      v-if="currentToolSubject && notesPanelOpen"
      :notes="askCards"
      :active-id="activeConversationId"
      :current-title="currentToolSubject.title_zh"
      @close="notesPanelOpen = false"
      @create-chapter-note="openChapterNote"
      @activate-note="activateNoteCard"
    />

    <ContextMenu
      :visible="menuVisible"
      :x="menuX"
      :y="menuY"
      :selection="selectedText"
      :active-annotation-id="activeAnnotationId"
      :annotation-allowed="annotationAllowed"
      @action="handleMenuAction"
      @close="closeMenu"
    />

    <Transition name="annotation-feedback">
      <div v-if="annotationFeedback" class="annotation-feedback" role="status" aria-live="polite">
        {{ annotationFeedback }}
      </div>
    </Transition>

    <div v-if="latexRepair.visible" class="latex-repair-backdrop" @click.self="closeLatexRepairDialog">
      <section class="latex-repair-dialog" role="dialog" aria-modal="true" aria-labelledby="latex-repair-title">
        <header class="latex-repair-header">
          <div>
            <p class="latex-repair-kicker">Selected {{ latexRepair.contentTarget === 'raw' ? 'source' : 'translated' }} text</p>
            <h2 id="latex-repair-title">Fix LaTeX</h2>
          </div>
          <button type="button" class="modal-icon-btn" @click="closeLatexRepairDialog" aria-label="Close">×</button>
        </header>

        <div class="latex-repair-body">
          <label>
            Original selection
            <textarea :value="latexRepair.originalText" readonly rows="4"></textarea>
          </label>

          <label>
            Candidate repair
            <textarea
              v-model="latexRepair.candidate"
              rows="5"
              :disabled="latexRepair.loading || latexRepair.applying"
              @input="renderLatexRepairPreview"
            ></textarea>
          </label>

          <div class="latex-repair-preview">
            <div class="preview-label">Rendered preview</div>
            <div ref="latexPreviewRef" class="latex-preview markdown-body latex-content" v-html="latexRepair.previewHtml"></div>
          </div>

          <p v-if="latexRepair.error" class="latex-repair-error">{{ latexRepair.error }}</p>
        </div>

        <footer class="latex-repair-actions">
          <button type="button" class="secondary-btn" :disabled="latexRepair.loading || latexRepair.applying" @click="retryLatexRepair">
            {{ latexRepair.loading ? 'Retrying...' : 'Retry' }}
          </button>
          <button type="button" class="secondary-btn" :disabled="latexRepair.loading || latexRepair.applying" @click="closeLatexRepairDialog">
            Cancel
          </button>
          <button type="button" class="primary-btn" :disabled="latexRepair.loading || latexRepair.applying || !latexRepair.candidate.trim()" @click="confirmLatexRepair">
            {{ latexRepair.applying ? 'Applying...' : 'Looks correct, replace' }}
          </button>
        </footer>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, onBeforeUnmount, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useBookStore } from '../stores/bookStore'
import { useLearningCards } from '../composables/useLearningCards'
import { useReaderContent } from '../composables/useReaderContent'
import { useSelectionMenu } from '../composables/useSelectionMenu'
import {
  defaultChapterReadingStatus,
  getChapterReadingStatus,
  setChapterReadingStatus
} from '../utils/chapterReadingStatus'
import {
  getFurthestReadChapter,
  rememberFurthestReadChapter
} from '../utils/readerProgress'
import { findAdjacentReaderLeaves, findChapterGuideLeaf } from '../utils/readerTree'
import { buildReaderItemQuery, findReaderLeafByRouteQuery } from '../utils/readerRoute'
import { renderMarkdown, renderMath } from '../utils/renderer'
import { applyReaderAnnotations } from '../utils/readerAnnotations'
import {
  buildConversationDocumentTitle,
  buildConversationMetadata,
  createConversationId,
  saveConversationPayload
} from '../utils/conversationMetadata'
import Sidebar from '../components/Sidebar.vue'
import ContextMenu from '../components/ContextMenu.vue'
import NotesPanel from '../components/NotesPanel.vue'
import ReaderPanes from '../components/ReaderPanes.vue'
import ReaderToolbar from '../components/ReaderToolbar.vue'

const route = useRoute()
const router = useRouter()
const bookStore = useBookStore()
const {
  activeConversationId,
  askCards,
  createChapterCard,
  createQuizQuestionCard,
  ensureQuizCard,
  ensureSelectionCard,
  activateAskCard,
  loadAskNotes,
} = useLearningCards()
const viewportRef = ref(null)
const viewMode = ref('single')
const sidebarOpen = ref(true)
const notesPanelOpen = ref(typeof window === 'undefined' ? true : window.innerWidth > 1440)
const readingPercent = ref(0)
const chapterReadingStatus = ref(defaultChapterReadingStatus())
const bookTree = ref([])
const guideTree = ref([])
const renderedGuide = ref('')
const guideLoading = ref(false)
const guideRequestId = ref(0)
const readerAnnotations = ref([])
const annotationFeedback = ref('')
let annotationFeedbackTimer = null
const latexPreviewRef = ref(null)
const latexRepair = ref({
  visible: false,
  loading: false,
  applying: false,
  originalText: '',
  candidate: '',
  contentTarget: 'translated',
  failedCandidates: [],
  error: '',
  previewHtml: ''
})

const book = computed(() => bookStore.currentBook)
const {
  currentItem,
  loading,
  renderedSource,
  renderedTarget,
  renderRevision,
  loadItem,
  renderCurrentViewport
} = useReaderContent(bookStore, book, viewportRef)

const currentChapter = computed(() => {
  if (!currentItem.value?.chapter_id) return null
  return {
    id: currentItem.value.chapter_id,
    title_zh: currentItem.value.source_title || currentItem.value.title,
    title_en: currentItem.value.source_title || currentItem.value.title,
    chapter_index: currentItem.value.chapter_index
  }
})
const currentToolSubject = computed(() => {
  if (!currentItem.value) return null
  return {
    id: currentItem.value.source_id || currentItem.value.id,
    bookId: book.value?.id || '',
    chapterId: currentItem.value.chapter_id || '',
    sourceType: currentItem.value.source_type || '',
    sourceId: currentItem.value.source_id || '',
    sourceTitle: currentItem.value.source_title || currentItem.value.title,
    title_zh: currentItem.value.source_title || currentItem.value.title,
    title_en: currentItem.value.source_title || currentItem.value.title,
    readerType: currentItem.value.type
  }
})
const readerNavigation = computed(() => {
  if (!currentItem.value) return { previous: null, next: null }
  return findAdjacentReaderLeaves(bookTree.value, currentItem.value.id)
})
const previousReaderItem = computed(() => readerNavigation.value.previous)
const nextReaderItem = computed(() => readerNavigation.value.next)
const canUseChapterContent = computed(() => Boolean(currentItem.value?.chapter_id || currentItem.value?.chapterId))
const currentChapterGuide = computed(() => {
  if (currentItem.value?.type === 'guide') return currentItem.value
  if (currentItem.value?.type !== 'chapter') return null
  return findChapterGuideLeaf(guideTree.value, currentItem.value.chapter_index)
})

const setViewMode = (mode) => {
  if (!canUseChapterContent.value) return
  if (!['single', 'dual', 'guide-dual'].includes(mode)) return
  viewMode.value = mode
  nextTick(() => renderCurrentViewport())
}

const resetGuidePane = () => {
  renderedGuide.value = ''
  guideLoading.value = false
}

const loadCurrentChapterGuide = async () => {
  const requestId = guideRequestId.value + 1
  guideRequestId.value = requestId
  renderedGuide.value = ''

  if (viewMode.value !== 'guide-dual' || currentItem.value?.type !== 'chapter') {
    guideLoading.value = false
    return
  }

  const guide = currentChapterGuide.value
  if (!guide) {
    guideLoading.value = false
    return
  }

  guideLoading.value = true
  try {
    const data = await bookStore.fetchReaderContent(book.value?.id, {
      readerType: 'guide',
      guideId: guide.id
    })
    if (requestId !== guideRequestId.value) return
    const guideMarkdown = data?.content || '_No guide content available._'
    renderedGuide.value = renderMarkdown(guideMarkdown, book.value)
    renderCurrentViewport()
  } catch (error) {
    if (requestId !== guideRequestId.value) return
    console.error('Failed to load chapter guide pane:', error)
    renderedGuide.value = renderMarkdown('**Error:** Failed to load chapter guide.', book.value)
    renderCurrentViewport()
  } finally {
    if (requestId === guideRequestId.value) {
      guideLoading.value = false
    }
  }
}

const syncChapterReadingStatus = (item) => {
  if (item?.type !== 'chapter') {
    chapterReadingStatus.value = defaultChapterReadingStatus()
    return
  }
  chapterReadingStatus.value = getChapterReadingStatus(book.value?.id, item.chapter_id)
}

const persistChapterReadingStatus = (nextStatus) => {
  if (currentItem.value?.type !== 'chapter') return
  chapterReadingStatus.value = setChapterReadingStatus(
    book.value?.id,
    currentItem.value.chapter_id,
    nextStatus
  )
}

const updateChapterProgress = (progress) => {
  persistChapterReadingStatus({
    ...chapterReadingStatus.value,
    progress
  })
}

const updateChapterDifficulty = (difficulty) => {
  persistChapterReadingStatus({
    ...chapterReadingStatus.value,
    difficulty
  })
}

const htmlToText = (html) => {
  const element = document.createElement('div')
  element.innerHTML = html || ''
  return element.textContent?.replace(/\s+/g, ' ').trim() || ''
}

const buildReaderItemContext = async (card) => {
  if (currentChapter.value?.id && book.value?.id) {
    if (card?.contextScope === 'selection') {
      return card.selectedText || ''
    }

    try {
      const chapterData = await bookStore.fetchReaderContent(book.value.id, {
        readerType: 'chapter',
        chapterId: currentChapter.value.id
      })
      const translatedContent = chapterData?.content_translated
      const rawContent = chapterData?.content_raw
      const body = typeof translatedContent === 'string' && translatedContent.trim()
        ? translatedContent
        : (typeof rawContent === 'string' ? rawContent : '')
      return body
    } catch (error) {
      console.error('Failed to load full chapter context for note:', error)
    }
  }

  const parts = [
    `Reader item type: ${currentItem.value?.type || 'unknown'}`,
    `Reader item title: ${currentItem.value?.title || ''}`
  ]

  if (card?.contextScope === 'selection') {
    parts.push('Selected text:', card.selectedText || '')
  }

  const visibleText = htmlToText(renderedTarget.value)
  if (visibleText) {
    parts.push('Visible content:', visibleText)
  }

  return parts.join('\n\n')
}

const resetToolCards = async (item) => {
  const subject = currentToolSubject.value
  if (!item || !subject) {
    readerAnnotations.value = []
    loadAskNotes([], { id: 'none', title_zh: '', title_en: '' })
    return
  }

  let notes = []
  if (subject.sourceType && subject.sourceId) {
    try {
      notes = await bookStore.fetchSourceNotes(book.value?.id, subject.sourceType, subject.sourceId)
    } catch (_error) {
      notes = []
    }
  }
  readerAnnotations.value = notes.filter((note) => note.type === 'annotation')
  loadAskNotes(notes, subject)
}

const replaceReaderRouteQuery = async (item, extraQuery = {}) => {
  if (!book.value?.id || !item) return
  try {
    await router.replace({
      name: 'reader',
      params: { id: book.value.id },
      query: buildReaderItemQuery(item, extraQuery)
    })
  } catch (error) {
    console.error('Failed to update reader URL:', error)
  }
}

const loadItemFromRouteQuery = async () => {
  if (!book.value || !bookTree.value.length) return
  const hasExplicitReaderTarget = Boolean(route.query.chapter_id || route.query.guide_id)
  const routeItem = hasExplicitReaderTarget
    ? findReaderLeafByRouteQuery(bookTree.value, guideTree.value, route.query)
    : getFurthestReadChapter(book.value.id, bookTree.value)
      || findReaderLeafByRouteQuery(bookTree.value, guideTree.value, route.query)
  if (!routeItem || currentItem.value?.id === routeItem.id) return
  await handleItemSelect(routeItem, { updateRoute: false })
}

const handleItemSelect = async (item, options = {}) => {
  closeMenu()
  readerAnnotations.value = []
  readingPercent.value = 0
  if (item?.type !== 'chapter') {
    viewMode.value = 'single'
    resetGuidePane()
  }
  syncChapterReadingStatus(item)
  rememberFurthestReadChapter(book.value?.id, bookTree.value, item)
  await loadItem(item)
  await resetToolCards(item)
  if (options.updateRoute !== false) {
    await replaceReaderRouteQuery(item, options.extraQuery)
  }
}

const goToReaderItem = async (item) => {
  if (!item) return
  await handleItemSelect(item)
}

const goToNextReaderItem = async () => {
  if (!nextReaderItem.value) return

  if (
    currentItem.value?.type === 'chapter' &&
    readingPercent.value >= 100 &&
    chapterReadingStatus.value.progress !== 'finished'
  ) {
    persistChapterReadingStatus({
      ...chapterReadingStatus.value,
      progress: 'finished'
    })
  }

  await goToReaderItem(nextReaderItem.value)
}

const openSelectionChat = async (action, text) => {
  if (!currentToolSubject.value) return

  if (viewMode.value !== 'single') {
    viewMode.value = 'single'
    await nextTick()
  }

  const card = action === 'chapter-note'
    ? createChapterCard(currentToolSubject.value, { initialPrompt: text })
    : ensureSelectionCard(currentToolSubject.value, text, { initialPrompt: text })
  await activateNoteCard(card)
}

const renderLatexRepairPreview = async () => {
  latexRepair.value.previewHtml = renderMarkdown(latexRepair.value.candidate || '', book.value)
  await nextTick()
  if (!latexPreviewRef.value) return
  try {
    renderMath(latexPreviewRef.value)
  } catch (error) {
    console.error('Failed to render LaTeX repair preview:', error)
  }
}

const requestLatexRepairCandidate = async () => {
  if (!currentChapter.value?.id || !latexRepair.value.originalText.trim()) return
  latexRepair.value.loading = true
  latexRepair.value.error = ''
  try {
    const response = await bookStore.suggestChapterLatexRepair(currentChapter.value.id, {
      selectedText: latexRepair.value.originalText,
      contentTarget: latexRepair.value.contentTarget,
      failedCandidates: latexRepair.value.failedCandidates
    })
    latexRepair.value.candidate = response?.replacement || ''
    await renderLatexRepairPreview()
  } catch (error) {
    latexRepair.value.error = error.response?.data?.detail || error.message || 'Failed to request LaTeX repair.'
  } finally {
    latexRepair.value.loading = false
  }
}

const openLatexRepairDialog = async (text, options = {}) => {
  if (currentItem.value?.type !== 'chapter' || !currentChapter.value?.id || !text.trim()) return
  latexRepair.value = {
    visible: true,
    loading: false,
    applying: false,
    originalText: text,
    candidate: '',
    contentTarget: options.contentTarget || 'translated',
    failedCandidates: [],
    error: '',
    previewHtml: ''
  }
  await requestLatexRepairCandidate()
}

const retryLatexRepair = async () => {
  const failed = latexRepair.value.candidate.trim()
  if (failed) {
    latexRepair.value.failedCandidates = [...latexRepair.value.failedCandidates, failed]
  }
  await requestLatexRepairCandidate()
}

const closeLatexRepairDialog = () => {
  latexRepair.value.visible = false
}

const confirmLatexRepair = async () => {
  if (!currentChapter.value?.id || !latexRepair.value.candidate.trim()) return
  latexRepair.value.applying = true
  latexRepair.value.error = ''
  try {
    await bookStore.applyChapterLatexRepair(currentChapter.value.id, {
      originalText: latexRepair.value.originalText,
      replacementText: latexRepair.value.candidate,
      contentTarget: latexRepair.value.contentTarget
    })
    closeLatexRepairDialog()
    await loadItem(currentItem.value)
  } catch (error) {
    latexRepair.value.error = error.response?.data?.detail || error.message || 'Failed to replace selected text.'
  } finally {
    latexRepair.value.applying = false
  }
}

const handleSelectionAction = async (action, text, options = {}) => {
  if (action === 'annotation-highlight' || action === 'annotation-underline') {
    await createReaderAnnotation(
      action === 'annotation-underline' ? 'underline' : 'highlight',
      text,
      options
    )
    return
  }
  if (action === 'annotation-remove') {
    await removeReaderAnnotation(options.annotationId)
    return
  }
  if (action === 'annotation-note') {
    const annotation = readerAnnotations.value.find((note) => note.id === options.annotationId)
    await openSelectionChat('selection-note', annotation?.selected_text || text)
    return
  }
  if (action === 'latex-repair') {
    await openLatexRepairDialog(text, options)
    return
  }
  if (action === 'chapter-note' && !text.trim()) {
    await openChapterNote()
    return
  }
  if (action === 'chapter-note' || action === 'selection-note') {
    await openSelectionChat(action, text)
  }
}

const {
  activeAnnotationId,
  annotationAllowed,
  closeMenu,
  handleMenuAction,
  menuVisible,
  menuX,
  menuY,
  selectedText
} = useSelectionMenu(viewportRef, handleSelectionAction)

const showAnnotationFeedback = (message) => {
  if (annotationFeedbackTimer) window.clearTimeout(annotationFeedbackTimer)
  annotationFeedback.value = message
  annotationFeedbackTimer = window.setTimeout(() => {
    annotationFeedback.value = ''
    annotationFeedbackTimer = null
  }, 3200)
}

const applySavedAnnotations = async () => {
  await nextTick()
  if (!viewportRef.value || renderRevision.value === 0) return
  applyReaderAnnotations(viewportRef.value, readerAnnotations.value)
}

const createReaderAnnotation = async (style, fallbackText, options = {}) => {
  const subject = currentToolSubject.value
  const selectedText = options.anchorText || fallbackText
  if (!subject || !selectedText.trim()) return

  try {
    const annotation = await bookStore.createAnnotation({
      bookId: subject.bookId,
      chapterId: subject.chapterId,
      sourceType: subject.sourceType,
      sourceId: subject.sourceId,
      sourceTitle: subject.sourceTitle,
      selectedText,
      startIndex: options.startIndex || 0,
      contentTarget: options.contentTarget || 'translated',
      style
    })
    readerAnnotations.value = [...readerAnnotations.value, annotation]
    window.getSelection()?.removeAllRanges()
    await applySavedAnnotations()
  } catch (error) {
    console.error('Failed to save reader annotation:', error)
    showAnnotationFeedback('标注保存失败，请重试')
  }
}

const removeReaderAnnotation = async (annotationId) => {
  if (!annotationId) return
  try {
    await bookStore.deleteNote(annotationId)
    readerAnnotations.value = readerAnnotations.value.filter((note) => note.id !== annotationId)
    await applySavedAnnotations()
  } catch (error) {
    console.error('Failed to remove reader annotation:', error)
    showAnnotationFeedback('标注删除失败，请重试')
  }
}

const activateNoteCard = async (card) => {
  activateAskCard(card)
  if (card?.type === 'selection') {
    await focusSelectionSource(card)
  }
  await openConversationPage(card)
}

const openChapterNote = async () => {
  const subject = currentToolSubject.value
  if (!subject) return
  const card = createChapterCard(subject)
  await activateNoteCard(card)
}

const openQuizDialog = async (options = {}) => {
  const subject = currentToolSubject.value
  if (!subject || !currentChapter.value?.id) return
  let card = null
  try {
    const question = await bookStore.fetchNextQuizQuestion(currentChapter.value.id, {
      quizMode: options.quizMode || 'chapter',
      questionType: options.questionType,
      personalizationContext: options.personalizationContext
    })
    card = createQuizQuestionCard(subject, question, options.personalizationContext || '')
  } catch (error) {
    console.error('Failed to load structured quiz question:', error)
    card = ensureQuizCard(subject)
  }
  await activateNoteCard(card)
}

const openConversationPage = async (card) => {
  if (!book.value || !currentItem.value || !card) return

  const metadata = buildConversationMetadata(book.value, currentItem.value)
  const conversationId = createConversationId()
  const routeData = router.resolve({
    name: 'conversation',
    params: {
      id: book.value.id,
      conversationId
    }
  })

  const contextText = await buildReaderItemContext(card)

  saveConversationPayload(conversationId, {
    mode: card.type === 'quiz' ? 'quiz' : 'note',
    card,
    contextText,
    metadata,
    title: buildConversationDocumentTitle(card, metadata)
  })

  window.open(routeData.href, '_blank', 'noopener')
}

const normalizeSourceText = (value = '') => value.replace(/\s+/g, ' ').trim()

const findTextRange = (root, needle) => {
  const normalizedNeedle = normalizeSourceText(needle)
  if (!root || !normalizedNeedle) return null

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
  const textNodes = []
  let combined = ''
  let node = walker.nextNode()
  while (node) {
    const normalizedNodeText = normalizeSourceText(node.textContent || '')
    if (normalizedNodeText) {
      textNodes.push({
        node,
        start: combined.length,
        rawText: node.textContent || '',
        normalizedText: normalizedNodeText
      })
      combined += `${normalizedNodeText} `
    }
    node = walker.nextNode()
  }

  const matchStart = combined.indexOf(normalizedNeedle)
  if (matchStart < 0) return null
  const matchEnd = matchStart + normalizedNeedle.length
  const startEntry = textNodes.find(entry => matchStart >= entry.start && matchStart <= entry.start + entry.normalizedText.length)
  const endEntry = textNodes.find(entry => matchEnd >= entry.start && matchEnd <= entry.start + entry.normalizedText.length)
  if (!startEntry || !endEntry) return null

  const range = document.createRange()
  range.setStart(startEntry.node, 0)
  range.setEnd(endEntry.node, endEntry.rawText.length)
  return range
}

const clearSourceHighlights = () => {
  viewportRef.value?.querySelectorAll?.('.source-note-highlight').forEach((element) => {
    element.replaceWith(...element.childNodes)
  })
}

const focusSelectionSource = async (card) => {
  if (!card?.selectedText) {
    viewportRef.value?.scrollTo?.({ top: 0, behavior: 'smooth' })
    return
  }

  await nextTick()
  clearSourceHighlights()
  const root = viewportRef.value?.querySelector?.('.markdown-body')
  const range = findTextRange(root, card.selectedText)
  if (!range) {
    viewportRef.value?.scrollTo?.({ top: 0, behavior: 'smooth' })
    return
  }

  const marker = document.createElement('mark')
  marker.className = 'source-note-highlight source-note-highlight--selection'
  try {
    range.surroundContents(marker)
  } catch (_error) {
    viewportRef.value?.scrollTo?.({ top: 0, behavior: 'smooth' })
    return
  }
  marker.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const focusRouteNote = async () => {
  const noteId = String(route.query.note_id || '')
  if (!noteId) return
  const card = askCards.value.find((item) => String(item.noteId || '') === noteId)
  if (!card) return

  notesPanelOpen.value = true
  activateAskCard(card)
  if (card.type === 'selection') {
    await focusSelectionSource(card)
  }
}

onMounted(async () => {
  const routeBookId = Number(route.params.id)
  let bookId = Number.isFinite(routeBookId) ? routeBookId : book.value?.id

  if (!bookId) {
    await bookStore.fetchBooks()
    bookId = bookStore.books[0]?.id
  }

  if (!bookId) return

  if (book.value?.id !== bookId || !Array.isArray(book.value?.chapters)) {
    await bookStore.fetchBookDetails(bookId)
  }
  if (!book.value) return

  await nextTick()

  try {
    const tree = await bookStore.fetchReaderTree(book.value.id)
    bookTree.value = Array.isArray(tree?.book) ? tree.book : []
    guideTree.value = Array.isArray(tree?.guide) ? tree.guide : []
  } catch (error) {
    console.error('Failed to load reader tree:', error)
    bookTree.value = []
    guideTree.value = []
  }

  await loadItemFromRouteQuery()
  await focusRouteNote()
  if (route.query.quiz === '1') {
    let personalization = ''
    try {
      const cached = window.sessionStorage.getItem(`bookQuizTarget:${book.value.id}`)
      if (cached) {
        const parsed = JSON.parse(cached)
        personalization = [
          parsed?.target_concept ? `Target concept: ${parsed.target_concept}` : '',
          parsed?.chapter_title ? `Selected chapter: ${parsed.chapter_title}` : '',
          parsed?.reason ? `Reason: ${parsed.reason}` : ''
        ].filter(Boolean).join('\n')
      }
    } catch (_error) {
      personalization = ''
    }
    await openQuizDialog({
      quizMode: String(route.query.quiz_mode || 'book'),
      questionType: String(route.query.question_type || ''),
      personalizationContext: personalization
    })
  }
})

onBeforeUnmount(() => {
  if (annotationFeedbackTimer) window.clearTimeout(annotationFeedbackTimer)
})

watch(
  () => [
    viewMode.value,
    currentItem.value?.id || '',
    currentChapterGuide.value?.id || ''
  ],
  () => {
    loadCurrentChapterGuide()
  }
)

watch(
  () => [renderRevision.value, readerAnnotations.value, viewMode.value],
  () => {
    window.requestAnimationFrame(() => applySavedAnnotations())
  }
)

watch(
  () => [
    route.params.id,
    route.query.reader_type,
    route.query.chapter_id,
    route.query.guide_id,
    route.query.note_id
  ],
  async () => {
    await loadItemFromRouteQuery()
    await focusRouteNote()
  }
)
</script>

<style scoped>
.reader-layout-wrapper {
  display: flex;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: white;
}

.reader-sidebar {
  width: 340px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-color);
  background: #fdfdfd;
}

.reader-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.reader-main :deep(.source-note-highlight) {
  border-radius: 2px;
  padding: 0 2px;
  color: inherit;
}

.reader-main :deep(.source-note-highlight--selection) {
  background: var(--color-selection-soft);
  border-bottom: 1.5px solid var(--color-selection);
}

.reader-main :deep(.source-note-highlight--key-step) {
  background: #e1f5ee;
  border-bottom: 1.5px solid #1d9e75;
}

.reader-main :deep(.source-note-highlight--proof) {
  background: #f1efe8;
  border-bottom: 1.5px solid #8f8c84;
}

.reader-main :deep(.source-note-highlight--underline) {
  background: transparent;
  text-decoration-line: underline;
  text-decoration-color: var(--color-selection);
  text-decoration-thickness: 1.5px;
  text-underline-offset: 0.18em;
}

.reader-main :deep(.reader-annotation) {
  margin: 0;
  padding: 0;
  border-radius: 2px;
  color: inherit;
  cursor: pointer;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
  transition: background-color 160ms ease, text-decoration-color 160ms ease;
}

.reader-main :deep(.reader-annotation--highlight) {
  background: rgba(247, 218, 92, 0.48);
}

.reader-main :deep(.reader-annotation--highlight:hover) {
  background: rgba(244, 207, 48, 0.66);
}

.reader-main :deep(.reader-annotation--underline) {
  background: transparent;
  text-decoration-line: underline;
  text-decoration-color: #a1772c;
  text-decoration-thickness: 1.5px;
  text-underline-offset: 0.18em;
}

.reader-main :deep(.reader-annotation--underline:hover) {
  text-decoration-color: #6f4c14;
}

.annotation-feedback {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 1100;
  padding: 10px 13px;
  border: 1px solid #e2c6be;
  border-radius: 8px;
  background: #fff7f3;
  color: #8c352c;
  box-shadow: 0 10px 26px rgba(79, 48, 39, 0.14);
  font-size: 13px;
  font-weight: 500;
}

.annotation-feedback-enter-active,
.annotation-feedback-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.annotation-feedback-enter-from,
.annotation-feedback-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.latex-repair-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: grid;
  place-items: center;
  padding: 1.5rem;
  background: rgba(28, 25, 21, 0.38);
}

.latex-repair-dialog {
  width: min(760px, 100%);
  max-height: min(860px, 92vh);
  overflow: auto;
  border: 1px solid #ded4c6;
  border-radius: 8px;
  background: #fffdf8;
  box-shadow: 0 20px 52px rgba(29, 24, 16, 0.2);
}

.latex-repair-header,
.latex-repair-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.2rem;
  border-bottom: 1px solid #eee4d7;
}

.latex-repair-actions {
  justify-content: flex-end;
  border-top: 1px solid #eee4d7;
  border-bottom: 0;
}

.latex-repair-kicker {
  margin: 0 0 0.2rem;
  color: #7b6b57;
  font-size: 0.76rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.latex-repair-header h2 {
  margin: 0;
  color: #2f281f;
  font-size: 1.1rem;
}

.modal-icon-btn {
  width: 2rem;
  height: 2rem;
  border: 1px solid #dfd4c5;
  border-radius: 6px;
  background: #fffaf1;
  cursor: pointer;
  font-size: 1.15rem;
  line-height: 1;
}

.latex-repair-body {
  display: grid;
  gap: 1rem;
  padding: 1.2rem;
}

.latex-repair-body label {
  display: grid;
  gap: 0.45rem;
  color: #4b4034;
  font-size: 0.84rem;
  font-weight: 600;
}

.latex-repair-body textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  border: 1px solid #ded4c6;
  border-radius: 6px;
  background: white;
  color: #2f281f;
  font: 0.9rem/1.55 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  padding: 0.75rem;
}

.latex-repair-preview {
  border: 1px solid #ded4c6;
  border-radius: 6px;
  background: white;
}

.preview-label {
  padding: 0.65rem 0.75rem;
  border-bottom: 1px solid #eee4d7;
  color: #7b6b57;
  font-size: 0.8rem;
  font-weight: 600;
}

.latex-preview {
  min-height: 4rem;
  padding: 0.85rem 1rem;
}

.latex-repair-error {
  margin: 0;
  color: #9f2f22;
  font-size: 0.88rem;
}

.primary-btn,
.secondary-btn {
  border-radius: 6px;
  cursor: pointer;
  font: inherit;
  padding: 0.58rem 0.85rem;
}

.primary-btn {
  border: 1px solid #2f6f56;
  background: #2f6f56;
  color: white;
}

.secondary-btn {
  border: 1px solid #d9cdbc;
  background: #fffaf1;
  color: #3a3128;
}

.primary-btn:disabled,
.secondary-btn:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

@media (max-width: 1180px) {
  .reader-sidebar.sidebar {
    width: 300px;
  }
}

@media (max-width: 900px) {
  .reader-layout-wrapper {
    flex-direction: column;
    height: auto;
    min-height: 100vh;
    overflow: auto;
  }

  .reader-main {
    min-height: 58vh;
    overflow: visible;
  }

  .reader-sidebar.sidebar {
    width: 100%;
    height: auto;
    max-height: 36vh;
    border-right: 0;
    border-bottom: 1px solid var(--border-color);
  }
}
</style>
