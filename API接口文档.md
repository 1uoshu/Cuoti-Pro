# Smart Learning Agent API 接口文档

合同版本：`v1.0`（2026-07-22；当前 URL 前缀仍为 `/api`）
状态：场景 1「作业上传与批改」和场景 2「错题本与薄弱知识点分层练习」的前端联调合同。

本文以当前后端路由、Pydantic 校验、数据库序列化器和 Agent 工作流实现为准。前端只调用本文件中的学生端后端 API，不直接调用模型或 Agent 服务。

## 1. 基本约定

### 1.1 地址与格式

- 本地开发：`http://localhost:8000`
- Docker Compose：由部署端口映射决定，默认仍为 `http://localhost:8000`
- 业务 API 前缀：`/api`
- OpenAPI：`GET /docs`（Swagger UI）、`GET /openapi.json`
- 请求和响应编码：UTF-8 JSON；文件上传使用 `multipart/form-data`
- 默认 CORS：`http://localhost:5173`（由 `CORS_ORIGINS` 配置）

所有 `/api` 业务端点（包括未匹配路由的 404 和方法不允许的 405）成功和失败均使用统一外层；`/`、`/docs`、`/openapi.json` 不使用该外层：

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

JWT 当前使用 HS256，默认有效期 12 小时（`JWT_EXPIRE_HOURS`）。没有刷新令牌；过期后重新登录。`POST /api/auth/logout` 是无状态确认，不会使已经签发的 JWT 立即失效，前端应删除本地令牌。

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
| 403 | 403 | 资源不属于当前用户 |
| 404 | 404 | 资源不存在 |
| 405 | 405 | 请求方法不允许 |
| 409 | 409 | 用户名冲突或练习重复提交 |
| 422 | 4220 | Pydantic 请求校验失败，详情在 `data.errors` |
| 500 | 500 | 文件保存等已知服务端失败（对用户仍返回通用文案） |
| 500 | 5000 | 未预期的服务/Agent 错误 |
| 500 | 5001 | 数据库操作失败 |

后端会把 FastAPI `HTTPException.detail` 字符串放入 4xx `message`，不会使用默认的 `detail` 外层。5xx 响应使用通用文案；内部 Agent/模型异常不会通过学生 API 或个人审计接口原样返回，不能依赖具体文案判断业务状态。

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

批改完成前 `total_score`、`student_score`、`overall_comment` 可以为 `null`，`weak_points` 始终为数组。列表接口通常带 `task`；详情接口额外带 `questions`。

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

题目识别结果中的文本字段可能为 `null`；已完成的 Agent 结果通常会填充这些字段。`confidence` 为 `0` 到 `1` 的小数，`needs_review` 仅是兼容性风险标志；当它为 `true` 时展示 `confidence_warning`，但不阻止完成、错题归档或掌握度更新。题目、解析和警告都是不可信文本，前端必须按纯文本渲染。

### 2.5 练习

练习任务数据：

```json
{
  "id": 1,
  "subject": "数学",
  "knowledge_point": "导数单调性",
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

### `GET /api/auth/pow/challenge?purpose=login|register`（匿名）

登录和注册前先申请一次性 PoW challenge。响应 `data`：

```json
{
  "challenge_id": "b8f1...",
  "purpose": "register",
  "difficulty": 4,
  "nonce_seed": "...",
  "expires_at": "2026-07-22T12:00:00+00:00"
}
```

客户端递增尝试 `nonce`，直到
`SHA-256("<nonce_seed>:<nonce>")` 的十六进制结果以 `difficulty` 个 `0` 开头。challenge 默认在
120 秒后失效，并绑定用途、客户端 IP 与 User-Agent；任意验证尝试都会原子消费，不能重放。

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

成功 `data`：`{"user": User, "access_token": "...", "token_type": "bearer"}`。数据库中第一个注册成功的
用户自动获得不可转让的 `admin` 角色，后续用户固定为 `student`；用户名已存在返回 `409`。

### `POST /api/auth/login`（匿名）

请求：`{"username":"student01","password":"password123","pow_challenge_id":"b8f1...","pow_nonce":"18342"}`。
成功返回与注册相同；用户名或密码不正确返回 `401`。PoW 失败、用途或客户端上下文不匹配返回
`400`；过期或已消费的 challenge 返回 `429`。

### `GET /api/auth/me`（需鉴权）

无请求体，返回 `data: User`。

### `PUT /api/auth/me`（需鉴权）

请求字段均可选，仅更新传入字段；`grade`、`school`、`main_subject` 传 `null` 可清空。`nickname` 在数据库中不可为空，传入时应保持 1-64 个字符；传 `nickname: null` 会在校验层返回 `422/4220`：

```json
{"nickname":"小明","grade":"高三","school":"一中","main_subject":"数学"}
```

返回更新后的 `data: User`。

### `PUT /api/auth/password`（需鉴权）

请求：`{"current_password":"password123","new_password":"newpassword123"}`。新密码 8-72 个字符。当前密码错误返回 `400`；成功返回 `{"updated":true}`。

### `POST /api/auth/logout`（需鉴权）

无请求体，返回 `{"logged_out":true}`，并立即撤销当前 access token。前端仍应清除本地 token。

## 4. 场景 1：作业上传与批改

### `POST /api/assignments`（需鉴权）

`multipart/form-data`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `file` | 文件 | 是 | 文件名后缀 `.jpg`、`.jpeg`、`.png`、`.pdf` |
| `subject` | 字符串 | 是 | 去除首尾空白后为 1-32 字符 |
| `title` | 字符串 | 否 | 省略时使用原文件名；服务端最多保存 128 字符 |

默认限制：文件不超过 `MAX_UPLOAD_MB=10` MB，PDF 不超过 `MAX_PDF_PAGES=10` 页；空文件、无效 PDF 或不支持的后缀返回 `400`。具体限制以部署环境变量为准。

成功响应 `data`：

```json
{
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

请求 JSON：

```json
{
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
  ]
}
```

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

## 6. 管理员与审计接口

以下接口均要求 `role=admin`。普通用户访问返回 `403`；管理员角色仅由首次注册自动授予，当前版本不提供角色转让或删除用户接口。

### `GET /api/admin/users`（管理员）

分页查询用户。查询参数 `offset`（默认 `0`）和 `limit`（`1-100`，默认 `50`）；响应为
`{"items":[User],"offset":0,"limit":50}`。

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
