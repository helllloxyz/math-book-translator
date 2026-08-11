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
          <button
            v-if="outlineReview && levelOneGroupIds.length"
            type="button"
            class="outline-collapse-all"
            :aria-label="allLevelOneGroupsCollapsed ? '展开全部 L1 目录' : '折叠全部 L1 目录'"
            :title="allLevelOneGroupsCollapsed ? '展开全部 L1 目录' : '折叠全部 L1 目录'"
            @click="toggleAllLevelOneGroups"
          >
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 5.5h10M3 10.5h10M6 3l-2.5 2.5L6 8M10 8l2.5 2.5L10 13" />
            </svg>
            <span>{{ allLevelOneGroupsCollapsed ? '展开 L1' : '折叠 L1' }}</span>
          </button>
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
              v-for="node in visibleOutlineRows"
              :key="node.id"
              :class="['outline-node', node.kind, { disabled: splitLevelValue(node) === '', deleted: splitLevelValue(node) === 'delete', toc: node.is_toc_like, collapsed: outlineGroupChildCounts[node.id] && collapsedLevelOneIds.has(node.id) }]"
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
                <span class="outline-index">
                  <span class="group-toggle-slot">
                    <button
                      v-if="outlineGroupChildCounts[node.id]"
                      type="button"
                      class="group-toggle"
                      :class="{ collapsed: collapsedLevelOneIds.has(node.id) }"
                      :aria-expanded="!collapsedLevelOneIds.has(node.id)"
                      :aria-label="collapsedLevelOneIds.has(node.id) ? `展开 ${node.title} 的 ${outlineGroupChildCounts[node.id]} 个下级标题` : `收起 ${node.title} 的 ${outlineGroupChildCounts[node.id]} 个下级标题`"
                      :title="collapsedLevelOneIds.has(node.id) ? '展开下级目录' : '收起下级目录'"
                      @click="toggleLevelOneGroup(node.id)"
                    >
                      <svg viewBox="0 0 12 12" aria-hidden="true"><path d="m3 4.5 3 3 3-3" /></svg>
                    </button>
                  </span>
                  <span class="outline-marker">{{ node.marker || node.key || '附属' }}</span>
                </span>
                <span class="outline-title-cell">
                  <span class="outline-title" :title="node.title">{{ node.title }}</span>
                  <span v-if="outlineGroupChildCounts[node.id] && collapsedLevelOneIds.has(node.id)" class="collapsed-count">
                    已收起 {{ outlineGroupChildCounts[node.id] }} 项
                  </span>
                </span>
                <span class="outline-meta">
                  {{ node.char_count || 0 }} 字
                </span>
                <button
                  type="button"
                  class="context-toggle"
                  :disabled="!node.context?.lines?.length"
                  :aria-label="`预览 ${node.title} 的上下文`"
                  title="预览上下文"
                  @click="openContextPreview(node)"
                >
                  <svg viewBox="0 0 16 16" aria-hidden="true">
                    <circle cx="7" cy="7" r="3.5" /><path d="m10 10 3 3" />
                  </svg>
                </button>
              </div>
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

  <Transition name="context-preview">
    <div
      v-if="show && contextPreviewNode"
      class="context-preview-overlay"
      @click.self="closeContextPreview"
    >
      <section
        ref="contextDialog"
        class="context-preview-dialog"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`context-preview-title-${contextPreviewNode.id}`"
        tabindex="-1"
        @keydown.esc="closeContextPreview"
      >
        <header class="context-preview-header">
          <div>
            <p class="context-preview-kicker">
              原文上下文 · 第 {{ contextPreviewNode.context.heading_line }} 行
            </p>
            <h2 :id="`context-preview-title-${contextPreviewNode.id}`">
              {{ contextPreviewNode.marker || contextPreviewNode.key }} {{ contextPreviewNode.title }}
            </h2>
            <p>显示标题前后各最多 {{ contextPreviewNode.context.radius }} 行，当前标题行已高亮。</p>
          </div>
          <button type="button" class="context-preview-close" aria-label="关闭上下文预览" @click="closeContextPreview">×</button>
        </header>
        <div class="context-code context-preview-code">
          <div
            v-for="(line, index) in contextPreviewNode.context.lines"
            :key="`${contextPreviewNode.id}-context-${index}`"
            :class="['context-line', { heading: contextLineNumber(contextPreviewNode, index) === contextPreviewNode.context.heading_line }]"
          >
            <span class="context-line-number">{{ contextLineNumber(contextPreviewNode, index) }}</span>
            <code>{{ line || ' ' }}</code>
          </div>
        </div>
      </section>
    </div>
  </Transition>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import {
  filterCollapsedImportOutlineRows,
  importOutlineGroupChildCount,
  importOutlineLevelOneGroups
} from '../utils/importOutline.js'

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
const collapsedLevelOneIds = ref(new Set())
const contextPreviewNodeId = ref(null)
const contextDialog = ref(null)
let contextPreviewTrigger = null

const isBlockedPreflight = computed(() => props.preflightWarning?.severity === 'blocked')
const outlineRows = computed(() => props.outlineReview?.nodes || [])
const outlineGroupChildCounts = computed(() => Object.fromEntries(
  outlineRows.value
    .map((node, index) => [
      node.id,
      importOutlineGroupChildCount(outlineRows.value, index, splitLevelById.value)
    ])
    .filter((entry) => entry[1] > 0)
))
const levelOneGroupIds = computed(() => (
  importOutlineLevelOneGroups(outlineRows.value, splitLevelById.value).map((node) => node.id)
))
const visibleOutlineRows = computed(() => filterCollapsedImportOutlineRows(
  outlineRows.value,
  collapsedLevelOneIds.value,
  splitLevelById.value
))
const allLevelOneGroupsCollapsed = computed(() => (
  levelOneGroupIds.value.length > 0
  && levelOneGroupIds.value.every((id) => collapsedLevelOneIds.value.has(id))
))
const contextPreviewNode = computed(() => (
  outlineRows.value.find((node) => node.id === contextPreviewNodeId.value) || null
))
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
    collapsedLevelOneIds.value = new Set()
    contextPreviewNodeId.value = null
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
  const nextLevels = {
    ...splitLevelById.value,
    [id]: value === 'delete' ? 'delete' : value === '' ? null : Number(value)
  }
  splitLevelById.value = nextLevels
  const validGroupIds = new Set(
    importOutlineLevelOneGroups(outlineRows.value, nextLevels).map((node) => node.id)
  )
  collapsedLevelOneIds.value = new Set(
    [...collapsedLevelOneIds.value].filter((nodeId) => validGroupIds.has(nodeId))
  )
}

const toggleLevelOneGroup = (id) => {
  const nextCollapsedIds = new Set(collapsedLevelOneIds.value)
  if (nextCollapsedIds.has(id)) {
    nextCollapsedIds.delete(id)
  } else {
    nextCollapsedIds.add(id)
  }
  collapsedLevelOneIds.value = nextCollapsedIds
}

const toggleAllLevelOneGroups = () => {
  collapsedLevelOneIds.value = allLevelOneGroupsCollapsed.value
    ? new Set()
    : new Set(levelOneGroupIds.value)
}

const openContextPreview = async (node) => {
  if (!node.context?.lines?.length) return
  contextPreviewTrigger = document.activeElement instanceof HTMLElement ? document.activeElement : null
  contextPreviewNodeId.value = node.id
  await nextTick()
  contextDialog.value?.focus()
}

const closeContextPreview = async () => {
  const trigger = contextPreviewTrigger
  contextPreviewNodeId.value = null
  contextPreviewTrigger = null
  await nextTick()
  trigger?.focus()
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

.outline-collapse-all {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
  min-height: 2.1rem;
  padding: 0.35rem 0.55rem;
  border: 1px solid var(--modal-line);
  border-radius: 8px;
  color: var(--modal-muted);
  background: var(--color-surface-raised, #ffffff);
  font: inherit;
  font-size: 0.72rem;
  font-weight: 650;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background 0.2s, transform 0.2s;
}

.outline-collapse-all svg {
  width: 0.95rem;
  height: 0.95rem;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.35;
}

.outline-collapse-all:hover {
  border-color: var(--color-accent, #a74a2f);
  color: var(--color-accent-dark, #803d2a);
  background: var(--color-accent-soft, #f7ebe5);
  transform: translateY(-1px);
}

.outline-collapse-all:focus-visible {
  outline: 2px solid var(--color-accent, #a74a2f);
  outline-offset: 2px;
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
  grid-template-columns: 4.7rem minmax(4.5rem, auto) minmax(0, 1fr) auto auto;
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

.outline-node.collapsed {
  background: rgba(241, 236, 226, 0.6);
}

.outline-index {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  min-width: 0;
}

.group-toggle-slot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.15rem;
  min-width: 1.15rem;
}

.group-toggle {
  width: 1.15rem;
  height: 1.15rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: 4px;
  color: var(--modal-muted);
  background: transparent;
  cursor: pointer;
  transition: color 0.2s, background 0.2s, transform 0.2s;
}

.group-toggle:hover {
  color: var(--color-accent-dark, #803d2a);
  background: var(--color-accent-soft, #f7ebe5);
}

.group-toggle:focus-visible {
  outline: 2px solid var(--color-accent, #a74a2f);
  outline-offset: 1px;
}

.group-toggle svg {
  width: 0.72rem;
  height: 0.72rem;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.5;
  transition: transform 0.2s;
}

.group-toggle.collapsed svg {
  transform: rotate(-90deg);
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

.outline-title-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  min-width: 0;
}

.collapsed-count {
  flex: 0 0 auto;
  padding: 0.18rem 0.35rem;
  border-radius: 4px;
  color: var(--color-accent-dark, #803d2a);
  background: var(--color-accent-soft, #f7ebe5);
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 0.62rem;
  font-weight: 650;
  white-space: nowrap;
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
  width: 1.95rem;
  min-height: 1.95rem;
  padding: 0;
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

.context-toggle:hover:not(:disabled) {
  border-color: var(--color-accent, #a74a2f);
  background: var(--color-accent-soft, #f7ebe5);
  color: var(--color-accent-dark, #803d2a);
}

.context-toggle:hover:not(:disabled) {
  transform: translateY(-1px);
}

.context-toggle:focus-visible {
  outline: 2px solid var(--color-accent, #a74a2f);
  outline-offset: 2px;
}

.context-toggle:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.context-preview-overlay {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: rgba(35, 29, 23, 0.56);
  backdrop-filter: blur(12px) saturate(0.75);
}

.context-preview-dialog {
  width: min(780px, calc(100vw - 2rem));
  height: min(820px, calc(100dvh - 2rem));
  max-height: calc(100dvh - 2rem);
  overflow: hidden;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  border: 1px solid rgba(255, 250, 242, 0.16);
  border-radius: 16px;
  color: #e7dfd4;
  background: #24201c;
  box-shadow: 0 32px 84px rgba(35, 25, 18, 0.38);
}

.context-preview-dialog:focus {
  outline: none;
}

.context-preview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem 1.1rem 0.9rem;
  border-bottom: 1px solid rgba(255, 250, 242, 0.12);
  background: #2a2521;
}

.context-preview-kicker {
  margin: 0 0 0.3rem;
  color: #c58a73;
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 0.64rem;
  font-weight: 650;
  letter-spacing: 0.07em;
}

.context-preview-header h2 {
  margin: 0;
  color: #fffaf2;
  font-family: var(--font-display, serif);
  font-size: 1.05rem;
  font-weight: 600;
  line-height: 1.3;
}

.context-preview-header p:last-child {
  margin: 0.3rem 0 0;
  color: #a99f94;
  font-size: 0.72rem;
  line-height: 1.45;
}

.context-preview-close {
  width: 2rem;
  height: 2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  padding: 0;
  border: 1px solid rgba(255, 250, 242, 0.16);
  border-radius: 8px;
  color: #c7bdb3;
  background: rgba(255, 250, 242, 0.04);
  font: inherit;
  font-size: 1.1rem;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
}

.context-preview-close:hover {
  border-color: rgba(228, 165, 143, 0.55);
  color: #fffaf2;
  background: rgba(184, 94, 65, 0.18);
}

.context-preview-close:focus-visible {
  outline: 2px solid #c58a73;
  outline-offset: 2px;
}

.context-preview-enter-active,
.context-preview-leave-active {
  transition: opacity 0.18s ease;
}

.context-preview-enter-active .context-preview-dialog,
.context-preview-leave-active .context-preview-dialog {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.context-preview-enter-from,
.context-preview-leave-to,
.context-preview-enter-from .context-preview-dialog,
.context-preview-leave-to .context-preview-dialog {
  opacity: 0;
}

.context-preview-enter-from .context-preview-dialog,
.context-preview-leave-to .context-preview-dialog {
  transform: translateY(8px) scale(0.985);
}

.context-code.context-preview-code {
  max-height: none;
  min-height: 0;
  padding-block: 0.7rem;
  font-variant-numeric: tabular-nums;
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
    grid-template-columns: 4.4rem minmax(3.8rem, auto) minmax(0, 1fr) auto;
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
    -webkit-line-clamp: 1;
  }

  .outline-header h2 {
    font-size: 1.08rem;
    white-space: nowrap;
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

  .outline-collapse-all {
    width: 2.1rem;
    padding: 0;
  }

  .outline-collapse-all span {
    display: none;
  }

  .context-toggle {
    width: 2rem;
    padding: 0;
  }

  .collapsed-count {
    display: none;
  }

  .context-preview-overlay {
    padding: 0.75rem;
  }

  .context-preview-dialog {
    width: 100%;
    max-height: calc(100dvh - 1.5rem);
    border-radius: 13px;
  }

  .context-preview-header {
    padding: 0.85rem;
  }

  .outline-actions .secondary-btn,
  .outline-actions .submit-btn {
    flex: 1;
    min-width: 0;
  }
}
</style>
