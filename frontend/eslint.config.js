import pluginVue from 'eslint-plugin-vue'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'
import prettierConfig from '@vue/eslint-config-prettier/skip-formatting'
import globals from 'globals'

/**
 * ESLint flat config（工程化收官阶段 A）
 *
 * 分层策略：
 *  - base：所有 src 代码（TS/JS 共存的渐进式迁移现状）
 *  - 严格度取「可用且不喧宾夺主」：error 只留真正伤维护性的
 *    （未用变量/死代码），风格类交给 Prettier
 *  - tests 放宽（mock 结构动态）
 */
export default defineConfigWithVueTs(
  {
    ignores: [
      'dist/**',
      'node_modules/**',
      'src/components.d.ts', // unplugin 自动生成
      'coverage/**',
    ],
  },

  // ── 基础：src 源码 ──────────────────────────────────────────
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  prettierConfig,

  {
    files: ['src/**/*.{ts,js,vue}'],
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      // ── 收紧：真正伤维护性的 ──
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrors: 'none',
        },
      ],
      '@typescript-eslint/no-explicit-any': 'warn',
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      'no-debugger': 'error',

      // ── 放宽：渐进迁移期不强制、风格类交 Prettier ──
      'vue/multi-word-component-names': 'off', // 视图单词命名（ChatView 等）可接受
      'vue/no-v-html': 'off', // Chat 渲染 markdown（md.html:false 内部生成），经评估保留
      'vue/require-default-prop': 'off', // TS 类型式声明自带可选语义
      'vue/html-self-closing': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-indent': 'off',
      'vue/html-closing-bracket-newline': 'off',
      'vue/first-attribute-linebreak': 'off',
      'vue/attributes-order': 'off',
    },
  },

  // ── tests：放宽 mock 场景 ────────────────────────────────────
  {
    files: ['tests/**/*.{js,ts}'],
    languageOptions: {
      globals: {
        ...globals.browser,
      },
    },
    rules: {
      'no-console': 'off',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
    },
  },

  // ── 配置文件自身 ────────────────────────────────────────────
  {
    files: ['*.config.js', 'vitest.config.js', 'tailwind.config.js', 'postcss.config.js', 'vite.config.js'],
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
  },
)
