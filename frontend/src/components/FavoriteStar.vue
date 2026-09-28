<template>
  <button
    type="button"
    class="inline-flex items-center justify-center w-7 h-7 rounded-md transition-colors cursor-pointer"
    :class="active
      ? 'text-amber-500 hover:text-amber-600'
      : 'text-[var(--text-muted)] hover:text-amber-500'"
    :title="active ? '取消收藏' : '收藏'"
    :aria-label="active ? '取消收藏' : '收藏'"
    :data-test="`fav-star-${type}-${id}`"
    :data-active="active ? '1' : '0'"
    @click.stop="onToggle"
  >
    <el-icon :size="15">
      <StarFilled v-if="active" />
      <Star v-else />
    </el-icon>
  </button>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { Star, StarFilled } from '@element-plus/icons-vue'
import { useFavoriteStore, type FavoriteType } from '../stores/favorite'

const props = defineProps<{
  type: FavoriteType
  id: string
}>()

const favStore = useFavoriteStore()

const active = computed(() => favStore.isFavorite(props.type, props.id))

onMounted(() => {
  void favStore.fetchFavorites()
})

async function onToggle(): Promise<void> {
  await favStore.toggle(props.type, props.id)
}
</script>
