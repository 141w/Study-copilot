import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'

/**
 * 子组件目录 → 父组件目录映射。
 * element-plus 的部分子组件（如 ElMenuItem/ElOption/ElTabPane）没有独立的
 * es/components/<dir>/index.mjs 入口，组件本体从父组件包导出。
 */
const EP_CHILD_TO_PARENT = {
  'anchor-link': 'anchor', 'aside': 'container', 'avatar-group': 'avatar',
  'breadcrumb-item': 'breadcrumb', 'button-group': 'button', 'carousel-item': 'carousel',
  'checkbox-button': 'checkbox', 'checkbox-group': 'checkbox', 'collapse-item': 'collapse',
  'descriptions-item': 'descriptions', 'dropdown-item': 'dropdown', 'dropdown-menu': 'dropdown',
  'footer': 'container', 'form-item': 'form', 'header': 'container', 'main': 'container',
  'menu-item': 'menu', 'menu-item-group': 'menu', 'option': 'select', 'option-group': 'select',
  'radio-button': 'radio', 'radio-group': 'radio', 'skeleton-item': 'skeleton',
  'splitter-panel': 'splitter', 'step': 'steps', 'sub-menu': 'menu', 'tab-pane': 'tabs',
  'table-column': 'table', 'timeline-item': 'timeline', 'tour-step': 'tour',
}

/**
 * 包装 ElementPlusResolver：把 `from: 'element-plus/es'`（根入口 index.mjs，
 * re-export 全量组件且 rollup 无法有效 tree-shake —— 曾致 945KB vendor chunk）
 * 重写为按组件子路径 `element-plus/es/components/<kebab-case>/index.mjs`。
 * sideEffects（组件样式）路径保持不变。
 */
function subpathElementPlusResolver() {
  const inner = ElementPlusResolver()
  const componentResolver = inner.find(r => r.type === 'component')
  const directiveResolver = inner.find(r => r.type === 'directive')
  const wrap = {
    type: 'component',
    resolve: async (name) => {
      const result = await componentResolver.resolve(name)
      if (!result) return result
      if (result.from === 'element-plus/es' && result.name && /^El[A-Z]/.test(result.name)) {
        // ElIcon -> icon；ElDatePicker -> date-picker（首字母大写前不加横线）
        // 注意：必须显式落到 /index.mjs —— element-plus package.json 的
        // exports 通配 './es/*.mjs' 才带 import 条件，无后缀目录路径解析失败。
        let kebab = result.name
          .slice(2)
          .replace(/([a-z0-9])([A-Z])/g, '$1-$2')
          .toLowerCase()
        kebab = EP_CHILD_TO_PARENT[kebab] || kebab
        return { ...result, from: `element-plus/es/components/${kebab}/index.mjs` }
      }
      return result
    },
  }
  return directiveResolver ? [wrap, directiveResolver] : [wrap]
}

export default defineConfig({
  plugins: [
    vue(),
    Components({
      resolvers: [subpathElementPlusResolver()],
      dts: 'src/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // 函数形式：按实际解析到的模块路径分组。
        // 对象形式 manualChunks: {'vendor-element-plus': ['element-plus']} 会把包
        // 根入口整体打入；函数形式只命中真正被引用的子模块。
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('element-plus')) return 'vendor-element-plus'
            if (id.includes('markdown-it') || id.includes('highlight.js')) return 'vendor-markdown'
            if (id.includes('axios')) return 'vendor-http'
            if (id.includes('gsap')) return 'vendor-gsap'
            if (id.includes('/vue/') || id.includes('vue-router') || id.includes('pinia') || id.includes('@vue/')) return 'vendor-vue'
          }
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
