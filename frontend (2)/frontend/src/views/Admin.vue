<template>
  <div class="admin-page">
    <PageHeader title="系统设置" subtitle="管理员专用：运行时配置与审计日志" gradient />

    <div v-if="!isAdmin" class="admin-empty">
      <el-result icon="warning" title="需要管理员权限">
        <template #sub-title>
          <span>当前账号不是管理员，无法访问系统设置</span>
        </template>
      </el-result>
    </div>

    <template v-else>
      <el-tabs v-model="activeTab" class="admin-tabs">
        <!-- ============= 标签：运行时配置 ============= -->
        <el-tab-pane label="运行时配置" name="config">
          <el-alert
            type="warning"
            :closable="false"
            class="admin-warn"
            title="修改将立即生效，并写入数据库与审计日志"
            description="API Key 加密存储；模型与 base_url 改动后，下次 LLM 调用即生效，无需重启服务。"
          />

          <el-skeleton v-if="loadingConfig" :rows="8" animated />

          <template v-else>
            <section class="config-section">
              <h3 class="section-title">LLM 配置</h3>
              <el-form :model="config" label-width="140px" class="config-form">
                <el-form-item label="API Key">
                  <el-input
                    v-model="config.openai_api_key"
                    type="password"
                    show-password
                    placeholder="sk-..."
                    clearable
                  />
                </el-form-item>
                <el-form-item label="Base URL">
                  <el-input
                    v-model="config.openai_base_url"
                    placeholder="https://api.openai.com/v1"
                    clearable
                  />
                </el-form-item>
                <el-form-item label="模型">
                  <el-input
                    v-model="config.openai_model"
                    placeholder="例如 gpt-4o / gpt-4o-mini / gpt-5.5"
                    clearable
                  />
                </el-form-item>
                <el-form-item label="推理强度">
                  <el-select v-model="config.openai_reasoning_effort">
                    <el-option v-for="opt in REASONING_OPTIONS" :key="opt" :label="opt" :value="opt" />
                  </el-select>
                </el-form-item>
                <el-form-item label="响应存储">
                  <el-switch
                    v-model="config.openai_disable_response_storage"
                    active-text="禁用"
                    inactive-text="允许"
                  />
                </el-form-item>
                <el-form-item label="超时（秒）">
                  <el-input-number v-model="config.openai_timeout_seconds" :min="10" :max="600" :step="10" />
                </el-form-item>
              </el-form>
            </section>

            <section class="config-section">
              <h3 class="section-title">业务参数</h3>
              <el-form :model="config" label-width="200px" class="config-form">
                <el-form-item label="复习置信度阈值">
                  <el-slider
                    v-model="config.review_confidence_threshold"
                    :min="0" :max="1" :step="0.05"
                    show-input
                    :show-input-controls="false"
                  />
                </el-form-item>
                <el-form-item label="最大上传体积（MB）">
                  <el-input-number v-model="config.max_upload_mb" :min="1" :max="200" />
                </el-form-item>
                <el-form-item label="PDF 最大页数">
                  <el-input-number v-model="config.max_pdf_pages" :min="1" :max="100" />
                </el-form-item>
                <el-form-item label="续期阈值（分钟）">
                  <el-input-number v-model="config.token_refresh_threshold_minutes" :min="0" :max="240" />
                </el-form-item>
                <el-form-item label="PoW 有效期（秒）">
                  <el-input-number v-model="config.pow_challenge_ttl_seconds" :min="30" :max="600" />
                </el-form-item>
                <el-form-item label="PoW 难度">
                  <el-input-number v-model="config.pow_difficulty" :min="0" :max="6" />
                </el-form-item>
              </el-form>
            </section>

            <div class="action-bar">
              <el-button type="primary" :loading="savingConfig" @click="saveConfig">
                保存全部配置
              </el-button>
              <el-button @click="reloadConfig">重新加载</el-button>
            </div>
          </template>
        </el-tab-pane>

        <!-- ============= 标签：审计日志 ============= -->
        <el-tab-pane :label="`审计日志（${auditTotal}）`" name="audit">
          <section class="config-section">
            <h3 class="section-title">筛选</h3>
            <el-form :model="auditFilter" label-width="100px" inline class="audit-filter">
              <el-form-item label="事件类型">
                <el-input
                  v-model="auditFilter.event_type"
                  placeholder="精确匹配，如 assignment.uploaded"
                  clearable
                  style="width: 220px"
                />
              </el-form-item>
              <el-form-item label="操作者">
                <el-input
                  v-model="auditFilter.actor_username"
                  placeholder="用户名精确匹配"
                  clearable
                  style="width: 180px"
                />
              </el-form-item>
              <el-form-item label="结果">
                <el-select
                  v-model="auditFilter.outcome"
                  clearable
                  placeholder="全部"
                  style="width: 140px"
                >
                  <el-option label="成功" value="success" />
                  <el-option label="失败" value="failure" />
                </el-select>
              </el-form-item>
              <el-form-item label=" ">
                <el-button type="primary" :icon="Search" @click="reloadAudit">查询</el-button>
                <el-button :icon="RefreshLeft" @click="resetAudit">重置</el-button>
                <el-button :icon="Download" @click="exportAuditCsv">导出 CSV</el-button>
              </el-form-item>
            </el-form>
          </section>

          <section class="config-section">
            <div class="audit-table-head">
              <h3 class="section-title">事件记录</h3>
              <span class="audit-paging-info">
                共 {{ auditTotal }} 条 · 第 {{ auditPage }} 页 / {{ auditTotalPages || 1 }}
              </span>
            </div>
            <el-skeleton v-if="loadingAudit" :rows="6" animated />

            <el-table
              v-else
              :data="auditRows"
              stripe
              border
              size="small"
              empty-text="没有匹配的审计记录"
              class="audit-table"
            >
              <el-table-column type="expand">
                <template #default="{ row }">
                  <div class="audit-detail">
                    <div class="audit-detail-row">
                      <span class="label">ID</span>
                      <span class="value">#{{ row.id }}</span>
                    </div>
                    <div class="audit-detail-row">
                      <span class="label">摘要</span>
                      <span class="value">{{ row.summary || '—' }}</span>
                    </div>
                    <div class="audit-detail-row">
                      <span class="label">资源</span>
                      <span class="value">
                        {{ row.resource_type || '—' }}
                        <template v-if="row.resource_id">#{{ row.resource_id }}</template>
                      </span>
                    </div>
                    <div class="audit-detail-row">
                      <span class="label">元数据</span>
                      <pre class="audit-meta">{{ formatJson(row.metadata) }}</pre>
                    </div>
                    <div v-if="row.error_message" class="audit-detail-row">
                      <span class="label">错误</span>
                      <span class="value error-text">{{ row.error_message }}</span>
                    </div>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="时间" width="170" prop="created_at">
                <template #default="{ row }">
                  <span class="time-cell">{{ formatTime(row.created_at) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="事件" min-width="200" prop="event_type">
                <template #default="{ row }">
                  <el-tag size="small" :type="eventTagType(row.event_type)">
                    {{ row.event_type }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作者" width="160" prop="actor_username">
                <template #default="{ row }">
                  <span v-if="row.actor_username">{{ row.actor_username }}</span>
                  <span v-else-if="row.actor_user_id" class="muted">#{{ row.actor_user_id }}</span>
                  <span v-else class="muted">系统</span>
                </template>
              </el-table-column>
              <el-table-column label="结果" width="80" align="center" prop="outcome">
                <template #default="{ row }">
                  <el-tag v-if="row.outcome === 'success'" type="success" size="small">成功</el-tag>
                  <el-tag v-else-if="row.outcome === 'failure'" type="danger" size="small">失败</el-tag>
                  <el-tag v-else size="small">{{ row.outcome }}</el-tag>
                </template>
              </el-table-column>
            </el-table>

            <div class="audit-pager">
              <el-pagination
                v-model:current-page="auditPage"
                :page-size="auditPageSize"
                :total="auditTotal"
                :page-sizes="[20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                background
                @current-change="reloadAudit"
                @size-change="onAuditSizeChange"
              />
            </div>
          </section>
        </el-tab-pane>
      </el-tabs>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, RefreshLeft, Search } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { adminApi, auditApi } from '@/api'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.userInfo?.role === 'admin')

const activeTab = ref('config')

/* ====================== Config ====================== */
const REASONING_OPTIONS = ['none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']
const loadingConfig = ref(true)
const savingConfig = ref(false)
const config = ref({
  openai_api_key: '',
  openai_base_url: '',
  openai_model: '',
  openai_reasoning_effort: 'none',
  openai_disable_response_storage: true,
  openai_timeout_seconds: 120,
  review_confidence_threshold: 0.85,
  max_upload_mb: 10,
  max_pdf_pages: 10,
  token_refresh_threshold_minutes: 60,
  pow_challenge_ttl_seconds: 120,
  pow_difficulty: 4
})

function normalizeConfig(raw) {
  const next = { ...raw }
  if (!REASONING_OPTIONS.includes(next.openai_reasoning_effort)) {
    next.openai_reasoning_effort = 'none'
  }
  return next
}

async function reloadConfig() {
  loadingConfig.value = true
  try {
    const res = await adminApi.getConfig()
    config.value = normalizeConfig(res.data)
  } catch (e) {
    console.error('[Admin] load config failed', e)
  } finally {
    loadingConfig.value = false
  }
}

async function saveConfig() {
  savingConfig.value = true
  try {
    await adminApi.updateConfig(config.value)
    ElMessage.success('已保存，配置立即生效')
  } catch (e) {
    console.error('[Admin] save config failed', e)
  } finally {
    savingConfig.value = false
  }
}

/* ====================== Audit ====================== */
const EVENT_TAG_TYPES = {
  'auth.login': '', 'auth.register': '', 'auth.logout': 'info',
  'auth.login.failed': 'danger', 'auth.register.conflict': 'danger',
  'auth.profile.updated': 'info', 'auth.password.updated': 'info',
  'auth.password.update.failed': 'danger',
  'assignment.uploaded': 'success', 'assignment.grading.completed': 'success',
  'assignment.grading.failed': 'danger',
  'assignment.access.denied': 'danger', 'assignment.task.access.denied': 'danger',
  'practice.generated': 'success', 'practice.submitted': 'success',
  'exam.generated': 'success', 'exam.submitted': 'success',
  'exam.access.denied': 'danger', 'exam.submit.denied': 'danger',
  'admin.user.sessions.revoked': 'warning', 'admin.audit.exported': 'warning',
  'admin.config.updated': 'warning'
}

const loadingAudit = ref(false)
const auditRows = ref([])
const auditTotal = ref(0)
const auditPage = ref(1)
const auditPageSize = ref(20)
const auditFilter = reactive({
  event_type: '',
  actor_username: '',
  outcome: ''
})

const auditTotalPages = computed(() => Math.max(1, Math.ceil(auditTotal.value / auditPageSize.value)))

function eventTagType(eventType) {
  if (EVENT_TAG_TYPES[eventType]) return EVENT_TAG_TYPES[eventType]
  if (eventType?.includes('failed') || eventType?.includes('denied') || eventType?.includes('conflict')) return 'danger'
  if (eventType?.startsWith('admin.')) return 'warning'
  return ''
}

function formatTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function formatJson(value) {
  if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) return '—'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

async function reloadAudit() {
  loadingAudit.value = true
  try {
    const params = {
      limit: auditPageSize.value,
      offset: (auditPage.value - 1) * auditPageSize.value
    }
    if (auditFilter.event_type) params.event_type = auditFilter.event_type
    if (auditFilter.actor_username) params.actor_username = auditFilter.actor_username
    // backend only supports event_type & actor_username filters; outcome is filtered client-side
    const res = await auditApi.list(params)
    let rows = res.data?.items || []
    if (auditFilter.outcome) {
      rows = rows.filter((row) => row.outcome === auditFilter.outcome)
    }
    auditRows.value = rows
    // 后端审计接口不返回 total，用启发式：若本页条数 < pageSize 则这是末页
    const pageFilled = res.data?.items?.length === auditPageSize.value
    auditTotal.value = pageFilled
      ? auditPage.value * auditPageSize.value + 1   // 至少还有下一页
      : (auditPage.value - 1) * auditPageSize.value + rows.length
  } catch (e) {
    console.error('[Admin] load audit failed', e)
    auditRows.value = []
    auditTotal.value = 0
  } finally {
    loadingAudit.value = false
  }
}

function onAuditSizeChange(size) {
  auditPageSize.value = size
  auditPage.value = 1
  reloadAudit()
}

function resetAudit() {
  auditFilter.event_type = ''
  auditFilter.actor_username = ''
  auditFilter.outcome = ''
  auditPage.value = 1
  reloadAudit()
}

async function exportAuditCsv() {
  try {
    const params = {}
    if (auditFilter.event_type) params.event_type = auditFilter.event_type
    if (auditFilter.actor_username) params.actor_username = auditFilter.actor_username
    const blob = await auditApi.exportCsv(params)
    const url = window.URL.createObjectURL(new Blob([blob]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    ElMessage.success('已导出 CSV')
  } catch (e) {
    console.error('[Admin] export csv failed', e)
  }
}

onMounted(() => {
  if (isAdmin.value) {
    reloadConfig()
  } else {
    loadingConfig.value = false
  }
})
</script>

<style scoped lang="scss">
.admin-page {
  padding: 24px;
  max-width: 1000px;
  margin: 0 auto;
}

.admin-warn {
  margin-bottom: 24px;
}

.admin-empty {
  padding: 64px 0;
}

.admin-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 20px;
  }
}

.config-section {
  background: #fff;
  border-radius: 16px;
  padding: 24px 32px;
  margin-bottom: 24px;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.05);
}

.section-title {
  margin: 0 0 20px 0;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}

.config-form {
  :deep(.el-form-item) {
    margin-bottom: 18px;
  }
}

.action-bar {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  padding: 16px 0 32px;
}

.audit-filter {
  :deep(.el-form-item) {
    margin-bottom: 0;
    margin-right: 16px;
  }
}

.audit-table-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16px;
}

.audit-paging-info {
  font-size: 13px;
  color: #64748b;
}

.audit-table {
  font-size: 13px;
}

.time-cell {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: #475569;
}

.muted {
  color: #94a3b8;
}

.audit-detail {
  padding: 8px 4px;
  font-size: 13px;
}

.audit-detail-row {
  display: grid;
  grid-template-columns: 80px 1fr;
  gap: 12px;
  margin-bottom: 6px;
  align-items: start;
}

.audit-detail .label {
  color: #94a3b8;
  font-size: 12px;
}

.audit-detail .value {
  color: #1e293b;
  word-break: break-word;
}

.error-text {
  color: #ef4444;
}

.audit-meta {
  margin: 0;
  padding: 8px 12px;
  background: #f1f5f9;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #334155;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;
  overflow: auto;
}

.audit-pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
