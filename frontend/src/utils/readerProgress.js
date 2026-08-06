import { flattenReaderLeaves } from './readerTree.js'

const STORAGE_PREFIX = 'math-book-reader-progress'

const stringValue = (value) => {
  if (value === null || value === undefined) return ''
  return String(value)
}

const chapterIdForItem = (item) => stringValue(item?.chapter_id || item?.chapterId)

const chapterLeaves = (bookTree) => flattenReaderLeaves(bookTree)
  .filter((item) => item.type === 'chapter' && chapterIdForItem(item))

const storageKey = (bookId) => `${STORAGE_PREFIX}:${bookId}`

export const getFurthestReadChapter = (bookId, bookTree = []) => {
  if (!bookId || typeof localStorage === 'undefined') return null

  try {
    const stored = localStorage.getItem(storageKey(bookId))
    if (!stored) return null
    const progress = JSON.parse(stored)
    const storedChapterId = stringValue(progress?.chapterId)
    if (!storedChapterId) return null

    return chapterLeaves(bookTree).find((item) => (
      chapterIdForItem(item) === storedChapterId
    )) || null
  } catch (_error) {
    return null
  }
}

export const rememberFurthestReadChapter = (bookId, bookTree = [], item) => {
  if (!bookId || item?.type !== 'chapter') return getFurthestReadChapter(bookId, bookTree)

  const leaves = chapterLeaves(bookTree)
  const currentChapterId = chapterIdForItem(item)
  const currentIndex = leaves.findIndex((leaf) => chapterIdForItem(leaf) === currentChapterId)
  if (currentIndex < 0) return getFurthestReadChapter(bookId, bookTree)

  const furthest = getFurthestReadChapter(bookId, bookTree)
  const furthestIndex = furthest
    ? leaves.findIndex((leaf) => chapterIdForItem(leaf) === chapterIdForItem(furthest))
    : -1

  if (furthestIndex >= currentIndex) return furthest
  if (typeof localStorage === 'undefined') return item

  try {
    localStorage.setItem(storageKey(bookId), JSON.stringify({
      chapterId: currentChapterId
    }))
  } catch (_error) {
    // Reading remains usable when storage is disabled or full.
  }
  return item
}
