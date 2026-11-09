"""MFA 验证码编码与 qrMfaBody（sign/mix-mode.js + auth/qr.js 移植）。

desktop-lite MFA 的 send_code / validate_code 用 mix_mode=1 表单，
type 3737（mobile_sms_verify）/ 363c（安全手机），std_verify_way 标验证方式。
"""
from __future__ import annotations

DESKTOP_LITE_AID = "339757"


def mix_mode_encode(plain: str) -> str:
    """UTF-8 逐字节 XOR 5 → 两位小写 hex。"""
    out = []
    for b in plain.encode("utf-8"):
        out.append(format(b ^ 5, "02x"))
    return "".join(out)


def code_encrypt(s: str) -> str:
    """code_encrypt：UTF-8 每字节 ^5 后的两位 hex（363c 场景）。"""
    out = []
    for b in s.encode("utf-8"):
        out.append(format(b ^ 5, "02x"))
    return "".join(out)


def qr_mfa_body(challenge: dict, verify_way: str, extra: dict | None = None) -> dict:
    """qrMfaBody 等价：desktop-lite 二次验证表单。"""
    biz = challenge.get("biz_params") or {}
    common = challenge.get("common_params") or {}
    extra = extra or {}

    def value(source: dict, key: str, fallback: str = "") -> str:
        candidate = source.get(key)
        if candidate is None or candidate == "":
            return fallback
        return str(candidate)

    body = {
        "mix_mode": "1",
    }
    if verify_way != "pwd_verify":
        body["type"] = "3737" if verify_way == "mobile_sms_verify" else "363c"
    body["encrypt_uid"] = challenge.get("encrypt_uid") or ""
    body["verify_ticket"] = ""
    body["copywriting_key"] = value(common, "copywriting_key", "qr_connect")
    body["ies_safety_diversion_tag"] = value(common, "ies_safety_diversion_tag", "mfa")
    body["new_verify_flow"] = value(common, "new_verify_flow")
    body["std_verify_flow_id"] = value(biz, "std_verify_flow_id", value(common, "std_verify_flow_id"))
    body["std_verify_scene"] = value(biz, "std_verify_scene", "account_login")
    body["std_verify_template"] = value(biz, "std_verify_template", "ato")
    body["std_verify_token"] = value(biz, "std_verify_token", value(common, "std_verify_token"))
    body["std_verify_type"] = value(biz, "std_verify_type", "MFA")
    body["std_verify_way"] = verify_way
    body.update(extra)
    body["aid"] = DESKTOP_LITE_AID
    body["new_authn_sdk_version"] = "1.0.0.421-web"
    return body


def pick_qr_biz_params(params: dict | None) -> dict:
    """MFA 校验通过后轮询 check_qrconnect 需携带的 biz 参数。"""
    keys = [
        "passport_mfa_retry_tag", "std_verify_flow_id", "std_verify_scene",
        "std_verify_template", "std_verify_token", "std_verify_type", "std_verify_way",
    ]
    result = {}
    if not params:
        return result
    for key in keys:
        v = params.get(key)
        if v is not None:
            result[key] = str(v)
    return result
