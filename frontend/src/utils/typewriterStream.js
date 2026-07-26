const defaultDelay = (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms))

export const appendWithTypewriter = async (content, append, options = {}) => {
    const text = String(content || '')
    if (!text) return

    const chunkSize = Math.max(1, Number(options.chunkSize || 6))
    const intervalMs = Math.max(0, Number(options.intervalMs ?? 12))
    const delay = options.delay || defaultDelay

    for (let index = 0; index < text.length; index += chunkSize) {
        append(text.slice(index, index + chunkSize))
        if (index + chunkSize < text.length && intervalMs > 0) {
            await delay(intervalMs)
        }
    }
}
