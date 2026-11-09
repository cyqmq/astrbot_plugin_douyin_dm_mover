"""Passport 签名与编码（@alemonjs/douyin sign/sign-qs.js + constants.js 移植）。

仅含登录所需：desktop 基础查询、sha256 sign、qs、jumpbyte canonical 参数编码、
form 编码、ts/随机辅助。a_bogus 见 abogus.py。
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import time

DESKTOP_ORIGIN = "https://imdesktop.douyin.com"
DESKTOP_AID = "339757"
DESKTOP_APP_VERSION = "1.2.1"
DESKTOP_PASSPORT_APP_KEY = "3c452fb664e3de0e936108429a0bc697"

DESKTOP_PARAM_ORDER = {
    "passport_jssdk_version": 0, "passport_jssdk_type": 1, "is_from_ttaccountsdk": 2,
    "aid": 3, "language": 4, "account_app_language": 5, "ts": 6, "next": 7,
    "need_logo": 8, "need_short_url": 9, "is_new_login": 10, "is_from_iesaccountsaas": 11,
    "account_sdk_source": 12, "account_sdk_source_info": 13, "p_js_v": 14, "p_js_t": 15,
    "p_zt": 16, "p_ver": 17, "request_host": 18, "p_bd": 19, "biz_trace_id": 20,
    "new_authn_sdk_version": 21, "device_id": 22, "iid": 23, "version_code": 24,
    "device_platform": 25, "sign": 100, "qs": 101, "msToken": 102, "a_bogus": 103,
}
_RANDOM_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def passport_noon_utc_ts(now_ms: int | None = None) -> str:
    """当日 UTC 12:00:00 的 Unix 秒。"""
    ms = now_ms if now_ms is not None else int(time.time() * 1000)
    import datetime

    dt = datetime.datetime.fromtimestamp(ms / 1000, datetime.UTC)
    noon = dt.replace(hour=12, minute=0, second=0, microsecond=0)
    return str(int(noon.timestamp()))


def random_biz_trace_id() -> str:
    return secrets.token_hex(4)


def random_ms_token_128(length: int = 128) -> str:
    return "".join(_RANDOM_ALPHABET[b & 63] for b in os.urandom(length))


def random_desktop_hex(length: int) -> str:
    return "".join("0123456789abcdef"[b & 15] for b in os.urandom(length))


def sorted_param_string(obj: dict, keep_first_n: int | None = None) -> tuple[str, list[str]]:
    keys = sorted(obj.keys())
    if keep_first_n is not None and keep_first_n >= 0:
        keys = keys[:keep_first_n]
    parts = []
    for k in keys:
        v = obj[k]
        if isinstance(v, (dict, list)):
            parts.append(f"{k}={json.dumps(v, separators=(',', ':'))}")
        else:
            parts.append(f"{k}={v}")
    return "&".join(parts), keys


def encode_qs_key_names(key_names: list[str]) -> str:
    """排序前 10 个 query 键名逗号拼接 → UTF-8 逐字节 XOR 5 → hex（无补零）。"""
    input_ = ",".join(key_names)
    out = []
    for ch in input_:
        cp = ord(ch)
        if cp <= 127:
            bytes_ = [cp]
        elif cp <= 2047:
            bytes_ = [0xC0 | (cp >> 6), 0x80 | (cp & 63)]
        else:
            bytes_ = [0xE0 | (cp >> 12), 0x80 | ((cp >> 6) & 63), 0x80 | (cp & 63)]
        for b in bytes_:
            out.append(format(5 ^ b, "x"))
    return "".join(out)


def build_passport_sign_qs(query: dict, body: dict, app_key: str) -> tuple[str, str]:
    """sign = sha256(排序 query 前10 & body & app_key)，qs 为前10 键名 XOR5 hex。"""
    qs_str, keys = sorted_param_string(query, 10)
    body_str, _ = sorted_param_string(body)
    payload = f"{qs_str}&{body_str}&app_key={app_key}"
    sign = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    qs = encode_qs_key_names(keys)
    return sign, qs


def encode_form_body(body: dict) -> str:
    parts = []
    for k, v in body.items():
        parts.append(f"{_uri_encode(k)}={_uri_encode('' if v is None else v)}")
    return "&".join(parts)


def _uri_encode(value) -> str:
    # encodeURIComponent：保留 -_.!~*'()
    import urllib.parse

    return urllib.parse.quote(str(value), safe="-_.!~*'()")


def encode_desktop_passport_params(params: dict) -> str:
    """jumpbyte canonical 顺序输出 form/query 串。"""
    def _order(k: str) -> int:
        if k in DESKTOP_PARAM_ORDER:
            return DESKTOP_PARAM_ORDER[k]
        return 1000

    keys = sorted(params.keys(), key=lambda k: (_order(k), k))
    return "&".join(f"{_uri_encode(k)}={_uri_encode('' if params[k] is None else params[k])}" for k in keys)


def build_desktop_passport_base_query(
    device_id: str | None = None,
    install_id: str | None = None,
    account_sdk_source_info: str = "",
    biz_trace_id: str | None = None,
    ts: str | None = None,
    next_: str | None = None,
    extra: dict | None = None,
) -> dict:
    """桌面 normal SDK Passport 基础查询（字段顺序对齐 douyin-im）。"""
    query = {
        "passport_jssdk_version": "2.4.12",
        "passport_jssdk_type": "normal",
        "is_from_ttaccountsdk": "1",
        "aid": DESKTOP_AID,
        "language": "zh",
        "ts": ts or passport_noon_utc_ts(),
    }
    if next_:
        query["next"] = next_
    if extra:
        query.update(extra)
    query.update({
        "is_new_login": "1",
        "is_from_iesaccountsaas": "1",
        "account_sdk_source": "web",
        "account_sdk_source_info": account_sdk_source_info or "",
        "p_js_v": "2.4.12",
        "p_js_t": "pro",
        "p_zt": "3.3.5",
        "p_ver": "1.0.29",
        "request_host": "file://",
        "p_bd": "1.0.1.7",
        "biz_trace_id": biz_trace_id or random_biz_trace_id(),
        "device_id": device_id,
        "iid": install_id,
        "version_code": DESKTOP_APP_VERSION,
        "device_platform": "PC",
    })
    return query


def desktop_passport_url(path: str, search: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{DESKTOP_ORIGIN}{normalized}?{search}"
