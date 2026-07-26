const STORAGE_PREFIX = 'math-book-reader-status'

const progressValues = new Set(['unread', 'reading', 'skipped', 'finished'])
const difficultyValues = new Set(['easy', 'confused', 'hard'])

export const progressOptions = [
  { value: 'unread', label: '未阅读' },
  { value: 'reading', label: '在读' },
  { value: 'skipped', label: '跳过' },
  { value: 'finished', label: '完成' },
]

export const difficultyOptions = [
  { value: 'easy', label: '简单' },
  { value: 'confused', label: '困惑' },
  { value: 'hard', label: '困难' },
]

export const defaultChapterReadingStatus = () => ({
  progress: 'unread',
  difficulty: 'easy',
})

const storageKey = (bookId, chapterId) => `${STORAGE_PREFIX}:${bookId}:${chapterId}`

const normalizeChapterReadingStatus = (status = {}) => {
  const defaults = defaultChapterReadingStatus()
  return {
    progress: progressValues.has(status.progress) ? status.progress : defaults.progress,
    difficulty: difficultyValues.has(status.difficulty) ? status.difficulty : defaults.difficulty,
  }
}

export const getChapterReadingStatus = (bookId, chapterId) => {
  if (!bookId || !chapterId || typeof localStorage === 'undefined') {
    return defaultChapterReadingStatus()
  }

  try {
    const stored = localStorage.getItem(storageKey(bookId, chapterId))
    return normalizeChapterReadingStatus(stored ? JSON.parse(stored) : {})
  } catch (_error) {
    return defaultChapterReadingStatus()
  }
}

export const setChapterReadingStatus = (bookId, chapterId, status) => {
  const normalized = normalizeChapterReadingStatus(status)
  if (!bookId || !chapterId || typeof localStorage === 'undefined') return normalized

  localStorage.setItem(storageKey(bookId, chapterId), JSON.stringify(normalized))
  return normalized
}
