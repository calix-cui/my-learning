<script setup lang="ts">
import emptyStateImage from '@/assets/empty-state.svg'
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box, Files, FolderOpened, Plus } from '@element-plus/icons-vue'

import { categoryStatistics, deleteCategory, listCategories } from '@/api/categories'
import CategoryFormDialog from '@/components/CategoryFormDialog.vue'
import StatCard from '@/components/StatCard.vue'
import type { Category, CategoryStatistic } from '@/types/api'

interface CategoryRow extends Category {
  product_count: number
}

const loading = ref(false)
const loadError = ref(false)
const rows = ref<CategoryRow[]>([])

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const editingCategory = ref<Category | null>(null)
const deletingId = ref<number | null>(null)

const categoryTotal = computed(() => rows.value.length)
const assignedProductTotal = computed(() =>
  rows.value.reduce((sum, row) => sum + row.product_count, 0),
)
const emptyCategories = computed(() => rows.value.filter((row) => row.product_count === 0))
const maxProductCount = computed(() =>
  rows.value.reduce((max, row) => Math.max(max, row.product_count), 0),
)

function countBarWidth(count: number): string {
  if (maxProductCount.value === 0) {
    return '0%'
  }
  return `${Math.max((count / maxProductCount.value) * 100, count > 0 ? 4 : 0)}%`
}
const emptyCategoryHint = computed(() => {
  if (rows.value.length === 0) {
    return '尚未创建任何分类'
  }
  if (emptyCategories.value.length === 0) {
    return '所有分类均已挂载商品'
  }
  return `「${emptyCategories.value[0].name}」等 ${emptyCategories.value.length} 个分类暂无商品`
})

/** 合并「分类列表」与「分类商品数统计」两个接口的数据 */
async function fetchRows() {
  loading.value = true
  loadError.value = false
  try {
    const [categories, statistics] = await Promise.all([listCategories(), categoryStatistics()])
    rows.value = mergeRows(categories, statistics)
  } catch {
    rows.value = []
    loadError.value = true
  } finally {
    loading.value = false
  }
}

function mergeRows(categories: Category[], statistics: CategoryStatistic[]): CategoryRow[] {
  const countMap = new Map(statistics.map((item) => [item.id, item.product_count]))
  return categories.map((category) => ({
    ...category,
    product_count: countMap.get(category.id) ?? 0,
  }))
}

function openCreate() {
  dialogMode.value = 'create'
  editingCategory.value = null
  dialogVisible.value = true
}

function openRename(row: CategoryRow) {
  dialogMode.value = 'edit'
  editingCategory.value = { id: row.id, name: row.name, create_time: row.create_time }
  dialogVisible.value = true
}

function handleSaved() {
  void fetchRows()
}

async function handleDelete(row: CategoryRow) {
  try {
    await ElMessageBox.confirm(
      `确定要删除分类「${row.name}」吗？删除后不可恢复。该分类下仍有商品时，后端会拒绝删除并提示先处理商品。`,
      '删除分类',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        confirmButtonClass: 'el-button--danger',
      },
    )
  } catch {
    return
  }

  deletingId.value = row.id
  try {
    await deleteCategory(row.id)
    ElMessage.success('删除成功')
    await fetchRows()
  } catch {
    // 分类下仍有商品时后端返回 409，错误文案已由拦截器展示
  } finally {
    deletingId.value = null
  }
}

onMounted(() => {
  void fetchRows()
})
</script>

<template>
  <div class="page">
    <section class="stat-grid">
      <StatCard label="分类总数" :value="categoryTotal" hint="覆盖全部商品分类">
        <el-icon><Files /></el-icon>
      </StatCard>
      <StatCard label="已归类商品" :value="assignedProductTotal" hint="各分类商品数之和">
        <el-icon><Box /></el-icon>
      </StatCard>
      <StatCard label="空分类" :value="emptyCategories.length" :hint="emptyCategoryHint">
        <el-icon><FolderOpened /></el-icon>
      </StatCard>
    </section>

    <section class="panel">
      <div class="panel__header">
        <div class="panel__title-group">
          <h2 class="panel__title">分类列表</h2>
          <span class="panel__meta">共 {{ categoryTotal }} 个分类</span>
        </div>
        <div class="panel__actions">
          <el-button type="primary" :icon="Plus" @click="openCreate">新增分类</el-button>
        </div>
      </div>

      <div class="panel__body">
        <el-table v-loading="loading" :data="rows" class="data-table data-table--tall" row-key="id">
          <el-table-column prop="id" label="ID" width="80" class-name="id-cell" />
          <el-table-column label="分类名称" width="440">
            <template #default="{ row }">
              <span
                class="category-name"
                :class="{ 'category-name--empty': row.product_count === 0 }"
              >
                {{ row.name }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="商品数" width="220" align="right">
            <template #default="{ row }">
              <span class="count-cell count-cell--right">
                <span class="count-cell__num">{{ row.product_count }}</span>
                <span class="count-cell__bar">
                  <span
                    class="count-cell__fill"
                    :style="{ width: countBarWidth(row.product_count) }"
                  />
                </span>
              </span>
            </template>
          </el-table-column>
          <el-table-column
            prop="create_time"
            label="创建时间"
            width="200"
            class-name="time-cell"
          />
          <el-table-column label="操作" width="204" align="center">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button link type="primary" @click="openRename(row)">改名</el-button>
                <span class="row-actions__divider" />
                <el-button
                  link
                  type="danger"
                  :loading="deletingId === row.id"
                  @click="handleDelete(row)"
                >
                  删除
                </el-button>
              </div>
            </template>
          </el-table-column>

          <template #empty>
            <el-empty v-if="loadError" description="数据加载失败，请稍后重试" :image-size="96">
              <el-button :loading="loading" @click="fetchRows">重新加载</el-button>
            </el-empty>
            <el-empty v-else :image="emptyStateImage" :image-size="120">
              <template #description>
                <p class="empty-state__title">还没有分类</p>
                <p class="empty-state__sub">创建分类后即可在商品中归类</p>
              </template>
              <el-button type="primary" :icon="Plus" @click="openCreate">新增分类</el-button>
            </el-empty>
          </template>
        </el-table>
      </div>

      <div class="table-footer">
        <span class="table-footer__total">共 {{ categoryTotal }} 条</span>
      </div>
    </section>

    <CategoryFormDialog
      v-model="dialogVisible"
      :mode="dialogMode"
      :category="editingCategory"
      @success="handleSaved"
    />
  </div>
</template>
