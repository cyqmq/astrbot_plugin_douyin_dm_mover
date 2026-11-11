"""HTTP 客户端（@alemonjs/douyin http/client.js + cookie.js + aid-sign.js 移植）。

用 requests 实现，Cookie 整站共享（不区分 domain/path，同参考实现）。
"""
from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlparse

import requests

from .sign import (
    DESKTOP_AID,
    DESKTOP_ORIGIN,
    DESKTOP_PASSPORT_APP_KEY,
    passport_noon_utc_ts,
    random_biz_trace_id,
    random_desktop_hex,
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)
CREATOR_ORIGIN = "https://creator.douyin.com"
CREATOR_AID = "2906"
CREATOR_PASSPORT_APP_KEY = "6ddd3ec693f3a124adb29b91b244ece5"


class CookieJarPy:
    """整站共享键值对 Cookie（同参考实现，不区分 domain/path）。"""

    def __init__(self, initial: str = ""):
        self._store: dict[str, str] = {}
        if initial:
            self.merge(initial)

    def get(self, name: str) -> str | None:
        return self._store.get(name)

    def has(self, name: str) -> bool:
        return name in self._store

    def set(self, name: str, value: str) -> None:
        self._store[name] = value

    def delete(self, name: str) -> None:
        self._store.pop(name, None)

    def merge(self, raw: str) -> None:
        for part in raw.split(";") + raw.split("\n"):
            part = part.strip()
            if not part:
                continue
            eq = part.find("=")
            if eq <= 0:
                continue
            name = part[:eq].strip()
            value = part[eq + 1 :].strip()
            low = name.lower()
            if (
                not name
                or low in ("path", "domain", "expires", "max-age", "secure", "httponly", "samesite")
            ):
                continue
            self._store[name] = value

    def to_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self._store.items())

    def merge_set_cookie(self, raw: str) -> None:
        if not raw:
            return
        import re

        parts = re.split(r",(?=\s*[^\s;,=]+\s*=)", raw)
        now = int(time.time() * 1000)
        for line in parts:
            seg = line.split(";")
            pair = seg[0]
            eq = pair.find("=")
            if eq <= 0:
                continue
            name = pair[:eq].strip()
            value = pair[eq + 1 :].strip()
            max_age = None
            expires = None
            for attribute in seg[1:]:
                sep = attribute.find("=")
                if sep < 0:
                    continue
                key = attribute[:sep].strip().lower()
                val = attribute[sep + 1 :].strip()
                if key == "max-age" and val.lstrip("-").isdigit():
                    max_age = int(val)
                if key == "expires":
                    try:
                        expires = _parse_http_date(val)
                    except Exception:
                        expires = None
            if max_age is not None:
                if max_age <= 0:
                    self._store.pop(name, None)
                else:
                    self._store[name] = value
            elif expires is not None and expires <= now:
                self._store.pop(name, None)
            else:
                self._store[name] = value


def _parse_http_date(value: str) -> int:
    import email.utils

    dt = email.utils.parsedate_to_datetime(value)
    return int(dt.timestamp() * 1000)


def _hmac_sha256_hex(key: bytes, message: bytes) -> str:
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _hex_to_bytes(hex_str: str) -> bytes:
    if len(hex_str) % 2 == 1:
        hex_str = "0" + hex_str
    return bytes.fromhex(hex_str)


def _derive_passport_sign_key(password: bytes, salt: bytes, length: int = 32) -> bytes:
    pw = password if password else bytes(32)
    first_hex = _hmac_sha256_hex(pw, salt)
    fixed_key = _hex_to_bytes(first_hex)
    rolling_hex = first_hex
    out = bytearray()
    round_ = 1
    while len(out) < length:
        rolling_hex = _hmac_sha256_hex(
            fixed_key, _hex_to_bytes(rolling_hex) + round_.to_bytes(1, "big")
        )
        out.extend(_hex_to_bytes(rolling_hex))
        round_ += 1
    return bytes(out[:length])


def build_passport_aid_sign(aid: str, path: str, ts: str, app_key: str | None = None) -> str:
    """x-tt-passport-aid-sign（64 hex HMAC-SHA256）。"""
    key = _derive_passport_sign_key(ts.encode("utf-8"), (app_key or CREATOR_PASSPORT_APP_KEY).encode("utf-8"), 32)
    message = f"aid={aid}&path={path}&ts={ts}"
    return _hmac_sha256_hex(key, message.encode("utf-8"))


class DouyinHttpPy:
    """抖音 HTTP 客户端：Cookie/UA/超时 + Passport 请求头 + 标准参数。"""

    def __init__(
        self,
        initial_cookies: str = "",
        user_agent: str = DEFAULT_USER_AGENT,
        enable_abogus: bool = True,
        enable_auto_aid_sign: bool = True,
        timeout: int = 30,
    ):
        self.jar = CookieJarPy(initial_cookies)
        self.user_agent = user_agent
        self.enable_abogus = enable_abogus
        self.enable_auto_aid_sign = enable_auto_aid_sign
        self.timeout = timeout
        self.device_id = "0"
        self.install_id = "0"
        self.guid = random_desktop_hex(32)
        self.biz_trace_id = random_biz_trace_id()
        self._verify_portrait = "login"
        if not self.jar.has("biz_trace_id"):
            self.jar.set("biz_trace_id", self.biz_trace_id)

    def get_cookies(self) -> str:
        return self.jar.to_header()

    def set_ms_token(self, value: str) -> None:
        self.jar.set("msToken", value)

    def get_ms_token(self) -> str | None:
        return self.jar.get("msToken")

    def get_user_agent(self) -> str:
        return self.user_agent

    def set_device(self, device: dict) -> None:
        self.device_id = str(device.get("deviceId") or self.device_id)
        self.install_id = str(device.get("installId") or self.install_id)
        self.guid = str(device.get("guid") or self.guid)

    def has_desktop_device(self) -> bool:
        return self.device_id != "0" and self.device_id.isdigit()

    def passport_headers(self, request_url: str | None) -> dict:
        desktop = bool(request_url and request_url.startswith(DESKTOP_ORIGIN))
        headers = {
            "Accept": "application/json, text/javascript",
            "Referer": DESKTOP_ORIGIN if desktop else f"{CREATOR_ORIGIN}/creator-micro/home",
        }
        csrf = self.jar.get("passport_csrf_token") or self.jar.get("passport_csrf_token_default")
        if csrf:
            headers["x-tt-passport-csrf-token"] = csrf
        headers["x-tt-passport-trace-id"] = self.biz_trace_id
        aid_sign = self._resolve_aid_sign(request_url, desktop)
        if aid_sign:
            headers["x-tt-passport-aid-sign"] = aid_sign
        headers["x-tt-passport-verify-portrait"] = self._verify_portrait
        return headers

    def _resolve_aid_sign(self, request_url: str | None, desktop: bool = False) -> str | None:
        if not self.enable_auto_aid_sign or not request_url:
            return None
        try:
            path = urlparse(request_url).path
            hostname = urlparse(request_url).hostname or ""
            aid = DESKTOP_AID if desktop else CREATOR_AID
            app_key = DESKTOP_PASSPORT_APP_KEY if desktop else CREATOR_PASSPORT_APP_KEY
            if not (path.startswith("/passport") or "sso" in hostname):
                path = f"/passport/sso{path}"
            return build_passport_aid_sign(aid, path, passport_noon_utc_ts(), app_key)
        except Exception:
            return None

    def request_raw(self, url: str, method: str = "GET", headers: dict | None = None, body: str | None = None, timeout: int | None = None, allow_redirects: bool = True) -> requests.Response:
        h = dict(headers or {})
        h.setdefault("User-Agent", self.user_agent)
        host = urlparse(url).hostname or ""
        session_host = (
            host == "douyin.com"
            or host.endswith(".douyin.com")
            or host == "imapi3-normal.zijieapi.com"
        )
        if session_host:
            cookie = self.jar.to_header()
            if cookie:
                h["Cookie"] = cookie
        resp = requests.request(
            method, url, headers=h, data=body, timeout=timeout or self.timeout,
            allow_redirects=allow_redirects,
        )
        if session_host:
            self.jar.merge_set_cookie(resp.headers.get("set-cookie", ""))
        ms = resp.headers.get("x-ms-token")
        if ms and (session_host or host == "mssdk.bytedance.com"):
            self.set_ms_token(ms)
        return resp

    def request_json(self, url: str, method: str = "GET", headers: dict | None = None, body: str | None = None, timeout: int | None = None) -> dict:
        resp = self.request_raw(url, method, headers, body, timeout)
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status_code} {urlparse(url).path}: {resp.text[:200]}")
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(f"invalid JSON from {urlparse(url).path}: {resp.text[:200]}")
        if not isinstance(data, dict):
            raise TypeError(f"non-object JSON from {urlparse(url).path}")
        return data
