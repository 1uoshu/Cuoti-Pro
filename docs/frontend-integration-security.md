# 前端对接与安全注意事项

本文给前端两位同学使用。接口细节以 [backend/docs/api.md](../backend/docs/api.md) 为准，这里只强调对接流程和安全边界。

## 对接流程

1. 本地后端地址默认是 `http://localhost:8000`，业务接口统一在 `/api` 下。
2. 所有成功和失败响应都有统一结构：`{ "code": number, "message": string, "data": ... }`。失败时 HTTP 状态码仍然是 `401`、`403`、`422` 等。
3. 登录或注册后保存 `data.access_token`，后续请求带请求头：`Authorization: Bearer <token>`。
4. 场景 1 的上传接口是 `POST /api/assignments`，使用 `multipart/form-data`，字段是 `file`、`subject`、可选 `title`。
5. 上传成功后不要立即认为批改完成，要用返回的 `task.id` 轮询 `GET /api/tasks/{task_id}`，直到 `status` 变成 `completed` 或 `failed`。
6. 场景 2 的薄弱点首页数据来自 `GET /api/dashboard`、`GET /api/mastery`、`GET /api/wrong-questions` 和 `/api/practices` 系列接口。
7. 个人审计日志来自 `GET /api/audit-logs/me`，可用于“最近登录/上传/批改/练习”类页面或测试验收。

## XSS 防护

前端必须把下面这些内容全部当作不可信输入处理：

- 学生上传文件名、题目 OCR 文本、学生答案、参考答案。
- Agent/大模型生成的解析、错因、学习建议、练习题。
- 审计日志中的 `summary` 和 `metadata`。
- 用户昵称、学校、年级、学科等个人资料。
- 后续 RAG/图数据库返回的任何文本。

执行规则：

- 优先使用 Vue 模板插值 `{{ text }}` 或组件的纯文本属性渲染内容。
- 不要对题目、答案、解析、错因、评论使用 `v-html`、`innerHTML`、`insertAdjacentHTML`。
- 如果未来必须支持 Markdown 或富文本，先禁用原始 HTML，再用 DOMPurify 这类库做白名单清洗。
- 不要把接口返回的字符串直接拼进 `<script>`、`style`、事件属性、动态组件名或未校验的 URL。
- 链接只允许 `http:`、`https:`、同站相对路径；禁止 `javascript:`、`data:` 这类可执行 URL。
- 图片或文件预览只使用用户本次选择的 `File` 对象生成 `URL.createObjectURL`，用完调用 `URL.revokeObjectURL`。
- 不要在前端信任 `confidence`、`is_correct`、`score` 等字段做越权判断；权限判断以后端返回为准。

## Token 与会话

- 当前后端使用 Bearer Token，不依赖 Cookie，所以常规 CSRF 风险较低。
- 不要把 token 放进 URL query、页面 DOM、日志、错误弹窗或截图。
- `localStorage` 简单易用，但一旦出现 XSS 会被读取；所以 XSS 防护是当前前端安全重点。
- 收到 `401` 时清理本地 token 并跳回登录页。
- 前端路由守卫只能改善体验，不能当作权限控制。真实权限由后端接口判断。

## 文件上传

- 前端可以做体验层校验：只允许 `.jpg`、`.jpeg`、`.png`、`.pdf`，最大 `10MB`。
- 这些限制后端也会再次校验，前端不要假设绕不过去。
- 不要把用户上传的 PDF 或图片内容作为 HTML 注入页面。
- 展示文件名时用普通文本渲染，不要拼 HTML。
- 上传失败时展示 `response.data.message` 即可，不要展示堆栈、请求头或 token。

## 接口错误处理

- `401`：未登录或 token 失效，跳登录。
- `403`：访问了不属于当前用户的资源，展示“无权限访问”。
- `404`：资源不存在，返回列表页或展示空状态。
- `409`：重复提交或用户名冲突，按业务提示处理。
- `422`：表单校验错误，应高亮对应输入项。
- `500`：展示通用失败提示，不要暴露内部异常。

## 前后端协作约定

- 前端新增页面前先看 [backend/docs/api.md](../backend/docs/api.md)，不要猜字段名。
- 如果接口字段不够用，先在群里说明页面需要什么数据，不要在前端硬编码假数据绕过去。
- Agent 生成内容可能不稳定，页面要能处理空数组、空字符串、低置信度和批改失败状态。
- 与学习效果相关的“已掌握”“薄弱点”“得分”等显示，应直接来自后端字段，不在前端重复计算核心业务规则。
