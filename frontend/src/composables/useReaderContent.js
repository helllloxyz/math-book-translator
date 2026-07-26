import { ref, nextTick } from 'vue'
import mermaid from 'mermaid'
import { renderMarkdown, renderMath } from '../utils/renderer'

export function useReaderContent(bookStore, book, viewportRef) {
  const currentItem = ref(null)
  const loading = ref(false)
  const renderedSource = ref('')
  const renderedTarget = ref('')
  const activeRequestId = ref(0)

  const resetContentState = () => {
    renderedSource.value = ''
    renderedTarget.value = ''
  }

  const renderViewportMathAndMermaid = async (requestId) => {
    await nextTick()
    if (requestId !== activeRequestId.value || !viewportRef.value) return

    viewportRef.value.querySelectorAll('.latex-content').forEach((element) => {
      try {
        renderMath(element)
      } catch (error) {
        console.error('Failed to render math:', error)
      }
    })
    if (requestId !== activeRequestId.value) return

    const mermaidNodes = viewportRef.value.querySelectorAll('.mermaid')
    if (!mermaidNodes.length) return

    try {
      await mermaid.run({ nodes: mermaidNodes })
    } catch (error) {
      console.error('Failed to render Mermaid diagrams:', error)
    }
  }

  const scheduleViewportRender = (requestId) => {
    window.requestAnimationFrame(() => {
      window.setTimeout(() => {
        renderViewportMathAndMermaid(requestId)
      }, 0)
    })
  }

  const renderCurrentViewport = () => {
    scheduleViewportRender(activeRequestId.value)
  }

  const normalizeList = (value) => {
    if (Array.isArray(value)) return value
    if (typeof value === 'string' && value.trim()) return [value]
    return []
  }

  const formatLearningItem = (item) => {
    if (typeof item === 'string') return item
    if (!item || typeof item !== 'object') return ''

    const title = item.name || item.title || item.term || ''
    const detail = item.description || item.statement || item.summary || item.content || ''
    if (title && detail) return `**${title}:** ${detail}`
    return title || detail
  }

  const formatLearningSection = (title, value) => {
    const items = normalizeList(value).map(formatLearningItem).filter(Boolean)
    if (!items.length) return ''

    return [`## ${title}`, ...items.map((item) => `- ${item}`)].join('\n')
  }

  const learningToMarkdown = (learning) => {
    const sections = [
      learning?.summary ? `## Summary\n\n${learning.summary}` : '',
      formatLearningSection('Concepts', learning?.concepts),
      formatLearningSection('Key Theorems', learning?.key_theorems),
      formatLearningSection('Dependencies', learning?.dependencies)
    ].filter(Boolean)

    return sections.length ? sections.join('\n\n') : '_No learning summary available._'
  }

  const loadChapter = async (item, requestId) => {
    const chapterId = item.chapterId || item.chapter_id
    const data = await bookStore.fetchReaderContent(book.value?.id, {
      readerType: 'chapter',
      chapterId
    })
    if (requestId !== activeRequestId.value) return
    if (!data) {
      throw new Error(`Chapter content not found: ${chapterId}`)
    }

    const rawContent = typeof data.content_raw === 'string' ? data.content_raw : ''
    const translatedContent = typeof data.content_translated === 'string' && data.content_translated.trim()
      ? data.content_translated
      : rawContent
    if (!rawContent.trim() && !translatedContent.trim()) {
      throw new Error(`Chapter content is empty: ${item.chapterId}`)
    }

    renderedSource.value = renderMarkdown(rawContent, book.value)
    renderedTarget.value = renderMarkdown(translatedContent, book.value)
  }

  const loadGuide = async (item, requestId) => {
    const chapterId = item.chapterId || item.chapter_id
    const chapterRequest = chapterId
      ? bookStore.fetchReaderContent(book.value?.id, {
          readerType: 'chapter',
          chapterId
        }).catch((error) => {
          console.error('Failed to load guide chapter context:', error)
          return null
        })
      : Promise.resolve(null)
    const [data, chapterData] = await Promise.all([
      bookStore.fetchReaderContent(book.value?.id, {
        readerType: 'guide',
        guideId: item.id
      }),
      chapterRequest
    ])
    if (requestId !== activeRequestId.value) return
    if (!data) {
      throw new Error(`Guide content not found: ${item.filename}`)
    }

    if (typeof data.content !== 'string' || !data.content) {
      throw new Error(`Guide content is empty: ${item.filename}`)
    }

    if (chapterData) {
      const rawContent = typeof chapterData.content_raw === 'string' ? chapterData.content_raw : ''
      const translatedContent = typeof chapterData.content_translated === 'string' && chapterData.content_translated.trim()
        ? chapterData.content_translated
        : rawContent
      renderedSource.value = renderMarkdown(translatedContent, book.value)
    }
    renderedTarget.value = renderMarkdown(data.content, book.value)
  }

  const loadLearning = async (item, requestId) => {
    const chapterId = item.chapterId || item.chapter_id
    const chapterRequest = chapterId
      ? bookStore.fetchReaderContent(book.value?.id, {
          readerType: 'chapter',
          chapterId
        }).catch((error) => {
          console.error('Failed to load learning chapter context:', error)
          return null
        })
      : Promise.resolve(null)
    const [data, chapterData] = await Promise.all([
      bookStore.fetchReaderContent(book.value?.id, {
        readerType: 'learning',
        chapterId
      }),
      chapterRequest
    ])
    if (requestId !== activeRequestId.value) return

    if (chapterData) {
      const rawContent = typeof chapterData.content_raw === 'string' ? chapterData.content_raw : ''
      const translatedContent = typeof chapterData.content_translated === 'string' && chapterData.content_translated.trim()
        ? chapterData.content_translated
        : rawContent
      renderedSource.value = renderMarkdown(translatedContent, book.value)
    }
    const learningData = data?.learning || data
    renderedTarget.value = renderMarkdown(learningToMarkdown(learningData), book.value)
  }

  const loadItem = async (item) => {
    const requestId = activeRequestId.value + 1
    activeRequestId.value = requestId

    resetContentState()

    if (!item) {
      currentItem.value = null
      loading.value = false
      return
    }

    currentItem.value = item
    loading.value = true

    try {
      if (item.type === 'chapter') {
        await loadChapter(item, requestId)
      } else if (item.type === 'guide') {
        await loadGuide(item, requestId)
      } else if (item.type === 'learning') {
        await loadLearning(item, requestId)
      } else {
        throw new Error(`Unsupported reader item type: ${item.type}`)
      }
    } catch (error) {
      if (requestId !== activeRequestId.value) return

      console.error('Failed to load reader item:', error)
      renderedTarget.value = renderMarkdown('**Error:** Failed to load content.', book.value)
    } finally {
      if (requestId !== activeRequestId.value) return

      loading.value = false
      scheduleViewportRender(requestId)
    }
  }

  return {
    currentItem,
    loading,
    renderedSource,
    renderedTarget,
    loadItem,
    renderCurrentViewport
  }
}
