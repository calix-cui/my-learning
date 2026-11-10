/**
 * 确认弹窗的命令式 API：`await confirmDialog({...})`。
 *
 * 状态放在模块里、宿主组件只管渲染，调用点就不用各自写一份 el-dialog。
 * 取消时 reject，调用方用 try/catch 或 `.catch()` 吞掉即可。
 */
import { reactive, readonly } from 'vue'

export interface PromptOptions {
  label?: string
  value?: string
  placeholder?: string
  /** 返回 true 表示通过；返回字符串会显示在输入框下方 */
  validator?: (value: string) => true | string
}

export interface MessageBoxOptions {
  title: string
  description?: string
  confirmText?: string
  cancelText?: string
  /** true 时主按钮用危险色（删除、注销这类不可逆操作） */
  danger?: boolean
  input?: PromptOptions
}

interface MessageBoxState {
  open: boolean
  options: MessageBoxOptions | null
}

const state = reactive<MessageBoxState>({ open: false, options: null })
let settle: ((value: string | boolean) => void) | null = null
let reject: (() => void) | null = null

export const messageBoxState = readonly(state) as Readonly<MessageBoxState>

function open(options: MessageBoxOptions): Promise<string | boolean> {
  state.options = options
  state.open = true
  return new Promise((resolve, rejectPromise) => {
    settle = resolve
    reject = rejectPromise
  })
}

/** 确认框：确定返回 true，取消/关闭 reject */
export function confirmDialog(options: MessageBoxOptions): Promise<boolean> {
  return open(options) as Promise<boolean>
}

/** 输入框：确定返回输入内容，取消/关闭 reject */
export function promptDialog(
  options: MessageBoxOptions & { input: PromptOptions },
): Promise<string> {
  return open(options) as Promise<string>
}

export function confirmBox(value: string | boolean) {
  state.open = false
  state.options = null
  settle?.(value)
  settle = null
  reject = null
}

export function cancelBox() {
  state.open = false
  state.options = null
  reject?.()
  settle = null
  reject = null
}
