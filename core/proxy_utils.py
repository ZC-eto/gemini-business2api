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
import json
import os
import re
import shutil
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Tuple, Callable, Any, Optional, Dict, List
from urllib.parse import quote, unquote, urlparse

import httpx
import requests

_RUNTIME_PROXY_CONTEXT: contextvars.ContextVar[Dict[str, str]] = contextvars.ContextVar(
    "runtime_proxy_context",
    default={},
)

_PROXY_GEO_ENDPOINTS = (
    "https://api.ip.sb/geoip",
    "https://ipapi.co/json/",
    "https://ipinfo.io/json",
)

_CHROMIUM_PATHS = (
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
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


def parse_proxy_components(proxy_url: str) -> Optional[Dict[str, Any]]:
    """解析标准代理 URL 的组成部分。"""
    if not proxy_url:
        return None

    normalized = normalize_proxy_url(proxy_url)
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.hostname:
        return None

    port = parsed.port
    if port is None:
        if parsed.scheme == "https":
            port = 443
        elif parsed.scheme in ("socks5", "socks5h"):
            port = 1080
        else:
            port = 80

    return {
        "scheme": parsed.scheme.lower(),
        "host": parsed.hostname,
        "port": int(port),
        "username": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "url": normalized,
    }


def mask_proxy_url(proxy_url: str) -> str:
    """对代理 URL 中的敏感信息做脱敏。"""
    components = parse_proxy_components(proxy_url)
    if not components:
        return proxy_url or ""

    auth = ""
    if components["username"]:
        auth = quote(components["username"], safe="")
        if components["password"]:
            auth = f"{auth}:***"
        auth = f"{auth}@"

    return f"{components['scheme']}://{auth}{components['host']}:{components['port']}"


def find_chromium_path() -> Optional[str]:
    """查找 Linux/Docker 环境中的 Chromium 可执行文件。"""
    for path in _CHROMIUM_PATHS:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return None


def prepare_chromium_proxy(proxy_url: str) -> Dict[str, Any]:
    """
    将代理 URL 转换为 Chromium 可用配置。

    返回：
    - browser_proxy_url: 传给 --proxy-server 的地址
    - extension_dir: 如需处理 HTTP 代理认证，则返回临时扩展目录
    - warnings: 浏览器代理层的提示信息
    """
    components = parse_proxy_components(proxy_url)
    if not components:
        return {
            "browser_proxy_url": proxy_url,
            "extension_dir": None,
            "apply_via_argument": True,
            "warnings": ["代理地址无法解析，浏览器可能无法使用该配置。"],
        }

    scheme = components["scheme"]
    host = components["host"]
    port = components["port"]
    username = components["username"]
    password = components["password"]
    warnings: List[str] = []

    if username or password:
        if scheme not in ("http", "https"):
            return {
                "browser_proxy_url": f"{scheme}://{host}:{port}",
                "extension_dir": None,
                "apply_via_argument": True,
                "warnings": [
                    "当前代理包含认证信息，但浏览器层仅为 HTTP/HTTPS 代理自动注入认证；该代理类型可能无法用于浏览器自动化。"
                ],
            }

        extension_dir = tempfile.mkdtemp(prefix="gb2api-proxy-auth-")
        manifest = {
            "manifest_version": 3,
            "name": "Gemini Business2API Proxy Auth",
            "version": "1.0.0",
            "permissions": [
                "proxy",
                "storage",
                "webRequest",
                "webRequestAuthProvider",
            ],
            "host_permissions": ["<all_urls>"],
            "background": {
                "service_worker": "background.js",
            },
        }
        proxy_config = {
            "mode": "fixed_servers",
            "rules": {
                "singleProxy": {
                    "scheme": scheme,
                    "host": host,
                    "port": port,
                },
                "bypassList": ["localhost", "127.0.0.1"],
            },
        }
        credentials = {
            "username": username,
            "password": password,
        }
        background = f"""
const proxyConfig = {json.dumps(proxy_config, ensure_ascii=False)};
const credentials = {json.dumps(credentials, ensure_ascii=False)};

function applyProxyConfig() {{
  chrome.proxy.settings.set({{ value: proxyConfig, scope: 'regular' }}, () => {{}});
}}

chrome.runtime.onInstalled.addListener(applyProxyConfig);
chrome.runtime.onStartup.addListener(applyProxyConfig);
applyProxyConfig();

chrome.webRequest.onAuthRequired.addListener(
  () => ({{ authCredentials: credentials }}),
  {{ urls: ['<all_urls>'] }},
  ['blocking']
);
""".strip()

        Path(extension_dir, "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        Path(extension_dir, "background.js").write_text(background, encoding="utf-8")
        warnings.append("已为浏览器临时注入代理认证扩展，用于处理带账号密码的 HTTP 代理。")
        return {
            "browser_proxy_url": f"{scheme}://{host}:{port}",
            "extension_dir": extension_dir,
            "apply_via_argument": False,
            "warnings": warnings,
        }

    return {
        "browser_proxy_url": f"{scheme}://{host}:{port}",
        "extension_dir": None,
        "apply_via_argument": True,
        "warnings": warnings,
    }


def cleanup_temp_dir(path: Optional[str]) -> None:
    """清理临时目录。"""
    if not path:
        return
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _normalize_geo_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ip": payload.get("ip") or payload.get("query") or payload.get("ipAddress") or "",
        "country": payload.get("country") or payload.get("country_name") or "",
        "country_code": payload.get("country_code") or payload.get("countryCode") or "",
        "region": payload.get("region") or payload.get("region_name") or "",
        "city": payload.get("city") or "",
        "organization": payload.get("organization") or payload.get("org") or payload.get("isp") or payload.get("asn_organization") or "",
    }


def _extract_geo_payload_from_text(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        return _normalize_geo_payload(json.loads(text))
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return _normalize_geo_payload(json.loads(match.group(0)))
        except Exception:
            return {}
    return {}


def _normalize_proxy_type(proxy_type: str) -> str:
    value = (proxy_type or "auto").strip().lower()
    if value in ("auto", "standard", "resin"):
        return value
    return "auto"


def _build_proxy_test_warnings(
    proxy_setting: str,
    proxy_url: str,
    *,
    purpose: str = "",
    proxy_type: str = "auto",
) -> List[str]:
    proxy_type = _normalize_proxy_type(proxy_type)
    warnings: List[str] = []
    resin = parse_resin_proxy_action(proxy_url)
    if proxy_type == "resin" and not resin:
        warnings.append("当前已选择 Resin 代理，但地址不符合 Resin 标准格式；rotate 和平台/账号识别不会生效。")
    if proxy_type == "standard" and resin:
        warnings.append("当前已选择普通代理，但地址看起来是 Resin 标准地址；如果要使用 rotate 和平台/账号识别，建议切换为 Resin 代理。")

    if resin and "{account}" not in (proxy_setting or "") and "{account_id}" not in (proxy_setting or "") and "{email}" not in (proxy_setting or ""):
        warnings.append("当前是固定账号地址，所有账号会共享同一个粘性租约；如果要按账号独立保持 IP，建议改成 {account} 模板。")

    if resin and purpose == "auth" and resin["platform"].strip().lower() == "chat":
        warnings.append("当前是账户操作代理，但平台名看起来是 chat；如果你有独立的 auth 平台，建议改成 auth.{account}。")
    if resin and purpose == "chat" and resin["platform"].strip().lower() == "auth":
        warnings.append("当前是聊天操作代理，但平台名看起来是 auth；如果你有独立的 chat 平台，建议改成 chat.{account}。")

    components = parse_proxy_components(proxy_url)
    if components and (components["username"] or components["password"]):
        warnings.append("这是带认证信息的代理地址，HTTP 客户端通常可直接使用；浏览器层需要额外处理代理认证。")
    return warnings


def probe_http_proxy_sync(
    proxy_setting: str,
    *,
    purpose: str = "",
    proxy_type: str = "auto",
    account_id: str = "",
    email: str = "",
    default_account: str = "proxy_test",
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """通过 requests 验证代理的 HTTP 连通性，并返回出口地理信息。"""
    proxy_url, no_proxy = resolve_proxy_setting(
        proxy_setting,
        account_id=account_id,
        email=email,
        default_account=default_account,
    )
    if not proxy_url:
        raise ValueError("代理地址为空")

    warnings = _build_proxy_test_warnings(proxy_setting, proxy_url, purpose=purpose, proxy_type=proxy_type)
    last_error = None
    for endpoint in _PROXY_GEO_ENDPOINTS:
        try:
            response = requests.get(
                endpoint,
                proxies={"http": proxy_url, "https": proxy_url},
                timeout=timeout,
                verify=False,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            geo = _extract_geo_payload_from_text(response.text)
            if not geo:
                raise ValueError("地理信息返回无法解析")

            return {
                "success": True,
                "mode": "http",
                "proxy_url": mask_proxy_url(proxy_url),
                "no_proxy": no_proxy,
                "endpoint": endpoint,
                "warnings": warnings,
                "geo": geo,
                "resin": parse_resin_proxy_action(proxy_url),
            }
        except Exception as exc:
            last_error = str(exc)

    return {
        "success": False,
        "mode": "http",
        "proxy_url": mask_proxy_url(proxy_url),
        "no_proxy": no_proxy,
        "warnings": warnings,
        "resin": parse_resin_proxy_action(proxy_url),
        "error": last_error or "代理连通性测试失败",
    }


def probe_browser_proxy_sync(
    proxy_setting: str,
    *,
    purpose: str = "",
    proxy_type: str = "auto",
    account_id: str = "",
    email: str = "",
    default_account: str = "proxy_test",
    browser_mode: str = "normal",
    user_agent: str = "",
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """使用真实 Chromium 浏览器验证代理是否生效。"""
    proxy_url, no_proxy = resolve_proxy_setting(
        proxy_setting,
        account_id=account_id,
        email=email,
        default_account=default_account,
    )
    if not proxy_url:
        raise ValueError("代理地址为空")

    from DrissionPage import ChromiumOptions, ChromiumPage

    warnings = _build_proxy_test_warnings(proxy_setting, proxy_url, purpose=purpose, proxy_type=proxy_type)
    chromium_path = find_chromium_path()
    if not chromium_path:
        return {
            "success": False,
            "mode": "browser",
            "proxy_url": mask_proxy_url(proxy_url),
            "no_proxy": no_proxy,
            "warnings": warnings,
            "resin": parse_resin_proxy_action(proxy_url),
            "error": "当前运行环境未找到 Chromium/Chrome，可先使用 HTTP 测试确认代理可达。",
        }

    options = ChromiumOptions()
    options.set_browser_path(chromium_path)
    options.set_argument("--incognito")
    options.set_argument("--no-sandbox")
    options.set_argument("--disable-dev-shm-usage")
    options.set_argument("--disable-setuid-sandbox")
    options.set_argument("--disable-blink-features=AutomationControlled")
    options.set_argument("--lang=zh-CN")
    options.set_pref("intl.accept_languages", "zh-CN,zh")
    options.set_argument("--window-size=1366,768")
    if user_agent:
        options.set_user_agent(user_agent)

    extension_dir = None
    try:
        proxy_config = prepare_chromium_proxy(proxy_url)
        extension_dir = proxy_config["extension_dir"]
        warnings.extend(proxy_config["warnings"])
        if proxy_config["apply_via_argument"]:
            options.set_argument("--proxy-server", proxy_config["browser_proxy_url"])
        else:
            options.set_proxy(proxy_config["browser_proxy_url"])
        if extension_dir:
            options.add_extension(extension_dir)

        normalized_mode = (browser_mode or "normal").strip().lower()
        if normalized_mode == "headless":
            options.set_argument("--headless", "new")
            options.set_argument("--disable-gpu")
        elif normalized_mode == "silent":
            options.set_argument("--start-minimized")

        options.auto_port()
        page = ChromiumPage(options)
        user_data_dir = getattr(page, "user_data_dir", None)
        try:
            page.set.timeouts(timeout)
            last_error = None
            for endpoint in _PROXY_GEO_ENDPOINTS:
                try:
                    page.get(endpoint, timeout=timeout, show_errmsg=True)
                    body = page.ele("tag:body", timeout=5)
                    text = body.text if body else (page.html or "")
                    geo = _extract_geo_payload_from_text(text)
                    if not geo:
                        raise ValueError("浏览器返回未包含可解析的出口信息")
                    return {
                        "success": True,
                        "mode": "browser",
                        "proxy_url": mask_proxy_url(proxy_url),
                        "no_proxy": no_proxy,
                        "endpoint": endpoint,
                        "warnings": warnings,
                        "geo": geo,
                        "browser_mode": normalized_mode,
                        "resin": parse_resin_proxy_action(proxy_url),
                    }
                except Exception as exc:
                    last_error = str(exc)
            return {
                "success": False,
                "mode": "browser",
                "proxy_url": mask_proxy_url(proxy_url),
                "no_proxy": no_proxy,
                "warnings": warnings,
                "browser_mode": normalized_mode,
                "resin": parse_resin_proxy_action(proxy_url),
                "error": last_error or "浏览器代理测试失败",
            }
        finally:
            try:
                page.quit()
            except Exception:
                pass
            cleanup_temp_dir(user_data_dir)
    finally:
        cleanup_temp_dir(extension_dir)


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
