const defaultDelay = (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms))

export const appendWithTypewriter = async (content, append, options = {}) => {
    const text = String(content || '')
    if (!text) return

    const chunkSize = Math.max(1, Number(options.chunkSize || 6))
    const intervalMs = Math.max(0, Number(options.intervalMs ?? 12))
    const delay = options.delay || defaultDelay
    const delayAfterLast = options.delayAfterLast === true

    for (let index = 0; index < text.length; index += chunkSize) {
        append(text.slice(index, index + chunkSize))
        if ((index + chunkSize < text.length || delayAfterLast) && intervalMs > 0) {
            await delay(intervalMs)
        }
    }
}

export const createTypewriterQueue = (append, options = {}) => {
    const chunkSize = Math.max(1, Number(options.chunkSize || 6))
    const intervalMs = Math.max(0, Number(options.intervalMs ?? 12))
    const delay = options.delay || defaultDelay
    let pending = ''
    let draining = null

    const drain = async () => {
        while (pending) {
            const visibleChunk = pending.slice(0, chunkSize)
            pending = pending.slice(chunkSize)
            append(visibleChunk)
            if (intervalMs > 0) {
                await delay(intervalMs)
            }
        }
    }

    const startDraining = () => {
        if (draining || !pending) return
        draining = drain().finally(() => {
            draining = null
            startDraining()
        })
    }

    return {
        enqueue(content) {
            const text = String(content || '')
            if (!text) return
            pending += text
            startDraining()
        },
        async flush() {
            while (draining) {
                await draining
            }
        }
    }
}
