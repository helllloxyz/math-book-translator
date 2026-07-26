import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const component = readFileSync(resolve(currentDir, 'ConversationDialog.vue'), 'utf8')

assert.match(
  component,
  /<Teleport\s+to="body"\s+:disabled="standalone">/,
  'standalone conversations should render inside the page instead of being teleported below the app shell'
)

assert.match(component, /class="dialog-status-dot"/, 'dialog header should include a compact status dot')
assert.match(component, /class="standalone-context-summary"/, 'standalone conversations should surface source metadata in the main page header')
assert.match(component, /class="standalone-actions"/, 'standalone conversations should keep source and delete actions in the top bar')
assert.match(component, /v-if="!standalone"/, 'the fixed source sidebar should be reserved for embedded dialog mode')
assert.match(component, /class="dialog-panel"/, 'conversation header and content should live in the main dialog panel')
assert.match(component, /class="dialog-content"/, 'dialog should keep messages and composer in a single content column')
assert.match(component, /class="dialog-context-sidebar"/, 'embedded dialog mode should still support the left context sidebar')
assert.match(component, /class="delete-conversation-button"/, 'left context sidebar should include a delete button')
assert.match(component, /emit\('delete', card\)/, 'delete button should emit the active card')
assert.match(component, /class="question-block latex-content question-context-details"/, 'selected context should render as a collapsible question block')
assert.match(
  component,
  /<section ref="messagesRef"[\s\S]*?<details[\s\S]*?v-if="isSelectionNote && selectedText"[\s\S]*?<p v-if="showEmptyMessage"/,
  'question context should render before the empty conversation state'
)
assert.match(component, /<summary>Question context<\/summary>/, 'question context should be collapsible')
assert.doesNotMatch(component, /Type your answer to start this quiz dialogue\./, 'quiz dialogues should not show the old empty prompt scaffold')
assert.match(component, /showEmptyMessage/, 'empty state visibility should be explicit so quiz can suppress the scaffold')
assert.doesNotMatch(component, /v-if="standalone && isQuiz" class="quiz-context standalone-context-card"/, 'standalone quiz conversations should not render the old quiz context card above the dialogue')
assert.match(component, /Array\.isArray\(props\.card\.messages\)\) return props\.card\.messages/, 'dialog should consume live message arrays so follow-up streams render without refresh')
assert.match(component, /class="dialog-toolbar"/, 'input footer should expose academic tool pills')
assert.match(component, /v-for="style in responseStyles"/, 'response style buttons should be loaded from configuration')
assert.match(component, /buildApiUrl\('\/config\/conversation-styles\.json'\)/, 'dialog should load editable root config response styles through the API')
assert.match(component, /responseStylePrompt/, 'send payload should include the selected response style prompt')
assert.match(component, /if \(!Array\.isArray\(rawStyles\)\) return DEFAULT_RESPONSE_STYLES/, 'dialog should fall back to default styles only for invalid config shapes')
assert.doesNotMatch(component, /styles\.length \? styles : DEFAULT_RESPONSE_STYLES/, 'dialog should honor an intentionally empty response style config')
assert.match(component, /class="thinking-indicator"/, 'dialog should show a waiting indicator before the first streamed token')
assert.match(component, /class="suggested-questions-section"/, 'assistant answers should include suggested follow-up questions')
assert.doesNotMatch(component, /\[\{\{\s*reference\.id\s*\}\}\]/, 'suggested questions should not render numbered citation labels')
assert.match(component, /copySelectionAsLatex/, 'dialog copy should preserve rendered KaTeX as LaTeX source')
assert.match(component, /document\.addEventListener\('copy', handleLatexCopy\)/, 'dialog should intercept copy events while mounted')
assert.match(component, /document\.removeEventListener\('copy', handleLatexCopy\)/, 'dialog should clean up the copy listener')
assert.match(component, /@keydown\.enter\.exact\.prevent="submitPrompt"/, 'enter should submit follow-up prompts from the dialog textarea')
assert.match(component, /min-height:\s*calc\(2em \+ 16px\)/, 'input textarea should default to two lines of text height')
assert.match(component, /\.conversation-dialog\s*\{[\s\S]*?flex-direction:\s*row;/, 'embedded dialog left sidebar should span the full dialog height')
assert.match(component, /width:\s*min\(860px,\s*calc\(100vw - 2rem\)\)/, 'dialog should be wider when the left sidebar is visible')
assert.match(component, /\.conversation-dialog\.standalone\s*\{[\s\S]*?width:\s*100%;[\s\S]*?height:\s*100vh;/, 'standalone conversation should fill the viewport instead of rendering as a framed panel')
assert.match(component, /\.conversation-dialog\.standalone \.dialog-panel\s*\{[\s\S]*?background:\s*transparent;/, 'standalone conversation panel should blend into the page background')
assert.match(component, /\.conversation-dialog\.standalone \.message-list\s*\{[\s\S]*?max-width:\s*760px;/, 'standalone message column should preserve a readable width')
assert.match(component, /\.answer-prose\s*\{[\s\S]*?font-size:\s*14px;/, 'answer prose should use a larger reading font')
assert.doesNotMatch(component, /\.delete-conversation-button\s*\{[\s\S]*?#(?:fff5f5|ffecec|9a2f2f|7c1f1f|e3b9b9|cc7c7c)/, 'delete button should use the same neutral palette as secondary actions')

console.log('conversation dialog behavior ok')
