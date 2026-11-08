"""阻塞式验证码等待器：供 MfaHandler.code_source 使用（QQ 管理指令喂码）。

运行在登录线程内（qrcode_login 是阻塞循环）。两种模式：
- ``auto_sms``：进入即发码，等待 /dyf mfa <code> 提交。
- ``manual_command``：等待 /dyf mfa 触发发码（trigger_send），再等 /dyf mfa <code>。
"""
from __future__ import annotations

import threading


class CodeWaiter:
    def __init__(self, mode: str = "auto_sms", timeout: int = 300):
        self.mode = mode or "auto_sms"
        self.timeout = max(60, int(timeout or 300))
        self._ev = threading.Event()
        self._code: str | None = None
        self._send = None

    def code_source(self, mobile: str | None, send_fn) -> str:
        """阻塞取码。send_fn 执行发码；返回验证码或空串。"""
        self._send = send_fn
        self._code = None
        self._ev.clear()
        if self.mode == "auto_sms":
            self._run_send()
        self._ev.wait(self.timeout)
        return self._code or ""

    def trigger_send(self) -> None:
        """manual_command：/dyf mfa 命令触发发码。"""
        self._run_send()

    def submit(self, code: str) -> None:
        self._code = (code or "").strip()
        self._ev.set()

    def _run_send(self) -> None:
        if self._send is None:
            return
        try:
            self._send()
        except Exception:
            pass
