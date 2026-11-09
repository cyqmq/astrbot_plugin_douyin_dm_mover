"""纯 Python 登录后端：@alemonjs/douyin 核心的 Python 移植（无 Node 依赖）。

接口与 ``AlemonjsLogin`` 对齐（``qrcode_login_async``），gateway 用它作为默认后端。
"""
from __future__ import annotations

import asyncio

from .alemonjs import AlemonjsResult
from .alemonjs_py import DouyinHttpPy, get_qrcode, poll_qr_confirm


class AlemonsPyLogin:
    """纯 Python 扫码登录（desktop + 2046 MFA），无 Node/子进程依赖。"""

    def __init__(self, on_qrcode=None, on_log=None, code_waiter=None):
        self._on_qrcode = on_qrcode or (lambda ev: None)
        self._on_log = on_log or (lambda text: None)
        self._code_waiter = code_waiter

    def _log(self, text: str) -> None:
        try:
            self._on_log(text)
        except Exception:
            pass

    async def qrcode_login_async(self, timeout: int = 300) -> AlemonjsResult:
        http = DouyinHttpPy({})
        self._log("纯 Python 登录：生成二维码")

        async def on_status(text: str) -> None:
            self._log(str(text))

        async def on_mfa(req: dict) -> str:
            kind = req.get("kind")
            if kind == "password":
                raise RuntimeError("登录触发密码二次验证，Python 后端暂不支持密码输入")
            if self._code_waiter is None:
                raise RuntimeError("需要短信验证码但无喂码通道，请在抖音 App 完成验证")
            mobile = req.get("maskedMobile")
            code = await asyncio.to_thread(
                self._code_waiter.code_source, mobile, lambda: None
            )
            if not code:
                raise RuntimeError("未收到短信验证码")
            self._log("验证码已提交，等待校验")
            return code

        info = get_qrcode(http)
        self._on_qrcode({"qrcodeBase64": info["qrcodeBase64"]})
        self._log("二维码已生成（纯 Python）")
        session = await poll_qr_confirm(
            http,
            info["token"],
            {
                "timeoutMs": max(60, int(timeout)) * 1000,
                "onStatus": on_status,
                "onMfa": on_mfa,
            },
        )
        device_id = http.device_id if http.has_desktop_device() else None
        return AlemonjsResult(
            cookie_str=session["cookies"],
            uid=session["platformUid"],
            device_id=device_id,
            user_data=session.get("userData"),
        )
