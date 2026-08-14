export const appendQuickInputText = (currentDraft, inputText) => {
  const current = String(currentDraft || '').trimEnd()
  const addition = String(inputText || '').trim()
  if (!addition) return current
  return current ? `${current}\n\n${addition}` : addition
}
