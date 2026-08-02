const MARKDOWN_EXTENSION = /\.(?:md|markdown)$/i
const GENERATED_TIMESTAMP_SUFFIX = /(?:[\s_-]+)\d{10,}$/

export const formatLibraryBookTitle = (value) => {
  const originalTitle = String(value ?? '').trim()
  if (!originalTitle) return '未命名图书'

  const cleanedTitle = originalTitle
    .replace(MARKDOWN_EXTENSION, '')
    .replace(GENERATED_TIMESTAMP_SUFFIX, '')
    .replace(/_+/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim()
    .replace(/\bmarkdown\b/gi, 'Markdown')

  return cleanedTitle || originalTitle
}
