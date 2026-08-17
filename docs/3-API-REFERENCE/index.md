# API Reference

All endpoints are prefixed with `/api`. Authentication uses JWT Bearer tokens unless noted.

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
  "email": "user@example.com"
}
```

---

### Login
```
POST /api/auth/login
```
Authenticate and receive JWT tokens.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
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

### Get Current User
```
GET /api/auth/me
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "username": "string",
  "email": "user@example.com"
}
```

---

### Refresh Token
```
POST /api/auth/refresh
Authorization: Bearer <refresh_token>
```

**Response:** `200 OK` — New access token pair.

---

## Documents

### Upload Document
```
POST /api/documents/upload
Content-Type: multipart/form-data
Authorization: Bearer <access_token>
```

**Form Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `file` | File | PDF, DOCX, or PPTX (max 50MB) |

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "filename": "lecture-notes.pdf",
  "status": "processing",
  "created_at": "2025-01-01T00:00:00Z"
}
```

---

### List Documents
```
GET /api/documents
Authorization: Bearer <access_token>
```

**Response:** `200 OK` — Array of document objects.

---

### Get Document
```
GET /api/documents/{document_id}
Authorization: Bearer <access_token>
```

**Response:** `200 OK` — Document detail with metadata.

---

### Delete Document
```
DELETE /api/documents/{document_id}
Authorization: Bearer <access_token>
```
Cascading delete: removes file, vector index, and related quiz/chat data.

**Response:** `204 No Content`

---

## Chat (RAG Q&A)

### Ask Question
```
POST /api/chat/ask
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "document_id": "uuid",
  "question": "What is the main topic of chapter 3?",
  "conversation_id": "uuid-or-null"
}
```

**Response:** `200 OK`
```json
{
  "answer": "Based on the document...",
  "citations": [
    {
      "index": 1,
      "text": "source excerpt...",
      "page": 5
    }
  ],
  "conversation_id": "uuid"
}
```

---

### Ask Question (Streaming)
```
POST /api/chat/ask/stream
Authorization: Bearer <access_token>
```

Same request body as `/ask`. Returns `text/event-stream` (SSE):

```
data: {"type": "token", "content": "Based"}
data: {"type": "token", "content": " on"}
data: {"type": "citation", "index": 1, "text": "..."}
data: {"type": "done"}
```

---

### Chat History
```
GET /api/chat/history
Authorization: Bearer <access_token>
```

**Response:** `200 OK` — Array of conversation summaries.

---

### Chat Detail
```
GET /api/chat/history/{conversation_id}
Authorization: Bearer <access_token>
```

**Response:** `200 OK` — Full conversation with messages and citations.

---

## Quiz

### Generate Quiz
```
POST /api/quiz/generate
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "document_id": "uuid",
  "question_count": 10,
  "question_types": ["multiple_choice", "short_answer"]
}
```

**Response:** `201 Created`
```json
{
  "quiz_id": "uuid",
  "questions": [
    {
      "id": "uuid",
      "type": "multiple_choice",
      "question": "What is ...?",
      "options": ["A", "B", "C", "D"],
      "answer": "A",
      "explanation": "Because..."
    }
  ]
}
```

---

**Note:** The current quiz API returns questions directly on generation and does not expose a standalone `/api/quiz/{quiz_id}` detail endpoint.

### Submit Answers
```
POST /api/quiz/submit
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "quiz_id": "uuid",
  "answers": [
    {"question_id": "uuid", "answer": "A"}
  ]
}
```

**Response:** `200 OK` — Grading results with score and per-question feedback.

---

### Result History
```
GET /api/quiz/result-history
Authorization: Bearer <access_token>
```

**Response:** `200 OK` — Array of past quiz results.

---

### Wrong Questions (Error Book)
```
GET /api/quiz/wrong-questions
Authorization: Bearer <access_token>
```

**Response:** `200 OK` — Array of incorrectly answered questions.

---

## Analysis

### Wrong Answer Analysis
```
POST /api/analysis/wrong
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "document_id": "uuid"
}
```

**Response:** `200 OK` — AI-generated analysis of weak areas.

---

### Knowledge Mastery
```
GET /api/analysis/knowledge
Authorization: Bearer <access_token>
```

**Response:** `200 OK` — Knowledge mastery breakdown by topic.

---

### Learning Progress
```
GET /api/analysis/progress
Authorization: Bearer <access_token>
```

**Response:** `200 OK` — Study progress statistics and trends.

---

## Configuration

### Get LLM Config
```
GET /api/config/llm
Authorization: Bearer <access_token>
```

---

### Save LLM Config
```
POST /api/config/llm
Authorization: Bearer <access_token>
```

**Request Body:**
```json
{
  "provider": "openrouter",
  "api_key": "sk-or-...",
  "model": "openai/gpt-4o-mini",
  "base_url": "https://openrouter.ai/api/v1"
}
```

---

## Notes

### List Notes
```
GET /api/notes
Authorization: Bearer ***
```

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `tag` | string | Filter by tag name |
| `course_id` | uuid | Filter by course space |
| `search` | string | Semantic search query |

**Response:** `200 OK` — Array of note objects.

---

### Create Note
```
POST /api/notes
Authorization: Bearer ***
```

**Request Body:**
```json
{
  "title": "string",
  "content": "markdown string",
  "note_type": "manual|ai",
  "course_id": "uuid-or-null",
  "tags": ["tag1", "tag2"]
}
```

**Response:** `201 Created` — Note object with id.

---

### Get Note
```
GET /api/notes/{note_id}
Authorization: Bearer ***
```

### Update Note
```
PUT /api/notes/{note_id}
Authorization: Bearer ***
```

### Delete Note
```
DELETE /api/notes/{note_id}
Authorization: Bearer ***
```

### Search Notes
```
POST /api/notes/search
Authorization: Bearer ***
```

**Request Body:**
```json
{
  "query": "search text",
  "limit": 10
}
```

### List Tags
```
GET /api/notes/tags
Authorization: Bearer ***
```

---

## Courses

### List Course Spaces
```
GET /api/courses
Authorization: Bearer ***
```

### Create Course Space
```
POST /api/courses
Authorization: Bearer ***
```

**Request Body:**
```json
{
  "name": "string",
  "description": "string"
}
```

### Get Course Space
```
GET /api/courses/{course_id}
Authorization: Bearer ***
```

Returns course with associated documents and notes.

### Update Course Space
```
PUT /api/courses/{course_id}
Authorization: Bearer ***
```

### Delete Course Space
```
DELETE /api/courses/{course_id}
Authorization: Bearer ***
```

---

## Transform

### Transform Content
```
POST /api/transform
Authorization: Bearer ***
```

**Request Body:**
```json
{
  "source_type": "document|note|text",
  "source_id": "uuid-or-null",
  "content": "string (if source_type=text)",
  "transform_type": "summary|key_points|outline|flashcards|mindmap|qa|translate|explain",
  "target_language": "string (for translate type)"
}
```

**Response:** `200 OK` — Transformed content.

### List Transform Types
```
GET /api/transform/transformations
Authorization: Bearer ***
```

---

## TTS

### Synthesize Speech
```
POST /api/tts/synthesize
Authorization: Bearer ***
```

**Request Body:**
```json
{
  "text": "string",
  "voice": "string (optional, default: zh-CN-XiaoxiaoNeural)"
}
```

**Response:** `200 OK` — Audio stream (audio/mpeg).

### List Voices
```
GET /api/tts/voices
Authorization: Bearer ***
```

---

## Tasks

### List Tasks
```
GET /api/tasks
Authorization: Bearer ***
```

### Get Task Status
```
GET /api/tasks/{task_id}
Authorization: Bearer ***
```

**Response:**
```json
{
  "id": "uuid",
  "task_type": "string",
  "status": "pending|running|completed|failed",
  "result": {},
  "error": "string-or-null",
  "created_at": "timestamp",
  "completed_at": "timestamp-or-null"
}
```

### Cancel Task
```
DELETE /api/tasks/{task_id}
Authorization: Bearer ***
```

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
