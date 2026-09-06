<template>
  <el-dialog
    v-model="visible"
    :title="activeTab === 'edit' ? (isEditing ? '编辑自定义角色' : '新建研讨角色') : '研讨角色管理'"
    width="640px"
    class="persona-manage-dialog"
    :close-on-click-modal="false"
    destroy-on-close
    @open="handleOpen"
  >
    <!-- 头部标签页切换（浏览库 vs 新建/编辑） -->
    <div class="flex items-center justify-between border-b border-[var(--border-default)] pb-3 mb-4">
      <div class="flex items-center gap-2">
        <button
          type="button"
          class="px-3 py-1.5 text-xs font-medium rounded-lg transition-all"
          :class="activeTab === 'list'
            ? 'bg-[var(--color-primary)] text-[var(--text-inverse)] shadow-sm'
            : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
          @click="activeTab = 'list'"
        >
          全部角色库 ({{ personas.length }})
        </button>
        <button
          type="button"
          class="px-3 py-1.5 text-xs font-medium rounded-lg transition-all flex items-center gap-1"
          :class="activeTab === 'edit'
            ? 'bg-[var(--color-primary)] text-[var(--text-inverse)] shadow-sm'
            : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]'"
          @click="startCreate"
        >
          <el-icon :size="12"><Plus /></el-icon>
          <span>{{ isEditing ? '编辑角色' : '新建角色' }}</span>
        </button>
      </div>

      <span class="text-xs text-[var(--text-muted)]">
        跨设备/浏览器自动云同步
      </span>
    </div>

    <!-- 视图 1：全部角色列表 -->
    <div v-if="activeTab === 'list'" class="space-y-4 max-h-[58vh] overflow-y-auto pr-1">
      <!-- 自定义角色分区 -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
            我的自定义角色 ({{ customPersonas.length }})
          </span>
          <el-button
            v-if="customPersonas.length > 0"
            size="small"
            text
            type="primary"
            class="!text-xs"
            @click="startCreate"
          >
            <el-icon class="mr-1"><Plus /></el-icon>
            添加角色
          </el-button>
        </div>

        <!-- 自定义角色为空 -->
        <div
          v-if="customPersonas.length === 0"
          class="border border-dashed border-[var(--border-default)] rounded-xl p-5 text-center bg-[var(--bg-primary)]/40"
        >
          <div class="w-10 h-10 rounded-xl mx-auto mb-2 flex items-center justify-center bg-[var(--color-primary)]/10 text-[var(--color-primary)]">
            <el-icon :size="20"><MagicStick /></el-icon>
          </div>
          <p class="text-xs font-medium text-[var(--text-primary)] mb-1">
            暂无自定义角色
          </p>
          <p class="text-[11px] text-[var(--text-muted)] mb-3 max-w-sm mx-auto">
            您可以创建专属的苏格拉底提问者、行业大牛、辩论挑刺助手或答辩导师，与内置角色同台研讨。
          </p>
          <el-button size="small" type="primary" @click="startCreate">
            <el-icon class="mr-1"><Plus /></el-icon>
            立即创建
          </el-button>
        </div>

        <!-- 自定义角色卡片列表 -->
        <div v-else class="grid grid-cols-1 gap-2.5">
          <div
            v-for="persona in customPersonas"
            :key="persona.id || persona.role"
            class="group relative flex items-start justify-between p-3 rounded-xl border border-[var(--border-default)] bg-[var(--surface-card)] hover:border-[var(--color-primary)] transition-all shadow-xs"
          >
            <div class="flex items-start gap-3 min-w-0 pr-2">
              <!-- 头像/徽章 -->
              <div
                class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 select-none shadow-xs"
                :style="{ backgroundColor: (persona.color || '#6366f1') + '1a', border: `1px solid ${(persona.color || '#6366f1')}33`, color: persona.color || '#6366f1' }"
              >
                <el-icon :size="18">
                  <component :is="getIconComponent(persona.avatar)" />
                </el-icon>
              </div>
              <!-- 文本介绍 -->
              <div class="min-w-0">
                <div class="flex items-center gap-2 mb-0.5">
                  <span class="font-medium text-xs text-[var(--text-primary)] truncate">
                    {{ persona.name }}
                  </span>
                  <span
                    class="text-[10px] px-1.5 py-0.2 rounded-full font-medium"
                    :style="{ color: persona.color || '#6366f1', backgroundColor: (persona.color || '#6366f1') + '15' }"
                  >
                    自定义
                  </span>
                </div>
                <p class="text-[11px] text-[var(--text-muted)] line-clamp-2 leading-relaxed">
                  {{ persona.system_message }}
                </p>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="flex items-center gap-1 shrink-0 pt-0.5 opacity-80 group-hover:opacity-100 transition-opacity">
              <el-tooltip content="编辑人设" placement="top" :enterable="false">
                <el-button
                  size="small"
                  circle
                  text
                  @click="startEdit(persona)"
                >
                  <el-icon :size="13"><Edit /></el-icon>
                </el-button>
              </el-tooltip>
              <el-popconfirm
                title="确定删除此自定义角色？"
                confirm-button-text="删除"
                cancel-button-text="取消"
                confirm-button-type="danger"
                @confirm="deletePersona(persona)"
              >
                <template #reference>
                  <el-button
                    size="small"
                    circle
                    text
                    type="danger"
                  >
                    <el-icon :size="13"><Delete /></el-icon>
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </div>
        </div>
      </div>

      <!-- 官方内置预置角色分区 -->
      <div class="pt-2">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs font-semibold text-[var(--text-secondary)] flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            官方内置角色 ({{ presetPersonas.length }})
          </span>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          <div
            v-for="preset in presetPersonas"
            :key="preset.role"
            class="flex items-start gap-2.5 p-3 rounded-xl border border-[var(--border-default)] bg-[var(--bg-primary)]/30"
          >
            <div
              class="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 select-none"
              :style="{ backgroundColor: (preset.color || '#10b981') + '15', color: preset.color || '#10b981' }"
            >
              <el-icon :size="16">
                <component :is="getIconComponent(preset.avatar)" />
              </el-icon>
            </div>
            <div class="min-w-0">
              <div class="flex items-center gap-1.5 mb-0.5">
                <span class="font-medium text-xs text-[var(--text-primary)]">
                  {{ preset.name }}
                </span>
                <span class="text-[10px] px-1 py-0.2 rounded bg-neutral-200 dark:bg-neutral-800 text-[var(--text-muted)]">
                  预置
                </span>
              </div>
              <p class="text-[11px] text-[var(--text-muted)] line-clamp-2 leading-relaxed">
                {{ preset.system_message }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 视图 2：新建 / 编辑角色表单 -->
    <div v-else class="space-y-4">
      <!-- 角色名称 -->
      <div>
        <label class="block text-xs font-medium text-[var(--text-primary)] mb-1.5">
          角色名称 <span class="text-[var(--color-error)]">*</span>
        </label>
        <el-input
          v-model="formData.name"
          placeholder="例如：苏格拉底、批判性审稿人、辩论反方"
          maxlength="20"
          show-word-limit
        />
      </div>

      <!-- 图标与代表色组合设置 -->
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <!-- 角色矢量图标 (SVG) -->
        <div>
          <label class="block text-xs font-medium text-[var(--text-primary)] mb-1.5">
            角色矢量图标
          </label>
          <div class="flex items-center gap-2.5 mb-2">
            <div
              class="w-9 h-9 rounded-lg flex items-center justify-center shrink-0 select-none shadow-xs border transition-colors"
              :style="{ backgroundColor: formData.color + '1a', borderColor: formData.color + '40', color: formData.color }"
            >
              <el-icon :size="18">
                <component :is="getIconComponent(formData.avatar)" />
              </el-icon>
            </div>
            <span class="text-xs text-[var(--text-secondary)] font-medium">
              {{ getIconLabel(formData.avatar) }}
            </span>
          </div>
          <!-- 快捷 SVG 矢量图标选择器 -->
          <div class="grid grid-cols-8 gap-1.5 p-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-primary)]/40">
            <button
              v-for="icon in availableIcons"
              :key="icon.name"
              type="button"
              :title="icon.label"
              class="w-7 h-7 rounded-md flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-hover)] transition-all"
              :class="formData.avatar === icon.name ? 'ring-2 ring-[var(--color-primary)] bg-[var(--bg-hover)] text-[var(--color-primary)]' : ''"
              @click="formData.avatar = icon.name"
            >
              <el-icon :size="15">
                <component :is="iconComponents[icon.name]" />
              </el-icon>
            </button>
          </div>
        </div>

        <!-- 代表色彩选择 -->
        <div>
          <label class="block text-xs font-medium text-[var(--text-primary)] mb-1.5">
            主题代表色
          </label>
          <div class="flex items-center gap-2 pt-1">
            <button
              v-for="color in themeColors"
              :key="color"
              type="button"
              class="w-6 h-6 rounded-full transition-transform flex items-center justify-center"
              :style="{ backgroundColor: color }"
              :class="formData.color === color ? 'scale-110 ring-2 ring-offset-2 ring-[var(--color-primary)]' : 'hover:scale-105'"
              @click="formData.color = color"
            >
              <el-icon v-if="formData.color === color" :size="12" class="text-white">
                <Check />
              </el-icon>
            </button>
          </div>
          <p class="text-[11px] text-[var(--text-muted)] mt-2">
            用于在研讨记录中标识该角色的发言卡片与气泡边框。
          </p>
        </div>
      </div>

      <!-- 人设提示词 (System Prompt) -->
      <div>
        <div class="flex items-center justify-between mb-1.5">
          <label class="text-xs font-medium text-[var(--text-primary)]">
            人设提示词 (System Prompt) <span class="text-[var(--color-error)]">*</span>
          </label>
          <span class="text-[10px] text-[var(--text-muted)]">
            决定角色的思维立场与发言风格
          </span>
        </div>
        <el-input
          v-model="formData.system_message"
          type="textarea"
          :rows="4"
          placeholder="设定该角色的身份、分析逻辑与语言风格。例如：&#10;你是一位专精批判性思维的苏格拉底式引导者。你善于通过层层反问激发求知欲，从不直接给出答案，而是引导对方发现逻辑漏洞并自我修正..."
          maxlength="2000"
          show-word-limit
        />

        <!-- 快捷预设灵感 -->
        <div class="flex items-center gap-1.5 mt-2 overflow-x-auto pb-1">
          <span class="text-[11px] text-[var(--text-muted)] shrink-0">快捷灵感：</span>
          <button
            v-for="tpl in promptTemplates"
            :key="tpl.label"
            type="button"
            class="px-2 py-0.5 text-[11px] rounded border border-[var(--border-default)] hover:border-[var(--color-primary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] shrink-0 transition-colors"
            @click="applyTemplate(tpl)"
          >
            {{ tpl.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- 底部操作按钮 -->
    <template #footer>
      <div class="flex items-center justify-end gap-2 pt-2 border-t border-[var(--border-default)]">
        <el-button
          size="small"
          @click="activeTab === 'edit' ? (activeTab = 'list') : (visible = false)"
        >
          {{ activeTab === 'edit' ? '返回列表' : '关闭' }}
        </el-button>
        <el-button
          v-if="activeTab === 'edit'"
          type="primary"
          size="small"
          :loading="saving"
          @click="submitForm"
        >
          保存角色
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Plus,
  Edit,
  Delete,
  Check,
  User,
  GraduationCap,
  ChatLineRound,
  EditPen,
  Brain,
  Lightning,
  MagicStick,
  Reading,
  Search,
  TrendCharts,
  Promotion,
  ChatDotSquare,
  Setting,
  Clock,
  Tickets,
  Document
} from '@/components/icons'
import { ElMessage } from 'element-plus'
import api from '../../services/api'

interface PersonaItem {
  id?: string
  role: string
  name: string
  avatar?: string
  color?: string
  system_message?: string
  is_custom?: boolean
  created_at?: string
}

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'updated', newRole?: string): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const activeTab = ref<'list' | 'edit'>('list')
const isEditing = ref<boolean>(false)
const editingId = ref<string | null>(null)
const saving = ref<boolean>(false)

const personas = ref<PersonaItem[]>([])

const iconComponents: Record<string, any> = {
  User,
  GraduationCap,
  ChatLineRound,
  EditPen,
  Brain,
  Lightning,
  MagicStick,
  Reading,
  Search,
  TrendCharts,
  Promotion,
  ChatDotSquare,
  Setting,
  Clock,
  Tickets,
  Document
}

const availableIcons = [
  { name: 'User', label: '导师' },
  { name: 'GraduationCap', label: '学者' },
  { name: 'ChatLineRound', label: '求知' },
  { name: 'EditPen', label: '速记' },
  { name: 'Brain', label: '哲思' },
  { name: 'Lightning', label: '极客' },
  { name: 'MagicStick', label: '启发' },
  { name: 'Reading', label: '研读' },
  { name: 'Search', label: '探究' },
  { name: 'TrendCharts', label: '评委' },
  { name: 'Promotion', label: '引领' },
  { name: 'ChatDotSquare', label: '研讨' },
  { name: 'Setting', label: '实践' },
  { name: 'Clock', label: '沉思' },
  { name: 'Tickets', label: '考评' },
  { name: 'Document', label: '考据' },
]

function getIconComponent(avatar?: string) {
  if (avatar && iconComponents[avatar]) {
    return iconComponents[avatar]
  }
  return User
}

function getIconLabel(avatar?: string) {
  const found = availableIcons.find(i => i.name === avatar)
  return found ? found.label : '导师'
}

const themeColors = [
  '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#6366f1', '#64748b'
]

const promptTemplates = [
  {
    label: '苏格拉底反问',
    name: '苏格拉底',
    avatar: 'Brain',
    color: '#8b5cf6',
    prompt: '你是一位精通批判性思维的苏格拉底式引导者。你善于通过层层反问激发求知欲，从不直接给出结论，而是引导对方发现自身的逻辑盲区并推导答案。'
  },
  {
    label: '底层原理极客',
    name: '极客导师',
    avatar: 'Lightning',
    color: '#06b6d4',
    prompt: '你是一位技术极客。发言风格严谨、直探本质，善于从计算机底层原理、系统架构或数学物理定理出发剖析概念，并主动指出常见的边界条件与性能瓶颈。'
  },
  {
    label: '答辩评委反方',
    name: '挑刺评委',
    avatar: 'TrendCharts',
    color: '#ef4444',
    prompt: '你是学术答辩的严格评委。你善于站在对立视角寻找论证的漏洞、可行性短板或未经验证的假设，迫使讨论更加扎实周密。'
  }
]

const formData = ref({
  name: '',
  avatar: 'User',
  color: '#6366f1',
  system_message: '',
  role: ''
})

const customPersonas = computed(() => personas.value.filter(p => p.is_custom))
const presetPersonas = computed(() => personas.value.filter(p => !p.is_custom))

const loadPersonas = async () => {
  try {
    const { data } = await api.get('/chat/personas')
    if (Array.isArray(data?.personas)) {
      personas.value = data.personas
    }
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '拉取角色库失败')
  }
}

const handleOpen = () => {
  activeTab.value = 'list'
  loadPersonas()
}

onMounted(() => {
  if (props.modelValue) {
    loadPersonas()
  }
})

const startCreate = () => {
  isEditing.value = false
  editingId.value = null
  formData.value = {
    name: '',
    avatar: 'User',
    color: '#6366f1',
    system_message: '',
    role: ''
  }
  activeTab.value = 'edit'
}

const startEdit = (persona: PersonaItem) => {
  isEditing.value = true
  editingId.value = persona.id || null
  formData.value = {
    name: persona.name,
    avatar: persona.avatar || 'User',
    color: persona.color || '#6366f1',
    system_message: persona.system_message || '',
    role: persona.role
  }
  activeTab.value = 'edit'
}

const applyTemplate = (tpl: typeof promptTemplates[0]) => {
  if (!formData.value.name) formData.value.name = tpl.name
  formData.value.avatar = tpl.avatar
  formData.value.color = tpl.color
  formData.value.system_message = tpl.prompt
}

const submitForm = async () => {
  const name = formData.value.name.trim()
  if (!name) {
    ElMessage.warning('请输入角色名称')
    return
  }
  const prompt = formData.value.system_message.trim()
  if (!prompt) {
    ElMessage.warning('请输入人设提示词')
    return
  }

  saving.value = true
  try {
    let savedRole: string | undefined
    if (isEditing.value && editingId.value) {
      const { data } = await api.put(`/chat/personas/${editingId.value}`, {
        name,
        avatar: formData.value.avatar.trim() || 'User',
        color: formData.value.color,
        system_message: prompt
      })
      savedRole = data.role
      ElMessage.success('角色已成功更新')
    } else {
      const { data } = await api.post('/chat/personas', {
        name,
        avatar: formData.value.avatar.trim() || 'User',
        color: formData.value.color,
        system_message: prompt
      })
      savedRole = data.role
      ElMessage.success('自定义角色创建成功')
    }

    await loadPersonas()
    emit('updated', savedRole)
    activeTab.value = 'list'
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '保存角色失败，请重试')
  } finally {
    saving.value = false
  }
}

const deletePersona = async (persona: PersonaItem) => {
  if (!persona.id) return
  try {
    await api.delete(`/chat/personas/${persona.id}`)
    ElMessage.success(`角色「${persona.name}」已删除`)
    await loadPersonas()
    emit('updated')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.detail || '删除角色失败')
  }
}
</script>

<style scoped>
.persona-manage-dialog :deep(.el-dialog__body) {
  padding-top: 10px;
  padding-bottom: 12px;
}
</style>
