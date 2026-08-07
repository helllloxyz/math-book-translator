import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const currentDir = dirname(fileURLToPath(import.meta.url))
const component = readFileSync(resolve(currentDir, 'ConversationDialog.vue'), 'utf8')

assert.doesNotMatch(
  component,
  /<Teleport\b/,
  'conversation pages should not use Teleport because they render their dialog directly in the route view'
)

assert.match(component, /class="dialog-status-dot"/, 'dialog header should include a compact status dot')
assert.match(component, /class="standalone-details"/, 'standalone conversations should keep secondary status information collapsible')
assert.match(component, /class="standalone-details-grid"/, 'expanded standalone details should expose source metadata and model status')
assert.doesNotMatch(component, /class="standalone-context-summary"/, 'standalone headers should not spread metadata across the full header row')
assert.match(component, /class="standalone-actions"/, 'standalone conversations should keep source and delete actions in the top bar')
assert.match(component, /class="standalone-actions"[\s\S]*?class="standalone-details"[\s\S]*?class="delete-conversation-button"/, 'standalone details should sit beside the source action instead of taking a separate header row')
assert.match(component, /title="Go to source"/, 'source action should retain a hover label after becoming icon-only')
assert.match(component, /title="Delete"/, 'delete action should retain a hover label after becoming icon-only')
assert.match(component, /title="详细信息"/, 'details action should retain a hover label after becoming icon-only')
assert.match(component, /class="action-icon"/, 'conversation actions should render compact SVG icons')
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
assert.match(component, /class="question-context-content" v-html="renderMessage\(selectedText\)"/, 'question context should pass selected Markdown through the KaTeX-capable renderer')
assert.doesNotMatch(component, /Type your answer to start this quiz dialogue\./, 'quiz dialogues should not show the old empty prompt scaffold')
assert.match(component, /showEmptyMessage/, 'empty state visibility should be explicit so quiz can suppress the scaffold')
assert.doesNotMatch(component, /v-if="standalone && isQuiz" class="quiz-context standalone-context-card"/, 'standalone quiz conversations should not render the old quiz context card above the dialogue')
assert.match(component, /Array\.isArray\(props\.card\.messages\)\) return props\.card\.messages/, 'dialog should consume live message arrays so follow-up streams render without refresh')
assert.doesNotMatch(component, /renderKatexMath|renderMathInElement/, 'dialog must not mutate the Vue-managed message list with KaTeX auto-rendering')
assert.match(component, /const syncMessageScroll = \(\) =>/, 'stream updates should only synchronize scrolling after Vue renders')
assert.match(component, /class="dialog-toolbar"/, 'input footer should expose academic tool pills')
assert.match(component, /v-if="!isQuiz" class="dialog-toolbar"/, 'note response-style tools should stay out of the teach-back quiz composer')
assert.match(component, /class="quiz-answer-guidance"/, 'quiz composer should explain that natural-language answers do not require formulas')
assert.match(component, /用自己的话讲讲，不必输入公式/, 'quiz answer placeholder should invite a natural-language explanation')
assert.match(component, /v-for="style in responseStyles"/, 'response style buttons should be loaded from configuration')
assert.match(component, /buildApiUrl\('\/config\/conversation-styles\.json'\)/, 'dialog should load editable root config response styles through the API')
assert.match(component, /responseStylePrompt/, 'send payload should include the selected response style prompt')
assert.match(component, /if \(!Array\.isArray\(rawStyles\)\) return DEFAULT_RESPONSE_STYLES/, 'dialog should fall back to default styles only for invalid config shapes')
assert.doesNotMatch(component, /styles\.length \? styles : DEFAULT_RESPONSE_STYLES/, 'dialog should honor an intentionally empty response style config')
assert.match(component, /class="thinking-indicator"/, 'dialog should show a waiting indicator before the first streamed token')
assert.match(component, /class="regenerate-quiz-button"/, 'Quiz conversations should expose a visible regenerate-question action')
assert.match(component, /emit\('regenerate'\)/, 'the regenerate action should be owned by the conversation page')
assert.match(component, /class="quiz-candidate-pool"/, 'Quiz pages should present the current candidate pool before the answer composer')
assert.match(component, /emit\('select-question', question\)/, 'learners should be able to choose which candidate to answer')
assert.match(component, /quizSelectionLocked/, 'candidate switching should lock after an answer has started')
assert.match(component, /typewriter-active/, 'a generated Quiz question should show an active typewriter caret while it is revealed')
assert.match(component, /class="quiz-generation-error"/, 'Quiz generation errors should include an inline retry state')
assert.match(component, /class="suggested-questions-section"/, 'assistant answers should include suggested follow-up questions')
assert.doesNotMatch(component, /\[\{\{\s*reference\.id\s*\}\}\]/, 'suggested questions should not render numbered citation labels')
assert.match(component, /copySelectionAsLatex/, 'dialog copy should preserve rendered KaTeX as LaTeX source')
assert.match(component, /document\.addEventListener\('copy', handleLatexCopy\)/, 'dialog should intercept copy events while mounted')
assert.match(component, /document\.removeEventListener\('copy', handleLatexCopy\)/, 'dialog should clean up the copy listener')
assert.match(component, /@keydown\.enter\.exact\.prevent="submitPrompt"/, 'enter should submit follow-up prompts from the dialog textarea')
assert.match(
  component,
  /if \(!prompt \|\| props\.card\?\.loading\) return\s+draft\.value = ''\s+emit\('send'/,
  'accepted prompts should clear the composer before the send handler can trigger a loading render'
)
assert.match(component, /props\.card\?\.initialPrompt/, 'a selected passage should be able to prefill the question composer')
assert.match(component, /messages\.value\.length \? '' : String\(props\.card\?\.initialPrompt \|\| ''\)/, 'prefill should only apply to a new conversation, not overwrite a saved follow-up')
assert.match(component, /min-height:\s*calc\(2em \+ 16px\)/, 'input textarea should default to two lines of text height')
assert.match(component, /\.conversation-dialog\s*\{[\s\S]*?flex-direction:\s*row;/, 'embedded dialog left sidebar should span the full dialog height')
assert.match(component, /width:\s*min\(860px,\s*calc\(100vw - 2rem\)\)/, 'dialog should be wider when the left sidebar is visible')
assert.match(component, /\.conversation-dialog\.standalone\s*\{[\s\S]*?width:\s*100%;[\s\S]*?height:\s*100vh;/, 'standalone conversation should fill the viewport instead of rendering as a framed panel')
assert.match(component, /\.conversation-dialog\.standalone \.dialog-panel\s*\{[\s\S]*?background:\s*transparent;/, 'standalone conversation panel should blend into the page background')
assert.match(component, /\.conversation-dialog\.standalone \.message-list\s*\{[\s\S]*?max-width:\s*760px;/, 'standalone message column should preserve a readable width')
assert.match(component, /\.answer-prose\s*\{[\s\S]*?font-size:\s*14px;/, 'answer prose should use a larger reading font')
assert.doesNotMatch(component, /\.delete-conversation-button\s*\{[\s\S]*?#(?:fff5f5|ffecec|9a2f2f|7c1f1f|e3b9b9|cc7c7c)/, 'delete button should use the same neutral palette as secondary actions')

console.log('conversation dialog behavior ok')
