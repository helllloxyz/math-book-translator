export const normalizeMathDelimiters = (content = '') => {
    return String(content)
        .replace(/(?<!\\)\\\[([\s\S]*?)(?<!\\)\\\]/g, (_match, expression) => (
            `\n$$\n${expression.trim()}\n$$\n`
        ))
        .replace(/(?<!\\)\\\(([\s\S]*?)(?<!\\)\\\)/g, (_match, expression) => (
            `$${expression}$`
        ))
}
