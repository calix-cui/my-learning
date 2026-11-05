<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { createCategory, updateCategory } from '@/api/categories'
import type { Category } from '@/types/api'

const props = defineProps<{
  modelValue: boolean
  mode: 'create' | 'edit'
  category?: Category | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'success', mode: 'create' | 'edit'): void
}>()

interface CategoryForm {
  name: string
}

const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = reactive<CategoryForm>({ name: '' })

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const title = computed(() => (props.mode === 'create' ? '新增分类' : '重命名分类'))

const rules: FormRules<CategoryForm> = {
  name: [
    { required: true, message: '请输入分类名称', trigger: 'blur' },
    { min: 1, max: 50, message: '分类名称长度为 1-50 个字符', trigger: 'blur' },
  ],
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) {
      return
    }
    form.name = props.mode === 'edit' ? (props.category?.name ?? '') : ''
    formRef.value?.clearValidate()
  },
)

async function handleSubmit() {
  const instance = formRef.value
  if (!instance) {
    return
  }
  const name = form.name.trim()
  if (!name) {
    form.name = ''
    return
  }
  try {
    await instance.validate()
  } catch {
    return
  }

  submitting.value = true
  try {
    if (props.mode === 'edit' && props.category) {
      await updateCategory(props.category.id, { name })
      ElMessage.success('分类名称已更新')
      emit('success', 'edit')
    } else {
      await createCategory({ name })
      ElMessage.success('分类新增成功')
      emit('success', 'create')
    }
    visible.value = false
  } catch {
    // 重名 409 等错误由拦截器统一展示后端 message，保留弹窗便于修改
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
    width="520px"
    align-center
    :close-on-click-modal="false"
    :close-on-press-escape="!submitting"
    :show-close="!submitting"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px" label-position="right">
      <el-form-item label="分类名称" prop="name">
        <el-input
          v-model.trim="form.name"
          maxlength="50"
          show-word-limit
          placeholder="请输入分类名称"
          @keyup.enter="handleSubmit"
        />
      </el-form-item>
      <p class="form-tip">分类名称长度为 1-50 个字符，且不能与已有分类重名。</p>
    </el-form>

    <template #footer>
      <el-button :disabled="submitting" @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>
