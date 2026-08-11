<template>
  <div v-if="show" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content card">
      <div :class="['modal-header', { 'outline-header': outlineReview }]">
        <div class="modal-heading">
          <p class="modal-kicker">
            {{ outlineReview ? '目录确认' : 'Library intake' }}
            <span v-if="outlineReview" class="heading-count">
              · {{ outlineReview.heading_count || outlineRows.length }} 个标题
            </span>
          </p>
          <h2>{{ outlineReview ? '确认章节结构' : 'Add Book' }}</h2>
          <p v-if="outlineReview" class="outline-summary">
            {{ outlineReview.recommendation || '选择章节切分点；默认按检测到的最低编号层级切分。' }}
          </p>
        </div>
        <div class="modal-header-actions">
          <label v-if="outlineReview" class="outline-depth-control">
            <span>导入粒度</span>
            <select v-model.number="importDepth" :disabled="loading">
              <option v-for="level in levelOptions" :key="level" :value="level">切至 L{{ level }}</option>
            </select>
          </label>
          <button class="close-btn" @click="$emit('close')" title="Close">×</button>
        </div>
      </div>
      
      <div :class="['modal-body', { 'outline-body': outlineReview }]">
        <div v-if="preflightWarning" class="preflight-warning">
          <h3>{{ isBlockedPreflight ? '导入已阻止' : '检查导入警告' }}</h3>
          <p>{{ preflightWarning.recommendation || '导入前可能需要检查章节拆分结果。' }}</p>
          <ul v-if="preflightWarning.issues?.length">
            <li v-for="(issue, index) in preflightWarning.issues" :key="`${issue.code || 'issue'}-${index}`">
              <span>{{ issue.message || issue }}</span>
              <ol v-if="issue.examples?.length" class="issue-examples">
                <li v-for="example in issue.examples" :key="example">{{ example }}</li>
              </ol>
            </li>
          </ul>
          <div v-if="chapterTypeSummary.length" class="chapter-type-summary">
            <div
              v-for="item in chapterTypeSummary"
              :key="item.type"
              :class="['type-chip', { highlight: item.type === 'exercise' }]"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.count }}</strong>
            </div>
          </div>
          <div v-if="preflightWarning.chapters?.length" class="chapter-preview">
            <div class="chapter-preview-header">
              <span>章节</span>
              <span>类型</span>
              <span>字符数</span>
            </div>
            <div
              v-for="chapter in preflightWarning.chapters"
              :key="`${chapter.chapter_index}-${chapter.title}`"
              class="chapter-preview-row"
            >
              <span class="chapter-title">
                {{ chapter.chapter_index }} {{ chapter.title }}
              </span>
              <span :class="['chapter-type', { exercise: chapter.content_type === 'exercise' }]">
                {{ chapter.content_type_label || chapter.content_type }}
              </span>
              <span class="chapter-chars">{{ chapter.char_count }}</span>
            </div>
          </div>
          <div class="preflight-actions">
            <button class="secondary-btn" :disabled="loading" @click="$emit('cancel-preflight')">
              {{ isBlockedPreflight ? 'Close' : 'Cancel' }}
            </button>
            <button
              v-if="preflightWarning?.severity !== 'blocked'"
              class="submit-btn primary-btn"
              :disabled="loading"
              @click="$emit('confirm-preflight')"
            >
              {{ loading ? 'Importing...' : '仍然导入' }}
            </button>
          </div>
        </div>

        <div v-else-if="outlineReview" class="outline-review">
          <div class="outline-tree">
            <div
              v-for="node in outlineRows"
              :key="node.id"
              :class="['outline-node', node.kind, { disabled: splitLevelValue(node) === '', deleted: splitLevelValue(node) === 'delete', toc: node.is_toc_like, expanded: expandedContextId === node.id }]"
              :style="{ '--depth': Math.max(0, outlineRowDepth(node) - 1) }"
            >
              <div class="outline-row">
                <select
                  class="outline-level-select"
                  :value="splitLevelValue(node)"
                  :disabled="loading"
                  :aria-label="`${node.title} 的切分层级`"
                  @change="setNodeSplitLevel(node.id, $event.target.value)"
                >
                  <option value="delete">删除</option>
                  <option value="">不切</option>
                  <option v-for="level in levelOptions" :key="level" :value="level">L{{ level }}</option>
                </select>
                <span class="outline-marker">{{ node.marker || node.key || '附属' }}</span>
                <span class="outline-title" :title="node.title">{{ node.title }}</span>
                <span class="outline-meta">
                  {{ splitLevelValue(node) === 'delete' ? '删除' : splitLevelValue(node) === '' ? '不切' : `L${splitLevelValue(node)}` }}
                  · {{ node.char_count || 0 }} 字
                </span>
                <button
                  type="button"
                  class="context-toggle"
                  :class="{ active: expandedContextId === node.id }"
                  :disabled="!node.context?.lines?.length"
                  :aria-expanded="expandedContextId === node.id"
                  :aria-controls="`outline-context-${node.id}`"
                  :aria-label="expandedContextId === node.id ? `收起 ${node.title} 的上下文` : `预览 ${node.title} 的上下文`"
                  :title="expandedContextId === node.id ? '收起上下文' : '预览上下文'"
                  @click="toggleNodeContext(node.id)"
                >
                  <span>{{ expandedContextId === node.id ? '收起' : '上下文' }}</span>
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <path d="m4 6 4 4 4-4" />
                  </svg>
                </button>
              </div>
              <section
                v-if="expandedContextId === node.id && node.context?.lines?.length"
                :id="`outline-context-${node.id}`"
                class="outline-context"
                :aria-label="`${node.title} 的原文上下文`"
              >
                <header class="context-header">
                  <span>原文上下文</span>
                  <span>第 {{ node.context.heading_line }} 行 · 前后各最多 {{ node.context.radius }} 行</span>
                </header>
                <div class="context-code">
                  <div
                    v-for="(line, index) in node.context.lines"
                    :key="`${node.id}-context-${index}`"
                    :class="['context-line', { heading: contextLineNumber(node, index) === node.context.heading_line }]"
                  >
                    <span class="context-line-number">{{ contextLineNumber(node, index) }}</span>
                    <code>{{ line || ' ' }}</code>
                  </div>
                </div>
              </section>
            </div>
          </div>
          <div class="preflight-actions outline-actions">
            <button class="secondary-btn" :disabled="loading" @click="$emit('cancel-outline')">取消</button>
            <button class="submit-btn primary-btn" :disabled="loading" @click="confirmOutline">
              {{ loading ? '正在导入…' : '确认并导入' }}
            </button>
          </div>
        </div>

        <template v-else>
        <div class="tabs">
          <button 
            :class="['tab-btn', { active: activeTab === 'local' }]" 
            @click="activeTab = 'local'"
          >
            Local Path
          </button>
          <button 
            :class="['tab-btn', { active: activeTab === 'upload' }]" 
            @click="activeTab = 'upload'"
          >
            Upload File
          </button>
          <button 
            :class="['tab-btn', { active: activeTab === 'package' }]" 
            @click="activeTab = 'package'"
          >
            Package
          </button>
        </div>

        <div v-if="activeTab === 'local'" class="tab-content">
          <p class="help-text">Enter a Markdown file path or a prepared book directory. Directories prefer full.md and can use meta.json when present.</p>
          <div class="input-group">
            <input 
              type="text" 
              v-model="localPath" 
              placeholder="e.g. /home/user/book-dir or /home/user/book/full.md" 
              class="modal-input"
            />
          </div>
          <button 
            class="submit-btn primary-btn" 
            :disabled="!localPath || loading" 
            @click="handleImport"
          >
            {{ loading ? 'Importing...' : 'Import Local Path' }}
          </button>
        </div>

        <div v-else-if="activeTab === 'upload'" class="tab-content">
          <p class="help-text">Choose a Markdown file to upload and split into reader chapters.</p>
          <label class="file-dropzone">
            <input type="file" @change="onFileChange" accept=".md" />
            <div class="dropzone-content">
              <span class="icon">📄</span>
              <span v-if="!selectedFile">Click to select or drop a Markdown file</span>
              <span v-else class="file-name">{{ selectedFile.name }}</span>
            </div>
          </label>
          <button 
            class="submit-btn primary-btn" 
            :disabled="!selectedFile || loading" 
            @click="handleUpload"
          >
            {{ loading ? 'Uploading...' : 'Upload and Import' }}
          </button>
        </div>

        <div v-else-if="activeTab === 'package'" class="tab-content package-tab">
          <section class="package-section">
            <div>
              <h3>Import Portable Package</h3>
              <p class="help-text">Upload a .zip package exported from this app. The package restores book files, translated chapters, guides, reader profile files, and images.</p>
            </div>
            <label class="file-dropzone compact">
              <input type="file" @change="onPackageFileChange" accept=".zip,application/zip" />
              <div class="dropzone-content">
                <span class="icon">ZIP</span>
                <span v-if="!selectedPackageFile">Select a book package</span>
                <span v-else class="file-name">{{ selectedPackageFile.name }}</span>
              </div>
            </label>
            <button 
              class="submit-btn primary-btn" 
              :disabled="!selectedPackageFile || loading" 
              @click="handlePackageImport"
            >
              {{ loading ? 'Importing...' : 'Import Package' }}
            </button>
          </section>
        </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  show: Boolean,
  loading: Boolean,
  preflightWarning: Object,
  outlineReview: Object
})

const emit = defineEmits(['close', 'import', 'upload', 'import-package', 'confirm-preflight', 'cancel-preflight', 'confirm-outline', 'cancel-outline'])

const activeTab = ref('local')
const localPath = ref('')
const selectedFile = ref(null)
const selectedPackageFile = ref(null)
const splitLevelById = ref({})
const importDepth = ref(1)
const expandedContextId = ref(null)

const isBlockedPreflight = computed(() => props.preflightWarning?.severity === 'blocked')
const outlineRows = computed(() => props.outlineReview?.nodes || [])
const levelOptions = computed(() => {
  const maxLevel = outlineRows.value.reduce((max, node) => {
    const nodeLevel = Number(node.split_level || node.level || 1)
    return Number.isFinite(nodeLevel) ? Math.max(max, nodeLevel) : max
  }, Number(props.outlineReview?.default_import_depth || 1))
  return Array.from({ length: Math.max(3, maxLevel + 1) }, (_item, index) => index + 1)
})

const chapterTypeSummary = computed(() => {
  const counts = new Map()
  for (const chapter of props.preflightWarning?.chapters || []) {
    const type = chapter.content_type || 'main_text'
    const label = chapter.content_type_label || type
    const current = counts.get(type) || { type, label, count: 0 }
    current.count += 1
    counts.set(type, current)
  }
  return Array.from(counts.values()).sort((a, b) => {
    if (a.type === 'exercise') return -1
    if (b.type === 'exercise') return 1
    return b.count - a.count
  })
})

const onFileChange = (e) => {
  selectedFile.value = e.target.files[0]
}

const onPackageFileChange = (e) => {
  selectedPackageFile.value = e.target.files[0]
}

watch(
  () => props.outlineReview,
  (outline) => {
    const plan = outline?.default_outline_plan
    const nextLevels = {}
    for (const node of plan?.nodes || outline?.nodes || []) {
      nextLevels[node.id] = node.split_level == null ? null : Number(node.split_level)
    }
    splitLevelById.value = nextLevels
    importDepth.value = Number(plan?.import_depth || outline?.default_import_depth || 1)
    expandedContextId.value = null
  },
  { immediate: true }
)

const splitLevelValue = (node) => {
  const splitLevel = splitLevelById.value[node.id]
  if (splitLevel === 'delete') {
    return 'delete'
  }
  return splitLevel == null ? '' : String(splitLevel)
}

const outlineRowDepth = (node) => {
  const currentLevel = splitLevelById.value[node.id]
  if (currentLevel === 'delete') {
    return Number(node.level || 1)
  }
  return Number(currentLevel || node.level || 1)
}

const setNodeSplitLevel = (id, value) => {
  splitLevelById.value = {
    ...splitLevelById.value,
    [id]: value === 'delete' ? 'delete' : value === '' ? null : Number(value)
  }
}

const toggleNodeContext = (id) => {
  expandedContextId.value = expandedContextId.value === id ? null : id
}

const contextLineNumber = (node, index) => Number(node.context?.start_line || 1) + index

const buildOutlinePlan = () => {
  const deletedHeadingIds = outlineRows.value
    .filter((node) => splitLevelById.value[node.id] === 'delete')
    .map((node) => node.id)
  return {
    import_depth: Number(importDepth.value || 1),
    nodes: outlineRows.value.map((node) => ({
      id: node.id,
      split_level: splitLevelById.value[node.id] === 'delete'
        ? null
        : splitLevelById.value[node.id] == null
          ? null
          : Number(splitLevelById.value[node.id]),
      deleted: splitLevelById.value[node.id] === 'delete'
    })),
    deleted_heading_ids: deletedHeadingIds
  }
}

const confirmOutline = () => {
  emit('confirm-outline', buildOutlinePlan())
}

const handleImport = () => {
  emit('import', localPath.value)
  localPath.value = ''
}

const handleUpload = () => {
  emit('upload', selectedFile.value)
  selectedFile.value = null
}

const handlePackageImport = () => {
  emit('import-package', selectedPackageFile.value)
  selectedPackageFile.value = null
}

</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  padding: 2rem;
  background: rgba(15, 23, 42, 0.52);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  backdrop-filter: blur(8px);
}

.modal-content {
  --modal-ink: #14213d;
  --modal-muted: #64748b;
  --modal-line: #dbe3ea;
  --modal-accent: #2563eb;
  --modal-accent-dark: #1d4ed8;

  background: #ffffff;
  width: min(920px, calc(100vw - 2rem));
  max-height: calc(100vh - 2rem);
  padding: 0;
  border: 1px solid rgba(203, 213, 225, 0.9);
  border-radius: 24px;
  overflow: hidden;
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.28);
}

.modal-content,
.modal-content * {
  box-sizing: border-box;
}

.modal-header {
  padding: 1.25rem 1.45rem;
  border-bottom: 1px solid rgba(219, 227, 234, 0.95);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.1), transparent 38%),
    linear-gradient(135deg, #ffffff 0%, #f7faf9 100%);
}

.modal-heading {
  min-width: 0;
}

.modal-header.outline-header {
  align-items: center;
  padding-block: 0.95rem;
}

.modal-header-actions {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  flex: 0 0 auto;
}

.modal-kicker {
  margin: 0 0 0.28rem;
  color: var(--modal-muted);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.heading-count {
  color: var(--modal-muted);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.03em;
  text-transform: none;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.28rem;
  color: var(--modal-ink);
  line-height: 1.2;
}

.outline-summary {
  max-width: 58ch;
  margin: 0.25rem 0 0;
  overflow: hidden;
  color: var(--modal-muted);
  font-size: 0.76rem;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.close-btn {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--modal-line);
  border-radius: 999px;
  font-size: 1.35rem;
  line-height: 1;
  cursor: pointer;
  color: #64748b;
  transition: all 0.2s;
}

.close-btn:hover {
  background: #ffffff;
  border-color: #b8c6d1;
  color: var(--modal-ink);
  transform: translateY(-1px);
}

.modal-body {
  padding: 1.35rem 1.45rem 1.45rem;
  max-height: calc(100vh - 7rem);
  overflow: auto;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
}

.modal-body.outline-body {
  padding-block: 0.85rem 1rem;
}

.tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.15rem;
  background: #eef4f9;
  padding: 0.28rem;
  border: 1px solid #e0e8f0;
  border-radius: 999px;
}

.tab-btn {
  flex: 1;
  padding: 0.62rem 0.8rem;
  border: none;
  background: none;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 600;
  color: #64748b;
  transition: all 0.2s;
}

.tab-btn.active {
  background: white;
  color: var(--modal-ink);
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.07);
}

.tab-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.package-tab {
  gap: 1.1rem;
}

.package-section {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1rem;
  border: 1px solid var(--modal-line);
  border-radius: 16px;
  background: #ffffff;
}

.package-section h3 {
  margin: 0 0 0.3rem;
  font-size: 0.98rem;
  color: var(--modal-ink);
}

.help-text {
  font-size: 0.85rem;
  color: var(--modal-muted);
  margin: 0;
  line-height: 1.55;
}

.modal-input {
  width: 100%;
  padding: 0.76rem 0.85rem;
  border: 1px solid var(--modal-line);
  border-radius: 12px;
  font-size: 0.95rem;
  color: var(--modal-ink);
  background: white;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.modal-input:focus {
  outline: none;
  border-color: #93c5fd;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.1);
}

.file-dropzone {
  border: 1px dashed #b8c6d1;
  border-radius: 18px;
  padding: 2.1rem 1.25rem;
  text-align: center;
  cursor: pointer;
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.86), rgba(241, 245, 249, 0.62));
  transition: border-color 0.2s, background 0.2s, transform 0.2s;
}

.file-dropzone:hover {
  border-color: #93c5fd;
  background: #f8fbff;
  transform: translateY(-1px);
}

.file-dropzone.compact {
  padding: 1.25rem;
}

.file-dropzone input {
  display: none;
}

.dropzone-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  color: var(--modal-muted);
  font-weight: 600;
}

.dropzone-content .icon {
  font-size: 2rem;
}

.file-name {
  font-weight: 600;
  color: var(--modal-accent);
}

.submit-btn {
  width: 100%;
  padding: 0.72rem 1rem;
  border-radius: 999px;
  font-weight: 700;
  cursor: pointer;
  border: none;
  transition: background 0.2s, transform 0.2s, box-shadow 0.2s;
}

.primary-btn {
  background: var(--modal-accent);
  color: white;
  box-shadow: 0 10px 20px rgba(37, 99, 235, 0.18);
}

.primary-btn:hover:not(:disabled) {
  background: var(--modal-accent-dark);
  transform: translateY(-1px);
}

.primary-btn:disabled {
  background: #cbd5e1;
  box-shadow: none;
  cursor: not-allowed;
}

.secondary-btn {
  padding: 0.72rem 1rem;
  border-radius: 999px;
  font-weight: 700;
  cursor: pointer;
  border: 1px solid var(--modal-line);
  background: white;
  color: #475569;
  transition: all 0.2s;
}

.secondary-btn:hover:not(:disabled) {
  background: #f8fafc;
  border-color: #b8c6d1;
  color: var(--modal-ink);
}

.secondary-btn:disabled {
  color: #aaa;
  cursor: not-allowed;
}

.preflight-warning {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.preflight-warning h3 {
  margin: 0;
  color: #92400e;
  font-size: 1.05rem;
}

.preflight-warning p {
  margin: 0;
  color: #555;
  line-height: 1.5;
}

.preflight-warning ul {
  margin: 0;
  padding-left: 1.25rem;
  color: #444;
  line-height: 1.5;
}

.outline-review {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.outline-depth-control {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--modal-muted);
  font-size: 0.72rem;
  font-weight: 650;
  white-space: nowrap;
}

.outline-depth-control select,
.outline-level-select {
  border: 1px solid var(--modal-line);
  border-radius: 8px;
  background: var(--color-surface-raised, white);
  color: var(--modal-ink);
  font: inherit;
}

.outline-depth-control select {
  min-height: 2.1rem;
  padding: 0.35rem 1.8rem 0.35rem 0.55rem;
  font-size: 0.76rem;
  font-weight: 700;
}

.outline-level-select {
  width: 4.7rem;
  min-width: 4.7rem;
  padding: 0.32rem 0.4rem;
  font-size: 0.8rem;
  font-weight: 700;
}

.outline-tree {
  max-height: min(560px, calc(100dvh - 245px));
  overflow: auto;
  border: 1px solid var(--modal-line);
  border-radius: 12px;
  background: var(--color-surface, white);
  scrollbar-gutter: stable;
}

.outline-node {
  border-bottom: 1px solid var(--modal-line);
  color: var(--modal-ink);
  transition: background 0.2s, color 0.2s;
}

.outline-node:last-child {
  border-bottom: 0;
}

.outline-row {
  --depth: 0;
  display: grid;
  grid-template-columns: 4.7rem minmax(3.25rem, auto) minmax(0, 1fr) auto auto;
  gap: 0.65rem;
  align-items: center;
  min-height: 2.85rem;
  padding: 0.42rem 0.65rem 0.42rem calc(0.65rem + var(--depth) * 1.15rem);
  font-size: 0.82rem;
}

.outline-node.disabled {
  color: var(--modal-muted);
  background: rgba(241, 236, 226, 0.34);
}

.outline-node.deleted {
  color: #9f1239;
  background: #fff1f2;
}

.outline-node.toc {
  background: var(--color-accent-soft, #fff7ed);
}

.outline-node.expanded {
  background: rgba(241, 236, 226, 0.6);
}

.outline-marker {
  color: var(--modal-muted);
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 0.76rem;
  font-weight: 650;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.outline-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 550;
}

.outline-meta {
  color: var(--modal-muted);
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 0.68rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.context-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  min-height: 1.95rem;
  padding: 0.3rem 0.48rem;
  border: 1px solid var(--modal-line);
  border-radius: 8px;
  background: var(--color-surface-raised, #ffffff);
  color: var(--modal-muted);
  font: inherit;
  font-size: 0.76rem;
  font-weight: 700;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s, color 0.2s, transform 0.2s;
}

.context-toggle svg {
  width: 0.85rem;
  height: 0.85rem;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.75;
  transition: transform 0.2s;
}

.context-toggle:hover:not(:disabled),
.context-toggle.active {
  border-color: var(--color-accent, #a74a2f);
  background: var(--color-accent-soft, #f7ebe5);
  color: var(--color-accent-dark, #803d2a);
}

.context-toggle:hover:not(:disabled) {
  transform: translateY(-1px);
}

.context-toggle.active svg {
  transform: rotate(180deg);
}

.context-toggle:focus-visible {
  outline: 2px solid var(--color-accent, #a74a2f);
  outline-offset: 2px;
}

.context-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.outline-context {
  margin: 0 0.65rem 0.65rem calc(0.65rem + var(--depth) * 1.15rem);
  overflow: hidden;
  border: 1px solid rgba(255, 250, 242, 0.12);
  border-radius: 9px;
  background: #24201c;
  box-shadow: 0 10px 22px rgba(64, 45, 32, 0.12);
}

.context-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.55rem 0.75rem;
  border-bottom: 1px solid rgba(255, 250, 242, 0.12);
  color: #f1ece4;
  font-size: 0.72rem;
  font-weight: 700;
}

.context-header span:last-child {
  color: #a99f94;
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.context-code {
  max-height: 22rem;
  overflow: auto;
  padding: 0.45rem 0;
  color: #e7dfd4;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.76rem;
  line-height: 1.65;
}

.context-line {
  display: grid;
  grid-template-columns: 3.5rem minmax(max-content, 1fr);
  min-width: max-content;
  padding-right: 0.75rem;
}

.context-line.heading {
  background: rgba(184, 94, 65, 0.24);
  color: #fffaf2;
}

.context-line.heading code {
  font-weight: 700;
}

.context-line-number {
  padding-right: 0.7rem;
  color: #7f756d;
  font-variant-numeric: tabular-nums;
  text-align: right;
  user-select: none;
}

.context-line.heading .context-line-number {
  color: #e4a58f;
}

.context-line code {
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  white-space: pre;
}

.issue-examples {
  margin: 0.35rem 0 0.6rem;
  padding-left: 1.2rem;
  color: #6b7280;
  line-height: 1.45;
}

.chapter-type-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.type-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.55rem;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  color: #4b5563;
  background: #f9fafb;
  font-size: 0.85rem;
}

.type-chip.highlight {
  border-color: #f59e0b;
  color: #92400e;
  background: #fffbeb;
}

.chapter-preview {
  max-height: min(420px, 48vh);
  overflow: auto;
  border: 1px solid var(--modal-line);
  border-radius: 16px;
  background: white;
}

.chapter-preview-header,
.chapter-preview-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(5.5rem, auto) 5rem;
  gap: 0.75rem;
  align-items: center;
  padding: 0.55rem 0.75rem;
}

.chapter-preview-header {
  position: sticky;
  top: 0;
  background: #f8fafc;
  color: #6b7280;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
}

.chapter-preview-row {
  border-top: 1px solid #f3f4f6;
  font-size: 0.86rem;
}

.chapter-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #374151;
}

.chapter-type {
  color: #4b5563;
  font-weight: 600;
}

.chapter-type.exercise {
  color: #92400e;
}

.chapter-chars {
  color: #6b7280;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.preflight-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.outline-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.55rem;
}

.outline-actions .secondary-btn,
.outline-actions .submit-btn {
  width: auto;
  min-width: 7.5rem;
}

@media (max-width: 640px) {
  .modal-overlay {
    padding: 0.75rem;
    align-items: flex-start;
  }

  .modal-content {
    width: 100%;
    max-height: calc(100vh - 1rem);
    border-radius: 20px;
  }

  .modal-header {
    padding: 1rem;
  }

  .modal-body {
    padding: 1rem;
  }

  .chapter-preview-header,
  .chapter-preview-row {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .chapter-chars {
    display: none;
  }

  .outline-row {
    grid-template-columns: 4.4rem minmax(2.5rem, auto) minmax(0, 1fr) auto;
  }

  .modal-header.outline-header {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: start;
    padding-block: 0.8rem;
  }

  .outline-meta {
    display: none;
  }

  .outline-summary {
    max-width: 100%;
    display: -webkit-box;
    overflow: hidden;
    white-space: normal;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .modal-header-actions {
    align-items: flex-start;
  }

  .outline-depth-control {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.2rem;
  }

  .outline-depth-control > span {
    display: none;
  }

  .context-toggle span {
    display: none;
  }

  .context-toggle {
    width: 2rem;
    padding: 0;
  }

  .outline-context {
    margin-left: 0.65rem;
  }

  .context-header {
    align-items: flex-start;
    flex-direction: column;
    gap: 0.2rem;
  }

  .outline-actions .secondary-btn,
  .outline-actions .submit-btn {
    flex: 1;
    min-width: 0;
  }
}
</style>
