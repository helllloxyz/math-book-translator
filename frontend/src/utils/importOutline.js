const normalizeLevel = (value) => {
  const level = Number(value)
  return Number.isFinite(level) && level > 0 ? level : 1
}

export const importOutlineNodeLevel = (node, splitLevelById = {}) => {
  const configuredLevel = splitLevelById[node?.id]
  if (configuredLevel === 'delete') {
    return normalizeLevel(node?.level)
  }
  return normalizeLevel(configuredLevel ?? node?.level)
}

export const importOutlineGroupChildCount = (nodes = [], rootIndex, splitLevelById = {}) => {
  const root = nodes[rootIndex]
  if (!root || importOutlineNodeLevel(root, splitLevelById) !== 1) return 0

  let count = 0
  for (let index = rootIndex + 1; index < nodes.length; index += 1) {
    if (importOutlineNodeLevel(nodes[index], splitLevelById) <= 1) break
    count += 1
  }
  return count
}

export const importOutlineLevelOneGroups = (nodes = [], splitLevelById = {}) => (
  nodes.filter((node, index) => importOutlineGroupChildCount(nodes, index, splitLevelById) > 0)
)

export const filterCollapsedImportOutlineRows = (
  nodes = [],
  collapsedLevelOneIds = new Set(),
  splitLevelById = {}
) => {
  const collapsedIds = collapsedLevelOneIds instanceof Set
    ? collapsedLevelOneIds
    : new Set(collapsedLevelOneIds || [])
  let hideCurrentGroupChildren = false

  return nodes.filter((node) => {
    if (importOutlineNodeLevel(node, splitLevelById) <= 1) {
      hideCurrentGroupChildren = collapsedIds.has(node.id)
      return true
    }
    return !hideCurrentGroupChildren
  })
}
