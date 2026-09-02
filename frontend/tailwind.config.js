/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      borderRadius: {
        'xs': '6px',
        'sm': '10px',
        'md': '14px',
        'lg': '18px',
        'xl': '24px',
        '2xl': '32px',
        '3xl': '40px',
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
