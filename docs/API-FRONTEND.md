# 错题Pro — 前端 API 文档

> 面向前端开发者的完整 API 参考。
> 基线：场景 1（上传批改 + 错题本）。
> 版本日期：2026-07-27

---

## 目录

- [1. 快速开始](#1-快速开始)
- [2. 认证模块](#2-认证模块)
- [3. 聊天会话与消息（场景 1 核心）](#3-聊天会话与消息场景-1-核心)
- [4. 批改模块（场景 1 核心）](#4-批改模块场景-1-核心)
- [5. 错题本（场景 1 核心）](#5-错题本场景-1-核心)
- [6. WebSocket 实时通信（场景 1 核心）](#6-websocket-实时通信场景-1-核心)
- [7. 其他模块（简略）](#7-其他模块简略)
- [8. 附录](#8-附录)

---

## 1. 快速开始

### 1.1 基础 URL

```
开发环境：http://localhost:8000/api
生产环境：由部署配置决定
```

前端项目中，`request.js` 已经封装了 axios 实例，基础路径已配置好，你只需要写相对路径（如 `/auth/login`）即可。

### 1.2 认证方式

系统使用 **JWT（JSON Web Token）** 做身份认证，分两种方式：

| 场景 | 认证方式 | 说明 |
|------|---------|------|
| HTTP 请求 | 请求头 `Authorization: Bearer {token}` | axios 拦截器已自动注入 |
| WebSocket | URL 参数 `?token={token}` | 连接时拼在 URL 上 |

**Token 从哪来？** 调用登录接口（`POST /api/auth/login`）后，响应的 `data.access_token` 就是 token。前端需要把它存到 localStorage 或 Pinia store 里。

### 1.3 统一响应格式

所有 HTTP 接口返回的 JSON 都遵循统一格式：

**成功响应：**
```json
{
  "code": 0,
  "message": "success",
  "data": { ... }  // 具体数据，可以是对象、数组或 null
}
```

**错误响应（HTTP 状态码非 200 时）：**
```json
{
  "detail": "错误描述信息"
}
```

> **新手提示**：在 axios 拦截器中，判断 `response.data.code === 0` 表示成功。错误时 HTTP 状态码是 4xx/5xx，错误信息在 `response.data.detail` 里。

### 1.4 场景 1 完整用户流程

下面是「上传作业 → 智能批改 → 查看错题」的完整流程，这也是你最需要理解的流程：

```
步骤 1：注册账号（POST /api/auth/register）
    ↓
步骤 2：登录获取 token（POST /api/auth/login）
    ↓
步骤 3：创建聊天会话（POST /api/agent/sessions）
    ↓
步骤 4：建立 WebSocket 连接（WS /api/agent/ws）
    ↓
步骤 5：上传作业图片（POST /api/agent/upload 或 POST /api/assignments）
    ↓
步骤 6：监听 WebSocket 事件，等待批改完成
    ↓
步骤 7：查看错题列表（GET /api/wrong-questions）
    ↓
步骤 8：确认待复核题目（POST /api/questions/{id}/confirm-review）
    ↓
步骤 9：给好/差评反馈（POST /api/questions/{id}/feedback）
```

下面按模块详细说明每个接口。

---

## 2. 认证模块

> 源文件：`backend/app/kernel/auth/routes.py`

### 2.1 获取 PoW 挑战

- **路径**: `GET /api/auth/pow/challenge`
- **源文件**: `backend/app/kernel/auth/routes.py:32`
- **用途**: 注册或登录前必须先获取一个 PoW（工作量证明）挑战。这是防机器人滥用的机制——你需要计算一个符合条件的 nonce 才能继续。**在注册和登录时都会用到。**
- **认证**: 不需要

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| purpose | string | 是 | 用途，只能是 `"register"` 或 `"login"` |

**请求示例：**
```
GET /api/auth/pow/challenge?purpose=register
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "challenge_id": "a1b2c3d4e5f6...",
    "purpose": "register",
    "difficulty": 4,
    "nonce_seed": "xYzAbCdEf...",
    "expires_at": "2026-07-27T12:05:00+00:00"
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 422 | 缺少 purpose 参数或值不合法 |

**前端使用提示：**

> **什么是 PoW？** 简单说就是让你的电脑做一道数学题，证明你不是机器人。拿到 `challenge_id`、`nonce_seed` 和 `difficulty` 后，你需要找到一个 `nonce`（数字），使得 `SHA256(nonce_seed + ":" + nonce)` 的前 `difficulty` 个字符都是 `0`。
>
> 听起来复杂？其实就是一个循环试错的过程，电脑很快就能算出来。

```javascript
// PoW 计算函数（可复用）
async function solvePow(nonceSeed, difficulty) {
  let nonce = 0
  const prefix = '0'.repeat(difficulty)
  while (true) {
    const text = `${nonceSeed}:${nonce}`
    // 使用 Web Crypto API 计算 SHA-256
    const msgBuffer = new TextEncoder().encode(text)
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('')
    if (hashHex.startsWith(prefix)) {
      return String(nonce)  // 找到了！
    }
    nonce++
    // 每 1000 次让出主线程，避免页面卡顿
    if (nonce % 1000 === 0) {
      await new Promise(r => setTimeout(r, 0))
    }
  }
}
```

---

### 2.2 注册

- **路径**: `POST /api/auth/register`
- **源文件**: `backend/app/kernel/auth/routes.py:38`
- **用途**: 创建新用户账号。注册成功后会自动返回 token，不需要再单独登录。**用户第一次使用系统时会用到。**
- **认证**: 不需要（但需要 PoW 挑战）

**请求参数（JSON Body）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| username | string | 是 | 用户名，3-32 位，只允许字母、数字、下划线 |
| password | string | 是 | 密码，8-72 位 |
| nickname | string | 是 | 昵称，1-64 位 |
| grade | string | 否 | 年级，如 `"高一"`、`"高三"` |
| main_subject | string | 否 | 主科，如 `"数学"`、`"英语"` |
| pow_challenge_id | string | 是 | 从 PoW 挑战接口获取的 challenge_id |
| pow_nonce | string | 是 | 你计算出来的 nonce |

**请求示例：**
```json
{
  "username": "zhangsan",
  "password": "mypassword123",
  "nickname": "张三",
  "grade": "高二",
  "main_subject": "数学",
  "pow_challenge_id": "a1b2c3d4...",
  "pow_nonce": "12345"
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user": {
      "id": 1,
      "username": "zhangsan",
      "nickname": "张三",
      "grade": "高二",
      "school": null,
      "main_subject": "数学",
      "role": "student",
      "created_at": "2026-07-27T10:00:00",
      "last_login_at": "2026-07-27T10:00:00"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 409 | 用户名已存在 |
| 400 | PoW 挑战无效或校验失败 |
| 422 | 请求参数不合法（如密码太短、用户名格式不对） |
| 429 | PoW 挑战已过期或已使用 |

**前端使用提示：**

> 注册成功后直接把 `access_token` 存起来就行了，不需要再调登录接口。注意：**第一个注册的用户会自动成为管理员**（role 为 "admin"）。

```javascript
// 完整的注册流程
async function register(formData) {
  // 1. 获取 PoW 挑战
  const challenge = await authApi.getPowChallenge('register')
  const { challenge_id, nonce_seed, difficulty } = challenge.data

  // 2. 计算 PoW
  const nonce = await solvePow(nonce_seed, difficulty)

  // 3. 提交注册
  const res = await authApi.register({
    username: formData.username,
    password: formData.password,
    nickname: formData.nickname,
    grade: formData.grade,
    pow_challenge_id: challenge_id,
    pow_nonce: nonce
  })

  // 4. 保存 token
  localStorage.setItem('token', res.data.access_token)
  return res.data.user
}
```

---

### 2.3 登录

- **路径**: `POST /api/auth/login`
- **源文件**: `backend/app/kernel/auth/routes.py:127`
- **用途**: 用户登录，获取 JWT token。**每次打开应用时会用到。**
- **认证**: 不需要（但需要 PoW 挑战）

**请求参数（JSON Body）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |
| pow_challenge_id | string | 是 | 从 PoW 挑战接口获取（purpose 为 "login"） |
| pow_nonce | string | 是 | 计算出来的 nonce |

**请求示例：**
```json
{
  "username": "zhangsan",
  "password": "mypassword123",
  "pow_challenge_id": "a1b2c3d4...",
  "pow_nonce": "67890"
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user": {
      "id": 1,
      "username": "zhangsan",
      "nickname": "张三",
      "grade": "高二",
      "school": null,
      "main_subject": "数学",
      "role": "student",
      "created_at": "2026-07-27T10:00:00",
      "last_login_at": "2026-07-27T10:05:00"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 401 | 用户名或密码错误 |
| 400 | PoW 挑战无效或校验失败 |
| 429 | PoW 挑战已过期或已使用 |

**前端使用提示：**

> 登录和注册的流程几乎一样，唯一区别是 `purpose` 参数不同。建议把 PoW 计算封装成一个通用函数。

```javascript
// 完整的登录流程
async function login(username, password) {
  // 1. 获取 PoW 挑战（注意 purpose 是 "login"）
  const challenge = await authApi.getPowChallenge('login')
  const { challenge_id, nonce_seed, difficulty } = challenge.data

  // 2. 计算 PoW
  const nonce = await solvePow(nonce_seed, difficulty)

  // 3. 提交登录
  const res = await authApi.login({
    username,
    password,
    pow_challenge_id: challenge_id,
    pow_nonce: nonce
  })

  // 4. 保存 token
  localStorage.setItem('token', res.data.access_token)
  return res.data.user
}
```

---

### 2.4 登出

- **路径**: `POST /api/auth/logout`
- **源文件**: `backend/app/kernel/auth/routes.py:166`
- **用途**: 退出登录，当前 token 会被立即作废。**用户点击"退出登录"时会用到。**
- **认证**: 需要 JWT

**请求参数：** 无

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "logged_out": true
  }
}
```

**前端使用提示：**

> 登出后记得清除本地存储的 token 和用户信息，并跳转到登录页。

```javascript
async function logout() {
  try {
    await authApi.logout()
  } finally {
    localStorage.removeItem('token')
    // 跳转到登录页
    router.push('/login')
  }
}
```

---

### 2.5 获取当前用户信息

- **路径**: `GET /api/auth/me`
- **源文件**: `backend/app/kernel/auth/routes.py:183`
- **用途**: 获取当前登录用户的详细信息。**页面初始化、显示用户头像和昵称时会用到。**
- **认证**: 需要 JWT

**请求参数：** 无

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "username": "zhangsan",
    "nickname": "张三",
    "grade": "高二",
    "school": null,
    "main_subject": "数学",
    "role": "student",
    "created_at": "2026-07-27T10:00:00",
    "last_login_at": "2026-07-27T10:05:00"
  }
}
```

**前端使用提示：**

> 通常在应用启动时（如 Pinia store 初始化）调用一次，把用户信息缓存起来。如果返回 401，说明 token 已过期，需要重新登录。

---

### 2.6 更新用户资料

- **路径**: `PUT /api/auth/me`
- **源文件**: `backend/app/kernel/auth/routes.py:188`
- **用途**: 修改用户的昵称、年级、学校、主科等信息。**个人中心页面的"编辑资料"功能会用到。**
- **认证**: 需要 JWT

**请求参数（JSON Body，所有字段可选）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| nickname | string | 否 | 昵称，1-64 位，不能为 null |
| grade | string | 否 | 年级 |
| school | string | 否 | 学校，最长 128 位 |
| main_subject | string | 否 | 主科 |

**请求示例：**
```json
{
  "nickname": "张三同学",
  "grade": "高三",
  "school": "北京市第一中学"
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "username": "zhangsan",
    "nickname": "张三同学",
    "grade": "高三",
    "school": "北京市第一中学",
    "main_subject": "数学",
    "role": "student",
    "created_at": "2026-07-27T10:00:00",
    "last_login_at": "2026-07-27T10:05:00"
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 422 | 参数不合法（如 nickname 为 null） |

---

### 2.7 修改密码

- **路径**: `PUT /api/auth/password`
- **源文件**: `backend/app/kernel/auth/routes.py:213`
- **用途**: 修改当前用户的密码。**修改成功后，所有已登录的设备都会被强制登出（token 全部失效）。**
- **认证**: 需要 JWT

**请求参数（JSON Body）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| current_password | string | 是 | 当前密码 |
| new_password | string | 是 | 新密码，8-72 位 |

**请求示例：**
```json
{
  "current_password": "oldpass123",
  "new_password": "newpass456"
}
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "updated": true
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 400 | 当前密码不正确 |

**前端使用提示：**

> 密码修改成功后，需要提示用户重新登录，因为旧 token 已经全部失效了。

---

## 3. 聊天会话与消息（场景 1 核心）

> 源文件：`backend/app/kernel/agent/routes.py`

聊天会话是整个系统的核心交互方式。用户在会话中发消息、上传作业，Agent 在会话中返回批改结果和学习建议。

### 3.1 创建会话

- **路径**: `POST /api/agent/sessions`
- **源文件**: `backend/app/kernel/agent/routes.py:32`
- **用途**: 创建一个新的聊天会话。**每次开始一次新的学习任务时（如上传一份新作业）需要创建新会话。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| title | string (query) | 否 | 会话标题，默认为 `"新对话"` |

**请求示例：**
```
POST /api/agent/sessions?title=数学作业批改
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "title": "数学作业批改",
    "created_at": "2026-07-27T10:00:00",
    "updated_at": "2026-07-27T10:00:00",
    "last_active_at": "2026-07-27T10:00:00"
  }
}
```

**前端使用提示：**

> 创建会话后，记住返回的 `id`，后面建立 WebSocket 连接和上传作业都需要用到它。

---

### 3.2 获取会话列表

- **路径**: `GET /api/agent/sessions`
- **源文件**: `backend/app/kernel/agent/routes.py:42`
- **用途**: 获取当前用户的所有聊天会话，按最近活跃时间排序。**侧边栏显示历史会话列表时会用到。**
- **认证**: 需要 JWT

**请求参数：** 无

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 2,
      "title": "英语作文批改",
      "created_at": "2026-07-27T11:00:00",
      "updated_at": "2026-07-27T11:30:00",
      "last_active_at": "2026-07-27T11:30:00"
    },
    {
      "id": 1,
      "title": "数学作业批改",
      "created_at": "2026-07-27T10:00:00",
      "updated_at": "2026-07-27T10:00:00",
      "last_active_at": "2026-07-27T10:00:00"
    }
  ]
}
```

---

### 3.3 重命名会话

- **路径**: `PATCH /api/agent/sessions/{session_id}`
- **源文件**: `backend/app/kernel/agent/routes.py:51`
- **用途**: 修改会话的标题。**用户双击会话标题进行编辑时会用到。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | int (path) | 是 | 会话 ID |
| title | string (form) | 是 | 新标题 |

**请求示例：**
```
PATCH /api/agent/sessions/1
Content-Type: application/x-www-form-urlencoded

title=高三数学期末作业
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "title": "高三数学期末作业",
    "created_at": "2026-07-27T10:00:00",
    "updated_at": "2026-07-27T10:05:00",
    "last_active_at": "2026-07-27T10:00:00"
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 404 | 会话不存在或不属于当前用户 |

**前端使用提示：**

> 注意这个接口用的是 `application/x-www-form-urlencoded` 格式（Form 表单），不是 JSON。用 axios 发送时需要这样写：

```javascript
// 重命名会话
const params = new URLSearchParams()
params.append('title', '新标题')
await request.patch(`/agent/sessions/${sessionId}`, params)
```

---

### 3.4 删除会话

- **路径**: `DELETE /api/agent/sessions/{session_id}`
- **源文件**: `backend/app/kernel/agent/routes.py:64`
- **用途**: 删除一个会话及其所有消息。**用户右键删除会话时会用到。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | int (path) | 是 | 会话 ID |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "deleted": true
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 404 | 会话不存在或不属于当前用户 |

---

### 3.5 获取消息列表

- **路径**: `GET /api/agent/sessions/{session_id}/messages`
- **源文件**: `backend/app/kernel/agent/routes.py:78`
- **用途**: 获取某个会话的历史消息。**打开会话时加载聊天记录会用到。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | int (path) | 是 | 会话 ID |
| limit | int (query) | 否 | 返回数量，默认 50，最大 200 |
| offset | int (query) | 否 | 偏移量，默认 0，用于分页 |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "session_id": 1,
      "role": "student",
      "content": "帮我批改这份作业",
      "card_type": null,
      "card_payload": null,
      "step_id": null,
      "created_at": "2026-07-27T10:01:00"
    },
    {
      "id": 2,
      "session_id": 1,
      "role": "agent",
      "content": "好的，我来帮你批改...",
      "card_type": null,
      "card_payload": null,
      "step_id": "step_abc123",
      "created_at": "2026-07-27T10:01:05"
    }
  ]
}
```

**消息角色说明：**

| role | 说明 |
|------|------|
| student | 学生（用户）发的消息 |
| agent | AI 助手的回复 |
| system | 系统消息（如上传通知） |

**特殊消息类型（card_type）：**

| card_type | 说明 |
|-----------|------|
| uploading | 作业上传通知，card_payload 包含 assignment_id 和 task_id |
| null | 普通文本消息 |

---

### 3.6 发送消息（HTTP 备用）

- **路径**: `POST /api/agent/sessions/{session_id}/messages`
- **源文件**: `backend/app/kernel/agent/routes.py:90`
- **用途**: 通过 HTTP 发送消息（WebSocket 不可用时的备用方案）。**正常情况下优先使用 WebSocket 发消息。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | int (path) | 是 | 会话 ID |
| content | string (form) | 是 | 消息内容 |

**前端使用提示：**

> 这个接口是 WebSocket 的降级方案。正常交互请使用 WebSocket（见第 6 节），响应更快、支持流式输出。

---

### 3.7 上传作业（聊天内）

- **路径**: `POST /api/agent/upload`
- **源文件**: `backend/app/kernel/agent/routes.py:109`
- **用途**: 在聊天会话中上传作业图片，系统会自动创建批改任务。**这是场景 1 的核心接口之一。**
- **认证**: 需要 JWT

**请求参数（multipart/form-data）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | File | 是 | 作业图片文件 |
| subject | string | 是 | 学科，如 `"数学"`、`"英语"` |
| title | string | 否 | 作业标题，不填则用文件名 |
| session_id | int | 否 | 关联的会话 ID，填了会自动在会话中记录上传消息 |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "assignment_id": 1,
    "task_id": "task_abc123",
    "status": "queued"
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 422 | 文件格式不支持或参数缺失 |

**前端使用提示：**

> 上传文件必须用 `FormData`，不能用 JSON。Element Plus 的 `el-upload` 组件可以很方便地处理文件上传。

```javascript
// 上传作业的完整示例
async function uploadHomework(file, subject, sessionId) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('subject', subject)
  if (sessionId) {
    formData.append('session_id', String(sessionId))
  }
  const res = await request.post('/agent/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
  return res.data  // { assignment_id, task_id, status }
}
```

---

### 3.8 事件回放

- **路径**: `GET /api/agent/sessions/{session_id}/replay`
- **源文件**: `backend/app/kernel/agent/routes.py:149`
- **用途**: 获取某个会话的 Agent 事件历史，用于断线重连后补全丢失的事件。**WebSocket 断开重连时会用到。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| session_id | int (path) | 是 | 会话 ID |
| since | string (query) | 否 | 从哪个 event_id 之后开始回放，不填则返回全部 |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "type": "plan.start",
      "step_id": null,
      "data": {},
      "event_id": "abc123",
      "timestamp": "2026-07-27T10:01:00+00:00"
    },
    {
      "type": "chat.text.delta",
      "step_id": "step_1",
      "data": {"delta": "正在分析"},
      "event_id": "def456",
      "timestamp": "2026-07-27T10:01:01+00:00"
    }
  ]
}
```

---

### 3.9 Tab 联想（工具提示）

- **路径**: `GET /api/agent/address-suggestions`
- **源文件**: `backend/app/kernel/agent/routes.py:182`
- **用途**: 在聊天输入框中按 Tab 键时，返回匹配前缀的工具列表。**这是一个辅助功能，帮助用户快速调用特定工具。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| prefix | string (query) | 否 | 工具名前缀，不填则返回全部 |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "name": "AssignmentGrading::GradeAssignment",
      "short_intent": "批改作业",
      "side_effect": "write",
      "description": "上传作业图片进行智能批改"
    }
  ]
}
```

---

## 4. 批改模块（场景 1 核心）

> 源文件：`backend/app/plugins/assignment_grading/routes.py`

### 4.1 上传作业进行批改

- **路径**: `POST /api/assignments`
- **源文件**: `backend/app/plugins/assignment_grading/routes.py:20`
- **用途**: 直接上传作业图片进行批改（不经过聊天会话）。**如果不需要在聊天中交互，可以直接用这个接口。**
- **认证**: 需要 JWT

**请求参数（multipart/form-data）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| file | File | 是 | 作业图片文件 |
| subject | string | 是 | 学科 |
| title | string | 否 | 作业标题 |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "assignment_id": 1,
    "task": {
      "id": "task_abc123",
      "status": "queued",
      "step": "queued",
      "progress": 0,
      "error_message": null
    }
  }
}
```

**与 `/api/agent/upload` 的区别：**

| 接口 | 区别 |
|------|------|
| `POST /api/agent/upload` | 在聊天会话中上传，可以指定 session_id，会自动记录消息 |
| `POST /api/assignments` | 独立上传，不关联聊天会话，适合"只批改不聊天"的场景 |

---

### 4.2 获取作业列表

- **路径**: `GET /api/assignments`
- **源文件**: `backend/app/plugins/assignment_grading/routes.py:52`
- **用途**: 获取当前用户的所有作业列表。**历史作业页面会用到。**
- **认证**: 需要 JWT

**请求参数：** 无

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "title": "高三数学周测",
      "subject": "数学",
      "status": "completed",
      "total_score": 100,
      "student_score": 85,
      "overall_comment": "整体不错，但第3题需要注意...",
      "weak_points": ["三角函数", "导数应用"],
      "created_at": "2026-07-27T10:00:00",
      "task": {
        "id": "task_abc123",
        "status": "completed",
        "step": "done",
        "progress": 100,
        "error_message": null
      }
    }
  ]
}
```

**作业状态（status）说明：**

| 状态 | 说明 |
|------|------|
| queued | 排队中，等待处理 |
| processing | 批改中 |
| completed | 批改完成 |
| failed | 批改失败 |

---

### 4.3 获取作业详情

- **路径**: `GET /api/assignments/{assignment_id}`
- **源文件**: `backend/app/plugins/assignment_grading/routes.py:63`
- **用途**: 获取作业的详细信息，包含所有题目的批改结果。**查看批改结果页面时会用到。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| assignment_id | int (path) | 是 | 作业 ID |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "title": "高三数学周测",
    "subject": "数学",
    "status": "completed",
    "total_score": 100,
    "student_score": 85,
    "overall_comment": "整体不错，但需要注意三角函数部分",
    "weak_points": ["三角函数", "导数应用"],
    "created_at": "2026-07-27T10:00:00",
    "task": {
      "id": "task_abc123",
      "status": "completed",
      "step": "done",
      "progress": 100,
      "error_message": null
    },
    "questions": [
      {
        "id": 1,
        "question_number": "1",
        "content": "已知 sin(x) = 0.5，求 x 的值",
        "student_answer": "x = 30°",
        "correct_answer": "x = 30° + 360°k 或 x = 150° + 360°k（k 为整数）",
        "question_type": "解答题",
        "knowledge_point": "三角函数",
        "score": 5,
        "max_score": 10,
        "is_correct": false,
        "explanation": "需要考虑周期性和补角情况",
        "confidence": 0.95,
        "needs_review": false,
        "confidence_warning": null,
        "created_at": "2026-07-27T10:01:00"
      }
    ]
  }
}
```

**题目字段说明：**

| 字段 | 说明 |
|------|------|
| question_number | 题号 |
| content | 题目内容 |
| student_answer | 学生的答案 |
| correct_answer | 正确答案 |
| question_type | 题型（选择题/填空题/解答题等） |
| knowledge_point | 知识点 |
| score | 得分 |
| max_score | 满分 |
| is_correct | 是否正确 |
| explanation | 解析 |
| confidence | AI 判定的置信度（0-1） |
| needs_review | 是否需要人工复核（置信度低时为 true） |
| confidence_warning | 置信度警告信息 |

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 404 | 作业不存在 |
| 403 | 无权访问（不是你的作业） |

---

### 4.4 查询任务状态

- **路径**: `GET /api/tasks/{task_id}`
- **源文件**: `backend/app/plugins/assignment_grading/routes.py:88`
- **用途**: 查询批改任务的处理进度。**上传作业后轮询批改进度时会用到。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| task_id | string (path) | 是 | 任务 ID（上传作业时返回的） |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "task_abc123",
    "status": "processing",
    "step": "grading",
    "progress": 60,
    "error_message": null
  }
}
```

**任务状态说明：**

| 状态 | 说明 |
|------|------|
| queued | 排队中 |
| processing | 处理中（step 字段显示具体步骤） |
| completed | 完成 |
| failed | 失败（error_message 有错误信息） |

**前端使用提示：**

> 如果你使用 WebSocket 连接，就不需要轮询这个接口了。WebSocket 会实时推送批改进度。只有在 WebSocket 不可用时才需要轮询。

```javascript
// 轮询任务状态的示例（备用方案）
async function pollTaskStatus(taskId, onComplete) {
  const poll = async () => {
    const res = await request.get(`/tasks/${taskId}`)
    const task = res.data
    if (task.status === 'completed') {
      onComplete(task)
    } else if (task.status === 'failed') {
      console.error('批改失败:', task.error_message)
    } else {
      setTimeout(poll, 2000)  // 每 2 秒轮询一次
    }
  }
  poll()
}
```

---

### 4.5 修改题目并重新批改

- **路径**: `PUT /api/questions/{question_id}`
- **源文件**: `backend/app/plugins/assignment_grading/routes.py:113`
- **用途**: 修改题目的内容、学生答案、正确答案或知识点，系统会重新批改该题。**用户认为 AI 判定有误，想要修正时会用到。**
- **认证**: 需要 JWT

**请求参数（JSON Body，所有字段可选）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| content | string | 否 | 题目内容 |
| student_answer | string | 否 | 学生答案 |
| correct_answer | string | 否 | 正确答案 |
| knowledge_point | string | 否 | 知识点 |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "question_number": "1",
    "content": "已知 sin(x) = 0.5，求 x 的值（0° ≤ x < 360°）",
    "student_answer": "x = 30° 或 x = 150°",
    "correct_answer": "x = 30° 或 x = 150°",
    "question_type": "解答题",
    "knowledge_point": "三角函数",
    "score": 10,
    "max_score": 10,
    "is_correct": true,
    "explanation": "在给定范围内，sin(x) = 0.5 的解为 30° 和 150°",
    "confidence": 0.98,
    "needs_review": false,
    "confidence_warning": null,
    "created_at": "2026-07-27T10:01:00"
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 404 | 题目不存在 |
| 403 | 无权修改（不是你的题目） |

---

### 4.6 给题目好/差评

- **路径**: `POST /api/questions/{question_id}/feedback`
- **源文件**: `backend/app/plugins/assignment_grading/routes.py:141`
- **用途**: 对 AI 的批改结果给出反馈（好评或差评）。**用于改进 AI 的批改质量。**
- **认证**: 需要 JWT

**请求参数（multipart/form-data）：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| question_id | int (path) | 是 | 题目 ID |
| rating | string (form) | 是 | 评分，只能是 `"good"` 或 `"bad"` |

**请求示例：**
```
POST /api/questions/1/feedback
Content-Type: application/x-www-form-urlencoded

rating=good
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "question_id": 1,
    "rating": "good"
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 400 | rating 不是 "good" 或 "bad" |
| 404 | 题目不存在 |
| 403 | 无权操作 |

**前端使用提示：**

> 这个接口用的是 form 格式，不是 JSON。可以用 Element Plus 的点赞/踩按钮来触发。

---

## 5. 错题本（场景 1 核心）

> 源文件：`backend/app/plugins/wrong_question_book/routes.py`

### 5.1 获取错题列表

- **路径**: `GET /api/wrong-questions`
- **源文件**: `backend/app/plugins/wrong_question_book/routes.py:20`
- **用途**: 获取当前用户的所有错题。**错题本主页面会用到。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| subject | string (query) | 否 | 按学科筛选，如 `"数学"` |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "id": 1,
      "subject": "数学",
      "knowledge_point": "三角函数",
      "wrong_reason": "未考虑周期性",
      "wrong_count": 2,
      "status": "unreviewed",
      "question": {
        "id": 1,
        "question_number": "1",
        "content": "已知 sin(x) = 0.5，求 x 的值",
        "student_answer": "x = 30°",
        "correct_answer": "x = 30° + 360°k 或 x = 150° + 360°k",
        "question_type": "解答题",
        "knowledge_point": "三角函数",
        "score": 5,
        "max_score": 10,
        "is_correct": false,
        "explanation": "需要考虑周期性和补角情况",
        "confidence": 0.95,
        "needs_review": false,
        "confidence_warning": null,
        "created_at": "2026-07-27T10:01:00"
      }
    }
  ]
}
```

**错题状态（status）说明：**

| 状态 | 含义 | 说明 |
|------|------|------|
| unreviewed | 未复习 | 新加入错题本的默认状态 |
| reviewing | 复习中 | 正在复习这道题 |
| mastered | 已掌握 | 已经学会了 |
| archived | 已归档 | 不再显示在主列表中 |

---

### 5.2 获取错题详情

- **路径**: `GET /api/wrong-questions/{question_id}`
- **源文件**: `backend/app/plugins/wrong_question_book/routes.py:25`
- **用途**: 获取某道错题的完整详情。**点击错题卡片查看详情时会用到。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| question_id | int (path) | 是 | 题目 ID（注意：是 question_id，不是 wrong_question 的 id） |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "wrong_question_id": 1,
    "subject": "数学",
    "knowledge_point": "三角函数",
    "wrong_reason": "未考虑周期性",
    "wrong_count": 2,
    "status": "unreviewed",
    "created_at": "2026-07-27T10:01:00",
    "question": {
      "id": 1,
      "question_number": "1",
      "content": "已知 sin(x) = 0.5，求 x 的值",
      "student_answer": "x = 30°",
      "correct_answer": "x = 30° + 360°k 或 x = 150° + 360°k",
      "question_type": "解答题",
      "knowledge_point": "三角函数",
      "score": 5,
      "max_score": 10,
      "is_correct": false,
      "explanation": "需要考虑周期性和补角情况",
      "confidence": 0.95,
      "needs_review": false,
      "confidence_warning": null,
      "created_at": "2026-07-27T10:01:00"
    }
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 404 | 错题不存在或不属于当前用户 |

---

### 5.3 更新错题状态

- **路径**: `PATCH /api/wrong-questions/{question_id}/status`
- **源文件**: `backend/app/plugins/wrong_question_book/routes.py:45`
- **用途**: 更新错题的复习状态。**用户标记"已掌握"或"开始复习"时会用到。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| question_id | int (path) | 是 | 题目 ID |
| status | string (form) | 是 | 新状态：`"unreviewed"` / `"reviewing"` / `"mastered"` / `"archived"` |

**请求示例：**
```
PATCH /api/wrong-questions/1/status
Content-Type: application/x-www-form-urlencoded

status=mastered
```

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "status": "mastered",
    "question_id": 1
  }
}
```

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 400 | 无效的状态值 |
| 404 | 错题不存在或不属于当前用户 |

---

### 5.4 确认待复核题目

- **路径**: `POST /api/questions/{question_id}/confirm-review`
- **源文件**: `backend/app/plugins/wrong_question_book/routes.py:70`
- **用途**: 当 AI 判定某题置信度较低（`needs_review = true`）时，学生确认后该题会被归档到错题本。**批改结果中出现"待复核"标记的题目需要用户确认。**
- **认证**: 需要 JWT

**请求参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| question_id | int (path) | 是 | 题目 ID |

**响应示例：**
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": 1,
    "status": "unreviewed",
    "already_archived": false
  }
}
```

**响应字段说明：**

| 字段 | 说明 |
|------|------|
| id | 错题本记录的 ID |
| status | 归档后的状态（如果原来是 needs_review，则为 "reviewing"） |
| already_archived | 是否已经在错题本中（重复确认时为 true） |

**错误码：**

| HTTP 状态码 | 说明 |
|------------|------|
| 404 | 题目不存在或无权限 |

---

## 6. WebSocket 实时通信（场景 1 核心）

> 源文件：`backend/app/kernel/agent/ws.py`

WebSocket 是系统的核心通信方式，用于实时接收 AI 的批改进度和回复。

### 6.1 连接地址

```
ws://localhost:8000/api/agent/ws?session_id={sessionId}&token={jwtToken}
```

**参数说明：**

| 参数 | 说明 |
|------|------|
| session_id | 会话 ID（必填） |
| token | JWT token（必填） |

### 6.2 完整连接代码示例

```javascript
/**
 * Agent WebSocket 连接管理器
 * 用法：
 *   const ws = new AgentWebSocket(sessionId, token)
 *   ws.on('chat.text.delta', (data) => { ... })
 *   ws.connect()
 */
class AgentWebSocket {
  constructor(sessionId, token) {
    this.sessionId = sessionId
    this.token = token
    this.ws = null
    this.listeners = {}  // 事件监听器
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 1000  // 初始重连延迟 1 秒
    this.lastEventId = null  // 用于断线重连的事件回放
  }

  // 获取 WebSocket URL
  getUrl() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/api/agent/ws?session_id=${this.sessionId}&token=${this.token}`
  }

  // 建立连接
  connect() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return  // 已经连接，不要重复连接
    }

    this.ws = new WebSocket(this.getUrl())

    // 连接成功
    this.ws.onopen = () => {
      console.log('[WS] 连接成功')
      this.reconnectAttempts = 0  // 重置重连计数
      this.reconnectDelay = 1000  // 重置重连延迟
      this._emit('connected', {})
    }

    // 收到消息
    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        const type = message.type
        const data = message.data || {}

        // 记录最新的 event_id，用于断线重连
        if (message.event_id) {
          this.lastEventId = message.event_id
        }

        // 触发对应的事件监听器
        this._emit(type, data, message)

        // 特殊处理：session.welcome 事件包含回放信息
        if (type === 'session.welcome') {
          console.log('[WS] 收到欢迎消息，回放起点:', data.replay_from_step_id)
        }
      } catch (e) {
        console.error('[WS] 解析消息失败:', e)
      }
    }

    // 连接关闭
    this.ws.onclose = (event) => {
      console.log('[WS] 连接关闭:', event.code, event.reason)
      this._emit('disconnected', { code: event.code, reason: event.reason })

      // 自动重连（除非是主动关闭或认证失败）
      if (event.code !== 1000 && event.code !== 4001) {
        this._reconnect()
      }
    }

    // 连接错误
    this.ws.onerror = (error) => {
      console.error('[WS] 连接错误:', error)
      this._emit('error', { error })
    }
  }

  // 发送消息
  send(content, tool = null) {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.error('[WS] 连接未建立，无法发送消息')
      return false
    }
    const message = {
      type: 'chat.message',
      content: content
    }
    if (tool) {
      message.tool = tool  // 可选：指定使用的工具，如 "AssignmentGrading::GradeAssignment"
    }
    this.ws.send(JSON.stringify(message))
    return true
  }

  // 取消当前操作
  cancel() {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return false
    }
    this.ws.send(JSON.stringify({ type: 'action.cancel' }))
    return true
  }

  // 关闭连接（主动关闭，不触发重连）
  close() {
    this.maxReconnectAttempts = 0  // 阻止自动重连
    if (this.ws) {
      this.ws.close(1000, '用户主动关闭')
    }
  }

  // 注册事件监听器
  on(eventType, callback) {
    if (!this.listeners[eventType]) {
      this.listeners[eventType] = []
    }
    this.listeners[eventType].push(callback)
    return this  // 支持链式调用
  }

  // 移除事件监听器
  off(eventType, callback) {
    if (!this.listeners[eventType]) return
    if (callback) {
      this.listeners[eventType] = this.listeners[eventType].filter(cb => cb !== callback)
    } else {
      delete this.listeners[eventType]
    }
  }

  // 触发事件
  _emit(eventType, data, fullMessage = null) {
    const callbacks = this.listeners[eventType] || []
    callbacks.forEach(cb => {
      try {
        cb(data, fullMessage)
      } catch (e) {
        console.error(`[WS] 事件处理器错误 (${eventType}):`, e)
      }
    })
  }

  // 断线重连
  _reconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] 重连次数超限，停止重连')
      this._emit('reconnect_failed', {})
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)  // 指数退避
    console.log(`[WS] ${delay}ms 后尝试第 ${this.reconnectAttempts} 次重连...`)

    setTimeout(() => {
      this.connect()
    }, delay)
  }
}
```

### 6.3 在 Vue 组件中使用

```javascript
import { ref, onUnmounted } from 'vue'
import { AgentWebSocket } from '@/utils/agent-ws'

export default {
  setup() {
    const messages = ref([])
    const isGrading = ref(false)
    let agentWs = null

    // 连接 WebSocket
    function connectToSession(sessionId) {
      const token = localStorage.getItem('token')
      agentWs = new AgentWebSocket(sessionId, token)

      // 监听连接成功
      agentWs.on('connected', () => {
        console.log('已连接到 Agent')
      })

      // 监听欢迎消息
      agentWs.on('session.welcome', (data) => {
        console.log('会话已建立，回放起点:', data.replay_from_step_id)
      })

      // 监听计划开始
      agentWs.on('plan.start', () => {
        isGrading.value = true
      })

      // 监听流式文本（AI 正在输出）
      agentWs.on('chat.text.delta', (data) => {
        // data.delta 是增量文本，需要追加到当前消息
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg && lastMsg.role === 'agent') {
          lastMsg.content += data.delta
        } else {
          messages.value.push({ role: 'agent', content: data.delta })
        }
      })

      // 监听工具调用（AI 正在使用工具）
      agentWs.on('plan.step.tool_call', (data) => {
        console.log('AI 正在调用工具:', data)
        // 可以显示一个 loading 提示
      })

      // 监听工具结果
      agentWs.on('plan.step.tool_result', (data) => {
        console.log('工具执行结果:', data)
      })

      // 监听计划完成
      agentWs.on('plan.done', () => {
        isGrading.value = false
        console.log('批改完成！')
      })

      // 监听记忆记录（AI 学习了新知识）
      agentWs.on('memory.recorded', (data) => {
        console.log('AI 记录了新知识:', data)
      })

      // 监听会话结束
      agentWs.on('session.end', () => {
        console.log('会话已结束')
      })

      // 监听断开连接
      agentWs.on('disconnected', (data) => {
        console.log('连接断开:', data)
      })

      // 监听重连失败
      agentWs.on('reconnect_failed', () => {
        console.error('重连失败，请刷新页面')
        // 可以弹出提示让用户手动刷新
      })

      // 建立连接
      agentWs.connect()
    }

    // 发送消息
    function sendMessage(content) {
      if (!agentWs) return
      messages.value.push({ role: 'student', content })
      agentWs.send(content)
    }

    // 上传作业
    async function uploadHomework(file, subject) {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('subject', subject)
      formData.append('session_id', String(currentSessionId.value))
      const res = await request.post('/agent/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      messages.value.push({
        role: 'student',
        content: `上传了作业：${file.name}`
      })
      return res.data
    }

    // 组件销毁时关闭连接
    onUnmounted(() => {
      if (agentWs) {
        agentWs.close()
      }
    })

    return {
      messages,
      isGrading,
      connectToSession,
      sendMessage,
      uploadHomework
    }
  }
}
```

### 6.4 客户端发送的消息格式

**发送普通消息：**
```json
{
  "type": "chat.message",
  "content": "帮我看看这道题怎么做"
}
```

**发送带工具指定的消息：**
```json
{
  "type": "chat.message",
  "content": "请批改这份作业",
  "tool": "AssignmentGrading::GradeAssignment"
}
```

**取消当前操作：**
```json
{
  "type": "action.cancel"
}
```

### 6.5 服务端推送的事件类型

以下是服务器可能推送的所有 12 种事件：

| 事件类型 | 说明 | data 字段 |
|---------|------|----------|
| `session.welcome` | 连接建立成功 | `{ "replay_from_step_id": "..." }` |
| `plan.start` | AI 开始处理计划 | `{}` |
| `plan.step.started` | 某个步骤开始 | `{ "step_id": "..." }` |
| `plan.step.tool_call` | AI 正在调用工具 | `{ "tool": "...", "args": {...} }` |
| `plan.step.tool_result` | 工具返回结果 | `{ "tool": "...", "result": {...} }` |
| `plan.step.error` | 步骤执行出错 | `{ "error": "..." }` |
| `plan.step.done` | 步骤完成 | `{ "step_id": "..." }` |
| `plan.done` | 整个计划完成 | `{}` |
| `plan.interrupt_request` | 用户请求中断 | `{ "reason": "cancel requested" }` |
| `chat.text.delta` | 流式文本增量 | `{ "delta": "正在分析..." }` |
| `memory.recorded` | AI 记录了新记忆 | `{ "content": "..." }` |
| `session.end` | 会话结束 | `{}` |

### 6.6 断线重连策略

WebSocket 连接可能因为网络问题断开。上面的 `AgentWebSocket` 类已经内置了自动重连机制：

1. **指数退避**：第一次重连等 1 秒，第二次 2 秒，第三次 4 秒...
2. **最大重试 5 次**：超过后触发 `reconnect_failed` 事件
3. **不重连的情况**：主动关闭（code 1000）或认证失败（code 4001）
4. **事件回放**：重连成功后，可以通过 `GET /api/agent/sessions/{id}/replay` 补全丢失的事件

**WebSocket 关闭码说明：**

| 代码 | 说明 |
|------|------|
| 1000 | 正常关闭 |
| 4001 | 认证失败（token 无效或已过期） |
| 其他 | 网络异常，会自动重连 |

---

## 7. 其他模块（简略）

### 7.1 学习仪表盘

> 源文件：`backend/app/plugins/learning_dashboard/routes.py`

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 获取仪表盘数据 | GET | `/api/dashboard` | 返回学习概览统计 |

---

### 7.2 学习洞察

> 源文件：`backend/app/plugins/learning_insights/routes.py`

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 获取报告 | GET | `/api/reports` | query: period(日报/周报/月报/学期报告), subject |
| 学习追踪概览 | GET | `/api/tracking/overview` | 学习进度总览 |
| 知识图谱 | GET | `/api/knowledge-graph` | query: subject |
| 复习计划 | GET | `/api/tracking/review-schedule` | query: status(pending/overdue/completed) |
| 活跃热力图 | GET | `/api/tracking/activity-heatmap` | query: days(7-30, 默认14) |
| 个人统计 | GET | `/api/profile/stats` | 学习统计数据 |
| 获取偏好设置 | GET | `/api/profile/preferences` | 用户学习偏好 |
| 更新偏好设置 | PUT | `/api/profile/preferences` | JSON body: daily_goal, review_time, difficulty, weak_reminder |

**偏好设置参数：**
- `daily_goal`: int, 5-100, 必须是 5 的倍数
- `review_time`: string, 格式 "HH:mm"
- `difficulty`: "adaptive" / "basic" / "variation" / "advanced"
- `weak_reminder`: boolean

---

### 7.3 掌握度追踪

> 源文件：`backend/app/plugins/mastery_tracking/routes.py`

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 获取掌握度 | GET | `/api/mastery` | 返回所有知识点的掌握度，按分数升序排列 |

---

### 7.4 分层练习

> 源文件：`backend/app/plugins/layered_practice/routes.py`

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 创建练习 | POST | `/api/practices` | JSON body: subject, knowledge_point, difficulty, question_count |
| 练习详情 | GET | `/api/practices/{id}` | 获取练习题目 |
| 提交答案 | POST | `/api/practices/{id}/submit` | JSON body: answers[{question_id, answer}] |

**难度选项：** `"基础补漏"` / `"同类变式"` / `"综合提升"` / `"高考真题"`

---

### 7.5 阶段考核

> 源文件：`backend/app/plugins/stage_assessment/routes.py`

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 创建考核 | POST | `/api/exams` | JSON body: subject, exam_type, knowledge_points, difficulty, question_count |
| 考核列表 | GET | `/api/exams` | 获取所有考核记录 |
| 成绩对比 | GET | `/api/exams/score-compare` | query: subject |
| 考核详情 | GET | `/api/exams/{id}` | 获取考核题目 |
| 提交考核 | POST | `/api/exams/{id}/submit` | JSON body: answers[{question_id, answer}] |

**考核类型：** `"专项小测"` / `"单元卷"` / `"模拟卷"` / `"高考专题卷"`
**难度选项：** `"基础"` / `"中等"` / `"较难"` / `"混合难度"`

---

### 7.6 审计日志（管理员）

> 源文件：`backend/app/kernel/audit/routes.py`

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 日志列表 | GET | `/api/audit-logs` | query: event_type, actor_username, limit, offset |
| 导出日志 | GET | `/api/audit-logs/export` | 返回 CSV 文件下载 |

---

### 7.7 管理后台（管理员）

> 源文件：`backend/app/kernel/admin/routes.py`

| 接口 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 用户列表 | GET | `/api/admin/users` | query: offset, limit |
| 踢出用户 | POST | `/api/admin/users/{id}/revoke-sessions` | 强制某用户下线 |
| 获取配置 | GET | `/api/admin/config` | 获取系统运行配置 |
| 更新配置 | PUT | `/api/admin/config` | 更新系统配置（如 API Key、模型等） |

**可更新的配置项：**
- `openai_api_key`: OpenAI API 密钥
- `openai_base_url`: API 基础地址
- `openai_model`: 使用的模型
- `openai_reasoning_effort`: 推理强度
- `max_upload_mb`: 最大上传文件大小
- `pow_difficulty`: PoW 难度

---

## 8. 附录

### 8.1 端点总览表

| # | 方法 | 路径 | 模块 | 认证 |
|---|------|------|------|------|
| 1 | GET | `/api/auth/pow/challenge` | 认证 | 无 |
| 2 | POST | `/api/auth/register` | 认证 | 无 + PoW |
| 3 | POST | `/api/auth/login` | 认证 | 无 + PoW |
| 4 | POST | `/api/auth/logout` | 认证 | JWT |
| 5 | GET | `/api/auth/me` | 认证 | JWT |
| 6 | PUT | `/api/auth/me` | 认证 | JWT |
| 7 | PUT | `/api/auth/password` | 认证 | JWT |
| 8 | POST | `/api/agent/sessions` | 会话 | JWT |
| 9 | GET | `/api/agent/sessions` | 会话 | JWT |
| 10 | PATCH | `/api/agent/sessions/{id}` | 会话 | JWT |
| 11 | DELETE | `/api/agent/sessions/{id}` | 会话 | JWT |
| 12 | GET | `/api/agent/sessions/{id}/messages` | 会话 | JWT |
| 13 | POST | `/api/agent/sessions/{id}/messages` | 会话 | JWT |
| 14 | POST | `/api/agent/upload` | 会话 | JWT |
| 15 | GET | `/api/agent/sessions/{id}/replay` | 会话 | JWT |
| 16 | GET | `/api/agent/address-suggestions` | 会话 | JWT |
| 17 | POST | `/api/assignments` | 批改 | JWT |
| 18 | GET | `/api/assignments` | 批改 | JWT |
| 19 | GET | `/api/assignments/{id}` | 批改 | JWT |
| 20 | GET | `/api/tasks/{task_id}` | 批改 | JWT |
| 21 | PUT | `/api/questions/{id}` | 批改 | JWT |
| 22 | POST | `/api/questions/{id}/feedback` | 批改 | JWT |
| 23 | GET | `/api/wrong-questions` | 错题本 | JWT |
| 24 | GET | `/api/wrong-questions/{id}` | 错题本 | JWT |
| 25 | PATCH | `/api/wrong-questions/{id}/status` | 错题本 | JWT |
| 26 | POST | `/api/questions/{id}/confirm-review` | 错题本 | JWT |
| 27 | WS | `/api/agent/ws` | WebSocket | token 参数 |
| 28 | GET | `/api/dashboard` | 仪表盘 | JWT |
| 29 | GET | `/api/reports` | 洞察 | JWT |
| 30 | GET | `/api/tracking/overview` | 洞察 | JWT |
| 31 | GET | `/api/knowledge-graph` | 洞察 | JWT |
| 32 | GET | `/api/tracking/review-schedule` | 洞察 | JWT |
| 33 | GET | `/api/tracking/activity-heatmap` | 洞察 | JWT |
| 34 | GET | `/api/profile/stats` | 洞察 | JWT |
| 35 | GET | `/api/profile/preferences` | 洞察 | JWT |
| 36 | PUT | `/api/profile/preferences` | 洞察 | JWT |
| 37 | GET | `/api/mastery` | 掌握度 | JWT |
| 38 | POST | `/api/practices` | 练习 | JWT |
| 39 | GET | `/api/practices/{id}` | 练习 | JWT |
| 40 | POST | `/api/practices/{id}/submit` | 练习 | JWT |
| 41 | POST | `/api/exams` | 考核 | JWT |
| 42 | GET | `/api/exams` | 考核 | JWT |
| 43 | GET | `/api/exams/score-compare` | 考核 | JWT |
| 44 | GET | `/api/exams/{id}` | 考核 | JWT |
| 45 | POST | `/api/exams/{id}/submit` | 考核 | JWT |
| 46 | GET | `/api/audit-logs` | 审计 | 管理员 |
| 47 | GET | `/api/audit-logs/export` | 审计 | 管理员 |
| 48 | GET | `/api/admin/users` | 管理 | 管理员 |
| 49 | POST | `/api/admin/users/{id}/revoke-sessions` | 管理 | 管理员 |
| 50 | GET | `/api/admin/config` | 管理 | 管理员 |
| 51 | PUT | `/api/admin/config` | 管理 | 管理员 |

### 8.2 错误码对照表

| HTTP 状态码 | 含义 | 常见原因 |
|------------|------|---------|
| 200 | 成功 | 请求正常处理 |
| 400 | 请求错误 | 参数格式不对、PoW 校验失败、密码不正确 |
| 401 | 未认证 | token 缺失、过期或无效 |
| 403 | 无权限 | 访问不属于自己的资源、非管理员访问管理接口 |
| 404 | 不存在 | 资源不存在（用户、会话、作业、题目等） |
| 409 | 冲突 | 用户名已存在、练习/考核已提交 |
| 422 | 参数不合法 | 必填字段缺失、字段格式不对、值超出范围 |
| 429 | 请求过多 | PoW 挑战已过期或已使用 |
| 500 | 服务器错误 | 后端未知异常 |

**错误响应格式：**
```json
{
  "detail": "具体错误描述"
}
```

### 8.3 TypeScript 类型定义

以下是前端常用的 TypeScript 类型定义，可以直接复制到项目中使用：

```typescript
// ===== 通用 =====
interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

// ===== 用户 =====
interface User {
  id: number
  username: string
  nickname: string
  grade: string | null
  school: string | null
  main_subject: string | null
  role: 'student' | 'admin'
  created_at: string
  last_login_at: string | null
}

interface AuthResponse {
  user: User
  access_token: string
  token_type: 'bearer'
}

// ===== 聊天会话 =====
interface ChatSession {
  id: number
  title: string
  created_at: string
  updated_at: string
  last_active_at: string | null
}

interface ChatMessage {
  id: number
  session_id: number
  role: 'student' | 'agent' | 'system'
  content: string
  card_type: string | null
  card_payload: Record<string, any> | null
  step_id: string | null
  created_at: string
}

// ===== 批改任务 =====
interface ProcessingTask {
  id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  step: string
  progress: number
  error_message: string | null
}

// ===== 作业 =====
interface Assignment {
  id: number
  title: string
  subject: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  total_score: number | null
  student_score: number | null
  overall_comment: string | null
  weak_points: string[]
  created_at: string
  task?: ProcessingTask
  questions?: Question[]
}

// ===== 题目 =====
interface Question {
  id: number
  question_number: string
  content: string
  student_answer: string | null
  correct_answer: string | null
  question_type: string | null
  knowledge_point: string | null
  score: number | null
  max_score: number | null
  is_correct: boolean | null
  explanation: string | null
  confidence: number | null
  needs_review: boolean
  confidence_warning: string | null
  created_at: string
}

// ===== 错题 =====
interface WrongQuestion {
  id: number
  subject: string
  knowledge_point: string | null
  wrong_reason: string | null
  wrong_count: number
  status: 'unreviewed' | 'reviewing' | 'mastered' | 'archived'
  question: Question
}

interface WrongQuestionDetail {
  wrong_question_id: number
  subject: string
  knowledge_point: string | null
  wrong_reason: string | null
  wrong_count: number
  status: string
  created_at: string | null
  question: Question
}

// ===== WebSocket 事件 =====
type AgentEventType =
  | 'session.welcome'
  | 'plan.start'
  | 'plan.step.started'
  | 'plan.step.tool_call'
  | 'plan.step.tool_result'
  | 'plan.step.error'
  | 'plan.step.done'
  | 'plan.done'
  | 'plan.interrupt_request'
  | 'chat.text.delta'
  | 'memory.recorded'
  | 'session.end'

interface AgentEvent {
  type: AgentEventType
  session_id: string
  step_id: string | null
  data: Record<string, any>
  event_id?: string
  timestamp?: string
}

// ===== 练习 =====
interface PracticeCreateRequest {
  subject: string
  knowledge_point: string
  difficulty: '基础补漏' | '同类变式' | '综合提升' | '高考真题'
  question_count: number
}

interface PracticeAnswerInput {
  question_id: number
  answer: string
}

interface PracticeSubmitRequest {
  answers: PracticeAnswerInput[]
}

// ===== 考核 =====
interface ExamCreateRequest {
  subject: string
  exam_type: '专项小测' | '单元卷' | '模拟卷' | '高考专题卷'
  knowledge_points: string[]
  difficulty: '基础' | '中等' | '较难' | '混合难度'
  question_count: number
}

// ===== 偏好设置 =====
interface ProfilePreferences {
  daily_goal: number | null
  review_time: string | null
  difficulty: 'adaptive' | 'basic' | 'variation' | 'advanced' | null
  weak_reminder: boolean | null
}
```

### 8.4 前端已有的 API 封装

项目中 `frontend/src/api/index.js` 已经封装了大部分接口，你可以直接使用：

```javascript
import {
  authApi,        // 认证相关
  uploadApi,      // 作业上传
  dashboardApi,   // 仪表盘
  knowledgeApi,   // 练习
  reviewApi,      // 报告
  assessmentApi,  // 考核
  trackingApi,    // 追踪
  errorBookApi,   // 错题本
  profileApi,     // 个人中心
  adminApi,       // 管理员
  auditApi        // 审计日志
} from '@/api'
```

> **注意**：目前前端的 API 封装中，部分接口的路径和后端不完全一致（如 `knowledgeApi.submitAnswer` 的路径需要确认）。使用时请以后端实际路径为准。

---

> **文档维护说明**：本文档基于后端代码自动生成，如有疑问请查看对应的源文件路径。
