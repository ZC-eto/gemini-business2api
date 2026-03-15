# Chat Proxy Rotate Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为聊天链路增加基于异常类型的 Resin 聊天代理切换能力，并同步收敛验证码发送状态策略与运行态展示。

**Architecture:** 以后端聊天主循环为切入点，在异常处理分支里判断是否属于代理/IP 问题；若当前聊天代理为 Resin，则在单请求内允许一次 rotate 并保持同账号重试；普通代理和直连只记录运行态和提示。验证码发送链路同步调整为 `confirmed/unknown` 完整轮询、`failed` 立即切 auth 代理。

**Tech Stack:** FastAPI、httpx、Python 运行态缓存、Vue 3、TypeScript

---

### Task 1: 固化聊天代理切换设计文档

**Files:**
- Create: `E:\Tools\gemini\gemini-business2api\docs\plans\2026-03-15-chat-proxy-rotate-design.md`

**Step 1: 写入设计文档**

- 记录聊天异常分类矩阵、Resin/标准代理/直连兼容边界、验证码状态策略。

**Step 2: 自检文档路径与命名**

- 确认文件命名与 `docs/plans` 现有风格一致。

**Step 3: Commit**

```bash
git add docs/plans/2026-03-15-chat-proxy-rotate-design.md
git commit -m "docs(proxy): add chat proxy rotate design"
```

### Task 2: 为聊天链路增加 rotate 判定工具

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\core\proxy_utils.py`

**Step 1: 增加聊天 rotate 能力判断**

- 封装：
  - 当前聊天代理是否为 Resin
  - 当前聊天代理是否支持自动 rotate
  - 聊天 rotate 后如何更新运行态状态

**Step 2: 补齐聊天运行态字段**

- 最近一次聊天 rotate 状态
- 最近一次聊天 rotate 原因
- 最近一次聊天 rotate 时间

**Step 3: 运行语法检查**

Run: `python -m py_compile core/proxy_utils.py`

**Step 4: Commit**

```bash
git add core/proxy_utils.py
git commit -m "feat(proxy): add chat rotate helpers"
```

### Task 3: 在聊天主循环接入异常分类与 Resin rotate

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\main.py`

**Step 1: 写出聊天异常分类函数**

- 区分：
  - 不切聊天代理：`429`、`401`
  - 切聊天代理：`403`（首个）、`Timeout`、`TLS`、`httpx` 网络错误、`504`
  - 维持现状：`502`

**Step 2: 在 `response_wrapper()` 加入单请求 rotate 保护**

- 同请求最多 rotate 一次
- 同账号因 rotate 最多重试一次
- 失败后回退现有切账号逻辑

**Step 3: 补充清晰日志**

- 写明命中条件、是否支持 rotate、rotate 成功/失败、是否回退为账号问题

**Step 4: 运行语法检查**

Run: `python -m py_compile main.py`

**Step 5: Commit**

```bash
git add main.py
git commit -m "feat(proxy): rotate chat resin proxy on network-style failures"
```

### Task 4: 调整验证码发送状态策略

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\core\gemini_automation.py`

**Step 1: 调整 `unknown` 轮询行为**

- `confirmed`：完整轮询
- `unknown`：也完整轮询一轮
- `failed`：明确失败立即返回上层

**Step 2: 收窄 `failed` 判定**

- 避免把“进入验证码页但无明确发送成功证据”的场景误判为 `failed`

**Step 3: 明确日志文案**

- 输出最终采用的是 `confirmed / unknown / failed` 哪个分支

**Step 4: 运行语法检查**

Run: `python -m py_compile core/gemini_automation.py`

**Step 5: Commit**

```bash
git add core/gemini_automation.py
git commit -m "fix(proxy): align verification wait strategy with send status"
```

### Task 5: 让账号页状态栏完整展示聊天链路 rotate 结果

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\frontend\src\types\api.ts`
- Modify: `E:\Tools\gemini\gemini-business2api\frontend\src\api\settings.ts`
- Modify: `E:\Tools\gemini\gemini-business2api\frontend\src\views\Accounts.vue`
- Modify: `E:\Tools\gemini\gemini-business2api\frontend\src\views\Settings.vue`
- Modify: `E:\Tools\gemini\gemini-business2api\main.py`

**Step 1: 确认运行态接口字段**

- 聊天链路返回最近 rotate 状态、原因、时间

**Step 2: 前端类型与展示适配**

- 状态栏显示：
  - 模式
  - 出口 IP / 地区 / 线路
  - 最近 rotate 结果 / 原因
  - 更新时间

**Step 3: 做最小静态自检**

- 检查模板字段、未使用变量、字段命名一致性

**Step 4: Commit**

```bash
git add frontend/src/types/api.ts frontend/src/api/settings.ts frontend/src/views/Accounts.vue frontend/src/views/Settings.vue main.py
git commit -m "feat(ui): surface chat proxy rotate status in runtime cards"
```

### Task 6: 最小验证与乱码扫描

**Files:**
- Modify: `E:\Tools\gemini\gemini-business2api\docs\plans\2026-03-15-chat-proxy-rotate.md`

**Step 1: 运行 Python 语法检查**

Run: `python -m py_compile main.py core/proxy_utils.py core/gemini_automation.py`

**Step 2: 运行最小聊天判定冒烟**

Run:

```bash
python -c "from core.proxy_utils import get_proxy_runtime_status_snapshot; print(sorted(get_proxy_runtime_status_snapshot(refresh_geo=False).keys()))"
```

**Step 3: 乱码扫描**

Run:

```bash
python -c "from pathlib import Path; pats=['锛','鍙','鎺','褰','鐢','浠','璇','涓€','宸','�']; files=['main.py','core/proxy_utils.py','core/gemini_automation.py','frontend/src/views/Accounts.vue']; bad=[]\nfor f in files:\n t=Path(f).read_text(encoding='utf-8');\n  [bad.append((f,p)) for p in pats if p in t]\nprint(bad)"
```

**Step 4: Commit**

```bash
git add docs/plans/2026-03-15-chat-proxy-rotate.md
git commit -m "docs(proxy): add chat proxy rotate implementation plan"
```
