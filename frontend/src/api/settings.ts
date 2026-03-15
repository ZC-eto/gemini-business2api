import apiClient from './client'
import type { ProxyRuntimeResponse, ProxyTestRequest, ProxyTestResult, Settings } from '@/types/api'

export const settingsApi = {
  // 获取设置
  get: () =>
    apiClient.get<never, Settings>('/admin/settings'),

  // 更新设置
  update: (settings: Settings) =>
    apiClient.put('/admin/settings', settings),

  testProxy: (payload: ProxyTestRequest) =>
    apiClient.post<ProxyTestRequest, ProxyTestResult>('/admin/settings/proxy-test', payload),

  getProxyRuntime: () =>
    apiClient.get<never, ProxyRuntimeResponse>('/admin/settings/proxy-runtime'),
}
