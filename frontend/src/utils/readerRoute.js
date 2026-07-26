import { flattenReaderLeaves, firstReaderLeaf } from './readerTree.js'

const stringValue = (value) => {
  if (value === null || value === undefined) return ''
  return String(value)
}

const mergeExtraQuery = (query, extraQuery = {}) => {
  Object.entries(extraQuery || {}).forEach(([key, value]) => {
    const normalized = stringValue(value)
    if (normalized) query[key] = normalized
  })
  return query
}

export const buildReaderItemQuery = (item, extraQuery = {}) => {
  if (!item) return mergeExtraQuery({}, extraQuery)

  const query = {
    reader_type: stringValue(item.type)
  }

  if (item.type === 'chapter' || item.type === 'learning') {
    query.chapter_id = stringValue(item.chapterId || item.chapter_id)
  }

  if (item.type === 'guide') {
    query.guide_id = stringValue(item.id || item.guideId || item.guide_id)
  }

  Object.keys(query).forEach((key) => {
    if (!query[key]) delete query[key]
  })

  return mergeExtraQuery(query, extraQuery)
}

export const findReaderLeafByRouteQuery = (bookTree = [], guideTree = [], query = {}) => {
  const readerType = stringValue(query.reader_type)
  const chapterId = stringValue(query.chapter_id)
  const guideId = stringValue(query.guide_id)
  const leaves = [...flattenReaderLeaves(bookTree), ...flattenReaderLeaves(guideTree)]

  if (readerType === 'guide' && guideId) {
    const guide = leaves.find((leaf) => leaf.type === 'guide' && leaf.id === guideId)
    if (guide) return guide
  }

  if ((readerType === 'chapter' || readerType === 'learning') && chapterId) {
    const chapter = leaves.find((leaf) => (
      leaf.type === readerType &&
      stringValue(leaf.chapter_id || leaf.chapterId) === chapterId
    ))
    if (chapter) return chapter
  }

  return firstReaderLeaf(bookTree)
    || firstReaderLeaf(guideTree)
}
