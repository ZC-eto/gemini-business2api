# Task Center And Proxy Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将代理状态收敛为账户/聊天两张主卡，保存设置后自动执行 HTTP 测试刷新状态，并把任务管理从账号页弹窗拆成独立页面。

**Architecture:** 继续复用现有 `/admin/settings/proxy-test` 与 `/admin/settings/proxy-runtime` 接口，补一层“测试结果写运行态”的后端能力；前端新增任务页，抽取可复用的代理状态卡显示逻辑；账号页只保留入口与概览，不再承载弹窗级任务中心。

**Tech Stack:** FastAPI, Vue 3, Pinia, TypeScript, Tailwind, Dokploy/GitHub Actions

---

### Task 1: 记录设计与当前 GitHub 触发异常结论

**Files:**
- Create: `docs/plans/2026-03-15-task-center-and-proxy-status-design.md`
- Create: `docs/plans/2026-03-15-task-center-and-proxy-status.md`

**Step 1: 保存设计文档**

- 写入已确认的 UI/代理/任务页方向。

**Step 2: 保存实现计划**

- 明确每个文件改动与测试步骤。

**Step 3: Commit**

```bash
git add docs/plans/2026-03-15-task-center-and-proxy-status-design.md docs/plans/2026-03-15-task-center-and-proxy-status.md
git commit -m "docs(proxy): capture task center and proxy status design"
```

### Task 2: 后端补齐“代理测试写运行态”

**Files:**
- Modify: `main.py`
- Modify: `core/proxy_utils.py`

**Step 1: 扩展代理测试结果写入能力**

- 在 `core/proxy_utils.py` 中新增辅助函数，将 `probe_http_proxy_sync` / `probe_browser_proxy_sync` 的结果写入 `_PROXY_RUNTIME_STATUS`。
- 支持：
  - `auth`
  - `chat`
- 失败时写 `error`、成功时写 `geo / latency / resin / proxy_url`。

**Step 2: 在 `/admin/settings/proxy-test` 中调用写入逻辑**

- HTTP/浏览器测试结束后，把结果同步写入运行态。

**Step 3: 在 `/admin/settings` 保存逻辑中补“空代理重置”**

- 当 `proxy_for_auth` 或 `proxy_for_chat` 为空时，把对应运行态重置为 `idle` 或 `direct` 描述，避免保留旧值。

**Step 4: Run**

```bash
python -m py_compile main.py core/proxy_utils.py
```

**Step 5: Commit**

```bash
git add main.py core/proxy_utils.py
git commit -m "feat(proxy): persist proxy test results into runtime status"
```

### Task 3: 设置页收敛为两张主卡，并在保存后自动跑 HTTP 测试

**Files:**
- Modify: `frontend/src/views/Settings.vue`
- Modify: `frontend/src/types/api.ts`
- Modify: `frontend/src/api/settings.ts` (如需)

**Step 1: 抽掉第三张“临时邮箱代理”主卡**

- 前端仅显示 `auth` 与 `chat` 两张卡。
- 在 `auth` 卡附加：
  - `临时邮箱轮询：复用账户代理`
  - 或 `临时邮箱轮询：直连`

**Step 2: 调整保存逻辑**

- `handleSave()` 成功后：
  - 如果 `proxy_for_auth` 非空，自动跑 `auth/http` 测试；
  - 如果 `proxy_for_chat` 非空，自动跑 `chat/http` 测试；
  - 再刷新运行态；
  - toast 文案区分：
    - 全部成功
    - 保存成功但部分测试失败

**Step 3: 保留手动浏览器测试**

- 不移除现有浏览器测试按钮。

**Step 4: Run**

- 若可用：

```bash
npm --prefix frontend run build
```

- 若本地无依赖，至少执行：

```bash
python -m py_compile main.py core/proxy_utils.py
```

**Step 5: Commit**

```bash
git add frontend/src/views/Settings.vue frontend/src/types/api.ts frontend/src/api/settings.ts
git commit -m "feat(ui): auto refresh proxy status after saving settings"
```

### Task 4: 抽取可复用代理状态卡

**Files:**
- Create: `frontend/src/components/proxy/ProxyRuntimeOverview.vue`
- Modify: `frontend/src/views/Settings.vue`
- Modify: `frontend/src/views/Accounts.vue`

**Step 1: 新建状态卡组件**

- 输入：
  - `auth`
  - `chat`
  - `mailProxyEnabled`
- 输出两张主卡。

**Step 2: 在设置页与账号页复用**

- Settings/Accounts 不再各自维护重复模板。

**Step 3: Commit**

```bash
git add frontend/src/components/proxy/ProxyRuntimeOverview.vue frontend/src/views/Settings.vue frontend/src/views/Accounts.vue
git commit -m "refactor(ui): share proxy runtime overview cards"
```

### Task 5: 将任务管理从弹窗改成独立页面

**Files:**
- Create: `frontend/src/views/Tasks.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/AppShell.vue`
- Modify: `frontend/src/views/Accounts.vue`
- Modify: `frontend/src/api/accounts.ts` (若需)

**Step 1: 新建 `Tasks.vue`**

- 搬迁现有任务中心逻辑：
  - 当前任务
  - 定时任务
  - 历史记录
  - 日志跟随/回到底部
- 页面顶部接入代理状态卡。

**Step 2: 路由接入**

- 新增 `/tasks`
- 侧边栏加入“任务管理”入口
- 顶部标题支持新页面名称

**Step 3: 账号页收缩**

- 删除任务弹窗模板和相关状态；
- `任务管理` 按钮改为跳转页面；
- 保留任务运行中的进度提示。

**Step 4: Run**

- 若可用：

```bash
npm --prefix frontend run build
```

**Step 5: Commit**

```bash
git add frontend/src/views/Tasks.vue frontend/src/router/index.ts frontend/src/layouts/AppShell.vue frontend/src/views/Accounts.vue
git commit -m "feat(ui): move task management into dedicated page"
```

### Task 6: 验证 GitHub Actions push 触发与 Dokploy 链路

**Files:**
- Modify: `.github/workflows/docker-build.yml`（仅在确认需要日志增强时）
- Modify: `docs/plans/2026-03-15-task-center-and-proxy-status-design.md`（补结论）

**Step 1: 推送当前分支并观察 GitHub Actions**

- 记录是否产生 `event=push` 的 workflow run。

**Step 2: 若仍未自动触发**

- 将结论记录为：
  - 当前 fork 仓库 `PushEvent` 存在；
  - workflow 处于 active；
  - 但 GitHub 未生成 push run；
  - manual dispatch 正常；
  - 问题不在应用仓库 YAML。

**Step 3: 如有必要再补 workflow 调试输出**

- 仅在能提升诊断价值时改 workflow。

**Step 4: 验证 Dokploy**

- 观察 GHCR 新 tag 是否生成；
- 观察 Dokploy compose 是否更新；
- 调用 `/health` 验证线上服务。

### Task 7: 最终测试与乱码检查

**Files:**
- Modify: 所有本轮变更文件

**Step 1: Python 语法检查**

```bash
python -m py_compile main.py core/proxy_utils.py core/register_service.py core/login_service.py core/gemini_automation.py
```

**Step 2: 前端最小构建检查**

```bash
npm --prefix frontend run build
```

**Step 3: 乱码扫描**

```bash
rg -n "锛|鍙|鎺|褰|鐢|浠|璇|涓€|宸|�" frontend src core docs main.py
```

**Step 4: Commit**

```bash
git add .
git commit -m "feat(ui): add task center and streamline proxy status flows"
```
