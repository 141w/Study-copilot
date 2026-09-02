# Findings: Study Copilot Prototype

## Design Decisions
- Chose to match existing project design system exactly (colors, fonts, shadows, radius)
- Extended with additional stat cards, refined card styles, and interactive states
- Primary color: #3b82f6 (blue) matching existing Color Primary
- Brand gradient: pink → orange (#ef2cc1 → #fc4c02) matching existing gradient-brand
- Font: Inter (matching --font-primary in project)

## Prototype Structure
- `index.html`: Single-page app with 8 views
- `style.css`: Complete design system + component styles
- `script.js`: View switching, mock chat, quiz interactions

## Views Included
1. Home (Landing): Hero + trust bar + feature cards + CTA + footer
2. Login: Centered card with Inter font
3. Dashboard: 4 stat cards + recent docs + activity timeline
4. Chat: Document selector + message bubbles + thinking state + input
5. Documents: Upload zone + document cards with status
6. Quiz: Settings form + question with radio options + progress
7. Analysis: 3 tabs (history, stats, weak areas)
8. Model Config: Provider cards + configuration form

## Navigation
- Sidebar: 9 items (Dashboard, AI问答, 文档阅读, 做题练习, 学习分析, 模型配置)
- Login → click any nav item or submit form
- All transitions animated with fadeInUp
