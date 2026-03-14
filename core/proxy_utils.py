"""
代理设置工具函数

支持格式:
- http://127.0.0.1:7890
- http://user:pass@127.0.0.1:7890
- socks5h://127.0.0.1:7890
- socks5h://user:pass@127.0.0.1:7890 | no_proxy=localhost,127.0.0.1,.local

NO_PROXY 格式:
- 逗号分隔的主机名或域名后缀
- 支持通配符前缀，如 .local 匹配 *.local
"""

import contextvars
import functools
import re
import threading
from contextlib import contextmanager
from typing import Tuple, Callable, Any, Optional, Dict
from urllib.parse import quote, unquote, urlparse

import httpx
import requests

_RUNTIME_PROXY_CONTEXT: contextvars.ContextVar[Dict[str, str]] = contextvars.ContextVar(
    "runtime_proxy_context",
    default={},
)


def parse_proxy_setting(proxy_str: str) -> Tuple[str, str]:
    """
    解析代理设置字符串，提取代理 URL 和 NO_PROXY 列表

    Args:
        proxy_str: 代理设置字符串，格式如 "http://127.0.0.1:7890 | no_proxy=localhost,127.0.0.1"

    Returns:
        Tuple[str, str]: (proxy_url, no_proxy_list)
        - proxy_url: 代理地址，如 "http://127.0.0.1:7890"
        - no_proxy_list: NO_PROXY 列表字符串，如 "localhost,127.0.0.1"
    """
    if not proxy_str:
        return "", ""

    proxy_str = proxy_str.strip()
    if not proxy_str:
        return "", ""

    # 检查是否包含 no_proxy 设置
    # 支持格式: proxy_url | no_proxy=host1,host2
    no_proxy = ""
    proxy_url = proxy_str

    # 使用 | 分隔代理和 no_proxy
    if "|" in proxy_str:
        parts = proxy_str.split("|", 1)
        proxy_url = parts[0].strip()
        no_proxy_part = parts[1].strip()

        # 解析 no_proxy=xxx 格式
        no_proxy_match = re.match(r"no_proxy\s*=\s*(.+)", no_proxy_part, re.IGNORECASE)
        if no_proxy_match:
            no_proxy = no_proxy_match.group(1).strip()

    return normalize_proxy_url(proxy_url), no_proxy


def has_proxy_placeholders(proxy_str: str) -> bool:
    """判断代理配置中是否包含模板变量。"""
    return bool(proxy_str and re.search(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", proxy_str))


def render_proxy_template(
    proxy_str: str,
    *,
    account_id: str = "",
    email: str = "",
    extra: Optional[Dict[str, Any]] = None,
    default_account: Optional[str] = None,
) -> str:
    """
    渲染代理模板，支持 {account} / {account_id} / {email} 以及自定义变量。

    说明：
    - 变量值会自动进行 URL 编码，避免邮箱中的 @ 等字符破坏代理 URL。
    - 若模板包含占位符但缺少必要变量，则抛出 ValueError。
    """
    if not proxy_str:
        return ""

    effective_account = account_id or email or default_account or ""
    effective_email = email or account_id or default_account or ""
    values: Dict[str, str] = {
        "account": quote(effective_account, safe=""),
        "account_id": quote(effective_account, safe=""),
        "email": quote(effective_email, safe=""),
        "account_raw": effective_account,
        "account_id_raw": effective_account,
        "email_raw": effective_email,
        "account_encoded": quote(effective_account, safe=""),
        "account_id_encoded": quote(effective_account, safe=""),
        "email_encoded": quote(effective_email, safe=""),
    }

    if extra:
        for key, value in extra.items():
            if value is None:
                continue
            rendered = str(value)
            values[key] = quote(rendered, safe="")
            values[f"{key}_raw"] = rendered
            values[f"{key}_encoded"] = quote(rendered, safe="")

    unresolved = set()

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in values and values[key] != "":
            return values[key]
        unresolved.add(key)
        return match.group(0)

    rendered = re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", _replace, proxy_str)
    if unresolved:
        keys = ", ".join(sorted(unresolved))
        raise ValueError(f"代理模板缺少变量: {keys}")
    return rendered


def resolve_proxy_setting(
    proxy_str: str,
    *,
    account_id: str = "",
    email: str = "",
    extra: Optional[Dict[str, Any]] = None,
    default_account: Optional[str] = None,
) -> Tuple[str, str]:
    """先渲染代理模板，再解析代理 URL 与 NO_PROXY。"""
    rendered = render_proxy_template(
        proxy_str,
        account_id=account_id,
        email=email,
        extra=extra,
        default_account=default_account,
    )
    return parse_proxy_setting(rendered)


@contextmanager
def proxy_runtime_context(
    *,
    account_id: str = "",
    email: str = "",
    extra: Optional[Dict[str, Any]] = None,
):
    """为当前协程设置代理模板上下文，供动态 HTTP 客户端按账号渲染代理。"""
    current = dict(_RUNTIME_PROXY_CONTEXT.get() or {})
    if account_id:
        current["account"] = account_id
        current["account_id"] = account_id
    if email:
        current["email"] = email
    if extra:
        for key, value in extra.items():
            if value is None:
                continue
            current[key] = str(value)
    token = _RUNTIME_PROXY_CONTEXT.set(current)
    try:
        yield current
    finally:
        _RUNTIME_PROXY_CONTEXT.reset(token)


def get_proxy_runtime_context() -> Dict[str, str]:
    """读取当前协程的代理模板上下文。"""
    return dict(_RUNTIME_PROXY_CONTEXT.get() or {})


def extract_host(url: str) -> str:
    """
    从 URL 中提取主机名

    Args:
        url: 完整 URL，如 "https://mail.chatgpt.org.uk/api/emails"

    Returns:
        str: 主机名，如 "mail.chatgpt.org.uk"
    """
    if not url:
        return ""

    url = url.strip()
    if not url:
        return ""

    # 如果没有协议前缀，添加一个以便解析
    if not url.startswith(("http://", "https://", "socks5://", "socks5h://")):
        url = "http://" + url

    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


def no_proxy_matches(host: str, no_proxy: str) -> bool:
    """
    检查主机是否在 NO_PROXY 豁免列表中

    Args:
        host: 要检查的主机名，如 "mail.chatgpt.org.uk"
        no_proxy: NO_PROXY 列表字符串，如 "localhost,127.0.0.1,.local"

    Returns:
        bool: 如果主机在豁免列表中返回 True，否则返回 False

    匹配规则:
        - 精确匹配: "localhost" 匹配 "localhost"
        - 域名后缀匹配: ".local" 匹配 "foo.local", "bar.foo.local"
        - IP 地址匹配: "127.0.0.1" 精确匹配
    """
    if not host or not no_proxy:
        return False

    host = host.lower().strip()
    if not host:
        return False

    # 解析 no_proxy 列表
    no_proxy_list = [item.strip().lower() for item in no_proxy.split(",") if item.strip()]

    for pattern in no_proxy_list:
        if not pattern:
            continue

        # 精确匹配
        if host == pattern:
            return True

        # 域名后缀匹配 (如 .local 匹配 foo.local)
        if pattern.startswith("."):
            if host.endswith(pattern) or host == pattern[1:]:
                return True
        else:
            # 也支持不带点的后缀匹配 (如 local 匹配 foo.local)
            if host.endswith("." + pattern):
                return True

    return False


def normalize_proxy_url(proxy_str: str) -> str:
    """
    标准化代理 URL 格式

    支持的输入格式:
    - http://127.0.0.1:7890
    - http://user:pass@127.0.0.1:7890
    - socks5://127.0.0.1:7890
    - socks5h://127.0.0.1:7890
    - 127.0.0.1:7890 (自动添加 http://)
    - host:port:user:pass (旧格式，自动转换)

    Returns:
        str: 标准化的代理 URL
    """
    if not proxy_str:
        return ""

    proxy_str = proxy_str.strip()
    if not proxy_str:
        return ""

    # 如果已经是标准 URL 格式，直接返回
    if proxy_str.startswith(("http://", "https://", "socks5://", "socks5h://")):
        return proxy_str

    # 尝试解析旧格式 host:port:user:pass
    parts = proxy_str.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    elif len(parts) == 2:
        # host:port 格式
        return f"http://{proxy_str}"

    # 无法识别的格式，尝试添加 http:// 前缀
    return f"http://{proxy_str}"


def parse_resin_proxy_action(proxy_url: str) -> Optional[Dict[str, str]]:
    """
    从标准 Resin 代理 URL 中提取 rotate 所需信息。

    期望格式：
    - http://Platform.Account:TOKEN@resin:2260
    """
    if not proxy_url:
        return None

    normalized = normalize_proxy_url(proxy_url)
    parsed = urlparse(normalized)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.hostname or not parsed.username or not parsed.password:
        return None

    userinfo = unquote(parsed.username)
    if "." not in userinfo:
        return None

    platform, account = userinfo.split(".", 1)
    platform = platform.strip()
    account = account.strip()
    token = unquote(parsed.password).strip()
    if not platform or not account or not token:
        return None

    base_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        base_url = f"{base_url}:{parsed.port}"

    return {
        "base_url": base_url.rstrip("/"),
        "platform": platform,
        "account": account,
        "token": token,
    }


def rotate_resin_proxy_sync(
    proxy_setting: str,
    *,
    account_id: str = "",
    email: str = "",
    extra: Optional[Dict[str, Any]] = None,
    default_account: Optional[str] = None,
    timeout: float = 15.0,
    log_callback: Optional[Callable[[str, str], None]] = None,
) -> bool:
    """
    根据代理模板自动调用 Resin 的 token rotate API。

    返回：
    - True: Rotate 请求成功
    - False: 非 Resin URL / 接口失败 / 无法解析
    """
    def _log(level: str, message: str) -> None:
        if log_callback:
            log_callback(level, message)

    try:
        proxy_url, _ = resolve_proxy_setting(
            proxy_setting,
            account_id=account_id,
            email=email,
            extra=extra,
            default_account=default_account,
        )
    except Exception as exc:
        _log("warning", f"⚠️ 解析代理模板失败，无法 rotate: {exc}")
        return False

    resin = parse_resin_proxy_action(proxy_url)
    if not resin:
        _log("info", "ℹ️ 当前代理不是 Resin 标准地址，跳过 rotate")
        return False

    endpoint = (
        f"{resin['base_url']}/"
        f"{quote(resin['token'], safe='')}/api/v1/"
        f"{quote(resin['platform'], safe='')}/actions/rotate-lease"
    )
    payload = {"account": resin["account"]}

    try:
        response = requests.post(endpoint, json=payload, timeout=timeout, verify=False)
    except Exception as exc:
        _log("warning", f"⚠️ 调用 Resin rotate API 失败: {exc}")
        return False

    if response.status_code == 200:
        _log("warning", f"♻️ Resin 已接受 rotate 请求: {resin['platform']}/{resin['account']}")
        return True

    detail = response.text[:300] if response.text else f"HTTP {response.status_code}"
    _log("warning", f"⚠️ Resin rotate API 返回异常: {response.status_code} {detail}")
    return False


class ProxyTemplateAsyncClient:
    """
    基于上下文动态渲染代理模板的轻量包装器。

    目的：
    - 让聊天链路继续像用 httpx.AsyncClient 一样调用 get/post/stream
    - 按当前账户上下文自动落到不同的 Resin 粘性代理地址
    """

    def __init__(
        self,
        proxy_setting_supplier: Callable[[], str],
        *,
        default_account: str = "shared",
        **client_kwargs,
    ) -> None:
        self._proxy_setting_supplier = proxy_setting_supplier
        self._default_account = default_account
        self._client_kwargs = client_kwargs
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._lock = threading.Lock()

    def _resolve_proxy_url(self) -> str:
        proxy_setting = (self._proxy_setting_supplier() or "").strip()
        if not proxy_setting:
            return ""

        ctx = get_proxy_runtime_context()
        proxy_url, _ = resolve_proxy_setting(
            proxy_setting,
            account_id=ctx.get("account_id") or ctx.get("account") or "",
            email=ctx.get("email") or "",
            extra=ctx,
            default_account=self._default_account,
        )
        return proxy_url

    def _get_client(self) -> httpx.AsyncClient:
        proxy_url = self._resolve_proxy_url()
        key = proxy_url or "__direct__"
        with self._lock:
            client = self._clients.get(key)
            if client is None:
                kwargs = dict(self._client_kwargs)
                kwargs["proxy"] = proxy_url or None
                client = httpx.AsyncClient(**kwargs)
                self._clients[key] = client
            return client

    async def get(self, *args, **kwargs):
        return await self._get_client().get(*args, **kwargs)

    async def post(self, *args, **kwargs):
        return await self._get_client().post(*args, **kwargs)

    async def request(self, *args, **kwargs):
        return await self._get_client().request(*args, **kwargs)

    def stream(self, *args, **kwargs):
        return self._get_client().stream(*args, **kwargs)

    async def aclose(self) -> None:
        with self._lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            await client.aclose()


def request_with_proxy_fallback(request_func: Callable, *args, **kwargs) -> Any:
    """
    带代理失败回退的请求包装器

    如果代理连接失败，自动禁用代理重试一次

    Args:
        request_func: 原始请求函数
        *args, **kwargs: 传递给请求函数的参数

    Returns:
        请求响应对象

    Raises:
        原始异常（如果直连也失败）
    """
    # 代理相关的错误类型
    PROXY_ERRORS = (
        "ProxyError",
        "ConnectTimeout",
        "ConnectionError",
        "407",  # Proxy Authentication Required
        "502",  # Bad Gateway (代理问题)
        "503",  # Service Unavailable (代理问题)
    )

    try:
        # 首次尝试（使用代理）
        return request_func(*args, **kwargs)
    except Exception as e:
        error_str = str(e)
        error_type = type(e).__name__

        # 检查是否是代理相关错误
        is_proxy_error = any(err in error_str or err in error_type for err in PROXY_ERRORS)

        if is_proxy_error and "proxies" in kwargs:
            # 禁用代理重试
            original_proxies = kwargs.get("proxies")
            kwargs["proxies"] = None

            try:
                # 直连重试
                return request_func(*args, **kwargs)
            except Exception:
                # 直连也失败，恢复原始代理设置并抛出原始异常
                kwargs["proxies"] = original_proxies
                raise e
        else:
            # 不是代理错误，直接抛出
            raise
