export const flattenReaderLeaves = (nodes = [], parentTitles = []) => {
  const leaves = []

  const visit = (node, depth, parents) => {
    if (!node || typeof node !== 'object') return
    if (node.kind === 'leaf') {
      leaves.push({ ...node, depth, parentTitles: parents })
      return
    }
    const nextParents = node.title ? [...parents, node.title] : parents
    ;(node.children || []).forEach((child) => visit(child, depth + 1, nextParents))
  }

  nodes.forEach((node) => visit(node, 0, parentTitles))
  return leaves
}

export const findReaderLeaf = (nodes = [], itemId) => {
  if (!itemId) return null
  return flattenReaderLeaves(nodes).find((leaf) => leaf.id === itemId) || null
}

export const findReaderLeafBySource = (nodes = [], sourceType, sourceId) => {
  if (!sourceType || !sourceId) return null
  return flattenReaderLeaves(nodes).find((leaf) => (
    leaf.source_type === sourceType &&
    leaf.source_id === sourceId
  )) || null
}

export const findChapterGuideLeaf = (nodes = [], chapterIndex) => {
  const normalizedIndex = String(chapterIndex || '').trim()
  if (!normalizedIndex) return null

  const leaves = flattenReaderLeaves(nodes)
  const scopedGuides = leaves.filter((leaf) => (
    leaf.type === 'guide' &&
    String(leaf.scope_id || '').trim() === normalizedIndex
  ))
  return scopedGuides.find((leaf) => leaf.scope_type === 'chapter')
    || scopedGuides.find((leaf) => leaf.scope_type === 'directory')
    || null
}

export const firstReaderLeaf = (nodes = []) => flattenReaderLeaves(nodes)[0] || null

export const findAdjacentReaderLeaves = (nodes = [], itemId) => {
  const leaves = flattenReaderLeaves(nodes)
  const index = leaves.findIndex((leaf) => leaf.id === itemId)
  if (index < 0) {
    return { previous: null, next: null }
  }

  return {
    previous: leaves[index - 1] || null,
    next: leaves[index + 1] || null
  }
}
