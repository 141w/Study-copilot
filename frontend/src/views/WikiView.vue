<template>
  <div class="max-w-6xl mx-auto px-6 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-semibold text-[var(--text-primary)]">知识 Wiki</h1>
        <p class="text-sm text-[var(--text-muted)] mt-1">概念页 + [[双链]]，把资料串成可点的知识网</p>
      </div>
      <div class="flex gap-2">
        <el-button data-test="wiki-ingest" :loading="ingesting" @click="ingestFromDocs">
          从文档提炼
        </el-button>
        <el-button type="primary" data-test="wiki-new" @click="startCreate()">新建概念页</el-button>
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
          @input="loadPages"
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
        </div>

        <div v-else class="card p-10 text-center text-sm text-[var(--text-muted)]">
          选择左侧概念页，或新建一篇开始整理知识
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
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
const pages = ref<WikiListItem[]>([])
const current = ref<WikiPage | null>(null)
const linkStatus = ref<Record<string, string | null>>({})

const form = reactive({ id: '' as string, slug: '', title: '', summary: '', content: '' })

const { renderMarkdown } = useMarkdown()

/** 将 [[slug]] 渲染成可点 span（交给 followLink 处理跳转） */
const rendered = computed(() => {
  if (!current.value) return ''
  const html = renderMarkdown(current.value.content || '')
  return html.replace(
    /\[\[([^\]|#]+)(?:[|#]([^\]]*))?\]\]/g,
    (_m, slug: string, label?: string) => {
      const s = String(slug).trim().toLowerCase()
      const text = label || slug
      const ok = !!linkStatus.value[s]
      return `<a href="#" class="wiki-link ${ok ? 'wiki-link-ok' : 'wiki-link-dead'}" data-slug="${s}">${text}</a>`
    }
  )
})

function linkTitle(slug: string): string {
  return linkStatus.value[slug] || slug
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

async function loadPages(): Promise<void> {
  loading.value = true
  try {
    const { data } = await api.get<WikiListItem[]>('/wiki', {
      params: search.value ? { q: search.value } : {}
    })
    pages.value = Array.isArray(data) ? data : []
  } catch {
    pages.value = []
  } finally {
    loading.value = false
  }
}

async function openPage(id: string): Promise<void> {
  try {
    const { data } = await api.get<WikiPage>(`/wiki/${id}`)
    current.value = data
    editing.value = false
    // 解析出链生死
    const links = data.links || []
    if (links.length) {
      const { data: resolved } = await api.get<Record<string, { title: string } | null>>('/wiki/resolve', {
        params: { slugs: links.join(',') }
      })
      const map: Record<string, string | null> = {}
      for (const [k, v] of Object.entries(resolved || {})) {
        map[k] = v?.title || null
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
  const hit = pages.value.find(p => p.slug === slug)
  if (hit) {
    void openPage(hit.id)
  } else {
    startCreate(slug)
  }
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
</script>

<style scoped>
.wiki-body :deep(.wiki-link) {
  color: var(--color-primary);
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
}
.wiki-body :deep(.wiki-link-dead) {
  color: #d97706;
  text-decoration-style: dashed;
}
</style>
