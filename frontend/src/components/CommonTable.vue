<template>
  <div class="common-table">
    <!-- 头部：标题 + 操作区 -->
    <div v-if="hasHeader" class="ct-header">
      <div class="ct-title">
        <el-icon v-if="headerIcon" class="ct-title-icon"><component :is="headerIcon" /></el-icon>
        <span>{{ title }}</span>
        <el-tag
          v-if="total !== undefined"
          type="info"
          effect="plain"
          round
          size="small"
        >{{ total }} 条</el-tag>
      </div>
      <div v-if="$slots.actions" class="ct-actions">
        <slot name="actions" />
      </div>
    </div>

    <!-- 表格 -->
    <el-table
      ref="tableRef"
      :data="data"
      :loading="loading"
      stripe
      highlight-current-row
      style="width: 100%"
      :empty-text="emptyText"
      v-bind="$attrs"
    >
      <slot />
    </el-table>

    <!-- 分页器（可选） -->
    <div v-if="pagination" class="ct-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="pageSizes"
        :total="total ?? data.length"
        :layout="paginationLayout"
        background
        small
        @change="onPaginationChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, useSlots } from 'vue'

const slots = useSlots()

const props = defineProps({
  /** 表格数据 */
  data: { type: Array, required: true },
  /** 表格标题（不传则隐藏标题行） */
  title: { type: String, default: '' },
  /** 标题旁的图标 */
  headerIcon: { type: [Object, Function], default: null },
  /** 总数（传则显示标签） */
  total: { type: Number, default: undefined },
  /** 加载中 */
  loading: { type: Boolean, default: false },
  /** 空状态提示 */
  emptyText: { type: String, default: '暂无数据' },
  /** 是否启用分页 */
  pagination: { type: Boolean, default: false },
  /** 分页布局 */
  paginationLayout: { type: String, default: 'total, sizes, prev, pager, next, jumper' },
  /** 每页条数选项 */
  pageSizes: { type: Array, default: () => [10, 20, 50, 100] },
  /** 当前页（v-model） */
  modelValue: { type: Number, default: 1 },
  /** 每页条数（v-model） */
  modelValuePageSize: { type: Number, default: 10 }
})

const emit = defineEmits(['update:modelValue', 'update:modelValuePageSize', 'pagination-change'])
const tableRef = ref(null)

const hasHeader = computed(() => props.title || slots.actions)
const currentPage = ref(props.modelValue)
const pageSize = ref(props.modelValuePageSize)

function onPaginationChange(page, size) {
  currentPage.value = page
  pageSize.value = size
  emit('update:modelValue', page)
  emit('update:modelValuePageSize', size)
  emit('pagination-change', { page, size })
}
</script>

<style scoped lang="scss">
.common-table {
  background: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-lg);
  padding: 24px 28px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.3s ease;

  &:hover {
    box-shadow: var(--shadow-md);
  }
}

/* ---- 头部 ---- */
.ct-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
}

.ct-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 17px;
  font-weight: 700;
  color: var(--ink);

  .ct-title-icon {
    color: var(--accent);
    font-size: 20px;
  }
}

.ct-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* ---- 表格样式 ---- */
:deep(.el-table) {
  background: transparent;

  th.el-table__cell {
    background: rgba(99, 102, 241, 0.04) !important;
    color: var(--ink-secondary);
    font-weight: 600;
    font-size: 13px;
  }

  .el-table__row:hover > td {
    background: rgba(99, 102, 241, 0.03) !important;
  }
}

/* ---- 分页 ---- */
.ct-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--separator);
}
</style>
