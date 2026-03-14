<template>
  <div class="space-y-8">
    <section v-if="isLoading" class="rounded-3xl border border-border bg-card p-6 text-sm text-muted-foreground">
      正在加载设置...
    </section>

    <section v-else class="rounded-3xl border border-border bg-card p-6">
      <div class="flex items-center justify-between">
        <p class="text-base font-semibold text-foreground">配置面板</p>
        <button
          class="rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-opacity
                 hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          :disabled="isSaving || !localSettings"
          @click="handleSave"
        >
          保存设置
        </button>
      </div>

      <div v-if="errorMessage" class="mt-4 rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">
        {{ errorMessage }}
      </div>

      <div v-if="localSettings" class="mt-6 space-y-8">
        <div class="grid gap-4 lg:grid-cols-3">
          <div class="space-y-4">
            <div class="rounded-2xl border border-border bg-card p-4">
              <p class="text-xs uppercase tracking-[0.3em] text-muted-foreground">基础</p>
              <div class="mt-4 space-y-3">
                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <label class="block">API 密钥</label>
                  <HelpTip text="支持多个密钥，用逗号分隔。例如: key1,key2,key3" />
                </div>
                <input
                  v-model="localSettings.basic.api_key"
                  type="text"
                  class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                  placeholder="可选，多个密钥用逗号分隔"
                />
                <label class="block text-xs text-muted-foreground">基础地址</label>
                <input
                  v-model="localSettings.basic.base_url"
                  type="text"
                  class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                  placeholder="自动检测或手动填写"
                />
                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>账户操作代理</span>
                  <HelpTip text="用于注册/登录/刷新操作的代理，支持标准地址或 Resin 模板，例如 http://AuthPlatform.{account}:token@resin:2260" />
                </div>
                <div class="space-y-2">
                  <div class="flex flex-wrap gap-2">
                    <button
                      v-for="option in proxyTypeOptions"
                      :key="`auth-${option.value}`"
                      type="button"
                      class="rounded-full border px-3 py-1 text-xs font-medium transition-colors"
                      :class="localSettings.basic.proxy_for_auth_type === option.value ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground'"
                      @click="localSettings.basic.proxy_for_auth_type = option.value"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                  <input
                    v-model="localSettings.basic.proxy_for_auth"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="http://AuthPlatform.{account}:token@resin:2260"
                  />
                  <p class="text-xs text-muted-foreground">
                    {{ proxyTypeHint(localSettings.basic.proxy_for_auth_type, 'auth') }}
                  </p>
                  <div class="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      class="rounded-full border border-border px-3 py-1 text-xs font-medium text-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                      :disabled="!localSettings.basic.proxy_for_auth || proxyTestState.auth.loading !== null"
                      @click="runProxyTest('auth', 'http')"
                    >
                      {{ proxyTestState.auth.loading === 'http' ? 'HTTP 测试中...' : 'HTTP 测试' }}
                    </button>
                    <button
                      type="button"
                      class="rounded-full border border-border px-3 py-1 text-xs font-medium text-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                      :disabled="!localSettings.basic.proxy_for_auth || proxyTestState.auth.loading !== null"
                      @click="runProxyTest('auth', 'browser')"
                    >
                      {{ proxyTestState.auth.loading === 'browser' ? '浏览器测试中...' : '浏览器测试' }}
                    </button>
                  </div>
                  <div class="space-y-2">
                    <div
                      v-for="mode in proxyModes"
                      :key="`auth-${mode}`"
                      v-if="proxyTestState.auth.results[mode]"
                      class="rounded-2xl border px-3 py-2 text-xs"
                      :class="proxyTestState.auth.results[mode]?.success ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-900'"
                    >
                      <p class="font-medium">
                        {{ mode === 'http' ? 'HTTP 测试' : '浏览器测试' }}
                        <span class="ml-1">{{ proxyTestState.auth.results[mode]?.success ? '成功' : '失败' }}</span>
                      </p>
                      <p v-if="proxyTestState.auth.results[mode]?.geo?.ip" class="mt-1">
                        出口 IP：{{ proxyTestState.auth.results[mode]?.geo?.ip }}
                        <span v-if="formatGeoLabel(proxyTestState.auth.results[mode])">
                          · {{ formatGeoLabel(proxyTestState.auth.results[mode]) }}
                        </span>
                      </p>
                      <p v-if="proxyTestState.auth.results[mode]?.geo?.organization" class="mt-1">
                        线路：{{ proxyTestState.auth.results[mode]?.geo?.organization }}
                      </p>
                      <p v-if="proxyTestState.auth.results[mode]?.resin" class="mt-1">
                        Resin：{{ proxyTestState.auth.results[mode]?.resin?.platform }} / {{ proxyTestState.auth.results[mode]?.resin?.account }}
                      </p>
                      <p v-if="proxyTestState.auth.results[mode]?.error" class="mt-1">
                        错误：{{ proxyTestState.auth.results[mode]?.error }}
                      </p>
                      <ul
                        v-if="proxyTestState.auth.results[mode]?.warnings?.length"
                        class="mt-1 list-disc space-y-1 pl-4"
                      >
                        <li v-for="warning in proxyTestState.auth.results[mode]?.warnings" :key="warning">{{ warning }}</li>
                      </ul>
                    </div>
                  </div>
                </div>
                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>聊天操作代理</span>
                  <HelpTip text="用于 JWT/会话/消息操作的代理，支持标准地址或 Resin 模板，例如 http://ChatPlatform.{account}:token@resin:2260" />
                </div>
                <div class="space-y-2">
                  <div class="flex flex-wrap gap-2">
                    <button
                      v-for="option in proxyTypeOptions"
                      :key="`chat-${option.value}`"
                      type="button"
                      class="rounded-full border px-3 py-1 text-xs font-medium transition-colors"
                      :class="localSettings.basic.proxy_for_chat_type === option.value ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted-foreground hover:text-foreground'"
                      @click="localSettings.basic.proxy_for_chat_type = option.value"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                  <input
                    v-model="localSettings.basic.proxy_for_chat"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="http://ChatPlatform.{account}:token@resin:2260"
                  />
                  <p class="text-xs text-muted-foreground">
                    {{ proxyTypeHint(localSettings.basic.proxy_for_chat_type, 'chat') }}
                  </p>
                  <div class="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      class="rounded-full border border-border px-3 py-1 text-xs font-medium text-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                      :disabled="!localSettings.basic.proxy_for_chat || proxyTestState.chat.loading !== null"
                      @click="runProxyTest('chat', 'http')"
                    >
                      {{ proxyTestState.chat.loading === 'http' ? 'HTTP 测试中...' : 'HTTP 测试' }}
                    </button>
                    <button
                      type="button"
                      class="rounded-full border border-border px-3 py-1 text-xs font-medium text-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                      :disabled="!localSettings.basic.proxy_for_chat || proxyTestState.chat.loading !== null"
                      @click="runProxyTest('chat', 'browser')"
                    >
                      {{ proxyTestState.chat.loading === 'browser' ? '浏览器测试中...' : '浏览器测试' }}
                    </button>
                  </div>
                  <div class="space-y-2">
                    <div
                      v-for="mode in proxyModes"
                      :key="`chat-${mode}`"
                      v-if="proxyTestState.chat.results[mode]"
                      class="rounded-2xl border px-3 py-2 text-xs"
                      :class="proxyTestState.chat.results[mode]?.success ? 'border-emerald-200 bg-emerald-50 text-emerald-900' : 'border-amber-200 bg-amber-50 text-amber-900'"
                    >
                      <p class="font-medium">
                        {{ mode === 'http' ? 'HTTP 测试' : '浏览器测试' }}
                        <span class="ml-1">{{ proxyTestState.chat.results[mode]?.success ? '成功' : '失败' }}</span>
                      </p>
                      <p v-if="proxyTestState.chat.results[mode]?.geo?.ip" class="mt-1">
                        出口 IP：{{ proxyTestState.chat.results[mode]?.geo?.ip }}
                        <span v-if="formatGeoLabel(proxyTestState.chat.results[mode])">
                          · {{ formatGeoLabel(proxyTestState.chat.results[mode]) }}
                        </span>
                      </p>
                      <p v-if="proxyTestState.chat.results[mode]?.geo?.organization" class="mt-1">
                        线路：{{ proxyTestState.chat.results[mode]?.geo?.organization }}
                      </p>
                      <p v-if="proxyTestState.chat.results[mode]?.resin" class="mt-1">
                        Resin：{{ proxyTestState.chat.results[mode]?.resin?.platform }} / {{ proxyTestState.chat.results[mode]?.resin?.account }}
                      </p>
                      <p v-if="proxyTestState.chat.results[mode]?.error" class="mt-1">
                        错误：{{ proxyTestState.chat.results[mode]?.error }}
                      </p>
                      <ul
                        v-if="proxyTestState.chat.results[mode]?.warnings?.length"
                        class="mt-1 list-disc space-y-1 pl-4"
                      >
                        <li v-for="warning in proxyTestState.chat.results[mode]?.warnings" :key="warning">{{ warning }}</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-4">
              <p class="text-xs uppercase tracking-[0.3em] text-muted-foreground">重试</p>
              <div class="mt-4 grid grid-cols-2 gap-3 text-sm">
                <label class="col-span-2 text-xs text-muted-foreground">账户切换次数</label>
                <input v-model.number="localSettings.retry.max_account_switch_tries" type="number" min="1" class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2" />

                <div class="col-span-2 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>验证码最大尝试次数</span>
                  <HelpTip text="单个账号获取验证码时的最大尝试次数。每次失败前会请求 Resin 切换一次账户操作代理；达到上限后才会换下一个账号。" />
                </div>
                <input v-model.number="localSettings.retry.verification_code_attempts" type="number" min="1" max="10" class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2" />

                <div class="col-span-2 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>验证码等待超时（秒）</span>
                  <HelpTip text="单次等待验证码的总时长。超时后会按重发次数继续重发；如果整轮失败，会进入下一次验证码尝试并切换账户代理。" />
                </div>
                <input v-model.number="localSettings.retry.verification_code_timeout_seconds" type="number" min="5" max="180" class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2" />

                <div class="col-span-2 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>验证码轮询间隔（秒）</span>
                  <HelpTip text="轮询临时邮箱检查验证码的时间间隔。值越小响应越快，但请求也会更频繁。" />
                </div>
                <input v-model.number="localSettings.retry.verification_code_poll_interval_seconds" type="number" min="1" max="30" class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2" />

                <label class="col-span-2 text-xs text-muted-foreground">对话冷却（小时）</label>
                <input v-model.number="textRateLimitCooldownHours" type="number" min="1" max="24" step="1" class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2" />

                <label class="col-span-2 text-xs text-muted-foreground">绘图冷却（小时）</label>
                <input v-model.number="imagesRateLimitCooldownHours" type="number" min="1" max="24" step="1" class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2" />

                <label class="col-span-2 text-xs text-muted-foreground">视频冷却（小时）</label>
                <input v-model.number="videosRateLimitCooldownHours" type="number" min="1" max="24" step="1" class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2" />

                <label class="col-span-2 text-xs text-muted-foreground">会话缓存秒数</label>
                <input v-model.number="localSettings.retry.session_cache_ttl_seconds" type="number" min="0" class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2" />

                <div class="col-span-2 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>自动刷新账号间隔（秒，0=关闭）</span>
                  <HelpTip text="仅在数据库存储启用时生效：用于检测账号配置变化并重载列表，不会刷新 Cookie。" />
                </div>
                <input v-model.number="localSettings.retry.auto_refresh_accounts_seconds" type="number" min="0" max="600" class="col-span-2 rounded-2xl border border-input bg-background px-3 py-2" />
              </div>
            </div>

          </div>

          <div class="space-y-4">
            <div class="rounded-2xl border border-border bg-card p-4">
              <p class="text-xs uppercase tracking-[0.3em] text-muted-foreground">自动注册/刷新</p>
              <div class="mt-4 space-y-3">
                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>浏览器模式</span>
                  <HelpTip text="normal=正常窗口；silent=静默最小化（有头但尽量不抢焦点）；headless=无头。" />
                </div>
                <SelectMenu
                  v-model="localSettings.basic.browser_mode"
                  :options="browserModeOptions"
                  class="w-full"
                />
                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>浏览器引擎</span>
                  <HelpTip text="UC: 支持无头/有头，但可能失败。DP: 支持无头/有头，更稳定，推荐使用。" />
                </div>
                <SelectMenu
                  v-model="localSettings.basic.browser_engine"
                  :options="browserEngineOptions"
                  class="w-full"
                />
                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>临时邮箱服务</span>
                  <HelpTip text="选择用于自动注册账号的临时邮箱服务提供商。" />
                </div>
                <SelectMenu
                  v-model="localSettings.basic.temp_mail_provider"
                  :options="tempMailProviderOptions"
                  class="w-full"
                />
                <div class="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                  <span>临时邮箱代理</span>
                  <HelpTip text="启用后临时邮箱请求将使用账户操作代理地址。" />
                </div>
                <Checkbox v-model="localSettings.basic.mail_proxy_enabled">
                  启用邮箱代理（使用账户操作代理）
                </Checkbox>

                <!-- DuckMail 配置 -->
                <template v-if="localSettings.basic.temp_mail_provider === 'duckmail'">
                  <Checkbox v-model="localSettings.basic.duckmail_verify_ssl">
                    DuckMail SSL 校验
                  </Checkbox>
                  <label class="block text-xs text-muted-foreground">DuckMail API</label>
                  <input
                    v-model="localSettings.basic.duckmail_base_url"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="https://api.duckmail.sbs"
                  />
                  <label class="block text-xs text-muted-foreground">DuckMail API 密钥</label>
                  <input
                    v-model="localSettings.basic.duckmail_api_key"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="dk_xxx"
                  />
                  <label class="block text-xs text-muted-foreground">DuckMail 域名（推荐）</label>
                  <input
                    v-model="localSettings.basic.register_domain"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="留空则自动选择"
                  />
                </template>

                <!-- Moemail 配置 -->
                <template v-if="localSettings.basic.temp_mail_provider === 'moemail'">
                  <label class="block text-xs text-muted-foreground">Moemail API</label>
                  <input
                    v-model="localSettings.basic.moemail_base_url"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="https://moemail.app"
                  />
                  <label class="block text-xs text-muted-foreground">Moemail API 密钥</label>
                  <input
                    v-model="localSettings.basic.moemail_api_key"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="X-API-Key"
                  />
                  <label class="block text-xs text-muted-foreground">Moemail 域名（可选，留空随机）</label>
                  <input
                    v-model="localSettings.basic.moemail_domain"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="moemail.app"
                  />
                </template>

                <!-- Freemail 配置 -->
                <template v-if="localSettings.basic.temp_mail_provider === 'freemail'">
                  <Checkbox v-model="localSettings.basic.freemail_verify_ssl">
                    Freemail SSL 校验
                  </Checkbox>
                  <label class="block text-xs text-muted-foreground">Freemail API</label>
                  <input
                    v-model="localSettings.basic.freemail_base_url"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="http://your-freemail-server.com"
                  />
                  <label class="block text-xs text-muted-foreground">Freemail JWT Token</label>
                  <input
                    v-model="localSettings.basic.freemail_jwt_token"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="eyJ..."
                  />
                  <label class="block text-xs text-muted-foreground">Freemail 域名（可选，留空随机）</label>
                  <input
                    v-model="localSettings.basic.freemail_domain"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="freemail.local"
                  />
                </template>

                <!-- GPTMail 配置 -->
                <template v-if="localSettings.basic.temp_mail_provider === 'gptmail'">
                  <Checkbox v-model="localSettings.basic.gptmail_verify_ssl">
                    GPTMail SSL 校验
                  </Checkbox>
                  <label class="block text-xs text-muted-foreground">GPTMail API</label>
                  <input
                    v-model="localSettings.basic.gptmail_base_url"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="https://mail.chatgpt.org.uk"
                  />
                  <label class="block text-xs text-muted-foreground">GPTMail API Key</label>
                  <input
                    v-model="localSettings.basic.gptmail_api_key"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="X-API-Key"
                  />
                  <label class="block text-xs text-muted-foreground">GPTMail 邮箱域名（可选，不带@）</label>
                  <input
                    v-model="localSettings.basic.gptmail_domain"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="留空则随机选择"
                  />
                </template>

                <!-- Cloudflare Mail 配置 -->
                <template v-if="localSettings.basic.temp_mail_provider === 'cfmail'">
                  <Checkbox v-model="localSettings.basic.cfmail_verify_ssl">
                    Cloudflare Mail SSL 校验
                  </Checkbox>
                  <label class="block text-xs text-muted-foreground">Cloudflare Mail API 地址</label>
                  <input
                    v-model="localSettings.basic.cfmail_base_url"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="https://your-cfmail-instance.example.com"
                  />
                  <label class="block text-xs text-muted-foreground">访问密码（x-custom-auth，无密码留空）</label>
                  <input
                    v-model="localSettings.basic.cfmail_api_key"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="留空则不使用密码"
                  />
                  <label class="block text-xs text-muted-foreground">邮箱域名（可选，不带@）</label>
                  <input
                    v-model="localSettings.basic.cfmail_domain"
                    type="text"
                    class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                    placeholder="留空则随机选择"
                  />
                </template>

                <label class="block text-xs text-muted-foreground">默认注册数量</label>
                <input
                  v-model.number="localSettings.basic.register_default_count"
                  type="number"
                  min="1"
                  class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>

          <div class="space-y-4">
            <div class="rounded-2xl border border-border bg-card p-4">
              <div class="flex items-center justify-between gap-2">
                <p class="text-xs uppercase tracking-[0.3em] text-muted-foreground">图像生成</p>
                <HelpTip text="不建议开启图像生成功能，容易思考不出图，建议用gemini-imagen" />
              </div>
              <div class="mt-4 space-y-3">
                <Checkbox v-model="localSettings.image_generation.enabled">
                  启用图像生成
                </Checkbox>
                <label class="block text-xs text-muted-foreground">输出格式</label>
                <SelectMenu
                  v-model="localSettings.image_generation.output_format"
                  :options="imageOutputOptions"
                  placement="up"
                  class="w-full"
                />
                <label class="block text-xs text-muted-foreground">支持模型</label>
                <SelectMenu
                  v-model="localSettings.image_generation.supported_models"
                  :options="imageModelOptions"
                  placeholder="选择模型"
                  placement="up"
                  multiple
                  class="w-full"
                />
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-4">
              <p class="text-xs uppercase tracking-[0.3em] text-muted-foreground">视频生成</p>
              <div class="mt-4 space-y-3">
                <label class="block text-xs text-muted-foreground">输出格式（使用 gemini-veo 模型时生效）</label>
                <SelectMenu
                  v-model="localSettings.video_generation.output_format"
                  :options="videoOutputOptions"
                  placement="up"
                  class="w-full"
                />
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-4">
              <div class="flex items-center justify-between gap-2">
                <p class="text-xs uppercase tracking-[0.3em] text-muted-foreground">每日配额</p>
                <HelpTip text="基于 Google 官方限额的主动配额计数，达到上限后自动切换账号。0 表示不限制该类型。" />
              </div>
              <div class="mt-4 space-y-3">
                <Checkbox v-model="localSettings.quota_limits.enabled">
                  启用主动配额计数
                </Checkbox>
                <label class="block text-xs text-muted-foreground">对话每日上限</label>
                <input
                  v-model.number="localSettings.quota_limits.text_daily_limit"
                  type="number"
                  min="0"
                  max="9999"
                  class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                  placeholder="120"
                />
                <label class="block text-xs text-muted-foreground">绘图每日上限</label>
                <input
                  v-model.number="localSettings.quota_limits.images_daily_limit"
                  type="number"
                  min="0"
                  max="9999"
                  class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                  placeholder="2"
                />
                <label class="block text-xs text-muted-foreground">视频每日上限</label>
                <input
                  v-model.number="localSettings.quota_limits.videos_daily_limit"
                  type="number"
                  min="0"
                  max="9999"
                  class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                  placeholder="1"
                />
                <p class="text-xs text-muted-foreground">每日北京时间 16:00 重置（对齐 Google 太平洋时间午夜）</p>
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-4">
              <p class="text-xs uppercase tracking-[0.3em] text-muted-foreground">公开展示</p>
              <div class="mt-4 space-y-3">
                <label class="block text-xs text-muted-foreground">Logo 地址</label>
                <input
                  v-model="localSettings.public_display.logo_url"
                  type="text"
                  class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                  placeholder="logo 地址"
                />
                <label class="block text-xs text-muted-foreground">聊天入口</label>
                <input
                  v-model="localSettings.public_display.chat_url"
                  type="text"
                  class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                  placeholder="聊天入口地址"
                />
                <label class="block text-xs text-muted-foreground">会话有效时长</label>
                <input
                  v-model.number="localSettings.session.expire_hours"
                  type="number"
                  min="1"
                  class="w-full rounded-2xl border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
            </div>

            <div class="rounded-2xl border border-border bg-card p-4">
              <p class="text-xs uppercase tracking-[0.3em] text-muted-foreground">说明</p>
              <p class="mt-4 text-sm text-muted-foreground">
                保存后会直接写入配置文件并热更新。修改后请关注日志面板确认是否生效。
              </p>
              <p class="mt-3 text-sm text-muted-foreground">
                自动注册/刷新默认启用，若依赖缺失会自动降级并提示。
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { settingsApi } from '@/api'
import { useSettingsStore } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { defaultMailProvider, mailProviderOptions } from '@/constants/mailProviders'
import SelectMenu from '@/components/ui/SelectMenu.vue'
import Checkbox from '@/components/ui/Checkbox.vue'
import HelpTip from '@/components/ui/HelpTip.vue'
import type { ProxyTestResult, Settings } from '@/types/api'

const settingsStore = useSettingsStore()
const { settings, isLoading } = storeToRefs(settingsStore)
const toast = useToast()

const localSettings = ref<Settings | null>(null)
const isSaving = ref(false)
const errorMessage = ref('')
const proxyModes = ['http', 'browser'] as const
type ProxyMode = (typeof proxyModes)[number]
type ProxyPurpose = 'auth' | 'chat'

const proxyTestState = ref<Record<ProxyPurpose, { loading: ProxyMode | null; results: Record<ProxyMode, ProxyTestResult | null> }>>({
  auth: {
    loading: null,
    results: {
      http: null,
      browser: null,
    },
  },
  chat: {
    loading: null,
    results: {
      http: null,
      browser: null,
    },
  },
})

const PROXY_TEST_ACCOUNT = 'account_001'
const PROXY_TEST_EMAIL = 'proxy.test@example.com'

// 429冷却时间：小时 ↔ 秒 的转换
const DEFAULT_COOLDOWN_HOURS = {
  text: 2,
  images: 4,
  videos: 4
} as const

const toCooldownHours = (seconds: number | undefined, fallbackHours: number) => {
  if (!seconds) return fallbackHours
  return Math.max(1, Math.round(seconds / 3600))
}

const createCooldownHours = (
  key: 'text_rate_limit_cooldown_seconds' | 'images_rate_limit_cooldown_seconds' | 'videos_rate_limit_cooldown_seconds',
  fallbackHours: number
) => computed({
  get: () => toCooldownHours(localSettings.value?.retry?.[key], fallbackHours),
  set: (hours: number) => {
    if (localSettings.value?.retry) {
      localSettings.value.retry[key] = hours * 3600
    }
  }
})

const textRateLimitCooldownHours = createCooldownHours(
  'text_rate_limit_cooldown_seconds',
  DEFAULT_COOLDOWN_HOURS.text
)
const imagesRateLimitCooldownHours = createCooldownHours(
  'images_rate_limit_cooldown_seconds',
  DEFAULT_COOLDOWN_HOURS.images
)
const videosRateLimitCooldownHours = createCooldownHours(
  'videos_rate_limit_cooldown_seconds',
  DEFAULT_COOLDOWN_HOURS.videos
)

const browserEngineOptions = [
  { label: 'DP - 支持无头/有头', value: 'dp' },
]
const browserModeOptions = [
  { label: 'normal - 正常窗口', value: 'normal' },
  { label: 'silent - 静默最小化', value: 'silent' },
  { label: 'headless - 无头', value: 'headless' },
]
const proxyTypeOptions = [
  { label: '自动检测', value: 'auto' },
  { label: '普通代理', value: 'standard' },
  { label: 'Resin 代理', value: 'resin' },
] as const
const tempMailProviderOptions = mailProviderOptions
const imageOutputOptions = [
  { label: 'Base64 编码', value: 'base64' },
  { label: 'URL 链接', value: 'url' },
]
const videoOutputOptions = [
  { label: 'HTML 视频标签', value: 'html' },
  { label: 'URL 链接', value: 'url' },
  { label: 'Markdown 格式', value: 'markdown' },
]
const imageModelOptions = computed(() => {
  const baseOptions = [
    { label: 'Gemini 3 Pro Preview', value: 'gemini-3-pro-preview' },
    { label: 'Gemini 3.1 Pro Preview', value: 'gemini-3.1-pro-preview' },
    { label: 'Gemini 3 Flash Preview', value: 'gemini-3-flash-preview' },
    { label: 'Gemini 2.5 Pro', value: 'gemini-2.5-pro' },
    { label: 'Gemini 2.5 Flash', value: 'gemini-2.5-flash' },
    { label: 'Gemini Auto', value: 'gemini-auto' },
  ]

  const selected = localSettings.value?.image_generation.supported_models || []
  for (const value of selected) {
    if (!baseOptions.some(option => option.value === value)) {
      baseOptions.push({ label: value, value })
    }
  }

  return baseOptions
})

const formatGeoLabel = (result: ProxyTestResult | null | undefined) => {
  const geo = result?.geo
  if (!geo) return ''
  return [geo.country, geo.region, geo.city].filter(Boolean).join(' / ')
}

const proxyTypeHint = (type: string | undefined, purpose: ProxyPurpose) => {
  if (type === 'resin') {
    return purpose === 'auth'
      ? 'Resin 模式下建议使用 auth.{account} 模板，这样验证码失败时才能按账号请求 rotate。'
      : 'Resin 模式下建议使用 chat.{account} 模板，这样每个账号会独立保持聊天出口 IP。'
  }
  if (type === 'standard') {
    return '普通代理支持 HTTP/SOCKS 地址，只做通用代理连通性与浏览器代理测试，不启用 Resin 平台/账号识别。'
  }
  return '自动检测会根据地址格式判断是否为 Resin；如果你明确知道当前代理类型，建议手动指定。'
}

watch(settings, (value) => {
  if (!value) return
  const next = JSON.parse(JSON.stringify(value))
  next.image_generation = next.image_generation || { enabled: false, supported_models: [], output_format: 'base64' }
  next.image_generation.output_format ||= 'base64'
  next.video_generation = next.video_generation || { output_format: 'html' }
  next.video_generation.output_format ||= 'html'
  next.basic = next.basic || {}
  next.basic.duckmail_base_url ||= 'https://api.duckmail.sbs'
  next.basic.duckmail_verify_ssl = next.basic.duckmail_verify_ssl ?? true
  next.basic.proxy_for_auth_type =
    next.basic.proxy_for_auth_type === 'auto' || next.basic.proxy_for_auth_type === 'standard' || next.basic.proxy_for_auth_type === 'resin'
      ? next.basic.proxy_for_auth_type
      : 'auto'
  next.basic.proxy_for_chat_type =
    next.basic.proxy_for_chat_type === 'auto' || next.basic.proxy_for_chat_type === 'standard' || next.basic.proxy_for_chat_type === 'resin'
      ? next.basic.proxy_for_chat_type
      : 'auto'
  next.basic.browser_engine = next.basic.browser_engine || 'dp'
  const normalizedBrowserMode =
    next.basic.browser_mode === 'normal' || next.basic.browser_mode === 'silent' || next.basic.browser_mode === 'headless'
      ? next.basic.browser_mode
      : ((next.basic.browser_headless ?? false) ? 'headless' : 'normal')
  next.basic.browser_mode = normalizedBrowserMode
  next.basic.browser_headless = normalizedBrowserMode === 'headless'
  next.basic.refresh_window_hours = Number.isFinite(next.basic.refresh_window_hours)
    ? next.basic.refresh_window_hours
    : 1
  next.basic.register_default_count = Number.isFinite(next.basic.register_default_count)
    ? next.basic.register_default_count
    : 1
  next.basic.register_domain = typeof next.basic.register_domain === 'string'
    ? next.basic.register_domain
    : ''
  next.basic.duckmail_api_key = typeof next.basic.duckmail_api_key === 'string'
    ? next.basic.duckmail_api_key
    : ''
  next.basic.temp_mail_provider = next.basic.temp_mail_provider || defaultMailProvider
  next.basic.moemail_base_url = next.basic.moemail_base_url || 'https://moemail.app'
  next.basic.moemail_api_key = typeof next.basic.moemail_api_key === 'string'
    ? next.basic.moemail_api_key
    : ''
  next.basic.moemail_domain = typeof next.basic.moemail_domain === 'string'
    ? next.basic.moemail_domain
    : ''
  next.basic.freemail_base_url = next.basic.freemail_base_url || 'http://your-freemail-server.com'
  next.basic.freemail_jwt_token = typeof next.basic.freemail_jwt_token === 'string'
    ? next.basic.freemail_jwt_token
    : ''
  next.basic.freemail_verify_ssl = next.basic.freemail_verify_ssl ?? true
  next.basic.freemail_domain = typeof next.basic.freemail_domain === 'string'
    ? next.basic.freemail_domain
    : ''
  next.basic.mail_proxy_enabled = next.basic.mail_proxy_enabled ?? false
  next.basic.gptmail_base_url = next.basic.gptmail_base_url || 'https://mail.chatgpt.org.uk'
  next.basic.gptmail_api_key = typeof next.basic.gptmail_api_key === 'string'
    ? next.basic.gptmail_api_key
    : ''
  next.basic.gptmail_verify_ssl = next.basic.gptmail_verify_ssl ?? true
  next.basic.gptmail_domain = typeof next.basic.gptmail_domain === 'string'
    ? next.basic.gptmail_domain
    : ''
  next.basic.cfmail_base_url = typeof next.basic.cfmail_base_url === 'string'
    ? next.basic.cfmail_base_url
    : ''
  next.basic.cfmail_api_key = typeof next.basic.cfmail_api_key === 'string'
    ? next.basic.cfmail_api_key
    : ''
  next.basic.cfmail_verify_ssl = next.basic.cfmail_verify_ssl ?? true
  next.basic.cfmail_domain = typeof next.basic.cfmail_domain === 'string'
    ? next.basic.cfmail_domain
    : ''
  next.retry = next.retry || {}
  next.retry.verification_code_attempts = Number.isFinite(next.retry.verification_code_attempts)
    ? next.retry.verification_code_attempts
    : 3
  next.retry.verification_code_timeout_seconds = Number.isFinite(next.retry.verification_code_timeout_seconds)
    ? next.retry.verification_code_timeout_seconds
    : 25
  next.retry.verification_code_poll_interval_seconds = Number.isFinite(next.retry.verification_code_poll_interval_seconds)
    ? next.retry.verification_code_poll_interval_seconds
    : 5
  next.retry.verification_code_resend_count = Number.isFinite(next.retry.verification_code_resend_count)
    ? next.retry.verification_code_resend_count
    : 2
  next.retry.auto_refresh_accounts_seconds = Number.isFinite(next.retry.auto_refresh_accounts_seconds)
    ? next.retry.auto_refresh_accounts_seconds
    : 60
  next.quota_limits = next.quota_limits || {}
  next.quota_limits.enabled = next.quota_limits.enabled ?? true
  next.quota_limits.text_daily_limit = Number.isFinite(next.quota_limits.text_daily_limit)
    ? next.quota_limits.text_daily_limit
    : 120
  next.quota_limits.images_daily_limit = Number.isFinite(next.quota_limits.images_daily_limit)
    ? next.quota_limits.images_daily_limit
    : 2
  next.quota_limits.videos_daily_limit = Number.isFinite(next.quota_limits.videos_daily_limit)
    ? next.quota_limits.videos_daily_limit
    : 1
  localSettings.value = next
})

onMounted(async () => {
  await settingsStore.loadSettings()
})

const runProxyTest = async (purpose: ProxyPurpose, mode: ProxyMode) => {
  if (!localSettings.value) return

  const proxy = purpose === 'auth'
    ? (localSettings.value.basic.proxy_for_auth || '').trim()
    : (localSettings.value.basic.proxy_for_chat || '').trim()

  if (!proxy) {
    toast.error('请先填写代理地址')
    return
  }

  proxyTestState.value[purpose].loading = mode
  errorMessage.value = ''
  try {
    const result = await settingsApi.testProxy({
      proxy,
      mode,
      purpose,
      proxy_type: purpose === 'auth' ? localSettings.value.basic.proxy_for_auth_type : localSettings.value.basic.proxy_for_chat_type,
      account_id: PROXY_TEST_ACCOUNT,
      email: PROXY_TEST_EMAIL,
    })
    proxyTestState.value[purpose].results[mode] = result
    if (result.success) {
      const ip = result.geo?.ip ? `，出口 ${result.geo.ip}` : ''
      toast.success(`${mode === 'http' ? 'HTTP' : '浏览器'}代理测试成功${ip}`)
    } else {
      toast.error(result.error || '代理测试失败')
    }
  } catch (error: any) {
    const message = error.message || '代理测试失败'
    proxyTestState.value[purpose].results[mode] = {
      success: false,
      mode,
      purpose,
      error: message,
      warnings: [],
    }
    toast.error(message)
  } finally {
    proxyTestState.value[purpose].loading = null
  }
}

const handleSave = async () => {
  if (!localSettings.value) return
  errorMessage.value = ''
  isSaving.value = true

  try {
    localSettings.value.basic.browser_mode =
      localSettings.value.basic.browser_mode === 'normal' ||
      localSettings.value.basic.browser_mode === 'silent' ||
      localSettings.value.basic.browser_mode === 'headless'
        ? localSettings.value.basic.browser_mode
        : 'normal'
    localSettings.value.basic.browser_headless = localSettings.value.basic.browser_mode === 'headless'
    await settingsStore.updateSettings(localSettings.value)
    toast.success('设置保存成功')
  } catch (error: any) {
    errorMessage.value = error.message || '保存失败'
    toast.error(error.message || '保存失败')
  } finally {
    isSaving.value = false
  }
}
</script>
