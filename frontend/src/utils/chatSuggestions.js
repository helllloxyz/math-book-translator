export const SUGGESTED_QUESTIONS_MARKER = '<!--SUGGESTED_QUESTIONS-->'

const normalizeQuestions = (questions) => {
    const seen = new Set()
    const normalized = []

    for (const question of questions) {
        const value = String(question || '').trim()
        if (!value || seen.has(value)) continue
        seen.add(value)
        normalized.push(value)
        if (normalized.length === 3) break
    }

    return normalized
}

export const extractSuggestedQuestions = (rawContent) => {
    const content = String(rawContent || '')
    const markerIndex = content.lastIndexOf(SUGGESTED_QUESTIONS_MARKER)
    if (markerIndex < 0) {
        return { content, suggestedQuestions: [] }
    }

    const answer = content.slice(0, markerIndex).trimEnd()
    const suggestionBlock = content.slice(markerIndex + SUGGESTED_QUESTIONS_MARKER.length)
    const questions = suggestionBlock
        .split(/\r?\n/)
        .map((line) => line.match(/^\s*-\s+(.+?)\s*$/)?.[1] || '')

    return {
        content: answer,
        suggestedQuestions: normalizeQuestions(questions)
    }
}

export const sanitizeSuggestedQuestions = (rawQuestions) => (
    Array.isArray(rawQuestions) ? normalizeQuestions(rawQuestions) : []
)
