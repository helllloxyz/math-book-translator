<template>
  <div v-if="show" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-content card">
      <div class="modal-header">
        <div>
          <p class="modal-kicker">Library Intake</p>
          <h2>Add Book</h2>
        </div>
        <button class="close-btn" @click="$emit('close')" title="Close">×</button>
      </div>
      
      <div class="modal-body">
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
          <div class="outline-review-head">
            <div>
              <h3>确认章节结构</h3>
              <p>{{ outlineReview.recommendation || '请选择哪些标题作为章节切分点。' }}</p>
            </div>
            <span class="outline-count">{{ outlineReview.heading_count || outlineRows.length }} headings</span>
          </div>
          <div class="outline-tools">
            <label class="outline-depth-control">
              <span>导入粒度</span>
              <select v-model.number="importDepth" :disabled="loading">
                <option v-for="level in levelOptions" :key="level" :value="level">按 L{{ level }} 切</option>
              </select>
            </label>
          </div>
          <div class="outline-tree">
            <label
              v-for="node in outlineRows"
              :key="node.id"
              :class="['outline-row', node.kind, { disabled: splitLevelValue(node) === '', deleted: splitLevelValue(node) === 'delete', toc: node.is_toc_like }]"
              :style="{ '--depth': Math.max(0, outlineRowDepth(node) - 1) }"
            >
              <select
                class="outline-level-select"
                :value="splitLevelValue(node)"
                :disabled="loading"
                @change="setNodeSplitLevel(node.id, $event.target.value)"
              >
                <option value="delete">删除</option>
                <option value="">不切</option>
                <option v-for="level in levelOptions" :key="level" :value="level">L{{ level }}</option>
              </select>
              <span class="outline-marker">{{ node.marker || node.key || '附属' }}</span>
              <span class="outline-title">{{ node.title }}</span>
              <span class="outline-meta">
                {{ splitLevelValue(node) === 'delete' ? '删除' : splitLevelValue(node) === '' ? '不切' : `L${splitLevelValue(node)}` }}
                · {{ node.char_count || 0 }} chars
              </span>
            </label>
          </div>
          <div class="preflight-actions">
            <button class="secondary-btn" :disabled="loading" @click="$emit('cancel-outline')">Cancel</button>
            <button class="submit-btn primary-btn" :disabled="loading" @click="confirmOutline">
              {{ loading ? 'Importing...' : '确认并导入' }}
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
              <p class="help-text">Upload a .zip package exported from this app. The package restores book files, translated chapters, learning context, guides, and images.</p>
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

          <section class="package-section">
            <div>
              <h3>Export Portable Package</h3>
              <p class="help-text">Choose a book from this library and download its remote storage directory as a .zip package.</p>
            </div>
            <select v-model="selectedExportBookId" class="modal-input package-select">
              <option value="">Select a book to export</option>
              <option v-for="book in books" :key="book.id" :value="String(book.id)">
                {{ book.title }}
              </option>
            </select>
            <button 
              class="submit-btn secondary-btn" 
              :disabled="!selectedExportBookId || loading" 
              @click="handlePackageExport"
            >
              {{ loading ? 'Preparing...' : 'Export Package' }}
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
  outlineReview: Object,
  books: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['close', 'import', 'upload', 'import-package', 'export-package', 'confirm-preflight', 'cancel-preflight', 'confirm-outline', 'cancel-outline'])

const activeTab = ref('local')
const localPath = ref('')
const selectedFile = ref(null)
const selectedPackageFile = ref(null)
const selectedExportBookId = ref('')
const splitLevelById = ref({})
const importDepth = ref(1)

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

const handlePackageExport = () => {
  emit('export-package', Number(selectedExportBookId.value))
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

.modal-kicker {
  margin: 0 0 0.28rem;
  color: var(--modal-muted);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.28rem;
  color: var(--modal-ink);
  line-height: 1.2;
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

.package-select {
  appearance: auto;
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
  gap: 1rem;
}

.outline-review-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.outline-review h3 {
  margin: 0 0 0.35rem;
  color: var(--modal-ink);
  font-size: 1.05rem;
}

.outline-review p {
  margin: 0;
  color: #555;
  line-height: 1.5;
}

.outline-count {
  flex: 0 0 auto;
  padding: 0.28rem 0.55rem;
  border: 1px solid var(--modal-line);
  border-radius: 999px;
  color: #64748b;
  font-size: 0.78rem;
  font-weight: 700;
  background: #f8fafc;
}

.outline-tools {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.outline-depth-control {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  color: #475569;
  font-size: 0.84rem;
  font-weight: 700;
}

.outline-depth-control select,
.outline-level-select {
  border: 1px solid var(--modal-line);
  border-radius: 10px;
  background: white;
  color: #334155;
  font: inherit;
}

.outline-depth-control select {
  padding: 0.42rem 0.55rem;
}

.outline-level-select {
  width: 4.7rem;
  min-width: 4.7rem;
  padding: 0.32rem 0.4rem;
  font-size: 0.8rem;
  font-weight: 700;
}

.outline-tree {
  max-height: min(460px, 50vh);
  overflow: auto;
  border: 1px solid var(--modal-line);
  border-radius: 16px;
  background: white;
}

.outline-row {
  --depth: 0;
  display: grid;
  grid-template-columns: 4.7rem minmax(3.25rem, auto) minmax(0, 1fr) auto;
  gap: 0.55rem;
  align-items: center;
  padding: 0.52rem 0.75rem 0.52rem calc(0.75rem + var(--depth) * 1.35rem);
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
  font-size: 0.86rem;
}

.outline-row:last-child {
  border-bottom: 0;
}

.outline-row.disabled {
  color: #94a3b8;
  background: #fbfdff;
}

.outline-row.deleted {
  color: #9f1239;
  background: #fff1f2;
}

.outline-row.toc {
  background: #fff7ed;
}

.outline-marker {
  color: #64748b;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.outline-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.outline-meta {
  color: #64748b;
  font-size: 0.78rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
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

  .outline-review-head,
  .outline-row {
    grid-template-columns: 4.7rem minmax(2.5rem, auto) minmax(0, 1fr);
  }

  .outline-review-head {
    display: block;
  }

  .outline-count,
  .outline-meta {
    display: none;
  }
}
</style>
