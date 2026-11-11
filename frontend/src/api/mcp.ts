import client from './client'

import type {
  ApiResponse,
  McpCatalog,
  McpCreatePayload,
  McpServer,
  McpServerList,
  McpTestResult,
  McpUpdatePayload,
} from '@/types/api'

/** 内置市场清单（带「是否已接入」） */
export async function fetchCatalog(): Promise<McpCatalog> {
  const { data } = await client.get<ApiResponse<McpCatalog>>('/mcp/catalog')
  return data.data
}

/** 已接入的服务器 */
export async function fetchServers(): Promise<McpServerList> {
  const { data } = await client.get<ApiResponse<McpServerList>>('/mcp/servers')
  return data.data
}

/** 接入一台服务器（内置条目只要 slug + path，自定义条目补齐字段） */
export async function createServer(payload: McpCreatePayload): Promise<McpServer> {
  const { data } = await client.post<ApiResponse<McpServer>>('/mcp/servers', payload)
  return data.data
}

/** 启停 / 改配置 */
export async function updateServer(id: number, payload: McpUpdatePayload): Promise<McpServer> {
  const { data } = await client.patch<ApiResponse<McpServer>>(`/mcp/servers/${id}`, payload)
  return data.data
}

/** 移除并关掉连接 */
export async function deleteServer(id: number): Promise<void> {
  await client.delete(`/mcp/servers/${id}`)
}

/** 试连：连一次、列一次工具、立刻关 */
export async function testServer(id: number): Promise<McpTestResult> {
  // 起子进程要几秒，别被全局 10s 超时打断
  const { data } = await client.post<ApiResponse<McpTestResult>>(
    `/mcp/servers/${id}/test`,
    undefined,
    { timeout: 30000 },
  )
  return data.data
}
