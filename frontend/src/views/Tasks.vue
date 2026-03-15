<template>
  <section class="space-y-6">
    <div class="rounded-3xl border border-border bg-card px-5 py-5 shadow-sm lg:px-6">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h3 class="text-lg font-semibold text-foreground">任务中心</h3>
          <p class="mt-1 text-sm text-muted-foreground">统一查看注册、刷新、历史记录与当前代理出口状态。</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="rounded-full border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            @click="refreshTaskSnapshot"
          >
            刷新任务
          </button>
          <button
            type="button"
            class="rounded-full border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            @click="fetchProxyRuntime(true)"
          >
            刷新代理状态
          </button>
        </div>
      </div>

      <div class="mt-5">
        <ProxyRuntimeOverview
          :auth="proxyRuntimeState.auth"
          :chat="proxyRuntimeState.chat"
          :mail="proxyRuntimeState.mail"
          :mail-proxy-enabled="Boolean(settings?.basic?.mail_proxy_enabled)"
        />
      </div>
    </div>

    <div class="rounded-3xl border border-border bg-card shadow-sm">
      <div class="border-b border-border/60 px-4 lg:px-6">
        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="rounded-t-2xl px-4 py-3 text-sm font-medium transition-colors"
            :class="activeTaskTab === 'current' ? 'bg-background text-primary' : 'text-muted-foreground hover:text-foreground'"
            @click="activeTaskTab = 'current'"
          >
            当前任务
          </button>
          <button
            type="button"
            class="rounded-t-2xl px-4 py-3 text-sm font-medium transition-colors"
            :class="activeTaskTab === 'scheduled' ? 'bg-background text-primary' : 'text-muted-foreground hover:text-foreground'"
            @click="activeTaskTab = 'scheduled'"
          >
            定时任务
          </button>
          <button
            type="button"
            class="rounded-t-2xl px-4 py-3 text-sm font-medium transition-colors"
            :class="activeTaskTab === 'history' ? 'bg-background text-primary' : 'text-muted-foreground hover:text-foreground'"
            @click="activeTaskTab = 'history'"
          >
            历史记录
          </button>
        </div>
      </div>

      <div v-if="activeTaskTab === 'current'" class="space-y-4 px-4 py-5 lg:px-6">
        <div v-if="automationError" class="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {{ automationError }}
        </div>

        <div v-if="registerTask || loginTask" class="grid gap-4 xl:grid-cols-2">
          <article v-if="registerTask" class="rounded-2xl border border-border bg-muted/20 px-4 py-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="flex items-center gap-2 text-sm font-medium text-foreground">
                  <span class="h-2.5 w-2.5 rounded-full" :class="getTaskStatusIndicatorClass(registerTask)" aria-hidden="true"></span>
                  注册任务
                </div>
                <p class="mt-2 text-xs text-muted-foreground">状态：{{ formatTaskStatus(registerTask) }} · 进度：{{ registerTask.progress }}/{{ registerTask.count }}</p>
                <p class="mt-1 text-xs text-muted-foreground">成功：{{ registerTask.success_count }} · 失败：{{ registerTask.fail_count }}</p>
              </div>
              <button
                v-if="isTaskActive(registerTask)"
                type="button"
                class="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-rose-500 hover:text-rose-600"
                @click="cancelRegister(registerTask.id)"
              >
                中断
              </button>
            </div>
          </article>

          <article v-if="loginTask" class="rounded-2xl border border-border bg-muted/20 px-4 py-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="flex items-center gap-2 text-sm font-medium text-foreground">
                  <span class="h-2.5 w-2.5 rounded-full" :class="getTaskStatusIndicatorClass(loginTask)" aria-hidden="true"></span>
                  刷新任务
                </div>
                <p class="mt-2 text-xs text-muted-foreground">状态：{{ formatTaskStatus(loginTask) }} · 进度：{{ loginTask.progress }}/{{ loginTask.account_ids.length }}</p>
                <p class="mt-1 text-xs text-muted-foreground">成功：{{ loginTask.success_count }} · 失败：{{ loginTask.fail_count }}</p>
              </div>
              <button
                v-if="isTaskActive(loginTask)"
                type="button"
                class="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-rose-500 hover:text-rose-600"
                @click="cancelLogin(loginTask.id)"
              >
                中断
              </button>
            </div>
          </article>
        </div>

        <div v-if="registerTask || loginTask || registerLogs.length || loginLogs.length" class="rounded-2xl border border-border bg-muted/20 p-4">
          <div class="mb-3 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <p class="text-xs text-muted-foreground">
              {{ taskLogMode === 'summary' ? '摘要模式仅保留关键事件（开始、结束、失败、告警）。' : '详情模式显示全部日志。' }}
            </p>
            <div class="flex flex-wrap items-center gap-2">
              <button
                v-if="!taskLogsAutoFollow"
                type="button"
                class="rounded-full border border-border px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                @click="jumpTaskLogsToBottom"
              >
                回到底部
              </button>
              <button
                type="button"
                class="rounded-full px-3 py-1 text-xs font-medium transition-colors"
                :class="taskLogMode === 'summary' ? 'bg-primary text-primary-foreground' : 'border border-border text-muted-foreground hover:text-foreground'"
                @click="toggleTaskLogMode"
              >
                {{ taskLogMode === 'summary' ? '摘要模式' : '详情模式' }}
              </button>
              <button
                type="button"
                class="rounded-full border border-border px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                :disabled="!registerLogs.length && !loginLogs.length && !registerTask && !loginTask && !automationError"
                @click="clearTaskLogs"
              >
                清空日志
              </button>
            </div>
          </div>

          <div ref="taskLogsRef" class="scrollbar-slim h-[48vh] overflow-y-auto rounded-2xl border border-border bg-background px-4 py-3" @scroll="handleTaskLogsScroll">
            <div v-if="visibleRegisterLogs.length" class="space-y-2">
              <p class="text-xs font-semibold text-foreground">注册日志</p>
              <div class="space-y-1 text-[11px] text-muted-foreground">
                <div v-for="(log, index) in visibleRegisterLogs" :key="`reg-${index}`" class="font-mono">{{ formatLogLine(log) }}</div>
              </div>
            </div>
            <div v-if="visibleLoginLogs.length" class="mt-4 space-y-2">
              <p class="text-xs font-semibold text-foreground">刷新日志</p>
              <div class="space-y-1 text-[11px] text-muted-foreground">
                <div v-for="(log, index) in visibleLoginLogs" :key="`login-${index}`" class="font-mono">{{ formatLogLine(log) }}</div>
              </div>
            </div>
            <div v-if="!visibleRegisterLogs.length && !visibleLoginLogs.length" class="text-xs text-muted-foreground">
              {{ registerLogs.length || loginLogs.length ? '摘要模式下暂无关键日志，可切换到详情模式查看全部日志。' : '日志已清空，新的日志会继续显示。' }}
            </div>
          </div>
        </div>

        <div v-if="!automationError && !registerTask && !loginTask && !registerLogs.length && !loginLogs.length" class="rounded-2xl border border-border bg-muted/20 px-4 py-10 text-center text-sm text-muted-foreground">
          暂无任务，后续注册或刷新任务会在这里持续显示。
        </div>
      </div>

      <div v-else-if="activeTaskTab === 'scheduled'" class="space-y-4 px-4 py-5 lg:px-6">
        <div class="rounded-2xl border border-border bg-muted/20 px-4 py-4">
          <div class="flex items-center justify-between gap-4">
            <div>
              <p class="text-sm font-medium text-foreground">启用定时刷新</p>
              <p class="mt-1 text-xs text-muted-foreground">自动检测并一次性刷新即将过期的账号</p>
            </div>
            <button
              type="button"
              class="relative inline-flex h-5 w-10 items-center rounded-full transition-colors"
              :class="scheduledRefreshEnabled ? 'bg-primary' : 'bg-muted'"
              @click="scheduledRefreshEnabled = !scheduledRefreshEnabled"
            >
              <span class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform" :class="scheduledRefreshEnabled ? 'translate-x-5' : 'translate-x-1'"></span>
            </button>
          </div>
        </div>

        <div class="grid gap-4 xl:grid-cols-2">
          <div class="space-y-4 rounded-2xl border border-border bg-muted/20 px-4 py-4">
            <label class="block text-xs text-muted-foreground">刷新时间</label>
            <input v-model="scheduledRefreshCron" type="text" class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm" placeholder="08:00,20:00 或 */120" />
            <p class="text-xs text-muted-foreground">每日时间支持 `08:00,20:00`，固定间隔支持 `*/120`。</p>

            <label class="block text-xs text-muted-foreground">冷却时间（小时）</label>
            <input v-model.number="refreshCooldownHours" type="number" min="1" max="48" class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm" />

            <label class="block text-xs text-muted-foreground">过期刷新窗口（小时）</label>
            <input v-model.number="refreshWindowHours" type="number" min="1" max="168" class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm" />
          </div>

          <div class="space-y-4 rounded-2xl border border-border bg-muted/20 px-4 py-4">
            <div>
              <p class="text-sm font-medium text-foreground">浏览器模式</p>
              <p class="mt-1 text-xs text-muted-foreground">normal 正常窗口；silent 静默最小化；headless 无头。</p>
            </div>
            <div class="grid grid-cols-3 gap-2">
              <button type="button" class="rounded-xl border px-3 py-2 text-xs transition-colors" :class="browserMode === 'normal' ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground'" @click="browserMode = 'normal'">normal</button>
              <button type="button" class="rounded-xl border px-3 py-2 text-xs transition-colors" :class="browserMode === 'silent' ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground'" @click="browserMode = 'silent'">silent</button>
              <button type="button" class="rounded-xl border px-3 py-2 text-xs transition-colors" :class="browserMode === 'headless' ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground'" @click="browserMode = 'headless'">headless</button>
            </div>
            <div class="rounded-2xl border border-border bg-background px-4 py-3 text-xs text-muted-foreground">
              验证码等待时长、轮询间隔、单账号尝试次数等策略统一在“系统设置 → 重试”中配置。
            </div>
            <ul class="list-inside list-disc space-y-1 text-xs text-muted-foreground">
              <li>同一时间只会执行一个刷新任务，新触发会复用当前任务。</li>
              <li>达到触发条件后，会一次性处理本轮所有符合条件的账号。</li>
              <li>修改配置后立即生效，无需重启服务。</li>
            </ul>
          </div>
        </div>

        <div class="flex justify-end gap-2">
          <button
            type="button"
            class="rounded-full border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary"
            @click="loadScheduledConfig"
          >
            重置
          </button>
          <button
            type="button"
            class="rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="isSavingScheduledConfig || isLoadingScheduledConfig"
            @click="saveScheduledConfig"
          >
            保存配置
          </button>
        </div>
      </div>

      <div v-else class="space-y-4 px-4 py-5 lg:px-6">
        <div v-if="isLoadingHistory" class="flex items-center justify-center py-12 text-sm text-muted-foreground">
          正在加载历史记录...
        </div>
        <div v-else-if="taskHistory.length === 0" class="rounded-2xl border border-border bg-muted/20 px-4 py-10 text-center text-sm text-muted-foreground">
          暂无历史记录，完成的任务会显示在这里。
        </div>
        <div v-else class="space-y-3">
          <article v-for="(record, index) in taskHistory" :key="index" class="rounded-2xl border border-border bg-muted/20 px-4 py-4">
            <div class="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div>
                <div class="flex items-center gap-2 text-sm font-medium text-foreground">
                  <span class="h-2.5 w-2.5 rounded-full" :class="getHistoryStatusIndicatorClass(record)" aria-hidden="true"></span>
                  {{ record.type === 'login' ? '刷新任务' : '注册任务' }}
                </div>
                <p class="mt-2 text-xs text-muted-foreground">
                  状态：<span :class="getHistoryStatusTextClass(record)">{{ formatTaskStatus(record) }}</span>
                </p>
                <p class="mt-1 text-xs text-muted-foreground">
                  进度：{{ record.progress }}/{{ getHistoryTotal(record) }} · 成功：{{ record.success_count }} · 失败：{{ record.fail_count }}
                </p>
              </div>
              <p class="text-xs text-muted-foreground">{{ new Date(record.created_at * 1000).toLocaleString('zh-CN') }}</p>
            </div>
          </article>
        </div>

        <div class="flex justify-end">
          <button
            type="button"
            class="rounded-full border border-border px-4 py-2 text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="taskHistory.length === 0"
            @click="clearTaskHistory"
          >
            清空历史
          </button>
        </div>
      </div>
    </div>

    <ConfirmDialog
      :open="confirmDialog.open.value"
      :title="confirmDialog.title.value"
      :message="confirmDialog.message.value"
      :confirm-text="confirmDialog.confirmText.value"
      :cancel-text="confirmDialog.cancelText.value"
      @confirm="confirmDialog.confirm"
      @cancel="confirmDialog.cancel"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAccountsStore } from '@/stores/accounts'
import { useSettingsStore } from '@/stores/settings'
import ProxyRuntimeOverview from '@/components/proxy/ProxyRuntimeOverview.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import { useConfirmDialog } from '@/composables/useConfirmDialog'
import { useToast } from '@/composables/useToast'
import { accountsApi, settingsApi } from '@/api'
import type { LoginTask, ProxyRuntimePurpose, ProxyRuntimeStatus, RegisterTask } from '@/types/api'

type TaskKind = 'register' | 'login'
type TaskLogLine = { time: string; level: string; message: string }
type TaskLogMode = 'summary' | 'detail'

const TASK_LOG_MODE_KEY = 'accounts-task-log-mode'
const REGISTER_CLEAR_KEY = 'accounts-register-log-clear'
const LOGIN_CLEAR_KEY = 'accounts-login-log-clear'
const TASK_LOG_SUMMARY_KEYWORDS = ['开始', '启动', '创建', '完成', '成功', '失败', '中断', '取消', '异常', '错误', '告警', 'warning', 'error', 'critical', 'timeout', '超时', '403', '429', '验证码', 'send code', 'task started', 'task finished', 'task completed', 'task cancelled', '切换', '重试', 'retry', '跳过', 'skip']

const accountsStore = useAccountsStore()
const settingsStore = useSettingsStore()
const { settings } = storeToRefs(settingsStore)
const toast = useToast()
const confirmDialog = useConfirmDialog()

const activeTaskTab = ref<'current' | 'scheduled' | 'history'>('current')
const automationError = ref('')
const registerTask = ref<RegisterTask | null>(null)
const loginTask = ref<LoginTask | null>(null)
const lastRegisterTaskId = ref<string | null>(null)
const lastLoginTaskId = ref<string | null>(null)
const registerLogClearMarker = ref<TaskLogLine | null>(null)
const loginLogClearMarker = ref<TaskLogLine | null>(null)
const taskLogsRef = ref<HTMLDivElement | null>(null)
const taskLogsAutoFollow = ref(true)
const taskLogMode = ref<TaskLogMode>(localStorage.getItem(TASK_LOG_MODE_KEY) === 'detail' ? 'detail' : 'summary')
const taskHistory = ref<any[]>([])
const isLoadingHistory = ref(false)
const scheduledRefreshEnabled = ref(false)
const scheduledRefreshCron = ref('08:00,20:00')
const refreshCooldownHours = ref(12)
const refreshWindowHours = ref(24)
const browserMode = ref<'normal' | 'silent' | 'headless'>('normal')
const isLoadingScheduledConfig = ref(false)
const isSavingScheduledConfig = ref(false)
const cachedSettings = ref<any>(null)
const proxyRuntimeState = ref<Record<ProxyRuntimePurpose, ProxyRuntimeStatus>>({
  auth: { purpose: 'auth', label: '账户操作链路', mode: 'idle' },
  mail: { purpose: 'mail', label: '临时邮箱链路', mode: 'idle' },
  chat: { purpose: 'chat', label: '聊天链路', mode: 'idle' },
})
const isRegistering = ref(false)
const isRefreshing = ref(false)

let registerTimer: number | null = null
let loginTimer: number | null = null
let backgroundTaskTimer: number | null = null
let proxyRuntimeTimer: number | null = null
let backgroundTaskPending = false

const clearRegisterTimer = () => {
  if (registerTimer !== null) {
    window.clearInterval(registerTimer)
    registerTimer = null
  }
}

const clearLoginTimer = () => {
  if (loginTimer !== null) {
    window.clearInterval(loginTimer)
    loginTimer = null
  }
}

const clearBackgroundTaskTimer = () => {
  if (backgroundTaskTimer !== null) {
    window.clearInterval(backgroundTaskTimer)
    backgroundTaskTimer = null
  }
  backgroundTaskPending = false
}

const clearProxyRuntimeTimer = () => {
  if (proxyRuntimeTimer !== null) {
    window.clearInterval(proxyRuntimeTimer)
    proxyRuntimeTimer = null
  }
}

const isTaskActive = (task: RegisterTask | LoginTask | null | undefined) =>
  task?.status === 'running' || task?.status === 'pending'

const getTaskByKind = (kind: TaskKind) => (kind === 'register' ? registerTask.value : loginTask.value)

const setLogClearMarker = (kind: TaskKind, marker: TaskLogLine | null) => {
  if (kind === 'register') registerLogClearMarker.value = marker
  else loginLogClearMarker.value = marker
}

const fetchProxyRuntime = async (showErrorToast = false) => {
  try {
    const response = await settingsApi.getProxyRuntime()
    proxyRuntimeState.value = {
      auth: response.statuses.auth || proxyRuntimeState.value.auth,
      mail: response.statuses.mail || proxyRuntimeState.value.mail,
      chat: response.statuses.chat || proxyRuntimeState.value.chat,
    }
  } catch (error: any) {
    if (showErrorToast) toast.error(error?.message || '获取代理运行态失败')
  }
}

const startProxyRuntimePolling = () => {
  clearProxyRuntimeTimer()
  proxyRuntimeTimer = window.setInterval(() => {
    void fetchProxyRuntime(false)
  }, 10000)
}

const readClearMarker = (key: string): TaskLogLine | null => {
  const raw = localStorage.getItem(key)
  if (!raw) return null
  const asNumber = Number(raw)
  if (Number.isFinite(asNumber)) return null
  try {
    const parsed = JSON.parse(raw) as Partial<TaskLogLine> | null
    if (!parsed || typeof parsed.time !== 'string' || typeof parsed.level !== 'string' || typeof parsed.message !== 'string') return null
    return { time: parsed.time, level: parsed.level, message: parsed.message }
  } catch {
    return null
  }
}

const writeClearMarker = (key: string, value: TaskLogLine | null) => {
  try {
    if (!value) {
      localStorage.removeItem(key)
      return
    }
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // ignore storage errors
  }
}

const syncRegisterTask = (task: RegisterTask | null) => {
  if (!task) {
    registerTask.value = null
    lastRegisterTaskId.value = null
    registerLogClearMarker.value = null
    writeClearMarker(REGISTER_CLEAR_KEY, null)
    return
  }
  registerTask.value = task
  if (task.id !== lastRegisterTaskId.value) {
    lastRegisterTaskId.value = task.id
    registerLogClearMarker.value = null
    writeClearMarker(REGISTER_CLEAR_KEY, null)
  }
}

const syncLoginTask = (task: LoginTask | null) => {
  if (!task) {
    loginTask.value = null
    lastLoginTaskId.value = null
    loginLogClearMarker.value = null
    writeClearMarker(LOGIN_CLEAR_KEY, null)
    return
  }
  loginTask.value = task
  if (task.id !== lastLoginTaskId.value) {
    lastLoginTaskId.value = task.id
    loginLogClearMarker.value = null
    writeClearMarker(LOGIN_CLEAR_KEY, null)
  }
}

const handleTaskIdle = (kind: TaskKind) => {
  if (kind === 'register') {
    clearRegisterTimer()
    isRegistering.value = false
    const current = registerTask.value
    if (current && isTaskActive(current)) syncRegisterTask({ ...current, status: 'cancelled' } as RegisterTask)
    return
  }
  clearLoginTimer()
  isRefreshing.value = false
  const current = loginTask.value
  if (current && isTaskActive(current)) syncLoginTask({ ...current, status: 'cancelled' } as LoginTask)
}

const handleTaskNotFound = (kind: TaskKind) => {
  handleTaskIdle(kind)
}

const loadCurrentTaskByKind = async (kind: TaskKind) => {
  try {
    const current = kind === 'register'
      ? await accountsApi.getRegisterCurrent()
      : await accountsApi.getLoginCurrent()
    if (current && 'id' in current) {
      const active = isTaskActive(current)
      if (kind === 'register') {
        syncRegisterTask(current)
        if (active) {
          isRegistering.value = true
          startRegisterPolling(current.id)
        }
      } else {
        syncLoginTask(current)
        if (active) {
          isRefreshing.value = true
          startLoginPolling(current.id)
        }
      }
    } else {
      handleTaskIdle(kind)
    }
  } catch (error: any) {
    if (error?.status === 404 || error?.message === 'Not found') handleTaskNotFound(kind)
    else automationError.value = error?.message || (kind === 'register' ? '加载注册任务失败' : '加载刷新任务失败')
  }
}

const loadCurrentTasks = async () => {
  await loadCurrentTaskByKind('register')
  await loadCurrentTaskByKind('login')
}

const updateRegisterTask = async (taskId: string) => {
  let task: RegisterTask
  try {
    task = await accountsApi.getRegisterTask(taskId)
  } catch (error: any) {
    if (error?.status === 404 || error?.message === 'Not found') {
      handleTaskNotFound('register')
      return
    }
    throw error
  }
  syncRegisterTask(task)
  if (!isTaskActive(task)) {
    isRegistering.value = false
    clearRegisterTimer()
    await accountsStore.loadAccounts()
    await fetchTaskHistory()
  }
}

const updateLoginTask = async (taskId: string) => {
  let task: LoginTask
  try {
    task = await accountsApi.getLoginTask(taskId)
  } catch (error: any) {
    if (error?.status === 404 || error?.message === 'Not found') {
      handleTaskNotFound('login')
      return
    }
    throw error
  }
  syncLoginTask(task)
  if (!isTaskActive(task)) {
    isRefreshing.value = false
    clearLoginTimer()
    await accountsStore.loadAccounts()
    await fetchTaskHistory()
  }
}

const startRegisterPolling = (taskId: string) => {
  clearRegisterTimer()
  registerTimer = window.setInterval(() => {
    void updateRegisterTask(taskId).catch((error: any) => {
      automationError.value = error?.message || '注册任务更新失败'
      clearRegisterTimer()
      isRegistering.value = false
    })
  }, 3000)
}

const startLoginPolling = (taskId: string) => {
  clearLoginTimer()
  loginTimer = window.setInterval(() => {
    void updateLoginTask(taskId).catch((error: any) => {
      automationError.value = error?.message || '刷新任务更新失败'
      clearLoginTimer()
      isRefreshing.value = false
    })
  }, 3000)
}

const startBackgroundTaskPolling = () => {
  if (backgroundTaskTimer !== null) return
  backgroundTaskTimer = window.setInterval(async () => {
    if (backgroundTaskPending) return
    backgroundTaskPending = true
    try {
      await loadCurrentTasks()
    } catch (error: any) {
      automationError.value = error?.message || '后台刷新失败'
    } finally {
      backgroundTaskPending = false
    }
  }, 6000)
}

const refreshTaskSnapshot = async () => {
  const tasks: Promise<void>[] = []
  if (registerTask.value?.id) tasks.push(updateRegisterTask(registerTask.value.id))
  if (loginTask.value?.id) tasks.push(updateLoginTask(loginTask.value.id))
  if (!tasks.length) await loadCurrentTasks()
  else await Promise.all(tasks)
}

const fetchTaskHistory = async () => {
  isLoadingHistory.value = true
  try {
    const response = await fetch('/admin/task-history', { headers: { 'Content-Type': 'application/json' } })
    if (!response.ok) throw new Error('获取历史记录失败')
    const data = await response.json()
    taskHistory.value = Array.isArray(data.history) ? data.history : []
  } catch (error: any) {
    toast.error(error?.message || '获取历史记录失败')
  } finally {
    isLoadingHistory.value = false
  }
}

const clearTaskHistory = async () => {
  const confirmed = await confirmDialog.ask({
    title: '清空历史记录',
    message: '确定要清空所有任务历史记录吗？',
    confirmText: '清空',
  })
  if (!confirmed) return
  try {
    const response = await fetch('/admin/task-history?confirm=yes', { method: 'DELETE', headers: { 'Content-Type': 'application/json' } })
    if (!response.ok) throw new Error('清空历史记录失败')
    taskHistory.value = []
    toast.success('历史记录已清空')
  } catch (error: any) {
    toast.error(error?.message || '清空历史记录失败')
  }
}

const loadScheduledConfig = async () => {
  isLoadingScheduledConfig.value = true
  try {
    const loaded = await settingsApi.get()
    cachedSettings.value = loaded
    scheduledRefreshEnabled.value = loaded.retry.scheduled_refresh_enabled ?? false
    scheduledRefreshCron.value = loaded.retry.scheduled_refresh_cron ?? '08:00,20:00'
    refreshCooldownHours.value = loaded.retry.refresh_cooldown_hours ?? 12
    refreshWindowHours.value = loaded.basic.refresh_window_hours ?? 24
    browserMode.value =
      loaded.basic.browser_mode === 'normal' || loaded.basic.browser_mode === 'silent' || loaded.basic.browser_mode === 'headless'
        ? loaded.basic.browser_mode
        : ((loaded.basic.browser_headless ?? false) ? 'headless' : 'normal')
  } catch (error: any) {
    toast.error(error?.message || '加载定时任务配置失败')
  } finally {
    isLoadingScheduledConfig.value = false
  }
}

const normalizeScheduledCronInput = (value: string) => {
  const raw = (value || '').trim()
  if (!raw) throw new Error('刷新时间不能为空')
  if (raw.startsWith('*/')) {
    const minutes = Number(raw.slice(2))
    if (!Number.isInteger(minutes) || minutes < 5) {
      throw new Error('间隔模式格式错误，应为 */分钟数，且最小 5 分钟')
    }
    return `*/${minutes}`
  }
  const normalized = raw.split(',').map((item) => item.trim()).filter(Boolean).map((time) => {
    const parts = time.split(':')
    if (parts.length !== 2) throw new Error(`时间格式错误: ${time}`)
    const hour = Number(parts[0])
    const minute = Number(parts[1])
    if (!Number.isInteger(hour) || !Number.isInteger(minute) || hour < 0 || hour > 23 || minute < 0 || minute > 59) {
      throw new Error(`时间超出范围: ${time}`)
    }
    return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
  })
  return Array.from(new Set(normalized)).sort().join(',')
}

const saveScheduledConfig = async () => {
  if (Number.isNaN(refreshCooldownHours.value) || refreshCooldownHours.value < 1 || refreshCooldownHours.value > 48) {
    toast.error('冷却时间必须在 1-48 小时之间')
    return
  }
  if (Number.isNaN(refreshWindowHours.value) || !Number.isInteger(refreshWindowHours.value) || refreshWindowHours.value < 1 || refreshWindowHours.value > 168) {
    toast.error('过期刷新窗口必须在 1-168 小时之间')
    return
  }
  if (!['normal', 'silent', 'headless'].includes(browserMode.value)) {
    toast.error('浏览器模式必须是 normal / silent / headless')
    return
  }
  isSavingScheduledConfig.value = true
  try {
    const normalizedCron = normalizeScheduledCronInput(scheduledRefreshCron.value)
    const loaded = cachedSettings.value || await settingsApi.get()
    loaded.retry.scheduled_refresh_enabled = scheduledRefreshEnabled.value
    loaded.retry.scheduled_refresh_cron = normalizedCron
    loaded.retry.refresh_cooldown_hours = refreshCooldownHours.value
    loaded.basic.refresh_window_hours = refreshWindowHours.value
    loaded.basic.browser_mode = browserMode.value
    loaded.basic.browser_headless = browserMode.value === 'headless'
    await settingsApi.update(loaded)
    cachedSettings.value = loaded
    scheduledRefreshCron.value = normalizedCron
    toast.success('定时任务配置已保存')
  } catch (error: any) {
    toast.error(error?.message || '保存定时任务配置失败')
  } finally {
    isSavingScheduledConfig.value = false
  }
}

const clearTaskLogs = async () => {
  const confirmed = await confirmDialog.ask({
    title: '清空当前日志',
    message: '确定要清空当前任务日志吗？',
    confirmText: '清空',
  })
  if (!confirmed) return
  ;(['register', 'login'] as TaskKind[]).forEach((kind) => {
    const task = getTaskByKind(kind)
    if (!task) return
    if (!isTaskActive(task)) {
      if (kind === 'register') syncRegisterTask(null)
      else syncLoginTask(null)
      return
    }
    const logs = (task.logs || []) as TaskLogLine[]
    if (!logs.length) return
    const marker = logs[logs.length - 1]
    setLogClearMarker(kind, marker)
    writeClearMarker(kind === 'register' ? REGISTER_CLEAR_KEY : LOGIN_CLEAR_KEY, marker)
  })
  automationError.value = ''
  toast.success('当前日志已清空')
}

const filterLogsAfterMarker = (logs: TaskLogLine[], marker: TaskLogLine | null) => {
  if (!marker) return logs
  for (let i = logs.length - 1; i >= 0; i -= 1) {
    const item = logs[i]
    if (item.time === marker.time && item.level === marker.level && item.message === marker.message) {
      return logs.slice(i + 1)
    }
  }
  return logs
}

const messageHasTaskSummaryKeyword = (message: string) => {
  const lower = message.toLowerCase()
  return TASK_LOG_SUMMARY_KEYWORDS.some((keyword) => lower.includes(keyword))
}

const isTaskSummaryLog = (log: TaskLogLine) => ['ERROR', 'WARNING', 'CRITICAL'].includes(log.level.toUpperCase()) || messageHasTaskSummaryKeyword(log.message)

const buildVisibleTaskLogs = (logs: TaskLogLine[]) => {
  if (taskLogMode.value === 'detail' || !logs.length) return logs
  const picked: TaskLogLine[] = [logs[0]]
  for (let i = 1; i < logs.length - 1; i += 1) {
    if (isTaskSummaryLog(logs[i])) picked.push(logs[i])
  }
  if (logs.length > 1) picked.push(logs[logs.length - 1])
  const seen = new Set<string>()
  return picked.filter((item) => {
    const key = `${item.time}|${item.level}|${item.message}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

const toggleTaskLogMode = () => {
  taskLogMode.value = taskLogMode.value === 'summary' ? 'detail' : 'summary'
}

const cancelRegister = async (taskId: string) => {
  try {
    await accountsApi.cancelRegisterTask(taskId, 'cancelled_by_user')
    await refreshTaskSnapshot()
    toast.success('已请求中断注册任务')
  } catch (error: any) {
    toast.error(error?.message || '中断注册任务失败')
  }
}

const cancelLogin = async (taskId: string) => {
  try {
    await accountsApi.cancelLoginTask(taskId, 'cancelled_by_user')
    await refreshTaskSnapshot()
    toast.success('已请求中断刷新任务')
  } catch (error: any) {
    toast.error(error?.message || '中断刷新任务失败')
  }
}

const registerLogs = computed(() =>
  filterLogsAfterMarker((registerTask.value?.logs || []) as TaskLogLine[], registerLogClearMarker.value)
)
const loginLogs = computed(() =>
  filterLogsAfterMarker((loginTask.value?.logs || []) as TaskLogLine[], loginLogClearMarker.value)
)
const visibleRegisterLogs = computed(() => buildVisibleTaskLogs(registerLogs.value))
const visibleLoginLogs = computed(() => buildVisibleTaskLogs(loginLogs.value))

const taskLogsDistanceToBottom = (container: HTMLDivElement) =>
  container.scrollHeight - (container.scrollTop + container.clientHeight)

const handleTaskLogsScroll = () => {
  const container = taskLogsRef.value
  if (!container) return
  taskLogsAutoFollow.value = taskLogsDistanceToBottom(container) <= 40
}

const scrollTaskLogsToBottom = async (force = false) => {
  await nextTick()
  const container = taskLogsRef.value
  if (!container || (!force && !taskLogsAutoFollow.value)) return
  container.scrollTop = container.scrollHeight
  taskLogsAutoFollow.value = true
}

const jumpTaskLogsToBottom = async () => {
  taskLogsAutoFollow.value = true
  await scrollTaskLogsToBottom(true)
}

const formatLogLine = (log: TaskLogLine) => `${log.time} [${log.level}] ${log.message}`

const getTaskResultType = (status: string, success: number, fail: number, total?: number) => {
  if (status === 'pending') return 'pending'
  if (status === 'running') return 'running'
  if (status === 'cancelled') return 'cancelled'
  if ((status === 'success' || status === 'failed') && typeof total === 'number' && total > 0) {
    if (success === total) return 'success'
    if (fail === total) return 'failed'
    if (success > 0 && fail > 0) return 'partial'
  }
  if (success > 0 && fail > 0) return 'partial'
  if (success > 0) return 'success'
  if (fail > 0) return 'failed'
  return 'none'
}

const formatTaskStatus = (task: any) => {
  const result = getTaskResultType(task?.status || '', task?.success_count ?? 0, task?.fail_count ?? 0, Number.isFinite(task?.total) ? task.total : undefined)
  if (result === 'pending') return '等待中'
  if (result === 'running') return '执行中'
  if (result === 'cancelled') return '已中断'
  if (result === 'success') return '已完成（全部成功）'
  if (result === 'failed') return '已完成（全部失败）'
  if (result === 'partial') return '已完成（部分失败）'
  return '已完成'
}

const getHistoryTotal = (record: any) => Number.isFinite(record?.total) ? record.total : (Number.isFinite(record?.progress) ? record.progress : 0)

const getHistoryStatusTextClass = (record: any) => {
  const result = getTaskResultType(record?.status, record?.success_count ?? 0, record?.fail_count ?? 0, getHistoryTotal(record))
  if (result === 'running' || result === 'pending') return 'text-sky-600'
  if (result === 'success') return 'text-emerald-600'
  if (result === 'failed') return 'text-rose-600'
  if (result === 'partial') return 'text-amber-600'
  return 'text-muted-foreground'
}

const getHistoryStatusIndicatorClass = (record: any) => {
  const result = getTaskResultType(record?.status, record?.success_count ?? 0, record?.fail_count ?? 0, getHistoryTotal(record))
  if (result === 'running' || result === 'pending') return 'bg-sky-400'
  if (result === 'success') return 'bg-emerald-400'
  if (result === 'failed') return 'bg-rose-500'
  if (result === 'partial') return 'bg-amber-400'
  return 'bg-muted-foreground'
}

const getTaskStatusIndicatorClass = (task: RegisterTask | LoginTask) => {
  const total = 'count' in task ? task.count : task.account_ids?.length
  const result = getTaskResultType(task.status, task.success_count ?? 0, task.fail_count ?? 0, total)
  if (result === 'running' || result === 'pending') return 'bg-sky-400'
  if (result === 'success') return 'bg-emerald-400'
  if (result === 'failed') return 'bg-rose-500'
  if (result === 'partial') return 'bg-amber-400'
  return 'bg-muted-foreground'
}

watch(taskLogMode, (mode) => localStorage.setItem(TASK_LOG_MODE_KEY, mode))
watch(activeTaskTab, async (tab) => {
  if (tab === 'history') await fetchTaskHistory()
  if (tab === 'scheduled') await loadScheduledConfig()
})
watch([visibleRegisterLogs, visibleLoginLogs, activeTaskTab, taskLogMode], async ([, , tab]) => {
  if (tab !== 'current') return
  await scrollTaskLogsToBottom()
}, { deep: true })

onMounted(async () => {
  registerLogClearMarker.value = readClearMarker(REGISTER_CLEAR_KEY)
  loginLogClearMarker.value = readClearMarker(LOGIN_CLEAR_KEY)
  if (!settings.value && !settingsStore.isLoading) {
    await settingsStore.loadSettings()
  }
  await loadCurrentTasks()
  await fetchProxyRuntime(false)
  startBackgroundTaskPolling()
  startProxyRuntimePolling()
})

onBeforeUnmount(() => {
  clearRegisterTimer()
  clearLoginTimer()
  clearBackgroundTaskTimer()
  clearProxyRuntimeTimer()
})
</script>
