"""QR 扫码登录与 MFA（@alemonjs/douyin auth/qr.js + passport-lite.js 移植）。"""
from __future__ import annotations

import asyncio
import inspect
import time
from urllib.parse import quote, urlencode

from .abogus import generate_jumpbyte_abogus
from .http import DouyinHttpPy
from .mixmode import code_encrypt, mix_mode_encode, pick_qr_biz_params, qr_mfa_body
from .sign import (
    DESKTOP_PASSPORT_APP_KEY,
    build_desktop_passport_base_query,
    build_passport_sign_qs,
    desktop_passport_url,
    encode_desktop_passport_params,
    encode_form_body,
    random_desktop_hex,
    random_ms_token_128,
)
from .source_info import default_browser_info, encode_browser_info

QR_POLL_INTERVAL_MS = 1100
QR_DEFAULT_BODY = {
    "need_logo": "false",
    "need_short_url": "false",
    "is_frontier": "true",
    "is_new_login": "1",
    "next": "https://www.douyin.com",
}
VERIFY_WAY_PRIORITY = [
    "assist_mobile_sms_verify",
    "mobile_sms_verify",
    "assist_mobile_up_sms_verify",
    "pwd_verify",
]
QR_BIZ_PARAM_KEYS = [
    "passport_mfa_retry_tag",
    "std_verify_flow_id",
    "std_verify_scene",
    "std_verify_template",
    "std_verify_token",
    "std_verify_type",
    "std_verify_way",
]


def sign_extras(http: DouyinHttpPy, body_wire: str = "") -> dict:
    extras = {
        "userAgent": http.get_user_agent(),
        "enableABogus": http.enable_abogus,
        "appKey": DESKTOP_PASSPORT_APP_KEY,
        "aBogusVariant": "jumpbyte-desktop",
        "bodyWire": body_wire,
    }
    ms = http.get_ms_token()
    if ms:
        extras["msToken"] = ms
    return extras


def resolve_account_sdk_source_info(http: DouyinHttpPy) -> str:
    stored = http.jar.get("sdk_source_info")
    if stored:
        return stored
    now = int(time.time() * 1000)
    base = default_browser_info()
    base["performance"]["timeOrigin"] = now
    base["browser"]["t"] = str(now)
    info = encode_browser_info(base)
    http.jar.set("sdk_source_info", info)
    return info


def _sign_passport_query(
    base_query: dict, body: dict, extras: dict, body_wire: str = ""
) -> dict:
    """signPassportQuery 等价：sign/qs/msToken/a_bogus → query dict。"""
    sign, qs = build_passport_sign_qs(base_query, body, extras.get("appKey", ""))
    query = dict(base_query)
    query["sign"] = sign
    query["qs"] = qs
    ms = extras.get("msToken")
    if ms:
        query["msToken"] = ms
    if not extras.get("enableABogus", True) or not extras.get("userAgent"):
        return query
    query_wire = urlencode(query)
    query["a_bogus"] = generate_jumpbyte_abogus(
        query=query_wire,
        body=extras.get("bodyWire") or "",
        user_agent=extras["userAgent"],
    )
    return query


def get_qrcode(http: DouyinHttpPy) -> dict:
    base_query = build_desktop_passport_base_query(
        device_id=http.device_id,
        install_id=http.install_id,
        account_sdk_source_info=resolve_account_sdk_source_info(http),
        biz_trace_id=http.biz_trace_id,
        next_=QR_DEFAULT_BODY["next"],
        extra={"need_logo": "false", "need_short_url": "false"},
    )
    query = _sign_passport_query(base_query, {}, sign_extras(http), "")
    url = desktop_passport_url("/passport/web/get_qrcode/", urlencode(query))
    res = http.request_json(url, "GET", headers=http.passport_headers(url))
    d = res.get("data") or {}
    if d.get("error_code") != 0 or not d.get("qrcode"):
        raise RuntimeError(f"get_qrcode error_code={d.get('error_code')}")
    info = {"token": d["token"], "qrcodeBase64": d["qrcode"], "expireTime": d.get("expire_time")}
    if d.get("qrcode_index_url"):
        info["qrcodeIndexUrl"] = d["qrcode_index_url"]
    return info


def check_qrconnect(
    http: DouyinHttpPy, token: str, body_overrides: dict | None = None, fp: str | None = None
) -> dict:
    body = {**QR_DEFAULT_BODY, "token": token}
    if body_overrides:
        body.update(body_overrides)
    base_query = build_desktop_passport_base_query(
        device_id=http.device_id,
        install_id=http.install_id,
        account_sdk_source_info=resolve_account_sdk_source_info(http),
        biz_trace_id=http.biz_trace_id,
        extra={"fp": fp} if fp else None,
    )
    body_wire = encode_form_body(body)
    query = _sign_passport_query(base_query, body, sign_extras(http, body_wire), body_wire)
    url = desktop_passport_url("/passport/web/check_qrconnect/", urlencode(query))
    headers = {"Content-Type": "application/x-www-form-urlencoded", **http.passport_headers(url)}
    res = http.request_json(url, "POST", headers=headers, body=body_wire)
    return res.get("data") or {}


def _desktop_lite_base_query(device_id: str | None) -> dict:
    return {
        "passport_jssdk_version": "5.1.2",
        "passport_jssdk_type": "lite",
        "is_from_ttaccountsdk": "1",
        "aid": "339757",
        "language": "zh",
        "account_app_language": "zh",
        "is_new_login": "1",
        "is_from_iesaccountsaas": "1",
        "biz_trace_id": random_desktop_hex(8),
        "new_authn_sdk_version": "1.0.0.421-web",
        "device_id": device_id or random_desktop_hex(16),
        "iid": "0",
        "version_code": "1.2.1",
        "device_platform": "PC",
    }


def desktop_lite_passport_form_post(http: DouyinHttpPy, path: str, body: dict) -> dict:
    query = _desktop_lite_base_query(http.device_id if http.has_desktop_device() else None)
    query["msToken"] = random_ms_token_128()
    body_wire = encode_desktop_passport_params(body)
    query_wire = encode_desktop_passport_params(query)
    abogus = generate_jumpbyte_abogus(
        query=query_wire, body=body_wire, user_agent=http.get_user_agent()
    )
    url = f"https://imdesktop.douyin.com{path}?{query_wire}&a_bogus={quote(abogus, safe='')}"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://imdesktop.douyin.com",
    }
    res = http.request_json(url, "POST", headers=headers, body=body_wire)
    return res


def send_qr_mfa_code(http: DouyinHttpPy, challenge: dict, verify_way: str) -> dict:
    return desktop_lite_passport_form_post(
        http, "/passport/web/send_code/", qr_mfa_body(challenge, verify_way, {"is6Digits": "1"})
    )


def validate_qr_mfa_code(
    http: DouyinHttpPy, challenge: dict, verify_way: str, code: str | None = None
) -> dict:
    encoded = None
    if code is not None:
        encoded = mix_mode_encode(code) if verify_way == "mobile_sms_verify" else code_encrypt(code)
    extra = {"code": encoded} if encoded else {}
    return desktop_lite_passport_form_post(
        http, "/passport/web/validate_code/", qr_mfa_body(challenge, verify_way, extra)
    )


def validate_qr_password(http: DouyinHttpPy, challenge: dict, password: str) -> dict:
    return desktop_lite_passport_form_post(
        http,
        "/passport/web/account/verify/",
        qr_mfa_body(challenge, "pwd_verify", {"password": code_encrypt(password)}),
    )


def _select_verify_way(data: dict) -> dict | None:
    ways = data.get("verify_ways") or []
    by_way = {w.get("verify_way"): w for w in ways if w.get("verify_way")}
    for name in VERIFY_WAY_PRIORITY:
        if name in by_way:
            return by_way[name]
    return None


def _session_from_confirmed(http: DouyinHttpPy, qr_token: str, user_data: dict | None) -> dict:
    platform_uid = None
    if user_data:
        platform_uid = user_data.get("user_id_str")
        if not platform_uid and user_data.get("user_id") not in (None, ""):
            platform_uid = str(user_data["user_id"])
    if not platform_uid:
        platform_uid = http.jar.get("uid_tt")
    if not platform_uid:
        raise RuntimeError("confirmed but no platformUid")
    session = {"platformUid": platform_uid, "cookies": http.get_cookies(), "qrToken": qr_token}
    if user_data:
        session["userData"] = user_data
    # 登录 confirmed 后拉一次账户档案（昵称/头像），失败不阻断登录
    try:
        from .profile import fetch_desktop_self_profile

        session["profile"] = fetch_desktop_self_profile(http)
    except Exception as exc:
        session["profile"] = {"uid": platform_uid, "nickname": "", "avatar": ""}
        session["profileError"] = str(exc)
    return session


async def poll_qr_confirm(http: DouyinHttpPy, token: str, options: dict | None = None) -> dict:
    """轮询扫码状态，处理短信/密码二次验证，直至 confirmed/expired/超时。"""
    options = options or {}
    poll_ms = options.get("pollIntervalMs", QR_POLL_INTERVAL_MS)
    timeout_ms = options.get("timeoutMs", 120000)
    on_status = options.get("onStatus")
    on_mfa = options.get("onMfa")
    deadline = time.time() * 1000 + timeout_ms
    last = None
    mfa_done = False
    notified_status = None
    extra_body: dict = {}
    verify_count = 0
    fp = None

    async def status(s: str) -> None:
        if on_status:
            await _maybe_await(on_status(s))

    while time.time() * 1000 < deadline:
        try:
            last = check_qrconnect(http, token, extra_body, fp)
        except Exception:
            await asyncio.sleep(poll_ms / 1000)
            continue
        if verify_count < 3 and (last.get("error_code") == 1044 or last.get("verify") or "verify" in (last.get("verify_way") or "")):
            verify_count += 1
            await status("verifying")
            raise RuntimeError("需要浏览器安全验证（当前 Python 后端暂不支持）")
        if (
            not mfa_done
            and (last.get("account_flow") == "verify" or last.get("biz_params") is not None)
        ):
            await status("verifying")
            challenge = {
                "encrypt_uid": last.get("encrypt_uid"),
                "biz_params": last.get("biz_params"),
                "common_params": last.get("common_params"),
            }
            way = _select_verify_way(last)
            if not way or not way.get("verify_way"):
                lst = ", ".join(
                    w.get("verify_way") for w in (last.get("verify_ways") or []) if w.get("verify_way")
                )
                raise RuntimeError(f"无可支持的验证方式（服务端可选：{lst or '无'}）")
            ww = way["verify_way"]
            if ww == "assist_mobile_up_sms_verify":
                await _up_sms_mfa_flow(http, challenge, way, on_status)
            elif ww == "pwd_verify":
                if not on_mfa:
                    raise RuntimeError("登录触发密码二次验证，但未提供 onMfa 回调")
                password = await _maybe_await(on_mfa({"kind": "password"}))
                if not password:
                    raise RuntimeError("密码二次验证未收到输入")
                validated = validate_qr_password(http, challenge, password)
                if not (validated.get("data") or {}).get("ticket"):
                    raise RuntimeError(
                        f"扫码密码验证失败: {(validated.get('data') or {}).get('error_code', '-')}"
                    )
                await status("密码验证通过")
            else:
                if not on_mfa:
                    raise RuntimeError("登录触发短信二次验证，但未提供 onMfa 回调")
                try_ways = [ww, "assist_mobile_sms_verify"] if ww == "mobile_sms_verify" else [ww]
                sent = None
                used_way = None
                for candidate in try_ways:
                    res = send_qr_mfa_code(http, challenge, candidate)
                    if res.get("message") == "success":
                        sent = res
                        used_way = candidate
                        break
                    sent = res
                if not sent or sent.get("message") != "success" or not used_way:
                    up = next(
                        (w for w in (last.get("verify_ways") or []) if w.get("verify_way") == "assist_mobile_up_sms_verify"),
                        None,
                    )
                    if up and up.get("verify_way"):
                        await status(
                            f"发码被拒（{sent.get('message') if sent else 'unknown'}），改用上行短信验证"
                        )
                        await _up_sms_mfa_flow(http, challenge, up, on_status)
                    else:
                        raise RuntimeError(
                            f"发送短信验证码失败: {sent.get('message') if sent else 'unknown'}"
                        )
                else:
                    if used_way != ww:
                        await status("已改用辅助手机接收验证码")
                    mobile = (sent.get("data") or {}).get("mobile") or way.get("mobile")
                    code = await _maybe_await(
                        on_mfa({"maskedMobile": str(mobile) if mobile is not None else None})
                    )
                    validated = validate_qr_mfa_code(http, challenge, used_way, code)
                    if not (validated.get("data") or {}).get("ticket"):
                        raise RuntimeError(
                            f"扫码短信验证失败: {(validated.get('data') or {}).get('error_code', '-')}"
                        )
                    await status("verified")
            extra_body = pick_qr_biz_params(last.get("biz_params"))
            mfa_done = True
            continue
        st = last.get("status")
        if st and st != notified_status:
            notified_status = st
            await status(st)
        if st == "confirmed":
            return _session_from_confirmed(http, token, last.get("user_data"))
        if st == "expired":
            raise RuntimeError("QR code expired")
        await asyncio.sleep(poll_ms / 1000)
    raise RuntimeError(f"QR login timeout; last={last.get('status') if last else 'none'}")


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


async def _up_sms_mfa_flow(http: DouyinHttpPy, challenge: dict, way: dict, on_status) -> None:
    content = way.get("sms_content") or "YZ"
    if on_status:
        await _maybe_await(on_status(
            f"请用安全手机（{way.get('mobile') or ''}）编辑短信\"{content}\"发送到 {way.get('channel_mobile') or ''}"
        ))
    deadline = time.time() * 1000 + 180000
    last = None
    while time.time() * 1000 < deadline:
        await asyncio.sleep(3)
        try:
            last = validate_qr_mfa_code(
                http, challenge, way.get("verify_way") or "assist_mobile_up_sms_verify"
            )
        except Exception:  # noqa: S112 - 轮询忽略单次失败继续等待
            continue
        if (last.get("data") or {}).get("ticket"):
            if on_status:
                await _maybe_await(on_status("短信验证通过"))
            return
    raise RuntimeError(
        f"上行短信验证超时: {(last.get('data') or {}).get('error_code', '-')}"
    )


async def login_by_qrcode(http: DouyinHttpPy, options: dict | None = None) -> dict:
    options = options or {}
    info = get_qrcode(http)
    return await poll_qr_confirm(http, info["token"], options)
