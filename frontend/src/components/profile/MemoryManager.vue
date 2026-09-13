<template>
  <div class="space-y-6">
    <!-- ── 顶部状态栏与控制 ── -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-[var(--color-primary-light)] text-[var(--color-primary)] flex items-center justify-center">
          <el-icon :size="20"><CollectionTag /></el-icon>
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">跨会话长期记忆引擎</h3>
            <span
              class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full font-medium"
              :class="memoryStore.config.enabled ? 'bg-emerald-500/10 text-emerald-500' : 'bg-neutral-500/10 text-neutral-400'"
            >
              <span
                class="w-1.5 h-1.5 rounded-full"
                :class="memoryStore.config.enabled ? 'bg-emerald-500 animate-pulse' : 'bg-neutral-400'"
              />
              {{ memoryStore.config.enabled ? '已启用' : '已暂停' }}
            </span>
          </div>
          <p class="text-xs text-[var(--text-secondary)] mt-0.5">
            五分类记忆体系（画像、偏好、事实、目标、兴趣），在提问与深度研讨时无感注入上下文。
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3 self-end sm:self-center flex-wrap">
        <div class="text-xs text-[var(--text-muted)] font-mono">
          容量: <span class="text-[var(--text-primary)] font-semibold">{{ memoryStore.activeItems.length }}</span> / {{ memoryStore.config.capacity }}
        </div>
        <el-switch
          :model-value="memoryStore.config.enabled"
          active-color="#10b981"
          @change="handleToggleEnabled"
        />
        <el-button type="primary" size="small" @click="showAddDialog = true">
          <el-icon class="mr-1"><Plus /></el-icon>添加记忆
        </el-button>
      </div>
    </div>

    <!-- ── 待确认推导记忆 (Pending Review) ── -->
    <div v-if="memoryStore.pendingItems.length > 0" class="p-4 rounded-xl bg-amber-500/10 border border-amber-500/25">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-medium text-sm">
          <el-icon><WarningFilled /></el-icon>
          <span>待确认学习特征 ({{ memoryStore.pendingItems.length }})</span>
        </div>
        <span class="text-xs text-[var(--text-muted)]">大模型对话推导，经确认后正式注入提示词</span>
      </div>

      <div class="space-y-2">
        <div
          v-for="item in memoryStore.pendingItems"
          :key="item.id"
          class="flex items-center justify-between p-3 rounded-lg bg-[var(--surface-card)] border border-[var(--border-default)]"
        >
          <div class="min-w-0 pr-3">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-[10px] px-1.5 py-0.5 rounded font-mono font-medium bg-amber-500/20 text-amber-600 dark:text-amber-400">
                {{ getKindLabel(item.kind) }}
              </span>
              <span class="text-xs font-semibold text-[var(--text-primary)] truncate font-mono">{{ item.key }}</span>
            </div>
            <p class="text-xs text-[var(--text-secondary)] mt-1">{{ item.content }}</p>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <el-button size="small" type="success" plain @click="handleConfirm(item.id)">
              <el-icon class="mr-1"><Check /></el-icon>确认
            </el-button>
            <el-button size="small" type="danger" text @click="handleDelete(item.id)">
              忽略
            </el-button>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 记忆分类三列看板 ── -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- 1. 常驻画像与学习偏好 -->
      <div class="p-4 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between pb-2.5 border-b border-[var(--border-default)] mb-3">
            <div class="flex items-center gap-2">
              <el-icon class="text-indigo-500"><User /></el-icon>
              <h4 class="text-sm font-semibold text-[var(--text-primary)]">常驻画像与偏好</h4>
            </div>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-500 font-medium">每轮必带</span>
          </div>
          <p class="text-[11px] text-[var(--text-muted)] mb-3">专业年级、学术背景、语言与回复风格</p>

          <div v-if="memoryStore.residentItems.length === 0" class="py-8 text-center text-xs text-[var(--text-muted)]">
            暂无常驻记忆条目
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="item in memoryStore.residentItems"
              :key="item.id"
              class="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-default)] text-xs flex items-start justify-between gap-2"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-1.5 mb-1">
                  <span class="text-[10px] px-1 py-0.2 rounded font-mono font-medium bg-indigo-500/15 text-indigo-400">
                    {{ getKindLabel(item.kind) }}
                  </span>
                  <span class="font-mono font-medium text-[var(--text-primary)] truncate">{{ item.key }}</span>
                </div>
                <p class="text-[var(--text-secondary)] leading-relaxed">{{ item.content }}</p>
              </div>
              <el-button
                size="small"
                type="danger"
                text
                class="!p-1 h-auto shrink-0 mt-0.5"
                title="删除该记忆条目"
                @click="handleDelete(item.id)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. 情境事实与当前任务 -->
      <div class="p-4 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between pb-2.5 border-b border-[var(--border-default)] mb-3">
            <div class="flex items-center gap-2">
              <el-icon class="text-emerald-500"><Aim /></el-icon>
              <h4 class="text-sm font-semibold text-[var(--text-primary)]">情境事实与目标</h4>
            </div>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500 font-medium">词法召回</span>
          </div>
          <p class="text-[11px] text-[var(--text-muted)] mb-3">考试日期、备考安排、章节攻坚任务</p>

          <div v-if="memoryStore.situationalItems.length === 0" class="py-8 text-center text-xs text-[var(--text-muted)]">
            暂无情境事实条目
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="item in memoryStore.situationalItems"
              :key="item.id"
              class="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-default)] text-xs flex items-start justify-between gap-2"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-1.5 mb-1">
                  <span class="text-[10px] px-1 py-0.2 rounded font-mono font-medium bg-emerald-500/15 text-emerald-500">
                    {{ getKindLabel(item.kind) }}
                  </span>
                  <span class="font-mono font-medium text-[var(--text-primary)] truncate">{{ item.key }}</span>
                </div>
                <p class="text-[var(--text-secondary)] leading-relaxed">{{ item.content }}</p>
              </div>
              <el-button
                size="small"
                type="danger"
                text
                class="!p-1 h-auto shrink-0 mt-0.5"
                title="删除该记忆条目"
                @click="handleDelete(item.id)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. 学科兴趣与拓展领域 -->
      <div class="p-4 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between pb-2.5 border-b border-[var(--border-default)] mb-3">
            <div class="flex items-center gap-2">
              <el-icon class="text-amber-500"><TrendCharts /></el-icon>
              <h4 class="text-sm font-semibold text-[var(--text-primary)]">学科兴趣与领域</h4>
            </div>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-500 font-medium">意图加权</span>
          </div>
          <p class="text-[11px] text-[var(--text-muted)] mb-3">高频探讨的学科领域与知识拓展倾向</p>

          <div v-if="memoryStore.interestItems.length === 0" class="py-8 text-center text-xs text-[var(--text-muted)]">
            暂无学科兴趣条目
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="item in memoryStore.interestItems"
              :key="item.id"
              class="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-default)] text-xs flex items-start justify-between gap-2"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-1.5 mb-1">
                  <span class="text-[10px] px-1 py-0.2 rounded font-mono font-medium bg-amber-500/15 text-amber-500">
                    {{ getKindLabel(item.kind) }}
                  </span>
                  <span class="font-mono font-medium text-[var(--text-primary)] truncate">{{ item.key }}</span>
                </div>
                <p class="text-[var(--text-secondary)] leading-relaxed">{{ item.content }}</p>
              </div>
              <el-button
                size="small"
                type="danger"
                text
                class="!p-1 h-auto shrink-0 mt-0.5"
                title="删除该记忆条目"
                @click="handleDelete(item.id)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ── 新建记忆弹窗 ── -->
    <el-dialog v-model="showAddDialog" title="添加长期记忆" width="480px">
      <el-form label-position="top" class="space-y-4">
        <el-form-item label="记忆分类">
          <el-select v-model="newForm.kind" class="w-full">
            <el-option label="个人画像 (Profile) - 专业/年级/学术背景" value="profile" />
            <el-option label="学习偏好 (Preference) - 语言/代码风格/详细度" value="preference" />
            <el-option label="情境事实 (Fact) - 考试日期/项目事实" value="fact" />
            <el-option label="当前目标 (Task) - 正在攻克的章节或复习计划" value="task" />
            <el-option label="关注兴趣 (Interest) - 经常探讨的学科领域" value="interest" />
          </el-select>
        </el-form-item>
        <el-form-item label="记忆标识 (Key)">
          <el-input v-model="newForm.key" placeholder="如：grade_major、code_preference" />
        </el-form-item>
        <el-form-item label="记忆正文">
          <el-input
            v-model="newForm.content"
            type="textarea"
            :rows="3"
            placeholder="例如：计算机科学大三本科生，正在复习操作系统与数据结构，喜欢用 Python 说明算法。"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="flex justify-end gap-2">
          <el-button @click="showAddDialog = false">取消</el-button>
          <el-button type="primary" :disabled="!newForm.content.trim()" @click="handleAddSubmit">
            保存
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  Plus,
  Check,
  Delete,
  User,
  Aim,
  WarningFilled,
  CollectionTag,
} from '@element-plus/icons-vue'
import { TrendCharts } from '@/components/icons'
import { ElMessage } from 'element-plus'
import { useMemoryStore } from '../../stores/memory'

const memoryStore = useMemoryStore()
const showAddDialog = ref(false)
const newForm = ref({
  kind: 'profile',
  key: '',
  content: '',
})

onMounted(() => {
  memoryStore.fetchMemories()
})

function getKindLabel(kind: string): string {
  switch (kind) {
    case 'profile':
      return '画像'
    case 'preference':
      return '偏好'
    case 'fact':
      return '事实'
    case 'task':
      return '目标'
    case 'interest':
      return '兴趣'
    default:
      return kind
  }
}

async function handleToggleEnabled(val: string | number | boolean) {
  try {
    await memoryStore.updateConfig({ enabled: Boolean(val) })
    ElMessage.success(val ? '长期记忆已开启' : '长期记忆已暂停')
  } catch {
    ElMessage.error('更新记忆设置失败')
  }
}

async function handleConfirm(id: string) {
  try {
    await memoryStore.confirmMemory(id)
    ElMessage.success('已确认该学习特征')
  } catch {
    ElMessage.error('确认失败')
  }
}

async function handleDelete(id: string) {
  try {
    await memoryStore.deleteMemory(id)
    ElMessage.success('已删除记忆条目')
  } catch {
    ElMessage.error('删除失败')
  }
}

async function handleAddSubmit() {
  if (!newForm.value.content.trim()) return
  try {
    await memoryStore.createMemory({
      kind: newForm.value.kind,
      key: newForm.value.key || newForm.value.content.slice(0, 15),
      content: newForm.value.content.trim(),
    })
    ElMessage.success('长期记忆已添加')
    showAddDialog.value = false
    newForm.value = { kind: 'profile', key: '', content: '' }
  } catch {
    ElMessage.error('添加记忆失败')
  }
}
</script>
