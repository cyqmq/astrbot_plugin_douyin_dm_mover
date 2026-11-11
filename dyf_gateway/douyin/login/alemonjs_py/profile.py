"""账户档案（@alemonjs/douyin fetchDesktopSelfProfile / douyin-im getSelfProfile 移植）。

桌面接口：GET /aweme/v1/web/user/profile/self/，靠 Cookie + 桌面参数 + a_bogus 签名。
参数按官方桌面指纹：device_platform=win32、screen 1707x1067、UA 去 Mozilla/ 作 browser_version。
"""
from __future__ import annotations

from urllib.parse import quote, urlencode

from .abogus import generate_jumpbyte_abogus
from .http import DouyinHttpPy

PROFILE_URL = "https://imdesktop.douyin.com/aweme/v1/web/user/profile/self/"


def desktop_rest_base_query(http: DouyinHttpPy) -> dict:
    """桌面 REST 通用指纹参数（profile/contact 共用）。"""
    ua = http.get_user_agent()
    return {
        "aid": "339757",
        "version": "1.2.1",
        "device_platform": "win32",
        "screen_width": "1707",
        "screen_height": "1067",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "browser_name": "Mozilla",
        "browser_version": ua.replace("Mozilla/", "", 1),
        "browser_online": "true",
        "cookie_enabled": "true",
        "device_id": http.device_id if http.has_desktop_device() else "0",
        "did": http.device_id if http.has_desktop_device() else "0",
        "iid": http.install_id or "0",
        "awemeim_guid": http.guid,
        "channel": "0",
    }


def fetch_desktop_self_profile(http: DouyinHttpPy) -> dict:
    """拉取当前账号昵称/头像。

    Returns: {"uid": str, "nickname": str, "avatar": str}
    失败抛 RuntimeError（由调用方按需吞掉）。
    """
    query = desktop_rest_base_query(http)
    query_wire = urlencode(query)
    abogus = generate_jumpbyte_abogus(
        query=query_wire, body="", user_agent=http.get_user_agent()
    )
    data = http.request_json(
        f"{PROFILE_URL}?{query_wire}&a_bogus={quote(abogus, safe='')}", "GET"
    )
    user = ((data.get("data") or {}).get("user")) or {}
    uid = (
        user.get("user_id_str")
        or (str(user["user_id"]) if user.get("user_id") not in (None, "") else "")
        or ""
    )
    nickname = user.get("nickname") or ""
    sec_uid = user.get("sec_uid") or ""
    avatar = ""
    thumb = user.get("avatar_thumb") or {}
    url_list = thumb.get("url_list") or []
    if url_list:
        avatar = url_list[0]
    return {"uid": uid, "nickname": nickname, "sec_uid": sec_uid, "avatar": avatar}
