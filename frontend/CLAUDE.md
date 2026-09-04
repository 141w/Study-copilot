# Frontend CLAUDE.md

Guidance for working on the Study Copilot frontend.

## Structure

```
frontend/
├── src/
│   ├── views/                 # Page-level components (one per route)
│   │   ├── HomeView.vue       # Landing page
│   │   ├── LoginView.vue      # Login form (TypeScript)
│   │   ├── RegisterView.vue   # Registration form
│   │   ├── UploadView.vue     # Document upload with drag-and-drop
│   │   ├── DocumentView.vue   # Document list & management
│   │   ├── ChatView.vue       # RAG Q&A with citations + streaming
│   │   ├── QuizView.vue       # Quiz taking (exam & practice modes)
│   │   ├── AnalysisView.vue   # Learning analytics dashboard
│   │   ├── ModelConfigView.vue # LLM provider configuration
│   │   ├── CourseListView.vue # Course space list
│   │   ├── CourseDetailView.vue # Course detail with docs & notes
│   │   ├── NotesView.vue      # Note management (manual + AI)
│   │   ├── TasksView.vue      # Async task management
│   │   ├── ProfileView.vue    # User profile & password settings
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatHistoryPanel.vue  # Conversation history sidebar
│   │   │   ├── ChatInput.vue         # Message input with document selector
│   │   ├── common/
│   │   │   ├── AppHeader.vue         # Top navigation bar (el-dropdown + theme toggle)
│   │   │   ├── AppSidebar.vue        # Side navigation (el-menu with router)
│   │   │   ├── ConfirmDialog.vue     # Reusable confirmation dialog
│   │   │   ├── DocumentPicker.vue    # Document selection dropdown
│   │   │   ├── EmptyState.vue        # Empty/placeholder state display
│   │   │   ├── PageHeader.vue        # Page-level header with breadcrumb
│   │   │   ├── SkeletonList.vue      # Skeleton loading for list views
│   │   ├── integrations/
│   │   │   ├── ClassroomBridgeDialog.vue  # Classroom platform integration
│   │   │   ├── OpenMAICLinkCard.vue        # OpenMAIC content link card
│   │   ├── CopilotBotAvatar.vue     # Bot persona/avatar engine
│   │   ├── CourseCard.vue           # Course space preview card (TypeScript)
│   │   ├── NoteCard.vue             # Note preview card (TypeScript)
│   │   ├── NoteEditor.vue           # Markdown editor with AI assist
│   │   ├── TaskPanel.vue            # Task status display with progress
│   │   ├── TransformDialog.vue      # Content transformation dialog
│   │   ├── TTSPlayer.vue            # Audio playback controls
│   │   ├── UrlImportDialog.vue      # URL import dialog
│   ├── stores/               # Pinia stores (TypeScript)
│   │   ├── auth.ts           # Login state, tokens, user info
│   │   ├── chat.ts           # Messages, streaming, conversations
│   │   ├── config.ts         # LLM configuration
│   │   ├── course.ts         # Course spaces, document associations
│   │   ├── document.ts       # Document list, upload state
│   │   ├── note.ts           # Notes list, tags, search, filters
│   │   ├── openmaic.ts       # OpenMAIC integration state
│   │   ├── quiz.ts           # Quiz state, answers, results
│   │   ├── sidebar.ts        # Sidebar navigation state
│   │   ├── theme.ts          # Light/dark theme state
│   │   ├── toast.ts          # Toast notification queue
│   ├── services/
│   │   ├── api.ts            # Axios instance with JWT interceptors
│   │   ├── authRefresh.ts    # Token auto-refresh interceptor
│   ├── composables/          # Reusable composition functions
│   │   ├── useApi.ts         # Unified API request handling
│   │   ├── useChatExport.ts  # Chat export Markdown builder
│   │   ├── useFormat.ts      # Date/number formatting utilities
│   │   ├── useMarkdown.ts    # Markdown rendering utilities
│   │   ├── useNoteDraft.ts   # Note draft auto-save
│   │   ├── useReducedMotion.ts # Respect prefers-reduced-motion
│   ├── types/                # TypeScript type definitions
│   │   ├── api.ts            # API response types
│   │   ├── markdown-it.d.ts  # Type declarations for markdown-it
│   │   └── models.ts         # Core data models (User, Document, Note, etc.)
│   ├── router/
│   │   └── index.ts          # Vue Router config with auth guards
│   ├── styles/
│   │   ├── variables.css     # Design system tokens (CSS variables)
│   │   ├── element-plus-theme.css # Element Plus theme overrides
│   │   └── global.css        # Global styles + reset
│   ├── env.d.ts              # TypeScript environment declarations
│   ├── App.vue               # Root component (layout shell)
│   └── main.ts               # App bootstrap
├── tests/                    # Vitest test suite
│   ├── setup.js
│   ├── components/
│   │   └── UploadView.test.js
│   ├── stores/
│   │   ├── auth.test.js
│   │   ├── chat.test.js
│   │   ├── quiz.test.js
├── tsconfig.json             # TypeScript configuration
├── tsconfig.node.json        # Node TypeScript config
├── vitest.config.js          # Test configuration
├── tailwind.config.js        # TailwindCSS utility layer config
├── postcss.config.js         # PostCSS (tailwindcss + autoprefixer)
├── eslint.config.js          # ESLint flat config
├── .prettierrc.json          # Prettier config
├── vite.config.js            # Vite dev/build config
├── package.json
```

## Key Patterns

### Vue 3 Composition API with TypeScript
All components use `<script setup lang="ts">` syntax:
```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const loading = ref(false)
</script>
```

### State Management (Pinia with TypeScript)
Each feature has its own store. Stores handle API calls and state:
```typescript
// stores/chat.ts
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatMessage } from '../types/models'

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const streaming = ref(false)

  async function sendMessage(documentId: string, question: string): Promise<void> {
    streaming.value = true
    // SSE streaming logic
  }

  return { messages, streaming, sendMessage }
})
```

Stores index (11 total): auth, chat, config, course, document, note, openmaic, quiz, sidebar, theme, toast.

### API Client
`services/api.ts` exports an Axios instance with:
- Base URL `/api` (proxied via Vite)
- JWT token injection via request interceptor
- Auto-refresh on 401 (`services/authRefresh.ts` — refresh token flow)
- Toast notifications on error
- Request retry for auth failures

### Composables
Reusable composition functions in `src/composables/` (6 total):
- `useApi.ts` — Unified API request handling with error management
- `useMarkdown.ts` — Markdown rendering utilities (markdown-it wrapper)
- `useChatExport.ts` — Chat export Markdown builder (buildChatMarkdown, formatDate)
- `useFormat.ts` — Date/number formatting utilities
- `useNoteDraft.ts` — Note draft auto-save (localStorage)
- `useReducedMotion.ts` — Respects user prefers-reduced-motion setting

### Type Definitions
Core types and declarations in `src/types/`:
- `api.ts` — API response types (ApiResponse, ApiError, PaginatedResponse)
- `models.ts` — Data models (User, Document, ChatMessage, Note, Course, Quiz, Task, etc.)
- `markdown-it.d.ts` — Type declarations for markdown-it plugin extensions

### Streaming (SSE)
Chat uses native `fetch` with `ReadableStream` for real-time token delivery from `/api/chat/ask` (stream: true). Supports:
- `sources` event — initial source documents
- `token` event — streaming tokens
- `answer` event — complete answer (for fast paths)
- `thinking` event — Agentic RAG thinking steps
- `answer_refined` event — reflection-based refinement
- `done` event — stream complete

User can cancel streaming via `AbortController`.

### Bot Persona Engine (CopilotBotAvatar)
The `CopilotBotAvatar` component renders bot avatars across the app, driven by an engine that resolves persona identity (name/avatar/biography) — accepted as the bot-id "copilot" and backed by a runtime template system.

### Routing
Vue Router with lazy-loaded routes and navigation guards (15 routes):
- Public: `/`, `/login`, `/register`
- Auth-protected: `/upload`, `/chat`, `/quiz`, `/analysis`, `/model-config`, `/documents`, `/courses`, `/courses/:id`, `/notes`, `/tasks`, `/profile`
- Navigation guard redirects unauthenticated users to `/login`

### Styling
- **Layout layer**: TailwindCSS utilities (grid, flex, spacing, typography)
- **Components**: Element Plus 2.14 (`el-button`, `el-card`, `el-input`, etc.) — auto-imported via unplugin-vue-components
- **Theme**: CSS variables design system (`styles/variables.css` + `styles/element-plus-theme.css`) — Light/Dark mode toggle
- **Animations**: GSAP 3.15 (page enter, scroll reveal, message slide-in)
- **Responsive**: Mobile-first, sidebar collapses on small screens
- **Markdown**: markdown-it 14.1 + highlight.js 11.9 for rendered content

## Running

```bash
cd frontend
npm install
npm run dev        # Vite dev server on port 3000
npm run test       # Run tests
npm run test:watch # Watch mode
npm run typecheck  # vue-tsc --noEmit
npm run lint       # ESLint
npm run format     # Prettier auto-format
```

## Build

```bash
npm run build      # Output to dist/
npm run preview    # Preview production build
```

## Tech Stack

| Category | Technology |
|----------|-----------|
| Framework | Vue 3.4 (Composition API with `<script setup lang="ts">`) |
| Language | TypeScript (渐进式迁移，JS/TS 共存) |
| Build Tool | Vite 5.2 |
| State | Pinia 2.1 |
| Routing | Vue Router 4.3 (lazy-loaded, auth guards) |
| UI Framework | Element Plus 2.14 (auto-import via unplugin-vue-components) |
| Icons | Element Plus Icons (`@element-plus/icons-vue`) |
| Styling | TailwindCSS 3.4 (layout primitives) + CSS Variables 设计系统 |
| HTTP | Axios 1.6 with JWT interceptors + auto-refresh |
| Rendering | markdown-it 14.1 + highlight.js 11.9 |
| Animations | GSAP 3.15 |
| Testing | Vitest 4.1 + Vue Test Utils 2.4 + Testing Library |
| Type Check | vue-tsc |
| Lint | ESLint 10.x + eslint-plugin-vue 10.x |
| Format | Prettier |

## Dependencies

```json
{
  "dependencies": {
    "vue": "^3.4.21",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.7",
    "axios": "^1.6.8",
    "element-plus": "^2.14.5",
    "@element-plus/icons-vue": "^2.3.2",
    "gsap": "^3.15.0",
    "highlight.js": "^11.9.0",
    "markdown-it": "^14.1.0"
  },
  "devDependencies": {
    "vite": "^5.2.8",
    "@vitejs/plugin-vue": "^5.0.4",
    "unplugin-vue-components": "^0.26.0",
    "unplugin-auto-import": "^0.17.0",
    "vitest": "^4.1.9",
    "@vue/test-utils": "^2.4.11",
    "@testing-library/vue": "^8.1.0",
    "tailwindcss": "^3.4.3",
    "postcss": "^8.4.38",
    "jsdom": "^29.1.1",
    "eslint": "^10.9.1",
    "eslint-plugin-vue": "^10.10.0",
    "@eslint/js": "^10.0.1",
    "@typescript-eslint/eslint-plugin": "^8.69.0",
    "@typescript-eslint/parser": "^8.69.0",
    "@vue/eslint-config-typescript": "^14.9.0",
    "@vue/eslint-config-prettier": "^10.2.0",
    "globals": "^17.12.0",
    "prettier": "^3.x"
  }
}
```
