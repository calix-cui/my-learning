<script setup lang="ts">
import emptyStateImage from '@/assets/empty-state.svg'
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  ArrowRight,
  Box,
  CircleCheck,
  Files,
  Refresh,
  Warning,
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { countProducts, listProducts } from '@/api/products'
import { categoryStatistics, listCategories } from '@/api/categories'
import StatCard from '@/components/StatCard.vue'
import type { Category, CategoryStatistic, ProductListItem } from '@/types/api'

const router = useRouter()

const loading = ref(false)
const loadError = ref(false)
const productTotal = ref(0)
const categories = ref<Category[]>([])
const statistics = ref<CategoryStatistic[]>([])
const recentProducts = ref<ProductListItem[]>([])
/** 概览统计与库存预警需要扫描商品列表，单页上限 100 条 */
const listedProducts = ref<ProductListItem[]>([])

const categoryTotal = computed(() => categories.value.length)
/** 各分类商品数之和，用于计算占比与平均值 */
const assignedProductTotal = computed(() =>
  statistics.value.reduce((sum, item) => sum + item.product_count, 0),
)
const averagePerCategory = computed(() => {
  if (statistics.value.length === 0) {
    return '0.0'
  }
  return (assignedProductTotal.value / statistics.value.length).toFixed(1)
})
const emptyCategories = computed(() => statistics.value.filter((item) => item.product_count === 0))
/** 分类商品数最大值，用于计算条形宽度比例 */
const maxProductCount = computed(() =>
  statistics.value.reduce((max, item) => Math.max(max, item.product_count), 0),
)

const shelfOnTotal = computed(() => listedProducts.value.filter((item) => item.shelf_status).length)
const shelfOffTotal = computed(() => Math.max(productTotal.value - shelfOnTotal.value, 0))
const shelfOnPercent = computed(() => percentOfTotal(shelfOnTotal.value))
const shelfOffPercent = computed(() => percentOfTotal(shelfOffTotal.value))
const lowStockProducts = computed(() =>
  listedProducts.value
    .filter((item) => item.stock <= 20)
    .sort((a, b) => a.stock - b.stock)
    .slice(0, 5),
)
const lowStockTotal = computed(
  () => listedProducts.value.filter((item) => item.stock <= 20).length,
)
const ringBackground = computed(() => {
  if (productTotal.value === 0) {
    return 'conic-gradient(#F3F4F6 0% 100%)'
  }
  return `conic-gradient(#10B981 0% ${shelfOnPercent.value}%, #F3F4F6 ${shelfOnPercent.value}% 100%)`
})

function percentOfTotal(count: number): string {
  if (productTotal.value === 0) {
    return '0.0'
  }
  return ((count / productTotal.value) * 100).toFixed(1)
}

function barWidth(count: number): string {
  if (maxProductCount.value === 0) {
    return '0%'
  }
  return `${Math.max((count / maxProductCount.value) * 100, count > 0 ? 2 : 0)}%`
}

function percentOf(count: number): string {
  if (assignedProductTotal.value === 0) {
    return '0.0%'
  }
  return `${((count / assignedProductTotal.value) * 100).toFixed(1)}%`
}

function formatPrice(price: string): string {
  const value = Number(price)
  return Number.isFinite(value) ? `¥${value.toFixed(2)}` : `¥${price}`
}

async function fetchOverview() {
  loading.value = true
  loadError.value = false
  try {
    const [count, categoryList, categoryStats, recentPage, productPage] = await Promise.all([
      countProducts(),
      listCategories(),
      categoryStatistics(),
      listProducts({ page: 1, page_size: 4 }),
      listProducts({ page: 1, page_size: 100 }),
    ])
    productTotal.value = count.total
    categories.value = categoryList
    statistics.value = categoryStats
    recentProducts.value = recentPage.items
    listedProducts.value = productPage.items
  } catch {
    loadError.value = true
    ElMessage.warning('概览数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

function goProductList() {
  void router.push('/products')
}

onMounted(() => {
  void fetchOverview()
})
</script>

<template>
  <div class="page">
    <section class="stat-grid stat-grid--4">
      <StatCard label="商品总数" :value="productTotal" hint="全部商品记录">
        <el-icon><Box /></el-icon>
      </StatCard>
      <StatCard label="分类数" :value="categoryTotal" hint="已维护的商品分类">
        <el-icon><Files /></el-icon>
      </StatCard>
      <StatCard
        label="上架商品"
        :value="shelfOnTotal"
        :hint="`占全部商品 ${shelfOnPercent}%`"
        tone="success"
      >
        <el-icon><CircleCheck /></el-icon>
      </StatCard>
      <StatCard
        label="下架商品"
        :value="shelfOffTotal"
        :hint="`占全部商品 ${shelfOffPercent}%`"
        tone="warning"
      >
        <el-icon><Warning /></el-icon>
      </StatCard>
    </section>

    <div class="dash-grid">
      <section class="panel">
        <div class="panel__header">
          <div class="panel__title-group">
            <h2 class="panel__title">各分类商品数</h2>
            <span class="panel__meta">按分类统计，含暂无商品的分类</span>
          </div>
          <el-button :icon="Refresh" circle :loading="loading" title="刷新" @click="fetchOverview" />
        </div>

        <div class="panel__body">
          <el-skeleton v-if="loading" :rows="4" animated />

          <el-empty v-else-if="statistics.length === 0" description="还没有分类" :image="emptyStateImage" :image-size="96">
            <el-button type="primary" @click="router.push('/categories')">去创建分类</el-button>
          </el-empty>

          <template v-else>
            <div class="distribution">
              <div v-for="item in statistics" :key="item.id" class="distribution__row">
                <span class="distribution__name" :title="item.name">{{ item.name }}</span>
                <div class="distribution__track">
                  <div class="distribution__bar" :style="{ width: barWidth(item.product_count) }" />
                </div>
                <span class="distribution__value">
                  {{ item.product_count }} 件 · {{ percentOf(item.product_count) }}
                </span>
              </div>
            </div>

            <div class="distribution__footer">
              <span>合计 {{ assignedProductTotal }} 件商品 · 平均每类 {{ averagePerCategory }} 件</span>
              <span v-if="emptyCategories.length > 0">「{{ emptyCategories[0].name }}」暂无商品</span>
              <span v-else>所有分类均已有商品</span>
            </div>
          </template>
        </div>
      </section>

      <section class="panel">
        <div class="panel__header">
          <h2 class="panel__title">上架状态分布</h2>
        </div>

        <div class="panel__body">
          <el-skeleton v-if="loading" :rows="3" animated />
          <div v-else class="shelf-ring">
            <div class="shelf-ring__chart" :style="{ background: ringBackground }">
              <div class="shelf-ring__center">
                <span class="shelf-ring__num">{{ productTotal }}</span>
                <span class="shelf-ring__label">件商品</span>
              </div>
            </div>
            <div class="shelf-ring__legend">
              <div class="legend-item">
                <span class="legend-item__dot legend-item__dot--on" />
                <span class="legend-item__num">{{ shelfOnTotal }}</span>
                <span class="legend-item__text">上架商品</span>
              </div>
              <div class="legend-item">
                <span class="legend-item__dot legend-item__dot--off" />
                <span class="legend-item__num">{{ shelfOffTotal }}</span>
                <span class="legend-item__text">下架商品</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel__header">
          <div class="panel__title-group">
            <h2 class="panel__title">库存预警</h2>
            <span class="stock-warning__badge">{{ lowStockTotal }} 个商品</span>
          </div>
          <span class="panel__meta">库存 ≤ 20</span>
        </div>

        <div class="panel__body">
          <el-skeleton v-if="loading" :rows="3" animated />
          <el-empty
            v-else-if="lowStockProducts.length === 0"
            description="暂无库存预警"
            :image-size="72"
          />
          <div v-else class="stock-warning__list">
            <div v-for="item in lowStockProducts" :key="item.id" class="stock-warning__item">
              <div class="stock-warning__info">
                <span class="stock-warning__name" :title="item.name">{{ item.name }}</span>
                <span class="stock-warning__meta">
                  {{ item.category_name }} · {{ item.shelf_status ? '上架' : '下架' }}
                </span>
              </div>
              <span
                class="stock-warning__value"
                :class="{ 'stock-warning__value--zero': item.stock === 0 }"
              >
                库存 {{ item.stock }}
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <section class="panel">
      <div class="panel__header">
        <div class="panel__title-group">
          <h2 class="panel__title">最近新增商品</h2>
          <span class="panel__meta">按创建时间倒序，展示最新 4 条</span>
        </div>
        <el-button link type="primary" @click="goProductList">
          查看全部
          <el-icon class="el-icon--right"><ArrowRight /></el-icon>
        </el-button>
      </div>

      <div class="panel__body">
        <el-table v-loading="loading" :data="recentProducts" class="data-table" row-key="id">
          <el-table-column prop="id" label="ID" width="80" class-name="id-cell" />
          <el-table-column prop="name" label="商品名称" width="400" show-overflow-tooltip />
          <el-table-column
            prop="category_name"
            label="分类"
            width="140"
            show-overflow-tooltip
          />
          <el-table-column label="价格" width="130" align="right">
            <template #default="{ row }">
              <span class="price-cell">{{ formatPrice(row.price) }}</span>
            </template>
          </el-table-column>
          <el-table-column
            prop="create_time"
            label="创建时间"
            width="260"
            class-name="time-cell"
          />
          <el-table-column label="状态" width="134" align="center">
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

          <template #empty>
            <el-empty :image="emptyStateImage" :image-size="96">
              <template #description>
                <p class="empty-state__title">还没有商品</p>
                <p class="empty-state__sub">新增商品后会在这里展示最近记录</p>
              </template>
              <el-button type="primary" @click="goProductList">去新增商品</el-button>
            </el-empty>
          </template>
        </el-table>
      </div>
    </section>
  </div>
</template>
