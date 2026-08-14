const ZERO_WIDTH_PATTERN = /[\u200b-\u200d\u2060]/g
const MATH_CLUSTER_PATTERN = /[A-Za-z0-9\u0370-\u03ff\u2070-\u209f\s\u200b-\u200d\u2060∞∈∗⋃()[\]{}_^+*\/\-=,:.\\]+/gu
const TRIPLED_SYMBOL_PATTERN = /(^|[^\p{L}\p{N}])([\p{L}\p{N}])\2\2(?=$|[^\p{L}\p{N}])/gu

const normalizedVisualText = (value) => value.replace(/[\s\u200b-\u200d\u2060]/g, '')

const recoverKatexCluster = (rawCluster) => {
  const leadingWhitespace = rawCluster.match(/^\s*/u)?.[0] || ''
  const trailingWhitespace = rawCluster.match(/\s*$/u)?.[0] || ''
  const cluster = rawCluster.trim()
  if (!cluster.includes('\\')) return { text: rawCluster, recovered: false }

  let bestMatch = null
  for (let middleStart = 1; middleStart < cluster.length - 1; middleStart += 1) {
    const visualPrefix = cluster.slice(0, middleStart)
    const normalizedPrefix = normalizedVisualText(visualPrefix)
    if (!normalizedPrefix) continue

    for (let middleEnd = middleStart + 1; middleEnd < cluster.length; middleEnd += 1) {
      const texSource = cluster.slice(middleStart, middleEnd)
      if (!texSource.includes('\\')) continue

      const visualSuffix = cluster.slice(middleEnd)
      if (normalizedPrefix !== normalizedVisualText(visualSuffix)) continue

      const score = normalizedPrefix.length
      if (!bestMatch || score > bestMatch.score) {
        bestMatch = { score, texSource: texSource.trim() }
      }
    }
  }

  if (!bestMatch?.texSource) return { text: rawCluster, recovered: false }
  return {
    text: `${leadingWhitespace}$${bestMatch.texSource}$${trailingWhitespace}`,
    recovered: true
  }
}

export const normalizeLegacyAnnotationText = (value = '') => {
  const input = String(value || '')
  let recoveredMath = false
  const recovered = input.replace(MATH_CLUSTER_PATTERN, (cluster) => {
    const result = recoverKatexCluster(cluster)
    recoveredMath ||= result.recovered
    return result.text
  })

  const withoutRenderingArtifacts = recovered.replace(ZERO_WIDTH_PATTERN, '')
  if (!recoveredMath) return withoutRenderingArtifacts

  return withoutRenderingArtifacts.replace(
    TRIPLED_SYMBOL_PATTERN,
    (_match, boundary, symbol) => `${boundary}$${symbol}$`
  )
}
