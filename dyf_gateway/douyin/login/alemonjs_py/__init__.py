"""@alemonjs/douyin 登录核心的纯 Python 移植（desktop 扫码 + 2046 MFA）。"""
from __future__ import annotations

from .abogus import generate_jumpbyte_abogus
from .contact import fetch_friend_list
from .http import DouyinHttpPy
from .mixmode import code_encrypt, mix_mode_encode, pick_qr_biz_params, qr_mfa_body
from .profile import desktop_rest_base_query, fetch_desktop_self_profile
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
    "desktop_rest_base_query",
    "encode_desktop_passport_params",
    "encode_form_body",
    "fetch_desktop_self_profile",
    "fetch_friend_list",
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
