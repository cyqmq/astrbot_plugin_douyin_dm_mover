"""账户档案（@alemonjs/douyin fetchDesktopSelfProfile / douyin-im getSelfProfile 移植）。

桌面接口：GET /aweme/v1/web/user/profile/self/，靠 Cookie + desktopFingerprint query
（无需 a_bogus 签名；a_bogus 端实测返回 data.user 为空）。
"""
from __future__ import annotations

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
    """拉取当前账号昵称/头像（desktopFingerprint query，无需 a_bogus 签名）。

    实测：a_bogus 签名端（generate_jumpbyte_abogus）访问本端点返回 data.user 为空
    （不抛异常）；改用 user.py _fingerprint（无 a_bogus）→ 完整返回
    uid/nickname/sec_uid/avatar。im/user/info 与本端点都无需 a_bogus。
    """
    from dyf_gateway.douyin.user import _fingerprint

    query = _fingerprint(
        str(getattr(http, "device_id", "") or ""),
        str(getattr(http, "guid", "") or ""),
    )
    data = http.request_json(f"{PROFILE_URL}?{query}", "GET")
    user = ((data.get("data") or {}).get("user")) or data.get("user") or {}
    uid = (
        str(user.get("user_id_str") or user.get("uid") or user.get("user_id") or "")
    )
    nickname = user.get("nickname") or ""
    sec_uid = user.get("sec_uid") or ""
    avatar = ""
    for key in ("avatar_larger", "avatar_thumb"):
        ul = ((user.get(key) or {}).get("url_list")) or []
        if ul:
            avatar = ul[0]
            break
    return {"uid": uid, "nickname": nickname, "sec_uid": sec_uid, "avatar": avatar}
