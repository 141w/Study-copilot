/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      // P2-1（design-taste-frontend §4.4 Shape Lock）：圆角对齐 CSS 变量令牌。
      // 等比体系（批次4）：控件 10px（sm/md）/ 嵌套面 14px（lg）/
      // 容器 20px（xl）/ 大容器 24px（2xl）——与 variables.css 单一来源。
      // 模板里既有 rounded-lg/xl/2xl 类自动跟随令牌，不再出现 12/16/18px 旁路值。
      borderRadius: {
        'xs': 'var(--radius-xs)',      // 6px  小徽标
        'sm': 'var(--radius-sm)',     // 10px 控件（按钮/输入框）
        'md': 'var(--radius-md)',     // 10px 控件（与 sm 同级，兼容旧写法）
        'lg': 'var(--radius-lg)',     // 14px 嵌套面（列表行内块/小图标底/气泡）
        'xl': 'var(--radius-xl)',     // 20px 容器（卡片/弹窗/大图标底）
        '2xl': 'var(--radius-2xl)',   // 24px 大容器（上传拖拽区）
        '3xl': '32px',                // 遗留值（全站未用，保留防破坏）
      },
      // P2-6：CSS 变量设计系统映射进 Tailwind colors。
      // 好处：bg-primary / text-secondary 等语义类随主题切换自动生效，
      // 替代散布 600+ 处的 bg-[var(--*)] 任意值语法（换主题色/重构时
      // 可全局替换）。现有任意值写法不受影响，二者可渐进共存。
      colors: {
        primary: {
          DEFAULT: 'var(--color-primary)',
          hover: 'var(--color-primary-hover)',
          light: 'var(--color-primary-light)',
        },
        secondary: 'var(--color-secondary)',
        accent: {
          DEFAULT: 'var(--color-accent)',
          light: 'var(--color-accent-light)',
        },
        success: {
          DEFAULT: 'var(--color-success)',
          light: 'var(--color-success-light)',
        },
        warning: {
          DEFAULT: 'var(--color-warning)',
          light: 'var(--color-warning-light)',
        },
        error: {
          DEFAULT: 'var(--color-error)',
          light: 'var(--color-error-light)',
        },
        info: {
          DEFAULT: 'var(--color-info)',
          light: 'var(--color-info-light)',
        },
        surface: {
          card: 'var(--surface-card)',
          overlay: 'var(--surface-overlay)',
          glass: 'var(--surface-glass)',
        },
        bg: {
          primary: 'var(--bg-primary)',
          secondary: 'var(--bg-secondary)',
          tertiary: 'var(--bg-tertiary)',
          hover: 'var(--bg-hover)',
          active: 'var(--bg-active)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
          inverse: 'var(--text-inverse)',
        },
        border: {
          DEFAULT: 'var(--border-default)',
          hover: 'var(--border-hover)',
          focus: 'var(--border-focus)',
        },
      },
    },
  },
}
