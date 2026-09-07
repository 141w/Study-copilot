# API Reference

All endpoints are prefixed with `/api`. Authentication uses JWT Bearer tokens unless noted.
Unauthenticated endpoints: `/`, `/health`, `/api/metrics`, `/api/classroom/webhook`.

---

## Table of Contents

- [Authentication](#authentication)
- [Documents](#documents)
- [Chat (RAG Q&A)](#chat-rag-qa)
- [Quiz](#quiz)
- [Analysis](#analysis)
- [Configuration](#configuration)
- [Notes](#notes)
- [Courses](#courses)
- [Transform](#transform)
- [TTS](#tts)
- [Tasks](#tasks)
- [Metrics](#metrics)
- [AI Classroom Integration](#ai-classroom-integration)
- [Error Responses](#error-responses)

---

## Authentication

### Register
```
POST /api/auth/register
```
Create a new user account.

**Request Body:**
```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "string"
}
```
**Response:** `201 Created`
```json
{
  "id": "uuid",
  "username": "string",
  "email": "user@example.com",
  "created_at": "2025-01-01T00:00:00"
}
```

---

### Login
```
POST /api/auth/login
```
Authenticate and receive JWT tokens. Uses `application/x-www-form-urlencoded` per OAuth2 password flow.

**Request Body:**
```
username=string&password=string
```
**Response:** `200 OK`
```json
{
  "access_token": "jwt.token.here",
  "refresh_token": "refresh.token.here",
  "token_type": "bearer"
}
```

---

### Refresh Token
```
POST /api/auth/refresh
```
Refresh the access token using a valid refresh token.

**Headers:** `Authorization: Bearer <refresh_token>`
**Response:** `200 OK` — New access + refresh token pair.

---

### Get Current User
```
GET /api/auth/me
```
**Headers:** `Authorization: Bearer <access_token>`
**Response:** `200 OK`
```json
{
  "id": "uuid",
  "username": "string",
  "email": "user@example.com",
  "created_at": "2025-01-01T00:00:00"
}
```

---

### Update Profile
```
PUT /api/auth/me
```
Update current user profile. Unprovided fields remain unchanged.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "username": "new-name",
  "email": "new@example.com"
}
```
**Response:** `200 OK` — Updated user object.

---

### Change Password
```
PUT /api/auth/password
```
Change password after verifying the old one.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "old_password": "current-pw",
  "new_password": "new-pw"
}
```
**Response:** `200 OK` — `{"detail": "密码已更新"}`

---

## Documents

### Upload Document
```
POST /api/documents/upload
Content-Type: multipart/form-data
```
**Headers:** `Authorization: Bearer ***`
**Body:** `file` field — PDF, DOCX, or PPTX (max 50MB). Rate limited to 10 req/min per IP.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "filename": "lecture-notes.pdf",
  "status": "processing",
  "message": "文档已开始后台处理，请稍候查看",
  "chunk_count": 0
}
```
**Note:** Processing is asynchronous. Track progress via `GET /api/tasks/{task_id}`.

---

### Import from URL
```
POST /api/documents/from-url
```
Import a web page's text content as a new document.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "url": "https://example.com/article"
}
```
**Response:** `200 OK` — Same shape as upload response, with a `task_id` for processing.

---

### List Documents
```
GET /api/documents?limit=50&offset=0
```
**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `limit` | int | 分页大小（1-200）；缺省返回全部 |
| `offset` | int | 分页偏移，默认 0 |

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Array of document objects.

---

### Get Document
```
GET /api/documents/{document_id}
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Document detail with metadata.

---

### Delete Document
```
DELETE /api/documents/{document_id}
```
Soft-delete. Removes from listing; file and vector index are cleaned up.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — `{"message": "删除成功"}`

---

### Restore Document
```
POST /api/documents/{document_id}/restore
```
Restore a soft-deleted document back to active.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — `{"message": "恢复成功"}`

---

## Chat (RAG Q&A)

All chat endpoints are rate limited to 30 req/min per IP.

### Ask Question
```
POST /api/chat/ask
```
**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "question": "What is the main topic of chapter 3?",
  "document_ids": ["uuid-1", "uuid-2"],
  "session_id": "uuid-or-null",
  "config": { "temperature": 0.7 }
}
```
**Response:** `200 OK`
```json
{
  "answer": "Based on the document...",
  "sources": [
    {
      "index": 1,
      "document_id": "uuid",
      "text": "source excerpt...",
      "page": "5",
      "source": "...",
      "relevance_score": 0.92
    }
  ],
  "used_source_indices": [1, 3],
  "filtered_sources": [],
  "session_id": "uuid"
}
```

**Note:** Set `"stream": true` in the request body to receive SSE events:
```
data: {"type": "token", "content": "Based"}
data: {"type": "token", "content": " on"}
data: {"type": "citation", "index": 1, "text": "..."}
data: {"type": "answer_refined", "content": "..."}
data: {"type": "done"}
```

---

### Chat History — List Sessions
```
GET /api/chat/history
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Array of conversation summaries.

---

### Chat History — Session Detail
```
GET /api/chat/history/{session_id}
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Full conversation with messages and citations.

---

### Update Session Title
```
PUT /api/chat/history/{session_id}
```
**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "title": "New title"
}
```
**Response:** `200 OK` — `{"message": "更新成功", "title": "New title"}`

---

### Delete Session
```
DELETE /api/chat/history/{session_id}
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — `{"message": "删除成功"}`

---

### Semantic Search Messages
```
POST /api/chat/search
```
Search across chat messages using vector similarity.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "query": "Python memory management",
  "session_id": "uuid-or-null",
  "top_k": 10
}
```
**Response:** `200 OK` — Ranked list of matching messages with similarity scores.
```json
[
  {
    "message_id": "uuid",
    "session_id": "uuid",
    "role": "user",
    "content": "Python garbage collection and memory management",
    "similarity": 0.82,
    "created_at": "2026-09-03T13:59:04"
  }
]
```
`session_id` is optional — omit for cross-session search, provide to limit to a single conversation.

---

### Get Persona List & Presets
```
GET /api/chat/personas
```
Get available persona presets and user custom personas (persisted in database).

**Headers:** `Authorization: Bearer ***` (optional; if authenticated, returns custom personas as well)  
**Response:** `200 OK`
```json
{
  "personas": [
    {
      "id": "teacher",
      "name": "苏老师",
      "role": "teacher",
      "avatar": "User",
      "color": "#3b82f6",
      "system_message": "...",
      "is_custom": false
    },
    {
      "id": "custom-uuid-1",
      "name": "苏格拉底",
      "role": "custom_socrates",
      "avatar": "Brain",
      "color": "#8b5cf6",
      "system_message": "...",
      "is_custom": true,
      "created_at": "2026-09-06T05:00:00"
    }
  ],
  "presets": [...],
  "custom": [...]
}
```

---

### Create Custom Persona
```
POST /api/chat/personas
```
Create a new user-defined persona for multi-agent discussions, persisted in the database.

**Headers:** `Authorization: Bearer ***`  
**Request Body:**
```json
{
  "name": "苏格拉底",
  "avatar": "Brain",
  "color": "#8b5cf6",
  "system_message": "你是一位古希腊哲学家，善于用反问法引导学生思考并发现认知漏洞。",
  "role": "custom_socrates"
}
```
**Response:** `200 OK` (returns created persona object with `is_custom: true`)

---

### Update Custom Persona
```
PUT /api/chat/personas/{persona_id}
```
Update an existing user-defined persona. Ownership is strictly validated.

**Headers:** `Authorization: Bearer ***`  
**Request Body:**
```json
{
  "name": "辩证法苏格拉底",
  "avatar": "Lightning",
  "color": "#8b5cf6",
  "system_message": "更新后的人设描述..."
}
```
**Response:** `200 OK`

---

### Delete Custom Persona
```
DELETE /api/chat/personas/{persona_id}
```
Delete a custom persona belonging to the current user.

**Headers:** `Authorization: Bearer ***`  
**Response:** `200 OK`
```json
{
  "message": "角色已删除",
  "id": "custom-uuid-1"
}
```

---

### Multi-Persona Discussion
```
POST /api/chat/discuss
```
Stream a multi-persona sequential discussion on a topic, optionally enriched with document context via RAG snippets or fair-budget full document bundle.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "question": "请讨论 Transformer 架构中自注意力机制的计算复杂度与优化方案",
  "document_ids": ["uuid-1"],
  "context_mode": "rag_snippets",
  "personas": [
    "teacher",
    "thinker",
    {
      "name": "算法工程师",
      "role": "工程实践专家",
      "avatar": "💻",
      "system_message": "你是一名资深工程专家，重点关注 FlashAttention 等显存与推理优化工程落地..."
    }
  ],
  "max_turns": 2
}
```

**Parameters:**
- `question` *(string, required)*: The discussion topic.
- `document_ids` *(list[string], optional)*: Associated documents for background context.
- `context_mode` *(string, optional)*: `"rag_snippets"` (default, adaptive vector retrieval) or `"full_docs"` (proportional fair budget document packing).
- `personas` *(list[string|object], optional)*: List of preset IDs (`"teacher"`, `"thinker"`, `"curious"`, `"notetaker"`) or custom persona objects (`{"name", "role", "avatar", "system_message"}`). Defaults to `["teacher", "thinker"]`.
- `max_turns` *(integer, optional)*: Discussion round count (default `2`, max `5`).

**Response:** `text/event-stream` (SSE). Events: `persona_speak` / `summary` / `error` / `done`.

---

## Quiz

### Generate Quiz
```
POST /api/quiz/generate
```
Generate quiz questions from documents.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "document_ids": ["uuid-1", "uuid-2"],
  "choice_count": 3,
  "short_answer_count": 2,
  "config": {}
}
```
**Response:** `200 OK`
```json
{
  "quizzes": [
    {
      "id": "uuid",
      "question_type": "choice",
      "question": "What is ...?",
      "options": ["A", "B", "C", "D"],
      "answer": "A",
      "explanation": "Because..."
    }
  ]
}
```

---

### Submit Answer
```
POST /api/quiz/submit
```
Submit and grade a single quiz answer.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "quiz_id": "uuid",
  "user_answer": "A"
}
```
**Response:** `200 OK`
```json
{
  "quiz_id": "uuid",
  "user_answer": "A",
  "correct_answer": "A",
  "is_correct": true,
  "explanation": "Because..."
}
```

---

### Result History
```
GET /api/quiz/result-history
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Array of past quiz submission results.

---

### Wrong Questions (Error Book)
```
GET /api/quiz/wrong-questions
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Array of incorrectly answered questions with answers and explanations.

---

## Analysis

### Wrong Answer Analysis
```
GET /api/analysis/wrong
```
AI-generated analysis of weak areas from wrong answers.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Analysis object identifying weak topics and suggestions.

---

### Knowledge Mastery
```
GET /api/analysis/knowledge
```
Knowledge mastery breakdown by topic.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK`
```json
{
  "total_quizzes": 20,
  "correct_count": 16,
  "accuracy_rate": 0.8
}
```

---

### Learning Progress
```
GET /api/analysis/progress
```
Study progress statistics and trends.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Progress data object.

---

## Configuration

### Get LLM Config
```
GET /api/config/llm
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Config object with masked API key.

---

### Save LLM Config
```
POST /api/config/llm
```
Create or replace the user's LLM configuration.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "provider": "openrouter",
  "api_key": "sk-or-...",
  "base_url": "https://openrouter.ai/api/v1",
  "model_name": "openai/gpt-4o-mini",
  "temperature": 0.7,
  "max_tokens": 2048,
  "embedding_model": "shibing624/text2vec-base-chinese",
  "embedding_dimension": 768,
  "message_format": "openai"
}
```

---

### Update LLM Config
```
PUT /api/config/llm
```
Same schema as `POST`. Updates existing config.

**Headers:** `Authorization: Bearer ***`

---

## Notes

### List Notes
```
GET /api/notes?course_space_id=uuid&tag=tag-name&limit=50&offset=0
```
**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `course_space_id` | uuid | Filter by course space |
| `tag` | string | Filter by tag name |
| `limit` | int | 分页大小（1-200）；缺省返回全部 |
| `offset` | int | 分页偏移，默认 0 |

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Array of brief note objects.

---

### Create Note
```
POST /api/notes
```
**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "title": "My Note",
  "content": "# Markdown content",
  "note_type": "markdown",
  "course_space_id": "uuid",
  "tag_names": ["tag1", "tag2"]
}
```
**Response:** `201 Created` — Full note object with tags.

---

### Get Note
```
GET /api/notes/{note_id}
```
**Response:** `200 OK` — Full note object with tags and course association.

---

### Update Note
```
PUT /api/notes/{note_id}
```
**Headers:** `Authorization: Bearer ***`
**Request Body:** Same fields as create, all optional (partial update).

**Response:** `200 OK` — Updated note object.

---

### Delete Note
```
DELETE /api/notes/{note_id}
```
Soft-delete note.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — `{"message": "删除成功"}`

---

### Restore Note
```
POST /api/notes/{note_id}/restore
```
Restore a soft-deleted note.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Restored note object.

---

### Search Notes
```
POST /api/notes/search
```
Semantic search across the user's notes using vector similarity.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "query": "search text",
  "top_k": 10
}
```
**Response:** `200 OK` — Results are plain objects (format from note_service.search_notes).

---

### List Tags
```
GET /api/notes/tags/all
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Array of tag objects.
```json
[
  { "id": "uuid", "name": "tag1", "created_at": "2025-01-01T00:00:00" }
]
```

---

### Delete Tag
```
DELETE /api/notes/tags/{tag_id}
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — `{"message": "标签删除成功"}`

---

## Courses

### List Course Spaces
```
GET /api/courses
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Array of course space objects.

---

### Create Course Space
```
POST /api/courses
```
**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "name": "Machine Learning 101",
  "description": "Intro to ML",
  "color": "#409EFF"
}
```
**Response:** `201 Created` — Course space object.

---

### Get Course Space
```
GET /api/courses/{course_id}
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Course space object.

---

### Update Course Space
```
PUT /api/courses/{course_id}
```
**Headers:** `Authorization: Bearer ***`
**Request Body:** (all fields optional)
```json
{
  "name": "Updated Name",
  "description": "Updated description",
  "color": "#67C23A"
}
```
**Response:** `200 OK` — Updated course space object.

---

### Delete Course Space
```
DELETE /api/courses/{course_id}
```
**Response:** `200 OK` — `{"message": "删除成功"}`

---

### List Course Documents
```
GET /api/courses/{course_id}/documents
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Array of document metadata associated with the course.

---

### Add Document to Course
```
POST /api/courses/{course_id}/documents
```
**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "document_id": "uuid"
}
```
**Response:** `201 Created` — `{"message": "Document added"}`

---

### Remove Document from Course
```
DELETE /api/courses/{course_id}/documents/{doc_id}
```
Sets `course_space_id = NULL` on the document.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — `{"message": "Document removed"}`

---

### Generate Course from Documents
```
POST /api/courses/generate
```
Generate a course outline + quizzes from source documents using LLM.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "doc_ids": ["uuid-1", "uuid-2"],
  "requirement": "Focus on neural networks"
}
```
**Response:** `201 Created`
```json
{
  "course_id": "uuid",
  "title": "Generated Course Title",
  "description": "Generated description...",
  "section_count": 8,
  "quiz_count": 15
}
```

---

## Transform

### List Transformation Types
```
GET /api/transform/transformations
```
List all available content transformation types.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Array of transformation descriptors.

---

### Transform Content
```
POST /api/transform
```
Perform content transformation. Provide exactly one of `source_text`, `note_id`, or `document_id`.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "transform_type": "summary|key_points|outline|flashcards|mindmap|qa|translate|explain",
  "source_text": "string (optional)",
  "source_title": "string",
  "note_id": "uuid (optional)",
  "document_id": "uuid (optional)"
}
```
**Response:** `200 OK`
```json
{
  "transform_type": "summary",
  "transform_name": "摘要",
  "result": "...",
  "source_title": "..."
}
```

---

## TTS (Text-to-Speech)

### Synthesize Speech
```
POST /api/tts/generate
```
Generate an audio file from text.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "text": "string",
  "voice": "zh-CN-XiaoxiaoNeural",
  "speed": 1.0
}
```
**Response:** `200 OK` — `audio/mpeg` file stream.

---

### List Voices
```
GET /api/tts/voices
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Available TTS voices grouped by language.

---

## Tasks

### Create Task
```
POST /api/tasks
```
Enqueue a background task for long-running operations (document processing, quiz generation, etc.).

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```
task_type=document_process&payload={"document_id":"uuid"}
```
Or as JSON:
```json
{
  "task_type": "document_process",
  "payload": {}
}
```
**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "task_type": "document_process",
  "status": "pending",
  "progress": 0,
  "result": null,
  "error": null,
  "created_at": "2025-01-01T00:00:00",
  "completed_at": null
}
```
Common `task_type` values: `document_process`, `quiz_generate`.

---

### List Tasks
```
GET /api/tasks?status=running&limit=50&offset=0
```
**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter by status (`pending`, `running`, `completed`, `failed`, `cancelled`) |
| `limit` | int | Max results (default 50) |
| `offset` | int | Pagination offset |

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK`
```json
{
  "tasks": [...],
  "total": 5
}
```

---

### Get Task Status
```
GET /api/tasks/{task_id}
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — Full task object.

---

### Cancel Task
```
DELETE /api/tasks/{task_id}
```
Cancel a pending or running task.

**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK` — `{"message": "任务已取消", "task": {...}}`

---

## Metrics

### Operational Metrics
```
GET /api/metrics
```
Unrestricted endpoint. Prometheus-style JSON snapshot.

**Response:** `200 OK`
```json
{
  "app": {
    "name": "Study Copilot",
    "uptime_seconds": 3600.5,
    "started_at": "2025-01-01T00:00:00"
  },
  "tasks": {
    "total": 42,
    "by_status": { "pending": 2, "running": 1, "completed": 38, "failed": 1, "cancelled": 0 }
  }
}
```

---

## AI Classroom Integration

### Create Classroom
```
POST /api/classroom/generate
```
Trigger AI interactive classroom generation from selected documents.

**Headers:** `Authorization: Bearer ***`
**Request Body:**
```json
{
  "doc_ids": ["uuid-1", "uuid-2"],
  "requirement": "string (max 500 chars)",
  "enable_web_search": false,
  "enable_tts": true,
  "enable_image_generation": false,
  "agent_mode": "default"
}
```
**Response:** `200 OK`
```json
{
  "class_id": "string",
  "job_id": "string",
  "status": "queued",
  "poll_url": "http://localhost:3001/api/generate-classroom/...",
  "course_id": "uuid",
  "message": "课堂生成已排队"
}
```

---

### Get Classroom Status & Auto-Sync
```
GET /api/classroom/{job_id}/status
```
Query the generation progress and status of a classroom job. Provides **dual-channel self-healing**: if the job is completed in the classroom engine, this endpoint automatically pulls generated outlines/scenes and synchronizes the course space and quizzes into Study Copilot without relying exclusively on webhook callbacks.

**Headers:** `Authorization: Bearer ***`  
**Response:** `200 OK`
```json
{
  "job_id": "job-12345",
  "status": "completed",
  "progress": 100,
  "step": "completed",
  "message": "课堂生成完毕",
  "done": true,
  "result": {
    "classroomId": "cls-123",
    "url": "http://localhost:3001/classroom/cls-123",
    "title": "课堂标题"
  }
}
```

---

### List Classrooms
```
GET /api/classroom/list
```
**Headers:** `Authorization: Bearer ***`
**Response:** `200 OK`
```json
{
  "classrooms": [
    {
      "course_id": "uuid",
      "title": "Classroom Name",
      "url": "http://localhost:3001/classroom/...",
      "created_at": "2025-01-01T00:00:00"
    }
  ],
  "total": 1
}
```

---

### Webhook (no auth)
```
POST /api/classroom/webhook
```
Classroom callback endpoint. Validates HMAC signature (`X-Classroom-Signature` header). No JWT required.

**Request Body:** JSON payload sent by the classroom engine.

---

## Error Responses

All error responses follow this format:
```json
{
  "detail": "Error description"
}
```

| Status | Meaning |
|--------|---------|
| 400 | Bad Request — Invalid input |
| 401 | Unauthorized — Missing or invalid token |
| 403 | Forbidden — Not allowed |
| 404 | Not Found — Resource doesn't exist |
| 413 | Payload Too Large — File exceeds 50MB |
| 422 | Validation Error — Request body validation failed |
| 429 | Too Many Requests — Rate limit exceeded |
| 500 | Internal Server Error |

## Interactive Docs

When the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
