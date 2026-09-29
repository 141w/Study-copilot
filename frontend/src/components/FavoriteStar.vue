<template>
  <el-button
    circle
    class="fav-btn"
    :class="{ 'is-fav': active }"
    :title="active ? '取消收藏' : '收藏'"
    :aria-label="active ? '取消收藏' : '收藏'"
    :aria-pressed="active"
    :data-test="`fav-star-${type}-${id}`"
    :data-active="active ? '1' : '0'"
    @click.stop="onToggle"
  >
    <el-icon :size="15" class="fav-icon">
      <StarFilled v-if="active" />
      <Star v-else />
    </el-icon>
  </el-button>
</template>

<style scoped>
/* 琥珀色只作用在图标本身，按钮皮肤保持 circle 统一规格 */
.fav-btn :deep(.fav-icon) {
  color: var(--text-muted);
  transition: color var(--transition-fast);
}
.fav-btn:hover :deep(.fav-icon) {
  color: #f59e0b; /* amber-500 */
}
.fav-btn.is-fav :deep(.fav-icon) {
  color: #f59e0b; /* amber-500 */
}
.fav-btn.is-fav:hover :deep(.fav-icon) {
  color: #d97706; /* amber-600 */
}
</style>

<script setup lang="ts">
// 图标钮统一规范：几何 / 底色 / 发丝描边 / hover / focus 全部交给 el-button circle，
// 组件本身不再手写 w-7 h-7 rounded-* 与 hover 底色。
// 收藏语义仍由星形自身表达（描边星 = 未收藏，实心琥珀星 = 已收藏），
// 因此不占用 type="primary" 的选中态——黑白主色会盖掉琥珀识别度。
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
