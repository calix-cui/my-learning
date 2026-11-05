<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Box, Files, Plus, Refresh, Search } from '@element-plus/icons-vue'

import emptyStateImage from '@/assets/empty-state.svg'
import { countProducts, deleteProduct, listProducts } from '@/api/products'
import { listCategories } from '@/api/categories'
import ProductFormDialog from '@/components/ProductFormDialog.vue'
import StatCard from '@/components/StatCard.vue'
import type { Category, ProductListItem } from '@/types/api'

/** 关键词输入值与实际生效的筛选值分开，只有回车或点查询才生效 */
const keywordInput = ref('')
const keyword = ref('')
const categoryId = ref<number | undefined>(undefined)

const loading = ref(false)
const loadError = ref(false)
const items = ref<ProductListItem[]>([])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const productTotal = ref(0)
const categories = ref<Category[]>([])

const dialogVisible = ref(false)
/** null 表示新增，数字表示正在编辑的商品 ID */
const editingId = ref<number | null>(null)
const deletingId = ref<number | null>(null)

const dialogMode = computed<'create' | 'edit'>(() => (editingId.value === null ? 'create' : 'edit'))
const hasFilter = computed(() => keyword.value.length > 0 || categoryId.value !== undefined)

const categoryName = computed(
  () => categories.value.find((item) => item.id === categoryId.value)?.name ?? '',
)

/** 当前生效的筛选条件描述，用于统计卡与搜索区右侧提示 */
const filterHint = computed(() => {
  const parts: string[] = []
  if (keyword.value) {
    parts.push(`关键词「${keyword.value}」`)
  }
  if (categoryId.value !== undefined) {
    parts.push(`分类「${categoryName.value}」`)
  }
  return parts.length > 0 ? parts.join(' · ') : '未使用筛选条件'
})

const listMeta = computed(() =>
  hasFilter.value ? `筛选结果 ${total.value} 件` : `共 ${total.value} 件商品`,
)

/** 价格统一展示为 ¥ + 两位小数（后端本身返回两位小数字符串） */
function formatPrice(price: string): string {
  const value = Number(price)
  return Number.isFinite(value) ? `¥${value.toFixed(2)}` : `¥${price}`
}

/** 库存数字配色：0 危险色、1~20 警告色，其余正文色（对齐设计规范） */
function stockClass(stock: number): string {
  if (stock === 0) {
    return 'stock-cell stock-cell--zero'
  }
  if (stock <= 20) {
    return 'stock-cell stock-cell--low'
  }
  return 'stock-cell'
}

/** 拉取当前分页数据；若当前页已被删空则自动回退到最后一页 */
async function fetchList() {
  loading.value = true
  loadError.value = false
  try {
    const query = {
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      category_id: categoryId.value,
    }
    let data = await listProducts(query)
    if (data.items.length === 0 && data.total > 0 && page.value > 1) {
      page.value = Math.max(1, Math.ceil(data.total / pageSize.value))
      data = await listProducts({ ...query, page: page.value })
    }
    items.value = data.items
    total.value = data.total
  } catch {
    // 拦截器已提示具体错误，这里只兜底表格状态
    items.value = []
    total.value = 0
    loadError.value = true
  } finally {
    loading.value = false
  }
}

/** 顶部统计：商品总数与分类数 */
async function fetchOverview() {
  try {
    const [count, categoryList] = await Promise.all([countProducts(), listCategories()])
    productTotal.value = count.total
    categories.value = categoryList
  } catch {
    // 统计信息失败不阻塞列表展示，错误提示已由拦截器完成
  }
}

function refreshAll() {
  void fetchList()
  void fetchOverview()
}

function handleSearch() {
  keyword.value = keywordInput.value.trim()
  page.value = 1
  void fetchList()
}

function handleReset() {
  keywordInput.value = ''
  keyword.value = ''
  categoryId.value = undefined
  page.value = 1
  void fetchList()
}

function handleCategoryChange() {
  page.value = 1
  void fetchList()
}

function handlePageChange(next: number) {
  page.value = next
  void fetchList()
}

function handlePageSizeChange(size: number) {
  pageSize.value = size
  page.value = 1
  void fetchList()
}

function openCreate() {
  editingId.value = null
  dialogVisible.value = true
}

function openEdit(row: ProductListItem) {
  editingId.value = row.id
  dialogVisible.value = true
}

/** 新增后回到第一页，编辑后停留在当前页 */
function handleSaved(mode: 'create' | 'edit') {
  if (mode === 'create') {
    page.value = 1
  }
  refreshAll()
}

async function handleDelete(row: ProductListItem) {
  try {
    await ElMessageBox.confirm(`确定要删除商品「${row.name}」吗？删除后不可恢复。`, '删除商品', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    })
  } catch {
    return
  }

  deletingId.value = row.id
  try {
    await deleteProduct(row.id)
    ElMessage.success('删除成功')
    // 删除的是当前页最后一条且不是第一页时，自动回上一页
    if (items.value.length === 1 && page.value > 1) {
      page.value -= 1
    }
    await Promise.all([fetchList(), fetchOverview()])
  } catch {
    // 失败提示已由拦截器完成
  } finally {
    deletingId.value = null
  }
}

onMounted(() => {
  refreshAll()
})
</script>

<template>
  <div class="page">
    <section class="stat-grid">
      <StatCard label="商品总数" :value="productTotal" hint="全部商品记录">
        <el-icon><Box /></el-icon>
      </StatCard>
      <StatCard label="分类数" :value="categories.length" hint="已维护的商品分类">
        <el-icon><Files /></el-icon>
      </StatCard>
      <StatCard label="当前筛选结果" :value="total" :hint="filterHint" tone="primary">
        <el-icon><Search /></el-icon>
      </StatCard>
    </section>

    <section class="panel panel--search">
      <div class="search-bar">
        <el-input
          v-model="keywordInput"
          class="search-bar__input"
          :prefix-icon="Search"
          clearable
          placeholder="搜索商品名称，回车查询"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select
          v-model="categoryId"
          class="search-bar__select"
          clearable
          placeholder="全部分类"
          @change="handleCategoryChange"
        >
          <el-option
            v-for="item in categories"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          />
        </el-select>
        <el-button type="primary" :loading="loading" @click="handleSearch">查询</el-button>
        <el-button :disabled="loading" @click="handleReset">重置</el-button>
        <span class="search-bar__hint">
          {{ hasFilter ? `已筛选：${filterHint}` : '支持按商品名称模糊搜索，回车即可查询' }}
        </span>
      </div>
    </section>

    <section class="panel">
      <div class="panel__header">
        <div class="panel__title-group">
          <h2 class="panel__title">商品列表</h2>
          <span class="panel__meta">{{ listMeta }}</span>
        </div>
        <div class="panel__actions">
          <el-button :icon="Refresh" circle :loading="loading" title="刷新" @click="refreshAll" />
          <el-button type="primary" :icon="Plus" @click="openCreate">新增商品</el-button>
        </div>
      </div>

      <div class="panel__body">
        <el-table v-loading="loading" :data="items" class="data-table" row-key="id">
          <el-table-column prop="id" label="ID" width="72" class-name="id-cell" />
          <el-table-column prop="name" label="商品名称" width="308" show-overflow-tooltip />
          <el-table-column
            prop="category_name"
            label="分类"
            width="104"
            show-overflow-tooltip
          />
          <el-table-column label="价格" width="116" align="right">
            <template #default="{ row }">
              <span class="price-cell">{{ formatPrice(row.price) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="库存" width="96" align="right">
            <template #default="{ row }">
              <span :class="stockClass(row.stock)">{{ row.stock }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="104" align="center">
            <template #default="{ row }">
              <el-tag
                :type="row.shelf_status ? 'success' : 'info'"
                effect="plain"
                class="status-tag"
                :class="row.shelf_status ? 'status-tag--success' : 'status-tag--info'"
              >
                {{ row.shelf_status ? '上架' : '下架' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="create_time"
            label="创建时间"
            width="180"
            class-name="time-cell"
          />
          <el-table-column label="操作" width="164" align="center">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
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
            <el-button :loading="loading" @click="refreshAll">重新加载</el-button>
          </el-empty>
          <el-empty v-else :image="emptyStateImage" :image-size="120">
            <template #description>
              <p class="empty-state__title">
                {{ hasFilter ? '没有符合条件的商品' : '还没有商品' }}
              </p>
              <p class="empty-state__sub">
                {{
                  hasFilter
                    ? `试试更换关键词，或清空筛选条件查看全部 ${productTotal} 件商品`
                    : '点击右上角「新增商品」创建第一件商品'
                }}
              </p>
            </template>
            <el-button v-if="hasFilter" :icon="Refresh" @click="handleReset">清空筛选</el-button>
            <el-button v-else type="primary" :icon="Plus" @click="openCreate">新增商品</el-button>
          </el-empty>
        </template>
        </el-table>
      </div>

      <div class="table-footer">
        <span class="table-footer__total">共 {{ total }} 条</span>
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          background
          layout="sizes, prev, pager, next"
          @current-change="handlePageChange"
          @size-change="handlePageSizeChange"
        />
      </div>
    </section>

    <ProductFormDialog
      v-model="dialogVisible"
      :mode="dialogMode"
      :product-id="editingId"
      :categories="categories"
      @success="handleSaved"
    />
  </div>
</template>
