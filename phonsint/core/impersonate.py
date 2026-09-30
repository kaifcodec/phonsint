import asyncio
import threading
from typing import Literal, Optional, cast
from curl_cffi import requests as cffi

DEFAULT_IMPERSONATE = "chrome"
DEFAULT_TIMEOUT = 15.0

_sessions: dict[tuple, cffi.Session] = {}
_key_locks: dict[tuple, threading.Lock] = {}
_warmed: set[tuple] = set()
_lock = threading.Lock()
_global_timeout: Optional[float] = None
_global_proxy: Optional[str] = None


def set_global_timeout(val: Optional[float]) -> None:
    global _global_timeout
    _global_timeout = val


def get_global_timeout() -> float:
    return _global_timeout if _global_timeout is not None else DEFAULT_TIMEOUT


def set_global_proxy(val: Optional[str]) -> None:
    global _global_proxy
    _global_proxy = val


def get_global_proxy() -> Optional[str]:
    return _global_proxy


def _get_warm_session(
    impersonate: str,
    proxy: Optional[str],
    warmup_url: Optional[str] = None,
) -> cffi.Session:
    key = (impersonate, proxy)
    with _lock:
        session = _sessions.get(key)
        if session is None:
            session = cffi.Session(
                impersonate=impersonate,  # type: ignore[arg-type]
                proxies={"http": proxy, "https": proxy} if proxy else None,
            )
            _sessions[key] = session
            _key_locks[key] = threading.Lock()

        key_lock = _key_locks.get(key)
        if key_lock is None:
            key_lock = threading.Lock()
            _key_locks[key] = key_lock

    if warmup_url and key not in _warmed:
        with key_lock:
            if key not in _warmed:
                try:
                    session.get(warmup_url, timeout=get_global_timeout())
                except Exception:
                    pass
                _warmed.add(key)

    return session


def impersonate_request(
    url: str,
    method: Literal["GET", "POST"] = "GET",
    warmup_url: Optional[str] = None,
    impersonate: str = DEFAULT_IMPERSONATE,
    **kwargs,
) -> cffi.Response:
    """Issue a request through a cookie-persistent browser-impersonating curl_cffi session."""
    session = _get_warm_session(impersonate, get_global_proxy(), warmup_url)
    kwargs.setdefault("timeout", get_global_timeout())
    kwargs.setdefault("allow_redirects", False)
    return cast(cffi.Response, session.request(method, url, **kwargs))


async def impersonate_request_async(
    url: str,
    method: Literal["GET", "POST"] = "GET",
    warmup_url: Optional[str] = None,
    impersonate: str = DEFAULT_IMPERSONATE,
    **kwargs,
) -> cffi.Response:
    """Async wrapper around impersonate_request."""
    return await asyncio.to_thread(
        impersonate_request,
        url,
        method=method,
        warmup_url=warmup_url,
        impersonate=impersonate,
        **kwargs,
    )
