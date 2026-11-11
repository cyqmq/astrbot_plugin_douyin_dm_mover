"""www 扫码登录（DouYin_Spider vendored 链复用）：登录响应头下发票据。

www 登录（`www.douyin.com/passport/web/`）才在响应头 `bd-ticket-guard-server-data`
下发 `{ticket, ts_sign, client_cert}`；imdesktop 扫码不产票据。此模块：
- 取码前 `bootstrap_auth` 前置（写 `bd_ticket_guard_client_data` cookie，公钥交服务端——
  否则扫码成功但响应永远无票据）；
- 每跳登录重定向 `apply_ticket_guard` 自动解析票据（vendored 链内建）；
- 返回 ``AlemonjsResult``（含 cookie_str/uid/ts_sign/private_key/client_cert/server_cert）。

IM/WS 保持 imdesktop（改造点 4）：本模块只产票 + 登录态 cookie。
"""
from __future__ import annotations

import asyncio
import base64
import io
import os
import sys

from .alemonjs_py_login import AlemonjsResult


def _vendored_login_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "vendored", "login"))


def _load_dy_login_api():
    """加载 vendored DYLoginApi（把 vendored/login 加进 sys.path 解析其内部绝对导入）。"""
    d = _vendored_login_dir()
    if d not in sys.path:
        sys.path.insert(0, d)
    from dy_apis.login_api import DYLoginApi

    return DYLoginApi()


def _make_qr_callback(on_qrcode):
    """vendored on_qrcode 收 qrcode_index_url（URL）；转 PNG base64 data URL 给前端。"""

    def cb(qr_url: str) -> None:
        if not on_qrcode:
            return
        try:
            import qrcode

            img = qrcode.make(qr_url or "")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            on_qrcode({"qrcodeBase64": base64.b64encode(buf.getvalue()).decode()})
        except Exception:
            on_qrcode({"qrcodeIndexUrl": qr_url or ""})

    return cb


def www_qrcode_login_sync(on_qrcode=None, timeout: int = 300):
    """同步 www 扫码（产票），返回 vendored DouyinAuth（含 ticket/ts_sign/client_cert/private_key）。"""
    api = _load_dy_login_api()
    return api.qrcode_login(
        timeout=timeout, show_qr=False, on_qrcode=_make_qr_callback(on_qrcode)
    )


def _result_from_auth(auth) -> AlemonjsResult:
    cookie = dict(getattr(auth, "cookie", None) or {})
    cookie_str = getattr(auth, "cookie_str", None) or "; ".join(
        f"{k}={v}" for k, v in cookie.items()
    )
    uid = str(getattr(auth, "uid", None) or cookie.get("uid_tt") or "")
    return AlemonjsResult(
        cookie_str=cookie_str,
        uid=uid,
        ticket=getattr(auth, "ticket", None) or "",
        ts_sign=getattr(auth, "ts_sign", None) or "",
        private_key=getattr(auth, "private_key", None) or "",
        client_cert=getattr(auth, "client_cert", None) or "",
        server_cert=getattr(auth, "server_cert", None) or "",
    )


async def www_qrcode_login_async(timeout: int = 300, on_qrcode=None) -> AlemonjsResult:
    """async 封装：www 扫码登录，返回 AlemonjsResult（含票据字段）。"""
    auth = await asyncio.to_thread(www_qrcode_login_sync, on_qrcode, timeout)
    return _result_from_auth(auth)
