export const conversationStorageKey = (conversationId) => `conversation:${conversationId}`

export const safeConversationId = (value = '') => {
  return String(value || '')
    .replace(/[^a-zA-Z0-9:_-]+/g, '-')
    .replace(/^-+|-+$/g, '') || `conversation-${Date.now()}`
}

export const createConversationId = () => {
  const randomId = globalThis.crypto?.randomUUID?.()
    || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
  return `conversation-${randomId}`
}

export const buildConversationMetadata = (book, item) => {
  const chapter = item?.chapter || {}
  const readerType = item?.type || item?.readerType || ''
  const chapterId = chapter.id || item?.chapterId || item?.chapter_id || ''
  const chapterIndex = chapter.chapter_index || item?.chapterIndex || item?.chapter_index || ''

  return {
    bookId: book?.id || '',
    bookTitle: book?.title || '',
    readerType,
    sourceType: item?.source_type || '',
    sourceId: item?.source_id || '',
    sourceTitle: item?.source_title || item?.title || chapter.title_zh || chapter.title_en || '',
    chapterId: readerType === 'chapter' ? chapterId : '',
    chapterIndex: readerType === 'chapter' ? chapterIndex : '',
    guideId: readerType === 'guide' ? (item?.id || item?.guideId || item?.guide_id || '') : ''
  }
}

export const buildConversationDocumentTitle = (card, metadata) => {
  const summary = card?.questionSummary || card?.title || ''
  const prefix = metadata?.chapterIndex || metadata?.chapterId || ''
  return [prefix, summary].filter(Boolean).join(' ').trim() || 'Conversation'
}

export const saveConversationPayload = (conversationId, payload) => {
  window.localStorage.setItem(
    conversationStorageKey(conversationId),
    JSON.stringify({
      ...payload,
      updatedAt: new Date().toISOString()
    })
  )
}

export const loadConversationPayload = (conversationId) => {
  const raw = window.localStorage.getItem(conversationStorageKey(conversationId))
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch (_error) {
    return null
  }
}
