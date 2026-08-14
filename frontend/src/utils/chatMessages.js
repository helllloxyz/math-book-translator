import { sanitizeSuggestedQuestions } from './chatSuggestions.js'

const CHAT_BLOCK_RE = /<div\s+class="(chat-user|chat-ai)">([\s\S]*?)<\/div>/gi

const sanitizeRole = (role) => role === 'user' ? 'user' : 'assistant'

const decodeHtmlEntities = (value = '') => {
    return value
        .replaceAll('&nbsp;', ' ')
        .replaceAll('&amp;', '&')
        .replaceAll('&lt;', '<')
        .replaceAll('&gt;', '>')
        .replaceAll('&quot;', '"')
        .replaceAll('&#39;', "'")
}

const stripTags = (value = '') => {
    return value
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<\/p>/gi, '\n')
        .replace(/<[^>]*>/g, '')
}

const sanitizeMessages = (messages) => {
    if (!Array.isArray(messages)) return []
    return messages
        .map((message) => {
            const role = sanitizeRole(message?.role)
            const suggestedQuestions = role === 'assistant'
                ? sanitizeSuggestedQuestions(message?.suggestedQuestions)
                : []
            return {
                role,
                content: String(message?.content || ''),
                ...(suggestedQuestions.length ? { suggestedQuestions } : {})
            }
        })
}

const parseLegacyHtmlMessages = (content) => {
    const messages = []
    CHAT_BLOCK_RE.lastIndex = 0
    let match = CHAT_BLOCK_RE.exec(content)
    while (match) {
        const role = match[1] === 'chat-user' ? 'user' : 'assistant'
        const normalizedContent = decodeHtmlEntities(stripTags(match[2])).trim()
        messages.push({ role, content: normalizedContent })
        match = CHAT_BLOCK_RE.exec(content)
    }
    return messages
}

export const deserializeMessages = (rawValue) => {
    if (Array.isArray(rawValue)) return sanitizeMessages(rawValue)
    if (typeof rawValue !== 'string') return []

    const content = rawValue.trim()
    if (!content) return []

    if (content.startsWith('[') || content.startsWith('{')) {
        try {
            const parsed = JSON.parse(content)
            if (Array.isArray(parsed)) return sanitizeMessages(parsed)
            if (Array.isArray(parsed?.messages)) return sanitizeMessages(parsed.messages)
        } catch (_error) {
            // Fall through to legacy format parsing.
        }
    }

    const legacyMessages = parseLegacyHtmlMessages(content)
    if (legacyMessages.length) return legacyMessages

    const fallbackText = decodeHtmlEntities(stripTags(content)).trim()
    return fallbackText ? [{ role: 'assistant', content: fallbackText }] : []
}

export const serializeMessages = (messages) => {
    return JSON.stringify(sanitizeMessages(messages))
}
