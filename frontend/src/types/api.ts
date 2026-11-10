/**
 * 与后端接口一一对应的类型定义。
 * 字段命名严格遵循 FastAPI 的返回结构（snake_case）。
 */

/** 统一响应包裹结构 */
export interface ApiResponse<T> {
  /** 业务状态码，200 表示成功 */
  code: number
  /** 提示信息，失败时为中文原因 */
  message: string
  /** 业务数据 */
  data: T
}

/** 对话消息 */
export interface ChatMessage {
  id: number
  conversation_id: number
  /** user / assistant / system */
  role: string
  content: string
  /** 生成该回复的模型；用户消息为 null */
  model: string | null
  create_time: string
}

/** 会话实体 */
export interface ChatConversation {
  id: number
  title: string
  /** 预留的多 Agent 标识，当前恒为 default */
  agent_key: string
  update_time: string
  create_time: string
}

/** 会话列表项，多一个消息条数 */
export interface ChatConversationListItem extends ChatConversation {
  message_count: number
}

/** 会话详情，带全部消息 */
export interface ChatConversationDetail extends ChatConversation {
  messages: ChatMessage[]
}

/** 会话分页响应 */
export interface ChatConversationPage {
  items: ChatConversationListItem[]
  total: number
  page: number
  page_size: number
}

/** 一问一答：发送消息的返回 */
export interface ChatExchange {
  user_message: ChatMessage
  assistant_message: ChatMessage
}

/** 当前登录用户 */
export interface AuthUser {
  id: number
  email: string
  display_name: string | null
  /** user / admin */
  role: string
  is_active: boolean
  create_time: string
  last_login_time: string | null
}

/** 一台登录设备 */
export interface LoginSession {
  id: number
  user_agent: string | null
  ip: string | null
  create_time: string
  last_seen_time: string
  expires_time: string
  /** 是否就是当前这次请求所用的会话 */
  is_current: boolean
}

/** 当前用户生效的模型配置（Key 只有末四位） */
export interface ModelSettings {
  provider: 'fake' | 'openai'
  base_url: string | null
  model: string | null
  timeout_seconds: number
  has_api_key: boolean
  api_key_hint: string | null
  /** 服务端是否配置了 APP_SECRET_KEY，决定能不能保存自定义 Key */
  can_store_api_key: boolean
  /** true = 还没保存过，当前用的是环境变量那套 */
  inherited_from_env: boolean
  update_time: string | null
}

/** 模型配置保存请求：api_key 三态——不传=不变，空串=清除 */
export interface ModelSettingsPayload {
  provider?: 'fake' | 'openai'
  base_url?: string | null
  model?: string | null
  timeout_seconds?: number
  api_key?: string
}

/** 连通性自测结果 */
export interface ModelTestResult {
  ok: boolean
  latency_ms: number
  model: string | null
  message: string
}

/** 账号里保存的外观（跨设备同步主题） */
export interface AppearanceSettings {
  theme_id: string | null
  theme_mode: 'light' | 'dark' | 'system' | null
  update_time: string | null
}
