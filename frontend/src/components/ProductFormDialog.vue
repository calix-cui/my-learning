<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { createProduct, getProduct, updateProduct } from '@/api/products'
import type { Category, ProductCreatePayload } from '@/types/api'

const props = defineProps<{
  modelValue: boolean
  mode: 'create' | 'edit'
  productId?: number | null
  categories: Category[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success', mode: 'create' | 'edit'): void
}>()

interface ProductForm {
  name: string
  category_id: number | undefined
  price: string
  stock: number
  shelf_status: boolean
}

const formRef = ref<FormInstance>()
const submitting = ref(false)
const detailLoading = ref(false)

const form = reactive<ProductForm>({
  name: '',
  category_id: undefined,
  price: '',
  stock: 0,
  shelf_status: true,
})

/** 弹窗显隐通过 v-model 双向绑定 */
const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const title = computed(() => (props.mode === 'create' ? '新增商品' : '编辑商品'))
const submitText = computed(() => (props.mode === 'create' ? '确定' : '保存'))

/** 价格校验：必填、非负、最多两位小数（与后端 decimal(10,2) 对齐） */
function validatePrice(_rule: unknown, value: unknown, callback: (error?: Error) => void) {
  const text = String(value ?? '').trim()
  if (!text) {
    callback(new Error('请输入商品价格'))
    return
  }
  if (!/^\d+(\.\d{1,2})?$/.test(text)) {
    callback(new Error('价格最多 2 位小数，且不能小于 0'))
    return
  }
  if (Number(text) > 999999.99) {
    callback(new Error('价格不能超过 999999.99'))
    return
  }
  callback()
}

const rules: FormRules<ProductForm> = {
  name: [
    { required: true, message: '请输入商品名称', trigger: 'blur' },
    { min: 1, max: 50, message: '商品名称长度为 1-50 个字符', trigger: 'blur' },
  ],
  category_id: [{ required: true, message: '请选择所属分类', trigger: 'change' }],
  price: [{ required: true, validator: validatePrice, trigger: 'blur' }],
  stock: [{ required: true, message: '请输入库存数量', trigger: 'blur' }],
}

/** 每次打开弹窗时重置表单；编辑模式再拉取最新详情回填 */
async function initialize() {
  form.name = ''
  form.category_id = undefined
  form.price = ''
  form.stock = 0
  form.shelf_status = true
  formRef.value?.clearValidate()

  if (props.mode !== 'edit' || !props.productId) {
    return
  }
  detailLoading.value = true
  try {
    const detail = await getProduct(props.productId)
    form.name = detail.name
    form.category_id = detail.category_id
    form.price = detail.price
    form.stock = detail.stock
    form.shelf_status = detail.shelf_status
  } catch {
    // 详情加载失败时拦截器已提示，关闭弹窗避免提交错误数据
    visible.value = false
  } finally {
    detailLoading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      void initialize()
    }
  },
)

async function handleSubmit() {
  const instance = formRef.value
  if (!instance) {
    return
  }
  try {
    await instance.validate()
  } catch {
    return
  }
  if (form.category_id === undefined) {
    return
  }

  const payload: ProductCreatePayload = {
    category_id: form.category_id,
    name: form.name.trim(),
    price: form.price.trim(),
    stock: form.stock,
    shelf_status: form.shelf_status,
  }

  submitting.value = true
  try {
    if (props.mode === 'edit' && props.productId) {
      await updateProduct(props.productId, payload)
      ElMessage.success('商品修改成功')
      emit('success', 'edit')
    } else {
      await createProduct(payload)
      ElMessage.success('商品新增成功')
      emit('success', 'create')
    }
    visible.value = false
  } catch {
    // 后端错误文案已由拦截器统一提示，这里保留弹窗便于用户修改
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="title"
    class="product-dialog"
    width="480px"
    align-center
    :close-on-click-modal="false"
    :close-on-press-escape="!submitting"
    :show-close="!submitting"
  >
    <el-form
      ref="formRef"
      v-loading="detailLoading"
      :model="form"
      :rules="rules"
      label-width="96px"
      label-position="right"
    >
      <el-form-item label="商品名称" prop="name">
        <el-input
          v-model.trim="form.name"
          maxlength="50"
          show-word-limit
          placeholder="请输入商品名称"
        />
      </el-form-item>

      <el-form-item label="所属分类" prop="category_id">
        <el-select v-model="form.category_id" clearable filterable placeholder="请选择所属分类">
          <el-option
            v-for="item in categories"
            :key="item.id"
            :label="item.name"
            :value="item.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="商品价格" prop="price">
        <el-input v-model.trim="form.price" placeholder="请输入价格，如 3.50" />
      </el-form-item>

      <el-form-item label="库存数量" prop="stock">
        <el-input-number
          v-model="form.stock"
          :min="0"
          :precision="0"
          :step="1"
          controls-position="right"
          class="product-form__number"
        />
      </el-form-item>

      <el-form-item label="上架状态" prop="shelf_status" class="switch-item">
        <div class="switch-line">
          <el-switch
            v-model="form.shelf_status"
            style="--el-switch-on-color: var(--pa-color-success)"
          />
          <span class="switch-label">{{ form.shelf_status ? '上架销售' : '已下架' }}</span>
        </div>
        <p class="form-tip">关闭后商品不在前台展示，仍保留在列表中</p>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button :disabled="submitting" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">
        {{ submitText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.product-form__number {
  width: 100%;
}
</style>
