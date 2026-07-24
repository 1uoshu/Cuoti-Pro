# Tickets: v1.0 后端缺失接口补全

为 Review / Tracking / Profile 三个前端页面补齐后端 API，并完成 auth/me 与 wrong-questions 的小幅增强；交付后，前端 8 个页面均能脱离 Mock 数据运行。Spec 见 `docs/specs/v1.0-missing-endpoints.md`。

工作顺序按依赖：先 T1（Tracking，纯扩展），再 T2（Profile，独立），再 T3（Auth/me，影响其他端点上下文），最后 T4（错题本）。T1/T2 之间无依赖，可并行，但工作区串行落地避免迁移冲突。

## T1. Tracking 4 端点 + 测试

**What to build：** 在 `learning_insights` 插件内落地追踪页所需的 4 个 GET 端点 —— `/api/tracking/overview`、`/api/knowledge-graph`、`/api/tracking/review-schedule`、`/api/tracking/activity-heatmap`。数据来源为 `mastery_records`、`wrong_questions`、`assignments`、`practice_tasks`、`exam_tasks`。

**Blocked by：** None — 可立即开始。

- [ ] service 函数 `get_tracking_overview / get_knowledge_graph / get_review_schedule / get_activity_heatmap` 实现并按 spec 契约返回
- [ ] `routes.py` 注册 4 个端点，沿用 `get_current_user` 与 `ok(...)`
- [ ] 测试 `tests/test_learning_insights_api.py` 追加 4 个测试：空数据返回、knowledge_graph 分档排序、review-schedule `active` 标记、heatmap level 阈值
- [ ] `pytest tests/test_learning_insights_api.py` 全绿

## T2. Profile 端点 + 偏好模型

**What to build：** 在 `learning_insights` 插件内落地 `/api/profile/stats`、`/api/profile/preferences` 的 GET / PUT。新增 `user_preferences` 表，按 `user_id` 一对一；写入校验 `daily_goal / review_time / difficulty / weak_reminder`。

**Blocked by：** None — 可立即开始。

- [ ] 新增 `app/plugins/learning_insights/models.py`：`UserPreferences` ORM
- [ ] Alembic 迁移 `20260723_0004_user_preferences.py`
- [ ] service 函数 `get_profile_stats / get_profile_preferences / update_profile_preferences` 实现
- [ ] `routes.py` 注册 3 个端点；PUT 使用 Pydantic schema 校验
- [ ] 测试：默认偏好、写入校验（边界）、stats 计算
- [ ] `pytest tests/test_learning_insights_api.py` 全绿

## T3. Auth/me 补充 created_at + last_login_at

**What to build：** 在 `users` 表新增 `last_login_at` 列，`serialize_user` 同时返回 `created_at` 与 `last_login_at`；`login` 成功路径上写入当前时间。Alembic 迁移同步。

**Blocked by：** None（独立）。

- [ ] `app/kernel/models.py`：`User` 增加 `last_login_at: Mapped[Optional[datetime]]`
- [ ] Alembic 迁移 `20260723_0005_user_last_login_at.py`
- [ ] `app/kernel/auth/services.serialize_user` 增加两个字段
- [ ] `app/kernel/auth/routes.login` 写 `last_login_at` 并 commit
- [ ] 测试 `tests/test_auth_sessions.py` 新增：注册后 `/api/auth/me` 含 `created_at`，登录后 `last_login_at` 被刷新
- [ ] `pytest tests/test_auth_sessions.py` 全绿（注意：现存 `test_first_registered_user_is_admin_and_later_users_are_students` 因测试顺序在批量运行时会失败，属于 pre-existing，本 ticket 不修）

## T4. wrong-questions 题目携带 created_at

**What to build：** 让 `assignment_grading.serializers.serialize_question` 返回 `created_at`（来自 `TimestampMixin`），无需新增字段、无迁移。

**Blocked by：** None。

- [ ] `serialize_question` 输出新增 `"created_at": question.created_at`
- [ ] 测试：现有 `test_weekly_report_aggregates_*` 与新写一个 wrong-questions 序列化测试，断言 `question.created_at` 存在
- [ ] `pytest tests/test_learning_insights_api.py tests/test_kernel_plugins.py` 全绿

## T5. 测试与代码评审

**What to build：** 跑完整测试套件 + `code-review` 双轴 review，确认改动与 spec 对齐、符合项目风格。

**Blocked by：** T1, T2, T3, T4。

- [ ] `pytest backend` 全部通过（pre-existing 失败除外）
- [ ] 在 `docs/specs/v1.0-missing-endpoints.md` 与本文件基础上运行 `/code-review`，记录结论
- [ ] 修复 review 反馈的 hard violation（基准 smell 为 judgement call）

## T6. 提交并推送到远程

**What to build：** 按 Conventional Commits 风格拆 commit，依次 push 到 `origin/main`。

**Blocked by：** T5。

- [ ] commit: `feat(backend): add tracking/profile endpoints in learning_insights plugin`
- [ ] commit: `feat(backend): persist user profile preferences`
- [ ] commit: `feat(auth): expose created_at and last_login_at on /api/auth/me`
- [ ] commit: `fix(api): include question.created_at in serializers`
- [ ] `git push origin main`
