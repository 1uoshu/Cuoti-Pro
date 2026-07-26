<<<<<<< HEAD
﻿# Smart Learning Agent API 接口文档

合同版本：`v1.0`（2026-07-22；当前 URL 前缀仍为 `/api`）
状态：场景 1「作业上传与批改」和场景 2「错题本与薄弱知识点分层练习」的前端联调合同。

本文以当前后端路由、Pydantic 校验、数据库序列化器和 Agent 工作流实现为准。前端只调用本文件中的学生端后端 API，不直接调用模型或 Agent 服务。
=======
# Smart Learning Agent API 接口文档

合同版本：`v2.1`（2026-07-27；当前 URL 前缀仍为 `/api`）
状态：场景 1「日常习题/试卷上传与自动批改」的 **chat-only Agent 架构**后端实现契约。
前版：`v2.0`（2026-07-27）、`v1.0`（2026-07-22）已废弃，本文件完全替代。

本文以需求文档《场景 1 需求分析 + 技术方案 + 落地路线图》为准，同时作为后端实现的唯一接口合同。
后端按本文实现接口，前端按本文对接；任何分歧以本文件为准。

---
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

## 1. 基本约定

### 1.1 地址与格式

- 本地开发：`http://localhost:8000`
- Docker Compose：由部署端口映射决定，默认仍为 `http://localhost:8000`
- 业务 API 前缀：`/api`
<<<<<<< HEAD
=======
- WebSocket 地址：`ws://<host>/api/agent/ws?session_id=<uuid>`（JWT 鉴权）
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)
- OpenAPI：`GET /docs`（Swagger UI）、`GET /openapi.json`
- 请求和响应编码：UTF-8 JSON；文件上传使用 `multipart/form-data`
- 默认 CORS：`http://localhost:5173`（由 `CORS_ORIGINS` 配置）

<<<<<<< HEAD
所有 `/api` 业务端点（包括未匹配路由的 404 和方法不允许的 405）成功和失败均使用统一外层；`/`、`/docs`、`/openapi.json` 不使用该外层：
=======
所有 `/api` 业务端点（包括未匹配路由的 404 和方法不允许的 405）成功和失败均使用统一外层；`/`、`/docs`、`/openapi.json`、WebSocket 不使用该外层：
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

`data` 可以是对象、数组或 `null`。成功时 `code` 固定为 `0`。4xx 业务错误优先展示 `message`，并按需读取 `data`；5xx 错误只展示通用失败提示，不向用户暴露内部异常细节。

### 1.2 鉴权

注册或登录成功后，使用返回的 JWT：

```http
Authorization: Bearer <access_token>
```

<<<<<<< HEAD
JWT 当前使用 HS256，默认有效期 12 小时（`JWT_EXPIRE_HOURS`）。没有刷新令牌；过期后重新登录。`POST /api/auth/logout` 是无状态确认，不会使已经签发的 JWT 立即失效，前端应删除本地令牌。
=======
JWT 使用 HS256，默认有效期 12 小时（`JWT_EXPIRE_HOURS`）。`POST /api/auth/logout` 会立即撤销当前 access token（Redis 白名单删除）。接近过期的有效请求可能返回 `Set-Token` 响应头，前端应使用其值替换本地 access token。

WebSocket 连接通过 URL 查询参数传递 token：`ws://<host>/api/agent/ws?session_id=<uuid>&token=<jwt>`。连接时校验，连接后不再逐帧校验。
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

未标记「需鉴权」的接口可匿名调用。所有需鉴权接口都只返回当前用户拥有的资源。

### 1.3 错误外层与状态码

```json
{
  "code": 4220,
  "message": "请求参数校验失败",
  "data": {
    "errors": [
      {"loc": ["body", "question_count"], "msg": "...", "type": "..."}
    ]
  }
}
```

| HTTP | `code` | 含义 |
| ---: | ---: | --- |
| 400 | 400 | 业务参数或上传内容不合法 |
| 401 | 401 | 缺少、过期或无效 JWT |
<<<<<<< HEAD
| 403 | 403 | 资源不属于当前用户 |
| 404 | 404 | 资源不存在 |
| 405 | 405 | 请求方法不允许 |
| 409 | 409 | 用户名冲突或练习重复提交 |
=======
| 403 | 403 | 资源不属于当前用户（跨生越权） |
| 404 | 404 | 资源不存在 |
| 405 | 405 | 请求方法不允许 |
| 409 | 409 | 用户名冲突或并发写冲突 |
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)
| 422 | 4220 | Pydantic 请求校验失败，详情在 `data.errors` |
| 500 | 500 | 文件保存等已知服务端失败（对用户仍返回通用文案） |
| 500 | 5000 | 未预期的服务/Agent 错误 |
| 500 | 5001 | 数据库操作失败 |

<<<<<<< HEAD
后端会把 FastAPI `HTTPException.detail` 字符串放入 4xx `message`，不会使用默认的 `detail` 外层。5xx 响应使用通用文案；内部 Agent/模型异常不会通过学生 API 或个人审计接口原样返回，不能依赖具体文案判断业务状态。
=======
后端会把 FastAPI `HTTPException.detail` 字符串放入 4xx `message`，不会使用默认的 `detail` 外层。5xx 响应使用通用文案；内部 Agent/模型异常不会通过学生 API 原样返回。

### 1.4 并发控制

同一 `user_id` 的写操作（上传、批改结算、待复核确认、错题状态变更）通过 Redis 租约锁串行。不同学生互不阻塞。锁超时 5 秒，超时返回 409 + `"系统忙，请稍后再试"`。

### 1.5 限流（Rate Limiting）

全局限流通过 Redis 滑动窗口实现，防止恶意请求和资源滥用。

| 维度 | 限制 | 窗口 | 触发返回 |
| --- | --- | --- | --- |
| 全局每 IP | 120 次 | 1 分钟 | `429 Too Many Requests` |
| 每用户（JWT） | 60 次 | 1 分钟 | `429 Too Many Requests` |
| 文件上传 | 10 次 | 1 分钟 | `429 Too Many Requests` |
| WebSocket 连接 | 5 个并发 | — | 关闭最旧连接（code 4029） |
| 登录/注册 | 10 次 | 1 分钟 | `429 Too Many Requests`（已有 PoW 防护叠加） |

限流中间件在鉴权**之前**执行（基于 IP），鉴权后叠加用户级限流。触发限流时响应：

```json
{
  "code": 429,
  "message": "请求过于频繁，请稍后再试",
  "data": {
    "retry_after": 30
  }
}
```

---
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

## 2. 公共数据结构

### 2.1 用户 `User`

```json
{
  "id": 1,
  "username": "student01",
  "nickname": "小明",
  "grade": "高三",
  "school": "一中",
  "main_subject": "数学",
  "role": "student"
}
```

`grade`、`school`、`main_subject` 可以为 `null`。密码和密码哈希永远不会出现在响应中。

### 2.2 处理任务 `Task`

```json
{
  "id": "task_abc123",
  "status": "processing",
  "step": "识别并批改作业",
  "progress": 45,
  "error_message": null
}
```

- `status`：`queued`、`processing`、`completed`、`failed`
- `progress`：整数 `0` 到 `100`
- `step`：展示用文本，不要按固定英文枚举解析
- `error_message`：成功为 `null`；失败时是用户可见的安全提示，不包含堆栈、密钥或内部服务细节

### 2.3 作业 `Assignment`

```json
{
  "id": 1,
  "title": "函数作业",
  "subject": "数学",
  "status": "completed",
  "total_score": 100.0,
  "student_score": 82.0,
  "overall_comment": "整体掌握较好，注意导数应用。",
  "weak_points": ["导数单调性"],
  "created_at": "2026-07-21T15:00:00",
  "task": {
    "id": "task_abc123",
    "status": "completed",
    "step": "completed",
    "progress": 100,
    "error_message": null
  }
}
```

<<<<<<< HEAD
批改完成前 `total_score`、`student_score`、`overall_comment` 可以为 `null`，`weak_points` 始终为数组。列表接口通常带 `task`；详情接口额外带 `questions`。
=======
批改完成前 `total_score`、`student_score`、`overall_comment` 可以为 `null`，`weak_points` 始终为数组。
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

### 2.4 作业题目 `Question`

```json
{
  "id": 10,
  "question_number": "1",
  "content": "求函数 f(x)=x^2 在 x=1 处的导数。",
  "student_answer": "2",
  "correct_answer": "2",
  "question_type": "计算题",
  "knowledge_point": "导数定义",
  "score": 10.0,
  "max_score": 10.0,
  "is_correct": true,
  "explanation": "使用导数公式可得 2x，在 x=1 时为 2。",
  "confidence": 0.96,
  "needs_review": false,
  "confidence_warning": null
}
```

<<<<<<< HEAD
题目识别结果中的文本字段可能为 `null`；已完成的 Agent 结果通常会填充这些字段。`confidence` 为 `0` 到 `1` 的小数，`needs_review` 仅是兼容性风险标志；当它为 `true` 时展示 `confidence_warning`，但不阻止完成、错题归档或掌握度更新。题目、解析和警告都是不可信文本，前端必须按纯文本渲染。

### 2.5 练习

练习任务数据：
=======
`confidence` 为 `0` 到 `1` 的小数。当 `confidence < REVIEW_CONFIDENCE_THRESHOLD`（默认 0.85）时 `needs_review=true`，同时展示 `confidence_warning`。`needs_review=true` 的错题**不自动归档**，需要学生在卡片上点确认后才进入错题本。题目、解析和警告都是不可信文本，前端必须按纯文本渲染。

### 2.5 会话 `ChatSession`

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "函数作业批改",
  "created_at": "2026-07-27T10:00:00",
  "updated_at": "2026-07-27T10:05:00",
  "last_active_at": "2026-07-27T10:05:00"
}
```

- `id`：UUID v4，由服务端生成
- `title`：可编辑，默认为第一条消息的截断或"新会话"
- `last_active_at`：最后一次消息时间，用于排序

### 2.6 消息 `ChatMessage`

```json
{
  "id": "msg_001",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "agent",
  "content": "批改完成，共 5 题。",
  "card_type": "student_exercise",
  "card_payload": {},
  "step_id": "step_003",
  "created_at": "2026-07-27T10:03:00"
}
```

- `role`：`student`（学生发的）、`agent`（Agent 回复的）、`system`（系统提示，如欢迎语）
- `content`：纯文本。当有 `card_type` 时 `content` 为卡片的摘要文本（一行人话）
- `card_type`：`null`（纯文本消息）或下列四种之一：
  - `"grading"` — 批改中卡片
  - `"student_exercise"` — 逐题批改结果卡片
  - `"wrong_question"` — 错题卡片（待复核确认用）
  - `"upload_failed"` — 上传/批改失败卡片
- `card_payload`：卡片结构化数据，结构见 §4.7
- `step_id`：Agent 运行时步骤 ID，用于断线回放定位

### 2.7 错题 `WrongQuestion`
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

```json
{
  "id": 1,
  "subject": "数学",
  "knowledge_point": "导数单调性",
<<<<<<< HEAD
  "difficulty": "基础补漏",
  "question_count": 2,
  "status": "ready",
  "student_score": null,
  "questions": [
    {
      "id": 11,
      "question_number": 1,
      "content": "判断 f(x)=x^2 在何处递增。",
      "standard_answer": "(0,+∞)",
      "explanation": "先求导并讨论导数符号。",
      "confidence": 0.94,
      "confidence_warning": null,
      "answers": []
    }
  ]
}
```

练习 `status`：`generating`、`ready`、`submitting`、`completed`、`failed`。创建接口等待生成完成后才返回，成功时通常为 `ready`；提交期间为 `submitting`，失败时接口返回错误并恢复为可提交状态，生成失败任务可能仅留在数据库中。每个 `answers` 最多一条，提交后包含：

```json
{
  "answer": "我的答案",
  "is_correct": true,
  "score": 10.0,
  "explanation": "判定说明",
  "confidence": 0.93,
  "confidence_warning": null
}
```

## 3. 认证 API

认证使用 `Authorization: Bearer <access_token>`，不使用 Cookie 或 CSRF token。JWT 是票据格式，
服务端同时在 Redis 中维护会话白名单；登出和改密码会立即撤销对应白名单 token。接近过期的有效
请求可能返回 `Set-Token` 响应头，前端应使用其值替换本地 access token。
=======
  "wrong_reason": "忽略定义域限制",
  "wrong_count": 1,
  "status": "active",
  "created_at": "2026-07-27T10:00:00",
  "question": {
    "id": 10,
    "question_number": "3",
    "content": "求函数 f(x)=ln(x) 的单调区间。",
    "student_answer": "在 R 上单调递增",
    "correct_answer": "在 (0,+∞) 上单调递增",
    "score": 0.0,
    "max_score": 10.0,
    "is_correct": false,
    "explanation": "忽略定义域限制，ln(x) 定义域为 (0,+∞)",
    "confidence": 0.92,
    "needs_review": false
  }
}
```

- `status`：`active`（正常错题）、`reviewed`（学生已复习）、`archived`（已归档）
- `wrong_count`：同一题累计错误次数（re-submission 时自增）
- 列表接口返回简略 `question`（只有 `id` + `content`），详情接口返回完整 `question`

---

## 3. 认证 API

认证使用 `Authorization: Bearer <access_token>`，不使用 Cookie 或 CSRF token。JWT 是票据格式，服务端同时在 Redis 中维护会话白名单；登出和改密码会立即撤销对应白名单 token。
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

### `GET /api/auth/pow/challenge?purpose=login|register`（匿名）

登录和注册前先申请一次性 PoW challenge。响应 `data`：

```json
{
  "challenge_id": "b8f1...",
  "purpose": "register",
  "difficulty": 4,
  "nonce_seed": "...",
<<<<<<< HEAD
  "expires_at": "2026-07-22T12:00:00+00:00"
}
```

客户端递增尝试 `nonce`，直到
`SHA-256("<nonce_seed>:<nonce>")` 的十六进制结果以 `difficulty` 个 `0` 开头。challenge 默认在
120 秒后失效，并绑定用途、客户端 IP 与 User-Agent；任意验证尝试都会原子消费，不能重放。
=======
  "expires_at": "2026-07-27T12:00:00+00:00"
}
```

客户端递增尝试 `nonce`，直到 `SHA-256("<nonce_seed>:<nonce>")` 的十六进制结果以 `difficulty` 个 `0` 开头。challenge 默认在 120 秒后失效，并绑定用途、客户端 IP 与 User-Agent；任意验证尝试都会原子消费，不能重放。
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

### `POST /api/auth/register`（匿名）

请求 JSON：

```json
{
  "username": "student01",
  "password": "password123",
  "nickname": "小明",
  "grade": "高三",
  "main_subject": "数学",
  "pow_challenge_id": "b8f1...",
  "pow_nonce": "18342"
}
```

- `username`：必填，3-32 个字符，仅 ASCII 字母、数字、下划线
- `password`：必填，8-72 个字符
- `nickname`：必填，1-64 个字符
- `grade`、`main_subject`：可选，最长 32 个字符

<<<<<<< HEAD
成功 `data`：`{"user": User, "access_token": "...", "token_type": "bearer"}`。数据库中第一个注册成功的
用户自动获得不可转让的 `admin` 角色，后续用户固定为 `student`；用户名已存在返回 `409`。
=======
成功 `data`：`{"user": User, "access_token": "...", "token_type": "bearer"}`。数据库中第一个注册成功的用户自动获得不可转让的 `admin` 角色，后续用户固定为 `student`；用户名已存在返回 `409`。
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

### `POST /api/auth/login`（匿名）

请求：`{"username":"student01","password":"password123","pow_challenge_id":"b8f1...","pow_nonce":"18342"}`。
<<<<<<< HEAD
成功返回与注册相同；用户名或密码不正确返回 `401`。PoW 失败、用途或客户端上下文不匹配返回
`400`；过期或已消费的 challenge 返回 `429`。
=======
成功返回与注册相同；用户名或密码不正确返回 `401`。PoW 失败、用途或客户端上下文不匹配返回 `400`；过期或已消费的 challenge 返回 `429`。
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

### `GET /api/auth/me`（需鉴权）

无请求体，返回 `data: User`。

### `PUT /api/auth/me`（需鉴权）

<<<<<<< HEAD
请求字段均可选，仅更新传入字段；`grade`、`school`、`main_subject` 传 `null` 可清空。`nickname` 在数据库中不可为空，传入时应保持 1-64 个字符；传 `nickname: null` 会在校验层返回 `422/4220`：
=======
请求字段均可选，仅更新传入字段；`grade`、`school`、`main_subject` 传 `null` 可清空。`nickname` 在数据库中不可为空，传入时应保持 1-64 个字符：
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

```json
{"nickname":"小明","grade":"高三","school":"一中","main_subject":"数学"}
```

返回更新后的 `data: User`。

### `PUT /api/auth/password`（需鉴权）

请求：`{"current_password":"password123","new_password":"newpassword123"}`。新密码 8-72 个字符。当前密码错误返回 `400`；成功返回 `{"updated":true}`。

### `POST /api/auth/logout`（需鉴权）

无请求体，返回 `{"logged_out":true}`，并立即撤销当前 access token。前端仍应清除本地 token。

<<<<<<< HEAD
## 4. 场景 1：作业上传与批改

### `POST /api/assignments`（需鉴权）

`multipart/form-data`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `file` | 文件 | 是 | 文件名后缀 `.jpg`、`.jpeg`、`.png`、`.pdf` |
| `subject` | 字符串 | 是 | 去除首尾空白后为 1-32 字符 |
| `title` | 字符串 | 否 | 省略时使用原文件名；服务端最多保存 128 字符 |

默认限制：文件不超过 `MAX_UPLOAD_MB=10` MB，PDF 不超过 `MAX_PDF_PAGES=10` 页；空文件、无效 PDF 或不支持的后缀返回 `400`。具体限制以部署环境变量为准。
=======
---

## 4. Agent 与 Chat 接口

本节描述 chat-only 架构下学生与 Agent 的全部交互接口。所有 Agent 能力通过 chat 消息流呈现，不跳页。

### 4.1 会话管理

#### `POST /api/agent/sessions`（需鉴权）

创建新会话。请求体（均可选）：

```json
{
  "title": "函数作业批改"
}
```

- `title`：可选，1-128 字符，省略时默认 `"新会话"`
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

成功响应 `data`：

```json
{
<<<<<<< HEAD
  "assignment_id": 1,
  "task": {"id":"task_abc123","status":"queued","step":"queued","progress":0,"error_message":null}
}
```

上传接口只负责保存文件和排队，前端不得把返回视为批改完成。

### `GET /api/tasks/{task_id}`（需鉴权）

轮询作业批改进度。建议每 1-3 秒请求一次，直到 `task.status` 为 `completed` 或 `failed`。

- `completed`：再请求 `GET /api/assignments/{assignment_id}` 读取题目和成绩
- `failed`：展示 `error_message`，不要读取不存在的成绩

### `GET /api/assignments`（需鉴权）

无查询参数。返回当前用户的 `Assignment[]`，按 `created_at` 倒序。

### `GET /api/assignments/{assignment_id}`（需鉴权）

返回 `Assignment` 加 `questions: Question[]`。资源不存在为 `404`，访问其他用户资源为 `403`。

### `PUT /api/questions/{question_id}`（需鉴权）

用于修正 OCR 或答案后重新判题。请求 JSON 字段均可选；至少建议传入需要修正的字段：

```json
{
  "content": "修正后的题目",
  "student_answer": "修正后的学生答案",
  "correct_answer": "修正后的参考答案",
  "knowledge_point": "导数单调性"
}
```

`content` 若传入不能为空，`knowledge_point` 最长 128 字符。接口会再次调用内置学习 Agent，可能耗时较长；成功返回更新后的 `Question`，同时重算作业总分、薄弱点、错题归档和掌握度。

## 5. 场景 2：错题本与薄弱知识点分层练习

### `GET /api/dashboard`（需鉴权）

返回：

```json
{
  "assignment_count": 3,
  "wrong_count": 8,
  "weak_points": [
    {"subject":"数学","knowledge_point":"导数单调性","mastery_score":40.0}
  ]
}
```

`weak_points` 最多 5 条，按掌握度从低到高。

### `GET /api/mastery`（需鉴权）

返回当前用户的掌握记录数组，按 `mastery_score` 从低到高：

```json
{
  "id": 1,
  "subject": "数学",
  "knowledge_point": "导数单调性",
  "mastery_score": 40.0,
  "correct_count": 2,
  "wrong_count": 3
}
```

### `GET /api/wrong-questions`（需鉴权）

可选查询参数 `subject`，按科目精确过滤。返回数组，按最近更新时间倒序：

```json
{
  "id": 1,
  "subject": "数学",
  "knowledge_point": "导数单调性",
  "wrong_reason": "忽略定义域",
  "wrong_count": 1,
  "status": "unreviewed",
  "question": {"id":10,"content":"题目原文"}
}
```

`question` 是完整 `Question` 对象。当前实现的默认 `status` 是 `unreviewed`，不是 `active`；前端不要假定只有某一个状态值。

### `POST /api/practices`（需鉴权）
=======
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "新会话",
  "created_at": "2026-07-27T10:00:00",
  "updated_at": "2026-07-27T10:00:00",
  "last_active_at": "2026-07-27T10:00:00"
}
```

#### `GET /api/agent/sessions`（需鉴权）

返回当前用户的全部会话，按 `last_active_at` 倒序。无分页（会话总量有限）。

响应 `data`：`ChatSession[]`

#### `PATCH /api/agent/sessions/{session_id}`（需鉴权）

修改会话属性。请求体：

```json
{
  "title": "7月27日数学作业"
}
```

- `title`：可选，1-128 字符

会话不存在返回 `404`，不属于当前用户返回 `403`。返回更新后的 `ChatSession`。

#### `DELETE /api/agent/sessions/{session_id}`（需鉴权）

删除会话及其所有消息（级联删除）。会话不存在返回 `404`，不属于当前用户返回 `403`。成功返回 `{"deleted":true}`。

---

### 4.2 Agent 上传与消息发送（统一入口）

#### `POST /api/agent/messages`（需鉴权）

**统一的消息发送入口**，支持三种模式：只发文字、只发文件、文件+文字同时发送。类似主流 AI 聊天产品（豆包、千问、ChatGPT）的交互方式。

`multipart/form-data`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `content` | 字符串 | 条件必填 | 文字内容，1-5000 字符。与 `file` 至少填一个 |
| `file` | 文件 | 条件必填 | `.jpg`、`.jpeg`、`.png`、`.pdf`。与 `content` 至少填一个 |
| `subject` | 字符串 | 否 | 学科，上传作业时建议填写；不填时 Agent 根据图片内容推断 |
| `session_id` | UUID | 否 | 指定会话；省略时自动创建新会话 |

**校验规则**：
- `content` 和 `file` 至少提供一个，否则返回 `400`
- 文件限制：不超过 `MAX_UPLOAD_MB=10` MB，PDF 不超过 `MAX_PDF_PAGES=30` 页
- 空文件、无效 PDF 或不支持的后缀返回 `400`

**三种发送模式的行为差异**：

**模式 A：只发文字**（`content` 有值，`file` 无）
```
学生消息 → Agent 意图识别 → 决定直接回答 或 调用工具
```
- 在会话中插入一条 `student` 消息（content 为文字，card_type 为 null）
- Agent 进入意图识别（见 §8.6），根据 prompt 判断：通用问答 → 流式文字回复；查错题 → 调错题本工具；出练习 → 提示场景 2 未开放；等等
- 通过 WebSocket 事件流回复

**模式 B：只发文件**（`file` 有值，`content` 无）
```
学生上传文件 → Agent 读图判断内容 → 意图识别 → 执行
```
- 保存文件，在会话中插入一条 `student` 消息（content 为文件名）
- Agent 读取图片内容，判断：
  - 是作业/试卷 → 自动进入批改流程（调 `AssignmentGrading::UploadAndGrade`）
  - 是其他内容（如课本截图、笔记）→ 根据图片内容给出相应回复
- 批改流程中出「批改中」卡片，完成后替换为「Student Exercise」卡片

**模式 C：文件+文字同时发送**（`content` 和 `file` 都有值）
```
学生上传文件 + 附带文字说明 → Agent 综合判断意图 → 执行
```
- 保存文件，在会话中插入一条 `student` 消息（content 为文字 + "[附件: filename]"）
- Agent 综合图片内容和文字判断意图，典型场景：

| 文字内容 | Agent 意图判断 | 执行 |
| --- | --- | --- |
| "帮我批改" / 无明确文字 | 作业批改 | 调批改工具 |
| "第3题怎么做" | 题目讲解（不批改） | LLM 读图 + 直接回答第3题 |
| "这道题为什么判错" | 错因分析 | LLM 读图 + 结合错题记录分析 |
| "帮我检查一下有没有错" | 批改+讲解 | 调批改工具 + 补充讲解 |
| "这是什么知识点" | 知识点识别 | LLM 读图 + 识别并讲解知识点 |
| "老师说答案是B，帮我确认" | 答案校验 | LLM 读图 + 对比分析 |
| "这道题的解题思路" | 解题讲解 | LLM 读图 + 详细讲解思路 |
| "帮我把这道题整理进错题本" | 手动归档 | 调错题本归档工具 |

成功响应 `data`：

```json
{
  "message_id": "msg_012",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "has_file": true,
  "assignment_id": 1,
  "task_id": "task_abc123"
}
```

- `message_id`：学生消息的 ID
- `session_id`：会话 ID
- `has_file`：是否包含文件
- `assignment_id`：仅在触发批改时返回，否则为 `null`
- `task_id`：仅在触发批改时返回，否则为 `null`

---

#### `POST /api/agent/upload`（需鉴权，旧接口兼容）

保留旧的文件上传专用接口，行为等同于 `POST /api/agent/messages` 的模式 B。建议新代码统一使用 `POST /api/agent/messages`。

`multipart/form-data`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `file` | 文件 | 是 | `.jpg`、`.jpeg`、`.png`、`.pdf` |
| `subject` | 字符串 | 是 | 去除首尾空白后为 1-32 字符 |
| `title` | 字符串 | 否 | 省略时使用原文件名；服务端最多保存 128 字符 |
| `session_id` | UUID | 否 | 指定会话；省略时自动创建新会话 |

成功响应 `data`：同 `POST /api/agent/messages`，额外返回 `grading_message_id`。

---

### 4.3 通用问答（Agent 文本对话，HTTP fallback）

#### `POST /api/agent/sessions/{session_id}/messages`（需鉴权）

HTTP fallback 通道，发送文本消息给 Agent。用于 WebSocket 不可用时的降级。
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

请求 JSON：

```json
{
<<<<<<< HEAD
  "subject": "数学",
  "knowledge_point": "导数单调性",
  "difficulty": "基础补漏",
  "question_count": 5
}
```

- `subject`：去除首尾空白后为 1-32 字符；`knowledge_point`：去除首尾空白后为 1-128 字符
- `difficulty` 必须是：`基础补漏`、`同类变式`、`综合提升`、`高考真题`
- `question_count`：1-10，默认 5

生成是同步长耗时请求，成功返回 `data: Practice`（状态 `ready`）。内置 Agent 会校验题数、知识点、重复题和置信度。

### `GET /api/practices/{practice_id}`（需鉴权）

返回 `data: Practice`，包含已生成题目及（若已提交）答案。其他用户资源返回 `403`。

### `POST /api/practices/{practice_id}/submit`（需鉴权）

一次提交全部题目：

```json
{
  "answers": [
    {"question_id": 11, "answer": "我的答案"},
    {"question_id": 12, "answer": "另一道答案"}
=======
  "content": "函数单调性怎么理解？"
}
```

- `content`：必填，1-5000 字符

**行为**：
1. 在会话中插入一条 `student` 角色消息
2. Agent 进入意图识别（见 §8.6），判断后执行
3. 在会话中插入一条 `agent` 角色消息

成功响应 `data`：

```json
{
  "student_message": {
    "id": "msg_010",
    "role": "student",
    "content": "函数单调性怎么理解？",
    "card_type": null,
    "card_payload": null,
    "step_id": null,
    "created_at": "2026-07-27T10:10:00"
  },
  "agent_message": {
    "id": "msg_011",
    "role": "agent",
    "content": "函数的单调性描述的是...",
    "card_type": null,
    "card_payload": null,
    "step_id": "step_005",
    "created_at": "2026-07-27T10:10:02"
  }
}
```

会话不存在返回 `404`，不属于当前用户返回 `403`。

---

### 4.4 消息历史与断线回放

#### `GET /api/agent/sessions/{session_id}/messages`（需鉴权）

获取会话的全部消息历史。按 `created_at` 正序。用于页面加载时渲染完整聊天记录。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `limit` | 整数 | 否 | 最近 N 条，默认 100，最大 500 |

响应 `data`：`ChatMessage[]`

会话不存在返回 `404`，不属于当前用户返回 `403`。

#### `GET /api/agent/sessions/{session_id}/replay`（需鉴权）

断线续接专用。返回指定 `step_id` 之后的所有消息和事件，用于 WebSocket 重连后补发丢失的内容。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `since` | 字符串 | 是 | `step_id`，来自 `session.welcome` 事件的 `replay_from_step_id` |

响应 `data`：

```json
{
  "replay_from": "step_003",
  "messages": [
    {
      "id": "msg_grading_001",
      "role": "agent",
      "content": "正在批改...",
      "card_type": "student_exercise",
      "card_payload": {},
      "step_id": "step_003",
      "created_at": "2026-07-27T10:03:00"
    }
  ],
  "pending_events": [
    {
      "event": "plan.done",
      "step_id": "step_004",
      "timestamp": "2026-07-27T10:04:00"
    }
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)
  ]
}
```

<<<<<<< HEAD
- `answers` 至少 1 项；`answer` 去除首尾空白后长度为 1-5000
- 必须覆盖该练习的全部题目且每题一次；缺题、重复题或多余题返回 `400`
- 已完成练习重复提交返回 `409`；另一个请求正在提交时也返回 `409`

判题完成后返回完整 `Practice`，`status` 为 `completed`，`student_score` 为百分制；每题 `answers[0]` 含判题结果。提交期间会同步调用 Agent/模型，请设置较长客户端超时（建议不少于 300 秒）。

## 7. 内核与示例接口

### `GET /`（匿名）

服务存活探针，响应不是统一 envelope：

```json
{"status":"ok","service":"Smart Learning Agent API","docs":"/docs"}
```

### `GET /api/plugins`（匿名）

返回已加载插件数组，每项包括 `name`、`version`、`description`、`category`、`dependencies`、`capabilities`、`metadata`。可用于检查后端能力，不应作为学生业务状态来源。

### `GET /api/example/ping`（匿名）

返回 `{"plugin":"example","status":"ok"}`，用于确认示例插件加载。

### `GET /api/example/capabilities`（需鉴权）

返回示例插件的开发能力说明和当前内核实现名称。该接口用于插件联调，不属于学生学习流程。
=======
- `messages`：`since` 之后持久化的消息（含 card_payload），按 `created_at` 正序
- `pending_events`：`since` 之后的运行时事件（用于重建前端状态），按时间正序

会话不存在返回 `404`，不属于当前用户返回 `403`。`since` 无效或已过期返回 400。

---

### 4.5 待复核确认

#### `POST /api/agent/sessions/{session_id}/review-confirm`（需鉴权）

学生对「待复核」题目确认归档。`needs_review=true` 的错题不自动归档，学生点确认后才进错题本。

请求 JSON：

```json
{
  "question_ids": [10, 12]
}
```

- `question_ids`：必填，至少 1 个，均为当前用户作业下的题目 ID

**行为**：
1. 校验题目存在、属于当前用户、`needs_review=true`
2. 将对应错题归档入错题本（`status="active"`）
3. 在会话中插入一条 `agent` 消息，`card_type="wrong_question"`，确认已归档
4. 写审计日志

成功响应 `data`：

```json
{
  "confirmed_count": 2,
  "archived_question_ids": [10, 12]
}
```

题目不存在、不属于当前用户、或 `needs_review=false` 返回 `400`。

---

### 4.6 WebSocket 事件通道

#### `GET /api/agent/ws?session_id=<uuid>&token=<jwt>`

WebSocket 连接端点。JWT 通过 URL 查询参数 `token` 传递（不使用 Header，因为浏览器 WebSocket API 不支持自定义 Header）。连接时校验 JWT 和 session_id 归属。

**连接生命周期**：
1. 客户端发起 WebSocket 连接
2. 服务端校验 JWT → 无效则关闭连接（code 4001）
3. 服务端校验 session_id 归属 → 不属于当前用户则关闭连接（code 4003）
4. 连接成功，服务端发送 `session.welcome` 事件
5. 客户端发送文本消息（JSON）→ 服务端处理并通过事件流回复
6. 任一方关闭连接

**客户端发送消息格式**（JSON）：

纯文字消息通过 WebSocket 发送：

```json
{
  "type": "chat.send",
  "content": "函数单调性怎么理解？"
}
```

- `type`：`"chat.send"`（发送文本消息）
- `content`：1-5000 字符

**包含文件的消息通过 HTTP 发送**（WebSocket 不支持文件传输）：
- 只发文件或文件+文字 → `POST /api/agent/messages`（`multipart/form-data`）
- 文件上传后，Agent 的回复通过 WebSocket 事件流推送
- 前端应在 HTTP 上传成功后，立即监听 WebSocket 等待 Agent 回复事件

**服务端推送事件格式**（JSON）：

所有事件都有以下公共字段：

```json
{
  "event": "<事件类型>",
  "step_id": "step_001",
  "timestamp": "2026-07-27T10:00:00.000Z",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

- `event`：事件类型，见下方 13 类
- `step_id`：步骤 ID，用于断线回放定位（`session.welcome` 中无此字段）
- `timestamp`：ISO 8601 UTC 时间戳
- `session_id`：所属会话

---

**13 类事件详解**：

**① `session.welcome`** — 连接成功后立即下发

```json
{
  "event": "session.welcome",
  "timestamp": "2026-07-27T10:00:00.000Z",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": {
    "replay_from_step_id": "step_003",
    "session_title": "函数作业批改"
  }
}
```

- `replay_from_step_id`：客户端应调用 `GET /api/agent/sessions/{id}/replay?since=step_003` 补发丢失的消息。若为 `null` 表示从头开始、无需回放
- `session_title`：当前会话标题

**② `plan.start`** — 本轮 Plan 开始

```json
{
  "event": "plan.start",
  "step_id": "step_001",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "plan_id": "plan_001",
    "goal": "批改上传的数学作业"
  }
}
```

- `plan_id`：本轮 Plan 的唯一 ID
- `goal`：Plan 目标的人话描述

**③ `intent.recognized`** — 意图识别结果（Agent 判断学生想干什么）

```json
{
  "event": "intent.recognized",
  "step_id": "step_001",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "intent": "homework_grading",
    "confidence": 0.92,
    "description": "识别为作业批改请求",
    "has_file": true,
    "tool_to_call": "AssignmentGrading::UploadAndGrade"
  }
}
```

- `intent`：识别出的意图类别，枚举值见 §8.6
- `confidence`：意图识别置信度（0-1）
- `description`：人话描述
- `has_file`：本次消息是否包含文件
- `tool_to_call`：Agent 决定调用的工具地址（`null` 表示不需要调工具、直接回答）

**④ `plan.step.tool_call`** — Tool Proposal（Agent 提议调用工具）

```json
{
  "event": "plan.step.tool_call",
  "step_id": "step_002",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "tool_address": "AssignmentGrading::UploadAndGrade",
    "proposal": "我将批改你上传的数学作业，识别题目并逐题判分。",
    "source": "agent",
    "side_effect": "write"
  }
}
```

- `tool_address`：工具地址，格式 `<Plugin>::<Tool>`（PascalCase + `::`）
- `proposal`：一句话说明「我打算调用 X，以便 Y」，对学生可见
- `source`：`"student"`（学生通过 Tab 联想显式选择）或 `"agent"`（Agent 自己的计划）
- `side_effect`：`"read"`、`"write"`、`"external"`。本期只有 `read` 和 `write`

**⑤ `plan.step.started`** — 工具开始执行

```json
{
  "event": "plan.step.started",
  "step_id": "step_002",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "tool_address": "AssignmentGrading::UploadAndGrade"
  }
}
```

**⑥ `plan.step.tool_result`** — 工具执行完成（含卡片数据）

```json
{
  "event": "plan.step.tool_result",
  "step_id": "step_003",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "tool_address": "AssignmentGrading::UploadAndGrade",
    "success": true,
    "card_type": "student_exercise",
    "card_payload": {},
    "summary": "批改完成，共 5 题"
  }
}
```

- `success`：工具是否执行成功
- `card_type`：卡片类型（`"student_exercise"` / `"upload_failed"` / `"wrong_question"` / `null`）
- `card_payload`：卡片结构化数据，前端用于渲染内嵌卡片，结构见 §4.7
- `summary`：一行人话摘要，也作为消息的 `content` 存入数据库

**⑦ `plan.step.error`** — 工具执行失败

```json
{
  "event": "plan.step.error",
  "step_id": "step_003",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "tool_address": "AssignmentGrading::UploadAndGrade",
    "error_message": "文件格式不支持，请上传 JPG/PNG/PDF 文件。",
    "card_type": "upload_failed",
    "card_payload": {}
  }
}
```

- `error_message`：用户可见的安全错误信息，不含堆栈
- `card_type`：通常为 `"upload_failed"`
- `card_payload`：失败卡片数据

**⑧ `plan.step.done`** — 单步完成

```json
{
  "event": "plan.step.done",
  "step_id": "step_003",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "tool_address": "AssignmentGrading::UploadAndGrade"
  }
}
```

**⑨ `chat.text.delta`** — 流式文本增量（通用问答 + Agent 回复）

```json
{
  "event": "chat.text.delta",
  "step_id": "step_005",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "delta": "函数的单调性",
    "accumulated": "函数的单调性描述的是"
  }
}
```

- `delta`：本次增量文本
- `accumulated`：从本轮开始累计的完整文本（方便前端直接替换，无需自己拼接）

**⑩ `plan.done`** — 本轮 Plan 全部完成

```json
{
  "event": "plan.done",
  "step_id": "step_004",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "plan_id": "plan_001",
    "success": true,
    "summary": "批改完成，共 5 题，其中 2 题判错。"
  }
}
```

**⑪ `plan.interrupt_request`** — 中断请求（本期占位）

```json
{
  "event": "plan.interrupt_request",
  "step_id": "step_002",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "plan_id": "plan_001",
    "reason": "student_requested"
  }
}
```

本期后端会发送此事件，但前端不需要渲染交互。预留接口契约。

**⑫ `memory.recorded`** — Agent 记忆写入（本期占位）

```json
{
  "event": "memory.recorded",
  "step_id": "step_004",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "memory_type": "preference",
    "summary": "学生对导数题判定给了好评"
  }
}
```

**⑬ `session.end`** — 会话结束

```json
{
  "event": "session.end",
  "step_id": "step_005",
  "timestamp": "...",
  "session_id": "...",
  "data": {
    "reason": "completed"
  }
}
```

- `reason`：`"completed"`（正常结束） / `"timeout"`（超时） / `"error"`（异常）

---

**WebSocket 关闭码**：

| Code | 含义 |
| ---: | --- |
| 4001 | JWT 无效或过期 |
| 4003 | session_id 不属于当前用户 |
| 4008 | 服务端主动关闭（超时无活动） |
| 1000 | 正常关闭 |

**断线续接流程**：
1. WebSocket 断开
2. 客户端重新连接 `GET /api/agent/ws?session_id=<uuid>&token=<jwt>`
3. 收到 `session.welcome`，读取 `replay_from_step_id`
4. 若 `replay_from_step_id` 不为 null，调用 `GET /api/agent/sessions/{id}/replay?since=<step_id>`
5. 用 replay 返回的 `messages` 和 `pending_events` 补齐 UI 状态
6. 继续监听 WebSocket 事件

**兜底：HTTP 轮询**
若 WebSocket 长时间无法连接，客户端可降级为：
- `GET /api/tasks/{task_id}` 轮询批改进度（每 1-3 秒）
- `GET /api/agent/sessions/{id}/messages` 定期拉取消息

---

### 4.7 卡片 payload 结构

所有卡片通过 `plan.step.tool_result` 事件下发，同时持久化到 `chat_messages.card_payload`。

**① `grading` — 批改中卡片**

```json
{
  "card_type": "grading",
  "card_payload": {
    "assignment_id": 1,
    "task_id": "task_abc123",
    "filename": "数学作业.jpg",
    "subject": "数学",
    "status": "processing",
    "step": "识别并批改作业",
    "progress": 45
  }
}
```

- `status`：`"queued"` / `"processing"` / `"completed"` / `"failed"`
- 批改完成时，此消息的 `card_type` 和 `card_payload` 会被更新为 `student_exercise`

**② `student_exercise` — 逐题批改结果卡片**

```json
{
  "card_type": "student_exercise",
  "card_payload": {
    "assignment_id": 1,
    "total_score": 100.0,
    "student_score": 82.0,
    "overall_comment": "整体掌握较好，注意导数应用。",
    "weak_points": ["导数单调性"],
    "questions": [
      {
        "id": 10,
        "question_number": "1",
        "content": "求函数 f(x)=x^2 在 x=1 处的导数。",
        "student_answer": "2",
        "correct_answer": "2",
        "is_correct": true,
        "knowledge_point": "导数定义",
        "confidence": 0.96,
        "needs_review": false,
        "explanation": null
      },
      {
        "id": 11,
        "question_number": "2",
        "content": "求 f(x)=ln(x) 的单调区间。",
        "student_answer": "在 R 上递增",
        "correct_answer": "在 (0,+∞) 上递增",
        "is_correct": false,
        "knowledge_point": "导数单调性",
        "confidence": 0.88,
        "needs_review": false,
        "explanation": "忽略定义域限制"
      },
      {
        "id": 12,
        "question_number": "3",
        "content": "...",
        "student_answer": "...",
        "correct_answer": "...",
        "is_correct": false,
        "knowledge_point": "导数极值",
        "confidence": 0.62,
        "needs_review": true,
        "explanation": "步骤不完整，未验证极值"
      }
    ],
    "review_questions": [12]
  }
}
```

- `questions`：完整题目列表，每题含判定结果
- `review_questions`：`needs_review=true` 的题目 ID 列表。这些题目的错题**不自动归档**，需要学生确认（调用 §4.5 `POST /api/agent/sessions/{session_id}/review-confirm`）
- `is_correct=true` 的题不显示 `explanation`

**③ `wrong_question` — 错题确认卡片**（待复核确认后下发）

```json
{
  "card_type": "wrong_question",
  "card_payload": {
    "confirmed_question_ids": [12],
    "message": "已将 1 道待复核题目归档进错题本。"
  }
}
```

**④ `upload_failed` — 上传/批改失败卡片**

```json
{
  "card_type": "upload_failed",
  "card_payload": {
    "filename": "作业.pdf",
    "subject": "数学",
    "error_message": "PDF 文件页数超过 30 页限制，请分批上传。",
    "suggestion": "建议将试卷按页拆分，每次上传不超过 30 页。"
  }
}
```

- `error_message`：用户可见的安全错误信息，**绝不包含堆栈、密钥或内部服务细节**
- `suggestion`：后续操作建议

---

### 4.8 Tab 地址联想

#### `GET /api/agent/address-suggestions?prefix=<string>`（需鉴权）

输入框中按 Tab 时触发，返回匹配的工具地址列表。建议在主链路跑通之后再实现。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `prefix` | 字符串 | 否 | 联想前缀，如 `"Ass"` 或 `"Assignment"`；为空时返回全部 |

响应 `data`：

```json
[
  {
    "address": "AssignmentGrading::UploadAndGrade",
    "short_intent": "上传并批改作业",
    "side_effect": "write",
    "description": "上传作业文件，自动识别题目、判分、标注知识点"
  }
]
```

- `address`：工具地址，格式 `<Plugin>::<Tool>`（PascalCase + `::`）
- `short_intent`：一句话描述该工具做什么
- `side_effect`：`"read"` / `"write"` / `"external"`
- `description`：详细说明（可选，本期可与 `short_intent` 相同）

---

## 5. 错题本接口

场景 1 的错题本接口。列表已有，需补全详情、状态流转和反馈。

### `GET /api/wrong-questions`（需鉴权）

可选查询参数 `subject`，按科目精确过滤。返回数组，按最近更新时间倒序。

响应 `data`：

```json
[
  {
    "id": 1,
    "subject": "数学",
    "knowledge_point": "导数单调性",
    "wrong_reason": "忽略定义域限制",
    "wrong_count": 1,
    "status": "active",
    "created_at": "2026-07-27T10:00:00",
    "question": {
      "id": 10,
      "content": "求 f(x)=ln(x) 的单调区间。"
    }
  }
]
```

列表接口的 `question` 是简略对象（只有 `id` + `content`），节省传输。

### `GET /api/wrong-questions/{wrong_question_id}`（需鉴权）

错题详情。返回完整 `WrongQuestion`（含完整 `question` 对象），见 §2.7。

- 资源不存在返回 `404`
- 不属于当前用户返回 `403`，并写 `access.denied` 审计日志

查看详情**进审计**（`event_type: "wrong_question.viewed"`）。

### `PATCH /api/wrong-questions/{wrong_question_id}/status`（需鉴权）

错题状态流转。请求 JSON：

```json
{
  "status": "reviewed"
}
```

- `status`：`"active"`（重新激活）、`"reviewed"`（已复习）、`"archived"`（归档）
- 合法流转：`active ↔ reviewed → archived`，`archived` 不可逆转为其他状态

返回更新后的 `WrongQuestion`（简略 question）。

状态变更写审计日志（`event_type: "wrong_question.status_changed"`）。

### `POST /api/questions/{question_id}/feedback`（需鉴权）

学生对某题判定给好/差评，写入个人偏好。不更新全局规范。

请求 JSON：

```json
{
  "rating": "good",
  "comment": "判定准确"
}
```

- `rating`：`"good"`（好评）或 `"bad"`（差评）
- `comment`：可选，最长 500 字符

题目不存在返回 `404`，不属于当前用户（通过 assignment → user_id 校验）返回 `403`。

成功返回 `{"recorded":true}`。数据写入 `user_preferences` 表，进审计日志（`event_type: "question.feedback"`）。

---
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

## 6. 管理员与审计接口

以下接口均要求 `role=admin`。普通用户访问返回 `403`；管理员角色仅由首次注册自动授予，当前版本不提供角色转让或删除用户接口。

### `GET /api/admin/users`（管理员）

<<<<<<< HEAD
分页查询用户。查询参数 `offset`（默认 `0`）和 `limit`（`1-100`，默认 `50`）；响应为
`{"items":[User],"offset":0,"limit":50}`。
=======
分页查询用户。查询参数 `offset`（默认 `0`）和 `limit`（`1-100`，默认 `50`）；响应为 `{"items":[User],"offset":0,"limit":50}`。
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)

### `POST /api/admin/users/{user_id}/revoke-sessions`（管理员）

立即撤销目标用户全部 Redis 会话白名单，返回 `{"user_id":1,"sessions_revoked":true}`。不删除用户或其学习数据。

### `GET /api/admin/config`（管理员）

读取可运行时管理的配置：OpenAI Base URL、模型、推理强度、响应存储开关、超时、上传/PDF 限制、审核阈值、token 续期阈值和 PoW 参数。`OPENAI_API_KEY` 永不返回，只以 `openai_api_key_configured` 布尔值表示是否已配置。

### `PUT /api/admin/config`（管理员）

按需提交上述字段更新运行时配置，例如：

```json
{
  "openai_base_url": "https://api.openai.com/v1",
  "openai_api_key": "sk-...",
  "openai_model": "gpt-4o",
  "openai_timeout_seconds": 120,
  "pow_difficulty": 4
}
```

配置持久化在数据库中，服务启动时重新加载；API Key 使用由 `JWT_SECRET_KEY` 派生的加密密钥保存，所有读取和审计记录都会脱敏。提交更新后立即作用于新的模型调用、上传限制和认证 challenge。

### `GET /api/audit-logs`（管理员）

全局查询不可变审计日志。`event_type`、`actor_username` 为可选精确筛选，`offset` 默认 `0`，`limit` 为 `1-100`、默认 `50`。响应为 `{"items":[AuditLog],"offset":0,"limit":50}`。

### `GET /api/audit-logs/export`（管理员）

使用与查询接口相同的 `event_type`、`actor_username` 筛选条件，下载 CSV。导出行为本身会写入审计日志。

审计日志没有删除、清理或修改 API；`metadata` 已对密码、令牌、密钥、Authorization 等敏感键脱敏，所有文本应按纯文本处理。

<<<<<<< HEAD
## 8. Agent、验算与置信度行为

内置 Agent 直接复用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。

内置 Agent 对数学、物理等可计算题可调用受限 `python_verify`（允许的数学库由后端沙箱控制），并要求检查数学等价性、定义域、边界条件和物理量纲。不同但等价的推导不因形式不同被判错；验算不确定时降低 `confidence`。

默认低置信度阈值为 `0.85`（`REVIEW_CONFIDENCE_THRESHOLD`）。低于阈值时返回 `needs_review=true` 或 `confidence_warning`，这是提示而非人工审核工作流：结果仍会完成、归档和更新掌握度，用户自行判断即可。

## 9. 前端联调流程与注意点

### 作业流程

1. 登录/注册保存 JWT。
2. `POST /api/assignments` 上传文件，记录 `assignment_id` 和 `task.id`。
3. 轮询 `GET /api/tasks/{task_id}`。
4. `completed` 后读取 `GET /api/assignments/{assignment_id}`；`failed` 展示错误并允许重新上传。
5. 详情中的题目和 Agent 文本使用纯文本渲染；长 OCR 文本允许换行和任意位置断行。

### 练习流程

1. 从 `/api/dashboard`、`/api/mastery` 或 `/api/wrong-questions` 选择知识点。
2. `POST /api/practices` 创建并等待同步生成完成。
3. 收集所有题答案后一次调用 `POST /api/practices/{id}/submit`。
4. 展示每题 `is_correct`、`score`、`explanation` 和 `confidence_warning`；不要因低置信度阻断提交。

### 通用注意点

- 每个请求都要处理非 2xx；4xx 用户提示取 `message`，5xx 使用固定通用失败提示，校验明细取 `data.errors`。
- 收到 401 时清除本地 JWT 并回到登录页；不要自动重试原请求造成循环。
- 资源 ID 是整数（作业、题目、练习）或字符串（批改任务），不要统一按一种类型处理。
- Agent 生成、判题和重新批改可能超过普通 Axios 默认超时；创建/提交练习建议使用 300 秒超时。
- 不要把 JWT、Agent key 或完整上传内容写入日志，也不要把不可信文本插入 HTML。

## 9. 后续迭代 API 合同预览（当前版本未实现，仅作前端预研参考）

以下接口来自任务书场景 3、4、5 的需求分析，当前后端尚未提供路由实现。本节作为前瞻性 API 合同，供前端团队评估架构和预留路由，实际调用将以后续发布的实现为准。

**本节中的所有接口均为 `需鉴权`，遵循第 1 节的统一外层、JWT 鉴权和错误码约定。**

---

### 10.1 场景 3 — 复盘报告与阶段评估（`assessmentApi`）

#### 公共数据结构

**阶段考核 `Exam`**

```json
{
  "id": 1,
  "title": "函数单元测验",
  "subject": "数学",
  "exam_type": "单元卷",
  "status": "completed",
  "total_score": 100.0,
  "student_score": 82.0,
  "time_limit_minutes": 45,
  "created_at": "2026-07-22T10:00:00",
  "questions": []
}
```

- `exam_type` 枚举：`专项小测`、`单元卷`、`模拟卷`、`高考专题卷`
- `status` 枚举：`generating`、`ready`、`in_progress`、`completed`、`failed`
- `time_limit_minutes`：`null` 表示不限时
- `questions`：结构复用 `PracticeQuestion`（每道题含 `id`、`content`、`standard_answer`、`confidence`、`answers` 等）

**复盘报告 `Report`**

```json
{
  "id": 1,
  "period": "周报",
  "start_date": "2026-07-15",
  "end_date": "2026-07-21",
  "subject": "数学",
  "assignment_count": 3,
  "wrong_count": 8,
  "practice_count": 2,
  "overall_score": 82.0,
  "previous_overall_score": 75.0,
  "score_change": 7.0,
  "weak_points": [
    {"knowledge_point": "导数单调性", "mastery_score": 40.0, "change": 10.0}
  ],
  "high_freq_errors": [
    {"knowledge_point": "导数定义", "wrong_count": 3}
  ],
  "mastery_changes": [
    {"knowledge_point": "导数单调性", "before": 30.0, "after": 40.0}
  ]
}
```

- `period` 枚举：`日报`、`周报`、`单元报告`、`月报`、`学期报告`
- `score_change`：正值表示进步，负值表示退步
- `mastery_changes`：本周期内有变化的知识点掌握度变化

---

#### `GET /api/reports`（后续迭代）

可选查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `period` | 字符串 | 精确过滤报告类型：`日报`、`周报`、`单元报告`、`月报`、`学期报告` |
| `subject` | 字符串 | 按学科精确过滤 |

返回 `Report[]`，按 `start_date` 倒序。

#### `GET /api/reports/{report_id}`（后续迭代）

返回完整 `Report`，包含 `mastery_changes` 和 `weak_points` 详情。

---

#### `GET /api/reports/score-compare`（后续迭代，`getScoreCompare`）

跨周期分数对比。将当前周期与上一周期（或指定基准周期）的核心指标并列展示。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `period` | 字符串 | 是 | 对比周期基准：`周报`、`月报`、`学期报告` |
| `subject` | 字符串 | 否 | 按学科过滤，不传则为全部学科汇总 |
| `reference_date` | ISO 日期 | 否 | 对比截止日期，默认当天 |

返回：

```json
{
  "subject": "数学",
  "period": "周报",
  "current_week_start": "2026-07-15",
  "current_week_end": "2026-07-21",
  "previous_week_start": "2026-07-08",
  "previous_week_end": "2026-07-14",
  "metrics": {
    "overall_score": {"current": 82.0, "previous": 75.0, "change": 7.0},
    "assignment_count": {"current": 3, "previous": 2, "change": 1},
    "wrong_count": {"current": 8, "previous": 12, "change": -4},
    "practice_count": {"current": 2, "previous": 1, "change": 1}
  },
  "segments": [
    {
      "knowledge_point": "导数单调性",
      "mastery_score": {"current": 60.0, "previous": 40.0, "change": 20.0}
    },
    {
      "knowledge_point": "三角函数",
      "mastery_score": {"current": 50.0, "previous": 55.0, "change": -5.0}
    }
  ]
}
```

`change` 正值表示改善，负值表示退步。`metrics` 中的 `wrong_count` 为负表示错题减少（是好事）。

---

#### `POST /api/exams`（后续迭代）

创建阶段考核（专项小测/单元卷/模拟卷）。请求 JSON：

```json
{
  "subject": "数学",
  "exam_type": "单元卷",
  "knowledge_points": ["导数定义", "导数单调性", "导数极值"],
  "question_count": 10,
  "time_limit_minutes": 45,
  "difficulty": "综合提升"
}
```

- `exam_type`：`专项小测`、`单元卷`、`模拟卷`、`高考专题卷`
- `knowledge_points`：至少 1 个知识点，最多 10 个
- `question_count`：1-30，默认 10
- `time_limit_minutes`：`null` 或 5-180 分钟，`null` 为不限时
- `difficulty`：复用练习难度的四级枚举

生成是同步长耗时请求，成功返回 `data: Exam`（状态 `ready`，含已生成题目）。

#### `GET /api/exams`（后续迭代）

返回当前用户的 `Exam[]`，按 `created_at` 倒序。

#### `GET /api/exams/{exam_id}`（后续迭代）

返回完整 `Exam`，包含所有题目及（若已提交）答案和判分结果。

#### `POST /api/exams/{exam_id}/start`（后续迭代）

开始限时作答，记录开始时间。若 `time_limit_minutes` 非空，服务端开始计时。返回 `{"started_at": "..."}`。

#### `POST /api/exams/{exam_id}/submit`（后续迭代）

一次提交考卷全部答案。请求和响应结构与 `POST /api/practices/{practice_id}/submit` 一致。

若设定了限时且超时提交，返回 `400` 并附 `{"reason": "time_exceeded", "elapsed_seconds": 3000}`。

---

### 10.2 场景 4 — 长期追踪与知识图谱（`trackingApi`）

#### 公共数据结构

**掌握度变化 `MasteryChange`**

```json
{
  "subject": "数学",
  "knowledge_point": "导数单调性",
  "changes": [
    {"date": "2026-07-01", "mastery_score": 30.0, "event": "作业批改"},
    {"date": "2026-07-08", "mastery_score": 40.0, "event": "分层练习"},
    {"date": "2026-07-15", "mastery_score": 55.0, "event": "阶段考核"},
    {"date": "2026-07-22", "mastery_score": 60.0, "event": "分层练习"}
  ],
  "trend": "improving",
  "current_score": 60.0,
  "target_score": 80.0
}
```

- `trend`：`improving`（上升）、`stable`（持平）、`declining`（下降）
- `changes[i].event`：触发掌握度变化的事件类型
- `target_score`：预设达标线，默认 80.0

**复习任务 `ReviewTask`**

```json
{
  "id": 1,
  "subject": "数学",
  "knowledge_point": "导数单调性",
  "days_since_last_practice": 7,
  "current_mastery": 55.0,
  "review_due_date": "2026-07-29",
  "status": "pending",
  "review_cycle": 7
}
```

- `review_cycle`：7、14 或 30 天
- `status`：`pending`、`completed`、`overdue`

---

#### `GET /api/tracking/mastery-change`（后续迭代，`getMasteryChange`）

查询某个知识点（或全部知识点）在指定时间窗口内的掌握度变化轨迹。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `subject` | 字符串 | 否 | 按学科过滤 |
| `knowledge_point` | 字符串 | 否 | 按知识点过滤。不传则返回全部知识点的变化 |
| `days` | 整数 | 否 | 统计最近 N 天，默认 30，范围 7-180 |

返回：

```json
{
  "time_window": {"start": "2026-06-22", "end": "2026-07-22", "days": 30},
  "items": [
    {
      "subject": "数学",
      "knowledge_point": "导数单调性",
      "changes": [
        {"date": "2026-07-01", "mastery_score": 30.0, "event": "作业批改"},
        {"date": "2026-07-08", "mastery_score": 40.0, "event": "分层练习"},
        {"date": "2026-07-22", "mastery_score": 60.0, "event": "分层练习"}
      ],
      "trend": "improving",
      "current_score": 60.0,
      "target_score": 80.0
    }
  ],
  "summary": {
    "improving_count": 5,
    "stable_count": 3,
    "declining_count": 1
  }
}
```

不传 `knowledge_point` 时，`items` 包含所有有变化记录的知识点，按 `current_score` 从低到高排列（优先关注最薄弱项）。

#### `GET /api/tracking/review-schedule`（后续迭代）

返回当前用户即将到期或已逾期的滚动复习任务列表。

查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `status` | 字符串 | 可选 `pending`（默认）、`overdue`、`completed` |
| `cycle` | 整数 | 可选 7、14、30，不传返回全部 |

返回 `ReviewTask[]`，按 `review_due_date` 升序（即将到期优先）。

#### `POST /api/tracking/review/{review_task_id}/complete`（后续迭代）

标记一个复习任务为已完成。系统自动触发该知识点的新一轮掌握度评估，并安排下一次复习（若当前周期为 7 天，完成后进入 14 天；14 天完成后进入 30 天；30 天完成后该知识点从活跃跟踪中毕业）。

请求体可包含练习结果（可选，用于更新掌握度）：

```json
{
  "practice_task_id": 42,
  "self_evaluation": "已掌握"
}
```

返回更新后的 `ReviewTask`（状态 `completed`，含下一次复习到期日或 `null` 表示已毕业）。

#### `GET /api/knowledge-graph`（后续迭代）

返回当前用户的知识掌握图谱可视化数据。

查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `subject` | 字符串 | 按学科过滤，不传返回全部学科 |

返回：

```json
{
  "nodes": [
    {"id": "数学-导数定义", "label": "导数定义", "subject": "数学", "mastery_score": 75.0, "status": "巩固中"},
    {"id": "数学-导数单调性", "label": "导数单调性", "subject": "数学", "mastery_score": 40.0, "status": "薄弱"},
    {"id": "数学-极值与最值", "label": "极值与最值", "subject": "数学", "mastery_score": 85.0, "status": "已掌握"}
  ],
  "edges": [
    {"source": "数学-导数定义", "target": "数学-导数单调性", "relation": "前置依赖"},
    {"source": "数学-导数单调性", "target": "数学-极值与最值", "relation": "前置依赖"}
  ]
}
```

- `node.status`：`未学习`（≤20）、`薄弱`（≤45）、`巩固中`（≤80）、`已掌握`（>80）
- `edges[i].relation`：知识点间关系标签

---

### 10.3 个人中心（`profileApi`）补充说明

当前版本个人资料管理已通过第 3 节「认证 API」的以下接口覆盖：

- `GET /api/auth/me` — 获取当前用户资料
- `PUT /api/auth/me` — 更新昵称、年级、学校、主学科
- `PUT /api/auth/password` — 修改密码

后续迭代可能扩展的接口（不作为当前联调依据）：

- `GET /api/profile/stats` — 个人学习统计摘要（累计上传数、累计练习数、总错题数、连续打卡天数等）
- `GET /api/profile/activity` — 近期学习活动时间线（按日期聚合的上传、练习、考核事件流）
- `PUT /api/profile/avatar` — 头像上传（multipart，限制格式和大小）

当前前端 `/profile` 页面仅需对接第 3 节的已有接口即可完成基础功能。上述扩展接口将在后续迭代中视优先级实现。

---

## 10. 合同审计结论（更新）

当前后端学生端 API 可以冻结供前端开发，前提是以本文为准。`backend/docs/api.md` 仅作为本合同的后端目录索引。

第 9 节列出的场景 3、4 接口为后续迭代 API 合同预览，当前版本后端不提供对应路由实现，前端不应在 v1.0 版本中对其发起实际调用。联调验收仅覆盖第 2-8 节描述的场景 1 和场景 2。
=======
---

## 7. 内核与示例接口

### `GET /`（匿名）

服务存活探针，响应不是统一 envelope：

```json
{"status":"ok","service":"Smart Learning Agent API","docs":"/docs"}
```

### `GET /api/plugins`（匿名）

返回已加载插件数组，每项包括 `name`、`version`、`description`、`category`、`dependencies`、`capabilities`、`metadata`。可用于检查后端能力。

### `GET /api/example/ping`（匿名）

返回 `{"plugin":"example","status":"ok"}`，用于确认示例插件加载。

### `GET /api/example/capabilities`（需鉴权）

返回示例插件的开发能力说明和当前内核实现名称。

---

## 8. Agent 运行时行为与置信度

### 8.1 Agent 双层能力

- **第一层（通用助手）**：学生在 chat 里随便问（如「函数单调性怎么理解」），Agent 流式回答（`chat.text.delta`），不走 Tool。
- **第二层（工具能力）**：学生上传作业时，Agent 先发 `plan.step.tool_call`（Proposal），然后执行 `AssignmentGrading::UploadAndGrade`，把结果作为卡片流回。

### 8.2 ToolSpec（工具治理）

每个 Tool 注册时声明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `side_effect` | 枚举 | `"read"`（不写库）/ `"write"`（写库）/ `"external"`（外发，本期无） |
| `requires_confirmation` | 布尔 | 执行前是否需要学生卡片确认 |
| `preconditions` | 字符串[] | 前置条件描述 |
| `autonomous` | 布尔 | Agent 是否可自主决定调用（vs 学生显式触发） |

场景 1 落地规则：
- 上传批改：`side_effect=write`，学生显式点击发起 → Proposal 可见但**不拦**（点击即执行）
- 待复核确认：`side_effect=write`，`requires_confirmation=true`（学生点确认才归档）
- 本期没有 `side_effect=external` 的 Tool

### 8.3 验算与置信度

内置 Agent 对数学、物理等可计算题可调用受限 `python_verify`（允许的数学库：math, sympy, pint 等），并要求检查数学等价性、定义域、边界条件和物理量纲。

默认低置信度阈值为 `0.85`（`REVIEW_CONFIDENCE_THRESHOLD`）。低于阈值时：
- `needs_review=true`
- 错题**不自动归档**
- 前端展示「待复核」标签 + 「点确认后才记入错题本」提示
- 学生调用 `POST /api/agent/sessions/{session_id}/review-confirm` 确认后才归档

### 8.4 审计要求

- 写接口 100% 经审计切面；审计失败 → 业务事务回滚
- 不在路由手写 `audit.record`
- 跨生越权访问统一返回 403/404，并写 `access.denied` 审计

### 8.5 新增 Agent 能力规则

**新增 Agent 能力 = 加一个插件 Tool，永不改运行时**。Planner 与 Executor 是运行时里两个独立接缝，本期 Planner 只产出单目标简单 Plan、Executor 线性跑；将来升级多步 DAG / Plan Revision / 中断取消都是往接缝里填，不动骨架。

### 8.6 LangGraph Agent 运行时

Agent 运行时基于 LangGraph `StateGraph` 构建，负责意图识别、工具调度和上下文组装。
运行时架构、状态定义、意图识别系统提示词、调度逻辑等实现细节见独立文档：

- **Agent 运行时设计文档**：`docs/agent-runtime.md`
- **意图识别系统提示词**：`docs/prompts/intent-recognition.md`

接口层面需要知道的是：
- 意图识别结果通过 WebSocket 事件 `intent.recognized` 推送给前端（见 §4.6 ③）
- 可用工具列表见 `GET /api/agent/tools`（需鉴权），返回当前注册的工具及权限声明

#### `GET /api/agent/tools`（需鉴权）

返回当前 Agent 运行时注册的工具列表，含权限声明。用于前端 Tab 联想和调试。

响应 `data`：

```json
[
  {
    "address": "AssignmentGrading::UploadAndGrade",
    "side_effect": "write",
    "requires_confirmation": false,
    "description": "上传作业文件，自动识别题目、判分、标注知识点"
  }
]
```

---

## 9. 本期不做的接口（冻结，后续迭代）

以下接口来自任务书场景 2-5 的需求分析。当前版本**后端不提供路由实现**，前端不应对其发起调用。本节仅作为前瞻性 API 合同，供后续迭代参考。

**冻结范围**：
- 场景 2：分层练习（`POST /api/practices`、`GET /api/practices/{id}`、`POST /api/practices/{id}/submit`）
- 场景 2：Dashboard（`GET /api/dashboard`、`GET /api/mastery`）
- 场景 3：复盘报告（`GET /api/reports`、`GET /api/reports/{id}`、`GET /api/reports/score-compare`）
- 场景 3：阶段考核（`POST /api/exams`、`GET /api/exams`、`POST /api/exams/{id}/start`、`POST /api/exams/{id}/submit`）
- 场景 4：长期追踪（`GET /api/tracking/mastery-change`、`GET /api/tracking/review-schedule`、`POST /api/tracking/review/{id}/complete`）
- 场景 4：知识图谱（`GET /api/knowledge-graph`）
- 场景 5：长效追踪与个人中心扩展（`GET /api/profile/stats`、`GET /api/profile/activity`）

这些接口的详细定义请参考 v1.0 文档历史版本。后续迭代实现时以最新需求文档为准。

---

## 10. 数据库变更（v2.0 新增）

### 已有表（保留不变）

`users`、`assignments`、`processing_tasks`、`questions`、`wrong_questions`、`audit_logs`、`user_preferences`、`system_settings`、`knowledge_points`、`mastery_records`、`practice_tasks`、`practice_questions`、`practice_answers`、`exam_tasks`、`exam_questions`、`exam_answers`

### 新增 2 张表

#### `chat_sessions`

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | UUID | PK | 由服务端生成（UUID v4） |
| `user_id` | INT | FK → users.id, NOT NULL, INDEX | 所属学生 |
| `title` | VARCHAR(128) | NOT NULL, DEFAULT "新会话" | 会话标题 |
| `created_at` | DATETIME | NOT NULL | 创建时间 |
| `updated_at` | DATETIME | NOT NULL | 最后更新时间 |
| `last_active_at` | DATETIME | NOT NULL, INDEX | 最后活跃时间（用于排序） |

#### `chat_messages`

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | VARCHAR(48) | PK | 消息 ID（格式 `msg_<uuid_hex[:24]>`） |
| `session_id` | UUID | FK → chat_sessions.id, NOT NULL, INDEX | 所属会话 |
| `role` | VARCHAR(16) | NOT NULL | `"student"` / `"agent"` / `"system"` |
| `content` | TEXT | NOT NULL | 纯文本内容（卡片摘要或聊天文本） |
| `card_type` | VARCHAR(32) | NULLABLE | `"grading"` / `"student_exercise"` / `"wrong_question"` / `"upload_failed"` / `null` |
| `card_payload` | JSON | NULLABLE | 卡片结构化数据 |
| `step_id` | VARCHAR(48) | NULLABLE, INDEX | Agent 运行时步骤 ID（用于断线回放） |
| `created_at` | DATETIME | NOT NULL | 创建时间 |

### `wrong_questions` 表变更

| 变更 | 说明 |
| --- | --- |
| `status` 默认值从 `"unreviewed"` 改为 `"active"` | 新的合法值：`active`、`reviewed`、`archived` |
| `wrong_count` 在重复提交时自增 | 同一题再次判错时 `wrong_count += 1` |

---

## 11. 前端联调流程（v2.0）

### 登录流程

1. `GET /api/auth/pow/challenge` → 客户端算 PoW
2. `POST /api/auth/login`（或 `/register`）→ 保存 JWT
3. 自动进入 `/chat` 页面

### Chat 主流程

1. 进入 chat → `GET /api/agent/sessions` 获取会话列表
2. 选择会话（或 `POST /api/agent/sessions` 新建）→ 连接 WebSocket `GET /api/agent/ws?session_id=<uuid>&token=<jwt>`
3. `GET /api/agent/sessions/{id}/messages` 加载历史消息
4. 上传作业：`POST /api/agent/upload`（含 file + subject + session_id）→ 立即出现「批改中」卡片
5. 监听 WebSocket 事件：
   - `plan.step.tool_call` → 显示 Proposal
   - `plan.step.tool_result`（`card_type=student_exercise`）→ 渲染逐题结果卡片
   - 若含 `review_questions` → 渲染「待复核」按钮
6. 待复核确认：`POST /api/agent/sessions/{session_id}/review-confirm`
7. 查看错题：`GET /api/wrong-questions` → 错题抽屉；点开调 `GET /api/wrong-questions/{id}`

### 通用问答

1. 在输入框输入文字 → WebSocket 发送 `{"type":"chat.send","content":"..."}`
2. 监听 `chat.text.delta` 事件 → 流式渲染 Agent 回复
3. 或 HTTP fallback：`POST /api/agent/sessions/{id}/messages`

### 断线续接

1. WebSocket 断开 → 自动重连
2. 收到 `session.welcome` → 读取 `replay_from_step_id`
3. 调用 `GET /api/agent/sessions/{id}/replay?since=<step_id>` → 补齐 UI
4. 继续监听新事件

### 通用注意点

- 每个请求都要处理非 2xx；4xx 用户提示取 `message`，5xx 使用固定通用失败提示
- 收到 401 时清除本地 JWT 并回到登录页；不要自动重试原请求造成循环
- Agent 批改可能超过普通 Axios 默认超时；上传建议使用 300 秒超时
- 不要把 JWT、Agent key 或完整上传内容写入日志
- 不可信文本（题目、解析、Agent 回复）必须按纯文本渲染，不插入 HTML

---

## 12. 合同审计结论

当前后端 API v2.0 可以冻结供后端开发。本文替代 v1.0，是唯一的接口合同。

第 4 节（Agent 与 Chat）是本次重写的核心新增内容，后端优先实现。第 5 节（错题本补全）为第二优先级。第 6-7 节（管理员、内核）保留现状。第 9 节（场景 2-5）冻结，后续迭代实现。

`backend/docs/api.md` 仅作为本合同的后端目录索引。
>>>>>>> 9ea8036 (feat: initial commit of Cuoti-Pro project)
