# Backend API

> 前端联调的完整中文合同已冻结在仓库根目录的 [API接口文档.md](../../API接口文档.md)。本文件保留后端目录内的快速摘要；字段、状态、错误码和边界以根目录合同为准。

Base URL for local development: `http://localhost:8000`.

All business endpoints live under `/api` and return the same envelope:

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

Error responses also use this envelope, but keep the matching HTTP status code:

```json
{
  "code": 4220,
  "message": "请求参数校验失败",
  "data": {
    "errors": []
  }
}
```

Use `Authorization: Bearer <access_token>` for endpoints marked as authenticated. Interactive OpenAPI documentation is available at `/docs` while the backend is running.

## Shared Types

### User

```json
{
  "id": 1,
  "username": "student01",
  "nickname": "小明",
  "grade": "高三",
  "school": "一中",
  "main_subject": "数学"
}
```

### Assignment

```json
{
  "id": 1,
  "title": "函数作业",
  "subject": "数学",
  "status": "completed",
  "total_score": 100,
  "student_score": 82,
  "overall_comment": "整体掌握较好，注意导数应用。",
  "weak_points": ["导数单调性"],
  "created_at": "2026-07-21T15:00:00",
  "task": {
    "id": "task_xxx",
    "status": "completed",
    "step": "completed",
    "progress": 100,
    "error_message": null
  }
}
```

### Question

```json
{
  "id": 10,
  "question_number": "1",
  "content": "题目原文",
  "student_answer": "学生答案",
  "correct_answer": "参考答案",
  "question_type": "计算题",
  "knowledge_point": "导数单调性",
  "score": 8,
  "max_score": 10,
  "is_correct": false,
  "explanation": "错因说明",
  "confidence": 0.91,
  "needs_review": false,
  "confidence_warning": null
}
```

`needs_review` is retained as a compatibility risk flag. It does not block completion,
wrong-question archiving, or mastery updates. When it is `true`, show
`confidence_warning` and let the user judge the result.

## Kernel

### `GET /api/plugins`

Public. Lists loaded plugins and declared capabilities.

Response data: `Plugin[]`.

### `GET /api/example/ping`

Public. Verifies that the reference plugin was loaded.

Response data:

```json
{ "plugin": "example", "status": "ok" }
```

### `GET /api/audit-logs/me`

Authenticated. Lists the current user's audit events, newest first.

Query:

- `event_type`: optional exact event type filter, for example `auth.login`.
- `limit`: optional, `1` to `100`, default `50`.

Response data:

```json
[
  {
    "id": 1,
    "event_type": "auth.login",
    "outcome": "success",
    "actor_user_id": 1,
    "actor_username": "student01",
    "resource_type": "user",
    "resource_id": "1",
    "summary": "User logged in",
    "metadata": {},
    "error_message": null,
    "created_at": "2026-07-21T15:00:00"
  }
]
```

Audit notes:

- The backend records security and learning workflow events in the kernel audit table.
- Audit metadata is redacted by key name for passwords, tokens, secrets, and authorization headers.
- Frontend pages should treat audit summaries and metadata as text, not HTML.

## Auth

### `POST /api/auth/register`

Public. Registers a student account and returns a token.

Request:

```json
{
  "username": "student01",
  "password": "password123",
  "nickname": "小明",
  "grade": "高三",
  "main_subject": "数学"
}
```

Response data:

```json
{
  "user": {},
  "access_token": "jwt-token",
  "token_type": "bearer"
}
```

### `POST /api/auth/login`

Public.

Request:

```json
{ "username": "student01", "password": "password123" }
```

Response data: same as register.

### `GET /api/auth/me`

Authenticated. Returns current user profile.

### `PUT /api/auth/me`

Authenticated. Updates profile.

Request:

```json
{
  "nickname": "小明",
  "grade": "高三",
  "school": "一中",
  "main_subject": "数学"
}
```

### `PUT /api/auth/password`

Authenticated. Updates password.

Request:

```json
{ "current_password": "password123", "new_password": "newpassword123" }
```

### `POST /api/auth/logout`

Authenticated. Stateless logout acknowledgement.

## Scene 1: Upload And Grading

### `POST /api/assignments`

Authenticated. Uploads a homework image or PDF and starts background grading.

Content type: `multipart/form-data`.

Form fields:

- `file`: required, `.jpg`, `.jpeg`, `.png`, or `.pdf`.
- `subject`: required, for example `数学`.
- `title`: optional.

Response data:

```json
{
  "assignment_id": 1,
  "task": {
    "id": "task_abc",
    "status": "queued",
    "step": "queued",
    "progress": 0,
    "error_message": null
  }
}
```

Frontend flow: upload first, then poll `GET /api/tasks/{task_id}` until `status` is `completed` or `failed`, then call `GET /api/assignments/{assignment_id}`.

### `GET /api/tasks/{task_id}`

Authenticated. Gets grading progress.

Response data:

```json
{
  "id": "task_abc",
  "status": "processing",
  "step": "识别并批改作业",
  "progress": 45,
  "error_message": null
}
```

### `GET /api/assignments`

Authenticated. Lists current user's assignments, newest first.

Response data: `Assignment[]`.

### `GET /api/assignments/{assignment_id}`

Authenticated. Gets assignment detail including recognized and graded questions.

Response data: `Assignment & { questions: Question[] }`.

### `PUT /api/questions/{question_id}`

Authenticated. Corrects OCR/answer data and regrades one question.

Request:

```json
{
  "content": "修正后的题目",
  "student_answer": "修正后的学生答案",
  "correct_answer": "修正后的参考答案",
  "knowledge_point": "导数单调性"
}
```

Response data: `Question`.

## Scene 2: Weak Point Practice

### `GET /api/dashboard`

Authenticated. Returns summary for the student homepage.

Response data:

```json
{
  "assignment_count": 3,
  "wrong_count": 8,
  "weak_points": [
    { "subject": "数学", "knowledge_point": "导数单调性", "mastery_score": 40 }
  ]
}
```

### `GET /api/mastery`

Authenticated. Lists knowledge-point mastery records sorted from weakest to strongest.

Response data:

```json
[
  {
    "id": 1,
    "subject": "数学",
    "knowledge_point": "导数单调性",
    "mastery_score": 40,
    "correct_count": 2,
    "wrong_count": 3
  }
]
```

### `GET /api/wrong-questions`

Authenticated. Lists archived wrong questions.

Query:

- `subject`: optional.

Response data:

```json
[
  {
    "id": 1,
    "subject": "数学",
    "knowledge_point": "导数单调性",
    "wrong_reason": "忽略定义域",
    "wrong_count": 1,
    "status": "unreviewed",
    "question": {}
  }
]
```

### `POST /api/practices`

Authenticated. Generates a layered practice task for one weak knowledge point.

Request:

```json
{
  "subject": "数学",
  "knowledge_point": "导数单调性",
  "difficulty": "基础补漏",
  "question_count": 5
}
```

Allowed `difficulty`: `基础补漏`, `同类变式`, `综合提升`, `高考真题`.

Response data:

```json
{
  "id": 1,
  "subject": "数学",
  "knowledge_point": "导数单调性",
  "difficulty": "基础补漏",
  "question_count": 5,
  "status": "ready",
  "student_score": null,
  "questions": [
    {
      "id": 1,
      "question_number": 1,
      "content": "题目",
      "standard_answer": "标准答案",
      "explanation": "解析",
      "confidence": 0.97,
      "confidence_warning": null,
      "answers": []
    }
  ]
}
```

### `GET /api/practices/{practice_id}`

Authenticated. Gets practice questions and previous submitted answers if any.

Response data: same as create practice.

### `POST /api/practices/{practice_id}/submit`

Authenticated. Submits all answers and updates mastery.

Request:

```json
{
  "answers": [
    { "question_id": 1, "answer": "我的答案" }
  ]
}
```

Response data: same as get practice, with `status: "completed"`, `student_score`, and per-question `answers`.
Each answer contains `answer`, `is_correct`, `score`, `explanation`, `confidence`, and
`confidence_warning`. A low-confidence warning is informational and never creates a
manual-review workflow.

## Error Notes

- HTTP `401`: missing or invalid token.
- HTTP `403`: current user does not own the resource.
- HTTP `404`: resource does not exist.
- HTTP `409`: duplicate username or repeated practice submission.
- HTTP `422`: request validation failed.
- HTTP `500`: unexpected backend error.
- Frontend code should read user-facing error text from `response.data.message`, not from FastAPI's default `detail` field.
