"""2046 二次验证（MFA）独立处理支路。

DouYin_Spider 的 login_api.py 不含 2046 自动处理（其 ``_raise_if_blocked`` 会直接抛
RuntimeError）。本模块在注入点（loader.py）拦截 2046，参考 catbus 的短信续登流程：
取决策（verify_ways / verify_ticket / encrypt_uid / event_params / std_verify_flow_id），
默认走短信验证，调 ``/passport/web/send_code/`` 与 ``/passport/web/validate_code/``
（type=22、verify_type 按 is_safe_mobile），验证通过后由 loader 继续轮询同一 token。

请求复用 DouYin_Spider 的签名与 Cookie 域过滤（``_sdk_params`` / ``_passport_headers`` /
``scoped_cookies`` / ``auth.request``），与登录会话共享同一份 Cookie。

MFA 模式（配置 mfa_mode）：
- ``auto_sms``   自动发送短信，验证码由 code_source 提供（默认 stdin，或 QQ 回复）
- ``manual_command`` 不自动发码，等待管理员触发（如 /dyf mfa）后发码并取码
- ``alert_wait`` 仅告警，等待用户在抖音 App 完成验证（不发短信）
"""
from __future__ import annotations

import urllib.parse

SMS_WAY = "mobile_sms_verify"


def extract_decision(res) -> dict:
    return (res or {}).get("data") or {}


def has_sms_way(res) -> bool:
    for w in extract_decision(res).get("verify_ways") or []:
        if (w or {}).get("verify_way") == SMS_WAY:
            return True
    return False


def sms_mobile(res) -> str | None:
    for w in extract_decision(res).get("verify_ways") or []:
        if (w or {}).get("verify_way") == SMS_WAY:
            return (w or {}).get("mobile")
    return None


def _base_body(decision: dict) -> list[tuple[str, str]]:
    body = [
        ("encrypt_uid", str(decision.get("encrypt_uid") or "")),
        ("verify_ticket", str(decision.get("verify_ticket") or "")),
        ("std_verify_way", SMS_WAY),
    ]
    scene = (decision.get("event_params") or {}).get("verify_scene")
    if scene:
        body.append(("std_verify_scene", str(scene)))
    flow = decision.get("std_verify_flow_id")
    if flow:
        body.append(("std_verify_flow_id", str(flow)))
    return body


def _mfa_request(auth, decision: dict, api: str, extra: list[tuple[str, str]]) -> dict:
    """POST /passport/web/<api>，body 顺序照 catbus，签名/Cookie 复用 DouYin_Spider。"""
    from dy_apis.login_api import headers_with_cookie, scoped_cookies
    from utils.passport import merge_set_cookies

    from .loader import load_login_api

    data_dict = dict(_base_body(decision) + extra)
    api_cls = load_login_api()()
    params = api_cls._sdk_params(
        auth, {"is_from_iesaccountsaas": "1"},
        data=data_dict, device_fp=True, with_ms_token=True,
    )
    params.with_a_bogus(data_dict, host="login.douyin.com")
    body = urllib.parse.urlencode(data_dict)
    resp = auth.request(
        "POST",
        api_cls.base_url + api,
        headers=headers_with_cookie(
            api_cls._passport_headers(
                auth, form=True, api="/passport/web/" + api
            ).get(),
            scoped_cookies(auth, "sms"),
        ),
        params=params.get(),
        data=body,
        split_cookie_header=True,
        verify=False,
        timeout=20,
        proxies=getattr(auth, "_proxies", None),
    )
    merge_set_cookies(auth, resp.cookies.get_dict())
    try:
        return resp.json()
    except Exception:
        return {}


def send_sms(auth, decision: dict) -> dict:
    """发短信验证码（2046 决策）。verify_type=301 安全手机 else 300。"""
    verify_type = "301"
    for w in decision.get("verify_ways") or []:
        if (w or {}).get("verify_way") == SMS_WAY:
            verify_type = "301" if (w or {}).get("is_safe_mobile") else "300"
            break
    return _mfa_request(
        auth, decision, "send_code/",
        [("type", "22"), ("aid", "6383"), ("verify_type", verify_type)],
    )


def validate_sms(auth, decision: dict, code: str) -> dict:
    return _mfa_request(
        auth, decision, "validate_code/",
        [("type", "22"), ("aid", "6383"), ("code", str(code))],
    )


def stdin_code_source(mobile: str | None, send_fn) -> str:
    """catbus 风格：自动发码后从 stdin 读 6 位验证码（回车跳过=等待 App）。"""
    try:
        send_fn()
    except Exception as e:
        print(f"[dyf] 发送验证码失败: {e}")
        return ""
    try:
        prompt = f"[dyf] 验证码已发送{f'（发往 {mobile}）' if mobile else ''}，请输入 6 位验证码（回车跳过）: "
        code = input(prompt).strip()
    except EOFError:
        return ""
    return code


class MfaHandler:
    """在注入点被调用的 2046 处理器。code_source(mobile, send_fn) -> str（阻塞）。"""

    def __init__(self, mode: str, alert, code_source=None):
        self.mode = mode or "auto_sms"
        self.alert = alert
        self.code_source = code_source or stdin_code_source

    def __call__(self, auth, res) -> None:
        decision = extract_decision(res)
        if self.mode == "alert_wait":
            self.alert("2046：请在抖音 App 完成二次验证，登录会继续等待")
            return
        if not has_sms_way(res):
            self.alert("2046：无短信验证选项，请在抖音 App 完成验证")
            return
        mobile = sms_mobile(res)

        def send_fn():
            out = send_sms(auth, decision)
            code = out.get("error_code")
            if code not in (0, None):
                raise RuntimeError(
                    f"发送验证码失败 error_code={code}: {out.get('description') or out}"
                )

        if self.mode == "manual_command":
            self.alert(
                f"2046：请运行 /dyf mfa 发送验证码{f'（发往 {mobile}）' if mobile else ''}"
            )

        try:
            code = self.code_source(mobile, send_fn)
        except Exception as e:
            self.alert(f"取验证码失败: {e}")
            return
        if not code:
            self.alert("未收到验证码，继续等待（可在 App 完成验证）")
            return
        out = validate_sms(auth, decision, code)
        if (out.get("error_code") or 0) == 0:
            self.alert("2046 验证码校验通过，等待登录放行")
        else:
            self.alert(
                f"2046 验证码校验未通过: {out.get('description') or out.get('error_code')}"
            )
