const createEmptyLearningContext = () => ({
  summary: '',
  concepts: [],
  key_theorems: [],
  dependencies: []
})

const formatLearningList = (items) => {
  if (!Array.isArray(items) || items.length === 0) return 'None available.'

  return items.map(item => {
    if (item == null) return '- Unnamed'
    if (typeof item === 'string') return `- ${item}`
    if (typeof item !== 'object') return `- ${String(item)}`

    const name = item.name || item.title || 'Unnamed'
    const description = item.description || item.statement || ''
    return `- ${name}${description ? `: ${description}` : ''}`
  }).join('\n')
}

export function useChapterLearningContext() {
  const buildCardContext = (card, chapter, learning = createEmptyLearningContext()) => {
    const chapterTitle = chapter?.title_zh || chapter?.title_en || ''
    const parts = [`Chapter: ${chapterTitle}`]

    if (card?.type === 'selection') {
      parts.push('Selected text:', card.selectedText || '')
    }

    parts.push(
      'Chapter summary:',
      learning.summary || 'No chapter summary is available yet.',
      'Chapter concepts:',
      formatLearningList(learning.concepts),
      'Key theorems:',
      formatLearningList(learning.key_theorems),
      'Dependencies:',
      formatLearningList(learning.dependencies)
    )

    return parts.join('\n\n')
  }

  return {
    buildCardContext,
    createEmptyLearningContext,
    formatLearningList
  }
}
