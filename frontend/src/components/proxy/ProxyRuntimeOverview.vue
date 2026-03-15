<template>
  <div class="grid gap-3 md:grid-cols-2">
    <div
      v-for="runtime in primaryCards"
      :key="runtime.purpose"
      class="rounded-2xl border border-border bg-muted/20 px-4 py-3"
    >
      <div class="flex items-start justify-between gap-3">
        <div>
          <p class="text-sm font-medium text-foreground">{{ cardLabel(runtime.purpose) }}</p>
          <p class="mt-1 text-xs text-muted-foreground">{{ proxyRuntimeSummary(runtime) }}</p>
        </div>
        <div class="flex flex-wrap items-center justify-end gap-2">
          <span
            class="inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-medium"
            :class="proxyRuntimeBadgeClass(runtime)"
          >
            {{ proxyRuntimeBadge(runtime) }}
          </span>
          <span class="inline-flex items-center rounded-full border border-border bg-background px-3 py-1 text-[11px] font-medium text-foreground">
            {{ proxyRuntimeRouteLabel(runtime) }}
          </span>
        </div>
      </div>

      <div class="mt-3 grid gap-1 text-xs text-muted-foreground">
        <p v-if="runtime.account_id">账号：{{ runtime.account_id }}</p>
        <p v-if="runtime.proxy_url">代理：{{ runtime.proxy_url }}</p>
        <p v-if="runtime.geo?.ip">
          出口 IP：{{ runtime.geo.ip }}
          <span v-if="formatRuntimeGeoLabel(runtime)">
            · {{ formatRuntimeGeoLabel(runtime) }}
          </span>
        </p>
        <p v-if="runtime.geo?.organization">线路：{{ runtime.geo.organization }}</p>
        <p v-if="formatRuntimeLatency(runtime.latency_ms)">延迟：{{ formatRuntimeLatency(runtime.latency_ms) }}</p>
        <p v-if="runtime.resin">Resin：{{ runtime.resin.platform }} / {{ runtime.resin.account }}</p>
        <p v-if="runtime.purpose === 'auth' && authMailSummary">{{ authMailSummary }}</p>
      </div>

      <div class="mt-3 flex flex-wrap items-center gap-2 text-[11px]">
        <span
          class="inline-flex items-center rounded-full border px-3 py-1 font-medium"
          :class="proxyRuntimeRotationClass(runtime)"
        >
          {{ proxyRuntimeRotationLabel(runtime) }}
        </span>
        <span
          v-if="runtime.cooldown_remaining_seconds"
          class="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-3 py-1 font-medium text-amber-900"
        >
          冷却 {{ formatRuntimeCooldown(runtime.cooldown_remaining_seconds) }}
        </span>
      </div>

      <div class="mt-3 space-y-1 text-xs text-muted-foreground">
        <p v-if="runtime.last_rotation_reason">切换说明：{{ runtime.last_rotation_reason }}</p>
        <p v-if="runtime.cooldown_reason">冷却原因：{{ runtime.cooldown_reason }}</p>
        <p v-if="runtime.error">错误：{{ runtime.error }}</p>
        <p v-else-if="runtime.geo_error">位置探测：{{ runtime.geo_error }}</p>
        <p>更新时间：{{ formatRuntimeUpdatedAt(runtime.updated_at) }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ProxyRuntimeStatus } from '@/types/api'

const props = withDefaults(defineProps<{
  auth: ProxyRuntimeStatus
  chat: ProxyRuntimeStatus
  mail?: ProxyRuntimeStatus | null
  mailProxyEnabled?: boolean
}>(), {
  mail: null,
  mailProxyEnabled: false,
})

const primaryCards = computed(() => [props.auth, props.chat])

const authMailSummary = computed(() => (props.mailProxyEnabled ? '临时邮箱轮询：复用账户代理' : '临时邮箱轮询：直连'))

const cardLabel = (purpose: ProxyRuntimeStatus['purpose']) => {
  if (purpose === 'auth') return '账户操作代理'
  if (purpose === 'chat') return '聊天操作代理'
  return '代理状态'
}

const proxyRuntimeBadge = (status: ProxyRuntimeStatus) => {
  if (status.mode === 'proxy') return '代理中'
  if (status.mode === 'direct') return '直连'
  return '未使用'
}

const proxyRuntimeBadgeClass = (status: ProxyRuntimeStatus) => {
  if (status.mode === 'proxy') return 'border-emerald-200 bg-emerald-50 text-emerald-900'
  if (status.mode === 'direct') return 'border-sky-200 bg-sky-50 text-sky-900'
  return 'border-border bg-muted/40 text-muted-foreground'
}

const proxyRuntimeRouteLabel = (status: ProxyRuntimeStatus) => {
  if (status.mode_label) return status.mode_label
  if (status.mode === 'direct') return '直连'
  if (status.route_kind === 'resin') return 'Resin 代理'
  if (status.route_kind === 'socks') return 'SOCKS 代理'
  if (status.route_kind === 'http') return 'HTTP 代理'
  if (status.mode === 'proxy') return '代理'
  return '未使用'
}

const proxyRuntimeRotationLabel = (status: ProxyRuntimeStatus) => {
  const value = (status.last_rotation_status || 'idle').toLowerCase()
  if (value === 'success') return '已切换'
  if (value === 'failed') return '切换失败'
  if (value === 'skipped') return '未切换'
  return '未切换'
}

const proxyRuntimeRotationClass = (status: ProxyRuntimeStatus) => {
  const value = (status.last_rotation_status || 'idle').toLowerCase()
  if (value === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-900'
  if (value === 'failed') return 'border-rose-200 bg-rose-50 text-rose-900'
  return 'border-border bg-muted/40 text-muted-foreground'
}

const formatRuntimeGeoLabel = (status: ProxyRuntimeStatus) =>
  [status.geo?.country, status.geo?.region, status.geo?.city].filter(Boolean).join(' / ')

const formatRuntimeUpdatedAt = (timestamp?: number) => {
  if (!timestamp) return '未更新'
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

const formatRuntimeCooldown = (seconds?: number) => {
  const remaining = Math.max(0, Number(seconds || 0))
  if (!remaining) return ''
  if (remaining >= 3600) return `${(remaining / 3600).toFixed(1)}h`
  if (remaining >= 60) return `${Math.ceil(remaining / 60)}m`
  return `${remaining}s`
}

const formatRuntimeLatency = (latency?: number | null) => {
  if (!Number.isFinite(latency ?? Number.NaN)) return ''
  return `${latency} ms`
}

const proxyRuntimeSummary = (status: ProxyRuntimeStatus) => {
  if (status.cooldown_remaining_seconds) {
    return `当前出口处于冷却期，剩余 ${formatRuntimeCooldown(status.cooldown_remaining_seconds)}`
  }
  if (status.mode === 'proxy') {
    return status.source || '最近一次真实流量已记录'
  }
  if (status.mode === 'direct') {
    return status.note || '当前未通过代理，直接访问目标服务'
  }
  return status.note || '尚未产生实际流量'
}
</script>
