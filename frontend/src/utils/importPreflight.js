export const extractImportPreflight = (error) => {
  const detail = error?.response?.data?.detail
  if (detail?.preflight && typeof detail.preflight === 'object') {
    return detail.preflight
  }
  return null
}

export const formatImportPreflightMessage = (preflight) => {
  if (!preflight) return ''
  const parts = []
  if (preflight.recommendation) parts.push(String(preflight.recommendation))

  for (const issue of preflight.issues || []) {
    if (!issue) continue
    if (typeof issue === 'string') {
      parts.push(issue)
      continue
    }
    const message = issue.message || issue.detail
    if (message) parts.push(String(message))
    for (const example of issue.examples || []) {
      parts.push(String(example))
    }
  }

  return parts.filter(Boolean).join('\n')
}

export const formatImportErrorMessage = (error) => {
  const detail = error?.response?.data?.detail
  const preflightMessage = formatImportPreflightMessage(extractImportPreflight(error))
  if (preflightMessage) return preflightMessage
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return error?.message || 'Unknown error'
}
