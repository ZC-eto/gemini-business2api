# Proxy Runtime Plan A Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为注册/刷新链路增加常驻代理状态栏、`unknown` 短窗口策略和坏链路冷却池，提升成功率与排障效率。

**Architecture:** 以后端运行态状态中心为核心，统一记录 `auth / mail / chat` 三条链路的最新出口、错误和切换信息；注册/刷新链路在验证码发送和轮询阶段根据 `confirmed / failed / unknown` 做更早决策；前端账号页轮询运行态并常驻展示。

**Tech Stack:** FastAPI、Pydantic、Python 运行态缓存、Vue 3、Pinia、TypeScript

---

### Task 1: 扩展代理运行态模型

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\core\proxy_utils.py`
- Modify: `E:\Tools\gemini\gemini-business2api\frontend\src\types\api.ts`

**Step 1: 扩展后端运行态字段**

- 增加最近切换结果、最近错误类别、最近延迟、链路模式标签。
- 增加直连出口记录能力。

**Step 2: 扩展前端类型**

- 为状态栏补齐新增字段类型。

**Step 3: 运行语法检查**

Run: `python -m py_compile core/proxy_utils.py`

**Step 4: Commit**

```bash
git add core/proxy_utils.py frontend/src/types/api.ts
git commit -m "feat(proxy): extend runtime status model"
```

### Task 2: 加入坏链路冷却池

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\core\proxy_utils.py`
- Modify: `E:\Tools\gemini\gemini-business2api\core\register_service.py`
- Modify: `E:\Tools\gemini\gemini-business2api\core\login_service.py`

**Step 1: 增加冷却池工具函数**

- 新增记录失败、判断是否在冷却期、读取冷却信息的函数。

**Step 2: 在注册/刷新链路接入**

- 在发送失败、403、验证码失败后记录坏链路。
- Resin 模式在冷却命中时优先 rotate。

**Step 3: 运行语法检查**

Run: `python -m py_compile core/proxy_utils.py core/register_service.py core/login_service.py`

**Step 4: Commit**

```bash
git add core/proxy_utils.py core/register_service.py core/login_service.py
git commit -m "feat(proxy): add bad-route cooldown tracking"
```

### Task 3: 优化验证码发送状态策略

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\core\gemini_automation.py`

**Step 1: 细化 `unknown` 策略**

- `failed` 立即失败。
- `confirmed` 正常轮询。
- `unknown` 仅允许一次短窗口等待，失败后尽快返回上层。

**Step 2: 写清楚日志**

- 在日志里明确输出：发送确认成功、发送明确失败、未知状态短窗口、冷却命中。

**Step 3: 运行语法检查**

Run: `python -m py_compile core/gemini_automation.py`

**Step 4: Commit**

```bash
git add core/gemini_automation.py
git commit -m "feat(proxy): optimize send-status decision flow"
```

### Task 4: 暴露运行态状态栏所需接口

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\main.py`
- Modify: `E:\Tools\gemini\gemini-business2api\frontend\src\api\settings.ts`

**Step 1: 确认接口返回字段**

- `/admin/settings/proxy-runtime` 返回新增字段。

**Step 2: 前端 API 层适配**

- 保持现有接口兼容，新增字段可选。

**Step 3: 运行语法检查**

Run: `python -m py_compile main.py`

**Step 4: Commit**

```bash
git add main.py frontend/src/api/settings.ts
git commit -m "feat(proxy): expose runtime status details"
```

### Task 5: 在账号页加入常驻状态栏

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\frontend\src\views\Accounts.vue`

**Step 1: 添加 3 张代理状态卡**

- 在账号页顶部工具栏下方展示 `auth / mail / chat`。

**Step 2: 加入轮询与格式化逻辑**

- 复用运行态接口。
- 根据模式显示 Resin / HTTP / SOCKS / 直连。

**Step 3: 展示切换结果与错误**

- 最近一次 rotate 结果、错误原因、更新时间。

**Step 4: 做最小静态自检**

- 检查脚本引用、模板变量、未使用变量。

**Step 5: Commit**

```bash
git add frontend/src/views/Accounts.vue
git commit -m "feat(proxy): add persistent runtime status bar"
```

### Task 6: 最小验证与文档收尾

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\docs\plans\2026-03-15-proxy-runtime-plan-a-design.md`
- Modify: `E:\Tools\gemini\gemini-business2api\docs\plans\2026-03-15-proxy-runtime-plan-a.md`

**Step 1: 运行 Python 语法检查**

Run: `python -m py_compile main.py core/proxy_utils.py core/register_service.py core/login_service.py core/gemini_automation.py`

**Step 2: 运行运行态最小冒烟**

Run:

```bash
python -c "from core.proxy_utils import get_proxy_runtime_status_snapshot; print(get_proxy_runtime_status_snapshot(refresh_geo=False).keys())"
```

**Step 3: 乱码扫描**

Run:

```bash
python -c "from pathlib import Path; files=['main.py']; print('scan changed files for mojibake before commit')"
```

**Step 4: Commit**

```bash
git add docs/plans
git commit -m "docs: add proxy runtime plan a design and implementation notes"
```
