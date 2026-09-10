<template>
  <div class="space-y-6">
    <!-- 顶部状态栏与开关 -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border-default)]">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl bg-[var(--color-primary-light)] text-[var(--color-primary)] flex items-center justify-center font-bold text-lg">
          🧠
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h3 class="text-sm font-semibold text-[var(--text-primary)]">跨会话长期记忆</h3>
            <span
              class="text-[11px] px-2 py-0.5 rounded-full font-medium"
              :class="memoryStore.config.enabled ? 'bg-emerald-500/10 text-emerald-500' : 'bg-zinc-500/10 text-zinc-500'"
            >
              {{ memoryStore.config.enabled ? '已启用' : '已暂停' }}
            </span>
          </div>
          <p class="text-xs text-[var(--text-secondary)] mt-0.5">
            自动留存学生画像、备考目标与学习偏好，在提问时无感注入 System 上下文。
          </p>
        </div>
      </div>
      <div class="flex items-center gap-3 self-end sm:self-center">
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

    <!-- 待确认推导记忆 (Pending Review) -->
    <div v-if="memoryStore.pendingItems.length > 0" class="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2 text-amber-600 dark:text-amber-400 font-medium text-sm">
          <el-icon><Bell /></el-icon>
          <span>待确认学习特征 ({{ memoryStore.pendingItems.length }})</span>
        </div>
        <span class="text-xs text-[var(--text-muted)]">系统根据对话推导，经确认后方会生效</span>
      </div>
      <div class="space-y-2.5">
        <div
          v-for="item in memoryStore.pendingItems"
          :key="item.id"
          class="flex items-center justify-between p-3 rounded-lg bg-[var(--surface-card)] border border-[var(--border-default)] shadow-xs"
        >
          <div class="min-w-0 pr-3">
            <div class="flex items-center gap-2">
              <span class="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-600 dark:text-amber-400 font-medium">
                {{ getKindLabel(item.kind) }}
              </span>
              <span class="text-xs font-semibold text-[var(--text-primary)] truncate">{{ item.key }}</span>
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

    <!-- 记忆分类看板 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- 常驻画像与学习偏好 -->
      <div class="p-4 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between pb-2 border-b border-[var(--border-default)] mb-3">
            <div class="flex items-center gap-2">
              <span class="text-base">👤</span>
              <h4 class="text-sm font-semibold text-[var(--text-primary)]">常驻画像与偏好</h4>
            </div>
            <span class="text-[11px] text-[var(--text-muted)]">每轮必带</span>
          </div>
          <div v-if="memoryStore.residentItems.length === 0" class="py-6 text-center text-xs text-[var(--text-muted)]">
            暂无常驻画像，可点击上方「添加记忆」补充专业或答疑偏好
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="item in memoryStore.residentItems"
              :key="item.id"
              class="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-default)] text-xs flex items-start justify-between gap-2"
            >
              <div>
                <span class="font-medium text-[var(--color-primary)]">[{{ item.key }}]</span>
                <span class="text-[var(--text-secondary)] ml-1">{{ item.content }}</span>
              </div>
              <el-button size="small" type="danger" text class="!p-1 h-auto" @click="handleDelete(item.id)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 情境事实与当前任务 -->
      <div class="p-4 rounded-xl bg-[var(--surface-card)] border border-[var(--border-default)] flex flex-col justify-between">
        <div>
          <div class="flex items-center justify-between pb-2 border-b border-[var(--border-default)] mb-3">
            <div class="flex items-center gap-2">
              <span class="text-base">🎯</span>
              <h4 class="text-sm font-semibold text-[var(--text-primary)]">情境事实与任务</h4>
            </div>
            <span class="text-[11px] text-[var(--text-muted)]">问题匹配时召回</span>
          </div>
          <div v-if="memoryStore.situationalItems.length === 0" class="py-6 text-center text-xs text-[var(--text-muted)]">
            暂无情境事实，将在涉及考试日期、章节目标时触发词法召回
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="item in memoryStore.situationalItems"
              :key="item.id"
              class="p-2.5 rounded-lg bg-[var(--bg-secondary)] border border-[var(--border-default)] text-xs flex items-start justify-between gap-2"
            >
              <div>
                <span class="font-medium text-emerald-600 dark:text-emerald-400">[{{ getKindLabel(item.kind) }}]</span>
                <span class="text-[var(--text-secondary)] ml-1">{{ item.content }}</span>
              </div>
              <el-button size="small" type="danger" text class="!p-1 h-auto" @click="handleDelete(item.id)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建记忆弹窗 -->
    <el-dialog v-model="showAddDialog" title="添加长期记忆" width="480px">
      <el-form label-position="top" class="space-y-4">
        <el-form-item label="记忆分类">
          <el-select v-model="newForm.kind" class="w-full">
            <el-option label="个人画像 (Profile) - 专业/年级/学术背景" value="profile" />
            <el-option label="学习偏好 (Preference) - 语言/代码风格/详细程度" value="preference" />
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
            placeholder="例如：计算机大三本科生，目前正在准备操作系统和数据结构期末考试，偏好用 Python 说明算法。"
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
import { Plus, Bell, Check, Delete } from '@element-plus/icons-vue'
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
