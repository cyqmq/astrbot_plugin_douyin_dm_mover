"""@alemonjs/douyin 登录核心的纯 Python 移植（desktop 扫码 + 2046 MFA）。"""
from __future__ import annotations

from .abogus import generate_jumpbyte_abogus
from .http import DouyinHttpPy
from .mixmode import code_encrypt, mix_mode_encode, pick_qr_biz_params, qr_mfa_body
from .qr import (
    check_qrconnect,
    desktop_lite_passport_form_post,
    get_qrcode,
    login_by_qrcode,
    poll_qr_confirm,
    send_qr_mfa_code,
    validate_qr_mfa_code,
)
from .sign import (
    build_passport_sign_qs,
    encode_desktop_passport_params,
    encode_form_body,
)
from .sm3 import sm3

__all__ = [
    "DouyinHttpPy",
    "build_passport_sign_qs",
    "check_qrconnect",
    "code_encrypt",
    "desktop_lite_passport_form_post",
    "encode_desktop_passport_params",
    "encode_form_body",
    "generate_jumpbyte_abogus",
    "get_qrcode",
    "login_by_qrcode",
    "mix_mode_encode",
    "pick_qr_biz_params",
    "poll_qr_confirm",
    "qr_mfa_body",
    "send_qr_mfa_code",
    "sm3",
    "validate_qr_mfa_code",
]
