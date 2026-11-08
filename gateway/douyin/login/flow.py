"""登录编排：扫码登录（复用 DouYin_Spider login_api.py）+ 会话持久化。

qrcode_login 为阻塞循环（含 2046 注入），由调用方放入后台线程运行。
登录成功后调用 LoginFlow 把会话写入 data 目录；已有有效会话可直接 build_auth 复用。
"""
from __future__ import annotations

from .loader import load_login_api, reset_mfa, set_mfa_handler
from .session import SessionStore


class LoginFlow:
    def __init__(self, data_dir: str, mfa_handler=None, on_qrcode=None, on_log=None):
        self.session = SessionStore(data_dir)
        self.mfa_handler = mfa_handler
        self.on_qrcode = on_qrcode
        self.on_log = on_log or (lambda m: None)

    def existing_auth(self):
        """已有有效会话 → 重建 auth；否则 None。"""
        if self.session.has_valid():
            return self.session.build_auth()
        return None

    def qrcode_login(self, timeout: int = 300):
        """阻塞扫码登录；成功返回登录后 auth（已落盘会话）。"""
        DYLoginApi = load_login_api()
        set_mfa_handler(self.mfa_handler)
        reset_mfa()
        api = DYLoginApi()
        auth = api.qrcode_login(
            timeout=timeout, show_qr=False, on_qrcode=self.on_qrcode
        )
        self.session.save(auth)
        self.on_log("扫码登录成功，会话已保存")
        return auth
