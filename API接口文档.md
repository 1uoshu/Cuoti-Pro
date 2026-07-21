# Smart Learning Agent API 接口文档

版本：`v1.0`（2026-07-22）
状态：场景 1「作业上传与批改」和场景 2「错题薄弱点练习」的前端联调合同。

本文以当前后端路由、Pydantic 校验、数据库序列化器和 Agent 工作流实现为准。前端只调用本文件中的学生端后端 API，不直接调用模型或 Agent 服务。

## 1. 基本约定

### 1.1 地址与格式

- 本地开发：`http://localhost:8000`
- Docker Compose：由部署端口映射决定，默认仍为 `http://localhost:8000`
- 业务 API 前缀：`/api`
- OpenAPI：`GET /docs`（Swagger UI）、`GET /openapi.json`
- 请求和响应编码：UTF-8 JSON；文件上传使用 `multipart/form-data`
- 默认 CORS：`http://localhost:5173`（由 `CORS_ORIGINS` 配置）

除根路径外，API 成功和失败均使用统一外层：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

`data` 可以是对象、数组或 `null`。成功时 `code` 固定为 `0`；失败时不要只依据 HTTP 状态，优先展示 `message`，并按需读取 `data`。

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
| 409 | 409 | 用户名冲突或练习重复提交 |
| 422 | 4220 | Pydantic 请求校验失败，详情在 `data.errors` |
| 500 | 5000 | 未预期的服务/Agent 错误 |
| 500 | 5001 | 数据库操作失败 |

后端会把 FastAPI `HTTPException.detail` 字符串放入 `message`，不会使用默认的 `detail` 外层。Agent/模型错误会被截断后返回，不能依赖具体文案判断业务状态。

## 2. 公共数据结构

### 2.1 用户 `User`

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
- `error_message`：成功为 `null`；失败时是有限长度的诊断文本

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

练习 `status`：`generating`、`ready`、`completed`、`failed`。创建接口等待生成完成后才返回，成功时通常为 `ready`；失败时接口返回错误，失败任务可能仅留在数据库中。每个 `answers` 最多一条，提交后包含：

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

### `POST /api/auth/register`（匿名）

请求 JSON：

```json
{
  "username": "student01",
  "password": "password123",
  "nickname": "小明",
  "grade": "高三",
  "main_subject": "数学"
}
```

- `username`：必填，3-32 个字符，仅 ASCII 字母、数字、下划线
- `password`：必填，8-72 个字符
- `nickname`：必填，1-64 个字符
- `grade`、`main_subject`：可选，最长 32 个字符

成功 `data`：`{"user": User, "access_token": "...", "token_type": "bearer"}`。用户名已存在返回 `409`。

### `POST /api/auth/login`（匿名）

请求：`{"username":"student01","password":"password123"}`。成功返回与注册相同；用户名或密码不正确返回 `401`。

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

无请求体，返回 `{"logged_out":true}`。这是无状态确认，前端仍需清除本地 JWT。

## 4. 场景 1：作业上传与批改

### `POST /api/assignments`（需鉴权）

`multipart/form-data`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | :---: | --- |
| `file` | 文件 | 是 | 文件名后缀 `.jpg`、`.jpeg`、`.png`、`.pdf` |
| `subject` | 字符串 | 是 | 去除首尾空白后不能为空 |
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

`content` 若传入不能为空，`knowledge_point` 最长 128 字符。接口会再次调用内置/外部 Agent，可能耗时较长；成功返回更新后的 `Question`，同时重算作业总分、薄弱点、错题归档和掌握度。

## 5. 场景 2：错题与薄弱点练习

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

- `subject`：1-32 字符；`knowledge_point`：1-128 字符；服务端会去除首尾空白
- `difficulty` 必须是：`基础补漏`、`同类变式`、`综合提升`、`高考真题`
- `question_count`：1-10，默认 5

生成是同步长耗时请求，成功返回 `data: Practice`（状态 `ready`）。内置 Agent 会校验题数、知识点、重复题和置信度；外部 Agent 适配器在最多 `question_count * 3` 次调用内收集去重题目，仍不足则失败。

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

- `answers` 至少 1 项；`answer` 长度 1-5000
- 必须覆盖该练习的全部题目且每题一次；缺题、重复题或多余题返回 `400`
- 已完成练习重复提交返回 `409`

判题完成后返回完整 `Practice`，`status` 为 `completed`，`student_score` 为百分制；每题 `answers[0]` 含判题结果。提交期间会同步调用 Agent/模型，请设置较长客户端超时（建议不少于 300 秒）。

## 6. 内核与示例接口

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

### `GET /api/audit-logs/me`（需鉴权）

查询当前用户审计事件：

- `event_type`：可选，精确匹配，例如 `auth.login`
- `limit`：可选，1-100，默认 50

返回数组，每项字段为 `id`、`event_type`、`outcome`、`actor_user_id`、`actor_username`、`resource_type`、`resource_id`、`summary`、`metadata`、`error_message`、`created_at`。`metadata` 已对密码、令牌、密钥、Authorization 等敏感键脱敏；所有字段按纯文本处理。

## 7. Agent、验算与置信度行为

默认模式是项目内置 Agent，直接复用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。只有配置 `AGENT_API_BASE_URL` 和 `AGENT_API_KEY` 时才启用可选外部 Agent 适配器；前端不需要也不应该持有这些服务凭据。

内置 Agent 对数学、物理等可计算题可调用受限 `python_verify`（允许的数学库由后端沙箱控制），并要求检查数学等价性、定义域、边界条件和物理量纲。不同但等价的推导不因形式不同被判错；验算不确定时降低 `confidence`。

默认低置信度阈值为 `0.85`（`REVIEW_CONFIDENCE_THRESHOLD`）。低于阈值时返回 `needs_review=true` 或 `confidence_warning`，这是提示而非人工审核工作流：结果仍会完成、归档和更新掌握度，用户自行判断即可。

## 8. 前端联调流程与注意点

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

- 每个请求都要处理非 2xx；用户提示取 `message`，校验明细取 `data.errors`。
- 收到 401 时清除本地 JWT 并回到登录页；不要自动重试原请求造成循环。
- 资源 ID 是整数（作业、题目、练习）或字符串（批改任务），不要统一按一种类型处理。
- Agent 生成、判题和重新批改可能超过普通 Axios 默认超时；创建/提交练习建议使用 300 秒超时。
- 不要把 JWT、Agent key 或完整上传内容写入日志，也不要把不可信文本插入 HTML。

## 9. 外部 Agent 适配器（仅后端配置，不是前端 API）

如部署方选择外部 Agent，后端会向 `AGENT_API_BASE_URL` 发送 `Authorization: Bearer <AGENT_API_KEY>`，不会转发学生 JWT。其兼容端点来自 `backend/docs/agent_api.json`：

| 用途 | 方法与路径 | 请求 |
| --- | --- | --- |
| 图片作业 | `POST /api/grade/image` | multipart：`student_id`、`question`、`subject`、`image` |
| PDF 作业 | `POST /api/grade/pdf` | multipart：`student_id`、`question`、`subject`、`pdf` |
| 单题重新批改 | `POST /api/grade` | JSON：`student_id`、`question`、`student_answer`、`subject` |
| 生成练习 | `POST /api/practice/generate` | form：`student_id`、`weak_points`、`difficulty`（`base`/`variant`/`advanced`/`exam`） |
| 练习判题 | `POST /api/practice/answer` | form：`student_id`、`question_json`、`student_answer` |

外部响应可包在 `data`、`result`、`output` 等对象中；后端会归一化字段别名并严格校验题目、分数、布尔值和置信度。外部服务的 200 响应结构在原 OpenAPI 中未定义，不能替代本文件的学生端合同。

## 10. 合同审计结论

当前后端学生端 API 可以冻结供前端开发，前提是以本文为准。与旧 `backend/docs/api.md` 相比，本文补齐了示例能力接口、真实错误 code、实际错题状态 `unreviewed`、练习全量提交约束、同步长耗时、上传/PDF 限制、字段可空性及 Agent 置信度策略。`backend/docs/agent_api.json` 是外部适配器输入合同，不是前端调用入口。
