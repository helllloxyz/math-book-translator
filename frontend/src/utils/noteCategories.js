export const NOTE_CATEGORIES = Object.freeze([
  { id: 'notes', label: '笔记' },
  { id: 'quiz', label: 'Quiz' },
  { id: 'marks', label: '标记' }
])

const CATEGORY_IDS = new Set(NOTE_CATEGORIES.map(category => category.id))

export const normalizeNoteCategory = (category) => (
  CATEGORY_IDS.has(category) ? category : 'notes'
)

export const noteCategory = (note) => {
  if (note?.type === 'quiz_chat') return 'quiz'
  if (note?.type === 'annotation') return 'marks'
  return 'notes'
}

export const notesInCategory = (notes, category) => {
  const normalizedCategory = normalizeNoteCategory(category)
  return (Array.isArray(notes) ? notes : []).filter(note => noteCategory(note) === normalizedCategory)
}

export const noteCategoryCounts = (notes) => {
  const counts = { notes: 0, quiz: 0, marks: 0 }
  ;(Array.isArray(notes) ? notes : []).forEach((note) => {
    counts[noteCategory(note)] += 1
  })
  return counts
}

export const annotationStyle = (note) => {
  try {
    const metadata = JSON.parse(note?.note_content || '{}')
    return metadata?.style === 'underline' ? 'underline' : 'highlight'
  } catch (_error) {
    return 'highlight'
  }
}
