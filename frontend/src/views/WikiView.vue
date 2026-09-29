<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-semibold text-[var(--text-primary)]">知识 Wiki</h1>
        <p class="text-sm text-[var(--text-muted)] mt-1">概念页 + [[双链]]，把资料串成可点的知识网</p>
      </div>
      <div class="flex gap-2">
        <el-button data-test="wiki-audit" :loading="auditing" @click="runAudit">
          死链巡检
        </el-button>
        <el-button data-test="wiki-ingest" :loading="ingesting" @click="ingestFromDocs">
          从文档提炼
        </el-button>
        <el-button type="primary" data-test="wiki-new" @click="startCreate()">新建概念页</el-button>
      </div>
    </div>

    <!-- 5.3 死链巡检报告 -->
    <div
      v-if="audit"
      class="card p-4 mb-6"
      data-test="wiki-audit-report"
    >
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-semibold text-[var(--text-primary)]">死链巡检</h3>
        <button class="text-xs text-[var(--text-muted)] underline cursor-pointer" @click="audit = null">关闭</button>
      </div>
      <div class="flex flex-wrap gap-3 text-xs mb-3">
        <span class="px-2 py-1 rounded bg-[var(--bg-secondary)]">页面 <b class="tabular-nums">{{ audit.stats.pages }}</b></span>
        <span class="px-2 py-1 rounded bg-[var(--bg-secondary)]">链接 <b class="tabular-nums">{{ audit.stats.links }}</b></span>
        <span
          class="px-2 py-1 rounded tabular-nums"
          :class="audit.stats.dead_links ? 'bg-amber-500/10 text-amber-600' : 'bg-emerald-500/10 text-emerald-600'"
          data-test="audit-dead-count"
        >
          死链 <b>{{ audit.stats.dead_links }}</b>
        </span>
        <span class="px-2 py-1 rounded bg-[var(--bg-secondary)]">
          孤页 <b class="tabular-nums">{{ audit.stats.orphan_pages }}</b>
        </span>
      </div>

      <div v-if="audit.pages.length" class="mb-3">
        <div class="text-xs text-[var(--text-muted)] mb-1.5">含死链的页面</div>
        <div
          v-for="p in audit.pages"
          :key="p.id"
          class="flex items-start gap-2 text-xs py-1.5 border-b border-[var(--border-default)] last:border-0"
        >
          <button class="text-[var(--color-primary)] underline cursor-pointer" @click="openPage(p.id)">
            {{ p.title }}
          </button>
          <div class="flex flex-wrap gap-1">
            <button
              v-for="d in p.dead_links"
              :key="d"
              type="button"
              class="px-1.5 py-0.5 rounded border border-dashed border-amber-400 text-amber-600 cursor-pointer"
              @click="startCreate(d)"
            >[[{{ d }}]]</button>
          </div>
        </div>
      </div>
      <div v-else class="text-xs text-emerald-600 mb-3">没有死链 ✓</div>

      <div v-if="audit.orphan_pages.length">
        <div class="text-xs text-[var(--text-muted)] mb-1.5">孤页（无人引用）</div>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="o in audit.orphan_pages"
            :key="o.id"
            type="button"
            class="px-2 py-0.5 rounded-full border border-[var(--border-default)] text-xs cursor-pointer hover:border-[var(--color-primary)]"
            @click="openPage(o.id)"
          >{{ o.title }}</button>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- List -->
      <div class="lg:col-span-1">
        <el-input
          v-model="search"
          placeholder="搜索标题或摘要…"
          clearable
          class="mb-3"
          data-test="wiki-search"
          @input="onSearchInput"
        />
        <div class="card !p-0 divide-y divide-[var(--border-default)] max-h-[70vh] overflow-y-auto">
          <div v-if="loading" class="p-4 text-sm text-[var(--text-muted)]">加载中…</div>
          <div v-else-if="!pages.length" class="p-4 text-sm text-[var(--text-muted)]">
            还没有概念页，点右上角新建
          </div>
          <button
            v-for="p in pages"
            :key="p.id"
            type="button"
            class="w-full text-left p-3 hover:bg-[var(--bg-hover)] cursor-pointer transition-colors"
            :class="current?.id === p.id ? 'bg-[var(--color-primary)]/10' : ''"
            :data-test="`wiki-item-${p.slug}`"
            @click="openPage(p.id)"
          >
            <div class="text-sm font-medium text-[var(--text-primary)] truncate">{{ p.title }}</div>
            <div class="text-[11px] text-[var(--text-muted)] mt-0.5 truncate">{{ p.slug }}</div>
            <p v-if="p.summary" class="text-xs text-[var(--text-muted)] mt-1 line-clamp-2">{{ p.summary }}</p>
          </button>
        </div>
      </div>

      <!-- Detail / Editor -->
      <div class="lg:col-span-2">
        <!-- Editor -->
        <div v-if="editing" class="card p-5" data-test="wiki-editor">
          <div class="flex items-center justify-between mb-4">
            <h2 class="font-medium text-[var(--text-primary)]">{{ form.id ? '编辑概念页' : '新建概念页' }}</h2>
            <div class="flex gap-2">
              <el-button size="small" @click="editing = false">取消</el-button>
              <el-button size="small" type="primary" :loading="saving" data-test="wiki-save" @click="save">
                保存
              </el-button>
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label class="text-xs text-[var(--text-secondary)] mb-1 block">标题</label>
              <el-input v-model="form.title" data-test="wiki-title" placeholder="如：梯度下降" />
            </div>
            <div>
              <label class="text-xs text-[var(--text-secondary)] mb-1 block">Slug（用于 [[链接]]）</label>
              <el-input v-model="form.slug" :disabled="!!form.id" placeholder="如：gradient-descent" />
            </div>
          </div>
          <div class="mb-3">
            <label class="text-xs text-[var(--text-secondary)] mb-1 block">一句话摘要</label>
            <el-input v-model="form.summary" placeholder="可选，列表里展示" />
          </div>
          <div>
            <label class="text-xs text-[var(--text-secondary)] mb-1 block">
              Markdown 正文（支持 [[slug]] 双链）
            </label>
            <el-input v-model="form.content" type="textarea" :rows="14" data-test="wiki-content" />
          </div>
        </div>

        <!-- Reader -->
        <div v-else-if="current" class="card p-6" data-test="wiki-reader">
          <div class="flex items-start justify-between gap-3 mb-2">
            <div>
              <h2 class="text-xl font-semibold text-[var(--text-primary)]">{{ current.title }}</h2>
              <p class="text-xs text-[var(--text-muted)] mt-1">
                <code class="px-1.5 py-0.5 rounded bg-[var(--bg-secondary)]">{{ current.slug }}</code>
                · rev {{ current.revision }}
              </p>
            </div>
            <div class="flex gap-2">
              <el-button size="small" data-test="wiki-history" @click="loadHistory">历史</el-button>
              <el-button size="small" data-test="wiki-edit" @click="startEdit">编辑</el-button>
              <el-button size="small" type="danger" plain data-test="wiki-delete" @click="remove">删除</el-button>
            </div>
          </div>

          <div v-if="current.dead_links?.length" class="mt-2 mb-3 text-xs text-amber-600">
            死链：
            <button
              v-for="d in current.dead_links"
              :key="d"
              type="button"
              class="underline cursor-pointer ml-1"
              @click="startCreate(d)"
            >[[{{ d }}]]</button>
            （点击创建）
          </div>

          <div class="prose-sm wiki-body mt-4" v-html="rendered"></div>

          <div v-if="current.links?.length" class="mt-6 pt-4 border-t border-[var(--border-default)]">
            <div class="text-xs text-[var(--text-muted)] mb-2">出链</div>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="s in current.links"
                :key="s"
                type="button"
                class="px-2.5 py-1 rounded-full border text-xs cursor-pointer"
                :class="linkStatus[s]
                  ? 'border-[var(--color-primary)] text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10'
                  : 'border-dashed border-amber-400 text-amber-600'"
                :data-test="`wiki-link-${s}`"
                @click="followLink(s)"
              >
                {{ linkTitle(s) }}
              </button>
            </div>
          </div>

          <!-- 5.4 版本历史 -->
          <div v-if="history?.length" class="mt-6 pt-4 border-t border-[var(--border-default)]" data-test="wiki-history-list">
            <div class="text-xs text-[var(--text-muted)] mb-2">
              版本历史
              <span class="ml-2">回滚后当前内容会存为新版本，仍可再次回滚</span>
            </div>
            <div class="space-y-1.5">
              <div
                v-for="h in history"
                :key="h.id"
                class="text-xs"
              >
                <div class="flex items-center justify-between">
                  <div class="min-w-0">
                    <span class="text-[var(--text-primary)]">rev {{ h.revision }}</span>
                    <span class="text-[var(--text-muted)] ml-2 truncate">{{ h.title }}</span>
                  </div>
                  <div class="flex gap-1">
                    <el-button
                      size="small"
                      text
                      :data-test="`wiki-diff-${h.revision}`"
                      @click="toggleDiff(h.revision)"
                    >{{ diffRev === h.revision ? '收起对比' : '对比' }}</el-button>
                    <el-button
                      size="small"
                      text
                      :data-test="`wiki-revert-${h.revision}`"
                      @click="revert(h.revision)"
                    >回滚</el-button>
                  </div>
                </div>
                <!-- F6：行级 diff -->
                <div
                  v-if="diffRev === h.revision"
                  class="mt-2 rounded border border-[var(--border-default)] p-2 space-y-0.5 max-h-64 overflow-y-auto"
                  data-test="wiki-diff-panel"
                >
                  <div v-if="diffLoading" class="text-[var(--text-muted)]">加载中…</div>
                  <div v-else-if="diffError" class="text-amber-600" data-test="wiki-diff-missing">
                    {{ diffError }}
                  </div>
                  <template v-else>
                    <div
                      v-for="(line, i) in diffLines"
                      :key="i"
                      class="text-[11px] font-mono px-1 rounded"
                      :class="line.type === 'add'
                        ? 'bg-emerald-500/10 text-emerald-700'
                        : line.type === 'del'
                          ? 'bg-red-500/10 text-red-600'
                          : 'text-[var(--text-muted)]'"
                    >{{ line.type === 'add' ? '+ ' : line.type === 'del' ? '- ' : '  ' }}{{ line.text }}</div>
                  </template>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="card p-10 text-center text-sm text-[var(--text-muted)]">
          选择左侧概念页，或新建一篇开始整理知识
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../services/api'
import { useMarkdown } from '../composables/useMarkdown'

interface WikiListItem {
  id: string
  slug: string
  title: string
  summary?: string
  page_type?: string
}
interface WikiPage extends WikiListItem {
  content: string
  revision: number
  links: string[]
  dead_links: string[]
}

const search = ref('')
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const ingesting = ref(false)
const history = ref<{ id: string; revision: number; title: string }[] | null>(null)
/** F6：当前展开 diff 的 revision */
const diffRev = ref<number | null>(null)
const diffLoading = ref(false)
const diffError = ref('')
const diffLines = ref<{ type: 'add' | 'del' | 'same'; text: string }[]>([])

async function toggleDiff(revision: number): Promise<void> {
  if (diffRev.value === revision) {
    diffRev.value = null
    return
  }
  if (!current.value) return
  diffRev.value = revision
  diffLoading.value = true
  diffError.value = ''
  diffLines.value = []
  try {
    const { data } = await api.get<{ content: string }>(
      `/wiki/${current.value.id}/revisions/${revision}`
    )
    const oldLines = (data?.content || '').split('\n')
    const newLines = (current.value.content || '').split('\n')
    diffLines.value = diffLinesFn(oldLines, newLines)
  } catch {
    diffError.value = '该版本无快照（可能产生于版本机制上线前）'
  } finally {
    diffLoading.value = false
  }
}

/** 行级 diff（LCS 简化：按行对齐，删旧增新） */
function diffLinesFn(
  oldLines: string[],
  newLines: string[]
): { type: 'add' | 'del' | 'same'; text: string }[] {
  // 简易 LCS
  const m = oldLines.length
  const n = newLines.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0))
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = oldLines[i] === newLines[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const out: { type: 'add' | 'del' | 'same'; text: string }[] = []
  let i = 0
  let j = 0
  while (i < m && j < n) {
    if (oldLines[i] === newLines[j]) {
      out.push({ type: 'same', text: oldLines[i] })
      i++
      j++
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: 'del', text: oldLines[i] })
      i++
    } else {
      out.push({ type: 'add', text: newLines[j] })
      j++
    }
  }
  while (i < m) out.push({ type: 'del', text: oldLines[i++] })
  while (j < n) out.push({ type: 'add', text: newLines[j++] })
  return out
}
const auditing = ref(false)
const audit = ref<{
  stats: { pages: number; links: number; dead_links: number; orphan_pages: number }
  pages: { id: string; slug: string; title: string; dead_links: string[] }[]
  orphan_pages: { id: string; slug: string; title: string }[]
} | null>(null)
const pages = ref<WikiListItem[]>([])
const current = ref<WikiPage | null>(null)
/** slug 归一结果 → 解析出的页面 {id,title}；null=死链 */
const linkStatus = ref<Record<string, { id: string; title: string } | null>>({})

const form = reactive({ id: '' as string, slug: '', title: '', summary: '', content: '' })

const { renderMarkdown } = useMarkdown()

/** 与后端 wiki_service.normalize_slug 对齐，避免前后端 key 不一致把活链标成死链 */
function normalizeSlug(raw: string): string {
  let s = (raw || '').trim().toLowerCase().replace(/\s+/g, '-')
  s = s.replace(/[^a-z0-9_\-/一-鿿]/g, '')
  s = s.replace(/-{2,}/g, '-').replace(/\/{2,}/g, '/')
  return s.replace(/^-+|-+$/g, '').slice(0, 128)
}

function escapeHtml(v: string): string {
  return v.replace(
    /[&<>"']/g,
    c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string
  )
}

/**
 * [[slug]] / [[slug|label]] → 可点链接（F1：废弃 HTML 占位符方案）。
 *
 * 源码阶段换成标准 Markdown 链接 `[label](wiki:slug)`（行内、不加 \n\n，
 * 避免把句子切成多段）；渲染完成后按 href 前缀 `wiki:` 定位 <a> 改写
 * class / data-slug / title。全局 useMarkdown 配置不动。
 * markdown-it 会对 href 做 URI 编码，读取时 decodeURIComponent 还原。
 */
const rendered = computed(() => {
  if (!current.value) return ''
  const source = (current.value.content || '').replace(
    /\[\[([^\]|#]+)(?:[|#]([^\]]*))?\]\]/g,
    (_m: string, slug: string, label?: string) => {
      const s = normalizeSlug(slug)
      const text = (label || slug).trim().replace(/([\[\]])/g, '\\$1')
      return `[${text}](wiki:${s})`
    }
  )
  let html = renderMarkdown(source)
  html = html.replace(/<a href="wiki:([^"]*)">([\s\S]*?)<\/a>/g, (_m: string, href: string, inner: string) => {
    let slug = href
    try {
      slug = decodeURIComponent(href)
    } catch {
      /* 保留原始 href 片段 */
    }
    const ok = !!linkStatus.value[slug]
    const title = ok ? '' : ` title="概念页「${escapeHtml(slug)}」尚未创建，点击创建"`
    return `<a href="#" class="wiki-link ${ok ? 'wiki-link-ok' : 'wiki-link-dead'}" data-slug="${escapeHtml(slug)}"${title}>${inner}</a>`
  })
  return html
})

function linkTitle(slug: string): string {
  return linkStatus.value[slug]?.title || slug
}

/** 5.3：全局死链巡检 */
async function runAudit(): Promise<void> {
  auditing.value = true
  try {
    const { data } = await api.get('/wiki/audit/dead-links')
    audit.value = data
    const n = data?.stats?.dead_links ?? 0
    ElMessage.success(n ? `发现 ${n} 条死链` : '没有死链')
  } catch {
    ElMessage.error('巡检失败')
  } finally {
    auditing.value = false
  }
}

async function loadHistory(): Promise<void> {
  if (!current.value) return
  try {
    const { data } = await api.get<{ id: string; revision: number; title: string }[]>(
      `/wiki/${current.value.id}/revisions`
    )
    history.value = Array.isArray(data) ? data : []
  } catch {
    history.value = []
  }
}

async function revert(revision: number): Promise<void> {
  if (!current.value) return
  try {
    const { data } = await api.post<WikiPage>(
      `/wiki/${current.value.id}/revert`,
      undefined,
      { params: { revision } }
    )
    current.value = data
    ElMessage.success(`已回滚到 rev ${revision}`)
    await loadHistory()
    await loadPages()
  } catch {
    ElMessage.error('回滚失败')
  }
}

/** 5.2：从就绪文档批量提炼概念页（取前 2 篇，避免单次过重） */
async function ingestFromDocs(): Promise<void> {
  ingesting.value = true
  try {
    const { data: docs } = await api.get<{ id: string; status: string }[]>('/documents')
    const ids = (Array.isArray(docs) ? docs : [])
      .filter(d => d.status === 'ready')
      .slice(0, 2)
      .map(d => d.id)
    if (!ids.length) {
      ElMessage.warning('没有可提炼的就绪文档')
      return
    }
    const { data } = await api.post<{ created: number; merged: number; errors: string[] }>(
      '/wiki/ingest',
      { document_ids: ids, max_pages: 6 }
    )
    const n = (data?.created || 0) + (data?.merged || 0)
    ElMessage.success(n ? `已生成/合并 ${n} 个概念页` : '未提炼出概念页')
    await loadPages()
  } catch {
    ElMessage.error('提炼失败')
  } finally {
    ingesting.value = false
  }
}

let searchSeq = 0
let searchTimer: ReturnType<typeof setTimeout> | null = null

async function loadPages(): Promise<void> {
  const my = ++searchSeq
  loading.value = true
  try {
    const { data } = await api.get<WikiListItem[]>('/wiki', {
      params: search.value ? { q: search.value } : {}
    })
    if (my !== searchSeq) return
    pages.value = Array.isArray(data) ? data : []
  } catch {
    if (my === searchSeq) pages.value = []
  } finally {
    if (my === searchSeq) loading.value = false
  }
}

function onSearchInput(): void {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => void loadPages(), 300)
}

async function openPage(id: string): Promise<void> {
  try {
    const { data } = await api.get<WikiPage>(`/wiki/${id}`)
    current.value = data
    editing.value = false
    history.value = null
    // 解析出链生死（截断防 414）
    const links = (data.links || []).slice(0, 50)
    if (links.length) {
      const { data: resolved } = await api.get<
        Record<string, { id: string; title: string } | null>
      >('/wiki/resolve', {
        params: { slugs: links.join(',') }
      })
      const map: Record<string, { id: string; title: string } | null> = {}
      for (const [k, v] of Object.entries(resolved || {})) {
        map[k] = v?.id ? { id: v.id, title: v.title } : null
      }
      linkStatus.value = map
    } else {
      linkStatus.value = {}
    }
  } catch {
    ElMessage.error('加载概念页失败')
  }
}

function followLink(slug: string): void {
  const s = normalizeSlug(slug)
  // 优先用 resolve 结果里的 id（不受搜索过滤影响）
  const hit = linkStatus.value[s]
  if (hit?.id) {
    void openPage(hit.id)
    return
  }
  const listed = pages.value.find(p => p.slug === s)
  if (listed) {
    void openPage(listed.id)
    return
  }
  // 死链：确认后以该 slug 建空页并回填
  void ElMessageBox.confirm(
    `概念页「${s}」尚未创建，点击创建`,
    '创建概念页',
    { type: 'info', confirmButtonText: '创建', cancelButtonText: '取消' }
  )
    .then(() => {
      startCreate(s)
    })
    .catch(() => {
      /* 用户取消 */
    })
}

function startCreate(slugHint = ''): void {
  editing.value = true
  form.id = ''
  form.slug = slugHint
  form.title = slugHint
  form.summary = ''
  form.content = ''
}

function startEdit(): void {
  if (!current.value) return
  editing.value = true
  form.id = current.value.id
  form.slug = current.value.slug
  form.title = current.value.title
  form.summary = current.value.summary || ''
  form.content = current.value.content || ''
}

async function save(): Promise<void> {
  saving.value = true
  try {
    if (form.id) {
      const { data } = await api.put<WikiPage>(`/wiki/${form.id}`, {
        title: form.title,
        summary: form.summary,
        content: form.content
      })
      current.value = data
    } else {
      const { data } = await api.post<WikiPage>('/wiki', {
        slug: form.slug,
        title: form.title,
        summary: form.summary,
        content: form.content,
        page_type: 'concept',
        status: 'published'
      })
      current.value = data
    }
    editing.value = false
    ElMessage.success('已保存')
    await loadPages()
    if (current.value) await openPage(current.value.id)
  } catch {
    ElMessage.error('保存失败（slug 可能已存在）')
  } finally {
    saving.value = false
  }
}

async function remove(): Promise<void> {
  if (!current.value) return
  try {
    await ElMessageBox.confirm(`删除「${current.value.title}」？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await api.delete(`/wiki/${current.value.id}`)
    current.value = null
    linkStatus.value = {}
    history.value = null
    ElMessage.success('已删除')
    await loadPages()
  } catch {
    ElMessage.error('删除失败')
  }
}

// 点击渲染后的 wiki-link
function onBodyClick(e: MouseEvent): void {
  const t = e.target as HTMLElement | null
  if (t?.classList?.contains('wiki-link')) {
    e.preventDefault()
    followLink(t.getAttribute('data-slug') || '')
  }
}

onMounted(() => {
  void loadPages()
  document.addEventListener('click', onBodyClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onBodyClick)
  if (searchTimer) clearTimeout(searchTimer)
})
</script>

<style scoped>
/* F1 视觉规格：行内双链与正文字号/行高/字重一致，不做 chip 形态 */
.wiki-body :deep(.wiki-link) {
  color: inherit;
  font: inherit;
  text-decoration: underline;
  text-underline-offset: 2px;
  text-decoration-thickness: 1px;
  cursor: pointer;
}
.wiki-body :deep(.wiki-link:hover) {
  text-decoration-thickness: 2px;
}
.wiki-body :deep(.wiki-link-dead) {
  color: var(--el-text-color-secondary, #909399);
  text-decoration-style: dashed;
}
</style>
