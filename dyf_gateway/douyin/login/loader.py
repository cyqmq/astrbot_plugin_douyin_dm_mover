"""加载 DouYin_Spider 登录闭包（vendored/login），并提供 2046 二次验证注入。

DouYin_Spider 的 login_api.py 以顶层包导入（``from builder.auth import ...``），
因此本模块将其根目录临时加入 sys.path 后再导入，不重写其任何算法。
2046 由 login_api 内部 ``_raise_if_blocked`` 抛出；这里在不改动 login_api.py 的
前提下，用 patch 拦截：把 2046 转交给注入的 MFA 处理器（按 token 只处理一次），
并吞掉异常让 qrcode_login 继续轮询同一个 token 等风控放行。

注意：本模块不得引入 astrbot（子进程 worker 也会用到登录）。
"""
from __future__ import annotations

import os
import sys

_LOGIN_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vendored", "login"
)

_LOADED = False
_MFA_HANDLER = None
_SENTINEL = object()
_CTX: dict = {"auth": None, "token": None, "handled_token": _SENTINEL}


def _ensure_path() -> None:
    if _LOGIN_ROOT not in sys.path:
        sys.path.insert(0, _LOGIN_ROOT)


def load_login_api():
    """返回 DYLoginApi 类（已 patch 2046 注入）。"""
    global _LOADED
    _ensure_path()
    from dy_apis.login_api import DYLoginApi

    if not _LOADED:
        _install_patch(DYLoginApi)
        _LOADED = True
    return DYLoginApi


def load_douyin_auth():
    """返回 builder.auth.DouyinAuth 类。"""
    _ensure_path()
    from builder.auth import DouyinAuth

    return DouyinAuth


def set_mfa_handler(handler) -> None:
    """handler(auth, res) -> None；res 为 check_qrconnect 的 2046 响应。"""
    global _MFA_HANDLER
    _MFA_HANDLER = handler


def reset_mfa() -> None:
    _CTX.update(auth=None, token=None, handled_token=_SENTINEL)


def _install_patch(dy_login_api_cls) -> None:
    orig_check = dy_login_api_cls.check_qrcode
    orig_raise = dy_login_api_cls._raise_if_blocked

    def _check(self, auth, token):
        _CTX["auth"] = auth
        _CTX["token"] = token
        return orig_check(self, auth, token)

    def _raise(api, res):
        code = (res.get("data") or {}).get("error_code")
        if code == 2046 and _MFA_HANDLER is not None:
            if _CTX.get("handled_token") != _CTX.get("token"):
                _CTX["handled_token"] = _CTX.get("token")
                try:
                    _MFA_HANDLER(_CTX.get("auth"), res)
                except Exception:
                    pass
            return
        return orig_raise(api, res)

    dy_login_api_cls.check_qrcode = _check
    dy_login_api_cls._raise_if_blocked = staticmethod(_raise)
