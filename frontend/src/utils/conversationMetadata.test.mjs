import assert from 'node:assert/strict'
import {
  buildConversationDocumentTitle,
  buildConversationMetadata,
  createConversationId
} from './conversationMetadata.js'

const book = { id: 7, title: 'Foundations of Differential Geometry' }
const chapterItem = {
  type: 'chapter',
  chapter_index: '21.5',
  title: 'Orientations and Atlases',
  chapter_id: 42,
  source_type: 'chapter_content',
  source_id: 'chapter:42',
  source_title: 'Orientations and Atlases'
}
const guideItem = {
  id: 'guide:book:reading-path',
  type: 'guide',
  title: 'Top-down reading path',
  filename: '01-reading-path.md',
  source_type: 'book_guide',
  source_id: 'guide:book:reading-path',
  source_title: 'Top-down reading path'
}
const learningItem = {
  type: 'learning',
  title: 'Orientations and Atlases',
  chapter_id: 42,
  chapter_index: '21.5',
  source_type: 'chapter_learning',
  source_id: 'learning:42',
  source_title: 'Orientations and Atlases'
}

const chapterCard = { questionSummary: 'Why must the determinant be positive?' }
const guideCard = { questionSummary: 'How should I read this guide?' }

assert.deepEqual(
  buildConversationMetadata(book, chapterItem),
  {
    bookId: 7,
    bookTitle: 'Foundations of Differential Geometry',
    readerType: 'chapter',
    sourceType: 'chapter_content',
    sourceId: 'chapter:42',
    sourceTitle: 'Orientations and Atlases',
    chapterId: 42,
    chapterIndex: '21.5',
    guideId: ''
  },
  'chapter metadata should include book and chapter identity'
)

assert.deepEqual(
  buildConversationMetadata(book, guideItem),
  {
    bookId: 7,
    bookTitle: 'Foundations of Differential Geometry',
    readerType: 'guide',
    sourceType: 'book_guide',
    sourceId: 'guide:book:reading-path',
    sourceTitle: 'Top-down reading path',
    chapterId: '',
    chapterIndex: '',
    guideId: 'guide:book:reading-path'
  },
  'guide metadata should keep book and guide identity without a chapter id'
)
assert.deepEqual(
  buildConversationMetadata(book, learningItem),
  {
    bookId: 7,
    bookTitle: 'Foundations of Differential Geometry',
    readerType: 'learning',
    sourceType: 'chapter_learning',
    sourceId: 'learning:42',
    sourceTitle: 'Orientations and Atlases',
    chapterId: 42,
    chapterIndex: '21.5',
    guideId: ''
  },
  'learning metadata should reuse the paired chapter identity'
)

assert.equal(
  buildConversationDocumentTitle(chapterCard, buildConversationMetadata(book, chapterItem)),
  '21.5 Why must the determinant be positive?'
)
assert.equal(
  buildConversationDocumentTitle(guideCard, buildConversationMetadata(book, guideItem)),
  'How should I read this guide?'
)

const selectedText = 'X_1, \\ldots, X_n \\in M, U, x^1, \\ldots, x^n, dx^1 \\wedge \\dots \\wedge dx^n'
const generatedConversationId = createConversationId()
assert.match(
  generatedConversationId,
  /^conversation-[a-z0-9-]+$/,
  'generated conversation ids should be short opaque route ids'
)
assert.equal(
  generatedConversationId.includes(selectedText),
  false,
  'generated conversation ids should not include selected text'
)

console.log('conversation metadata behavior ok')
