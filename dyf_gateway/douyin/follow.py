"""抖音网页版好友关注/取关（REST，零 proto 逆向）。

依赖现有登录态（``DouyinHttpPy`` cookie）+ ``a_bogus`` 签名（``generate_jumpbyte_abogus``），
对齐抖音网页版 ``/aweme/v1/web/commit/item/follow/`` 接口：POST body 带
``to_user_id/sec_user_id/action/source_type``，query 带网页端参数 + ``a_bogus``。
"""
from __future__ import annotations

from urllib.parse import quote, urlencode

from .login.alemonjs_py.abogus import generate_jumpbyte_abogus
from .video import _ensure_web_identity

FOLLOW_URL = "https://www.douyin.com/aweme/v1/web/commit/item/follow/"

ACTION_FOLLOW = 1
ACTION_UNFOLLOW = 2


def _web_follow_query() -> dict:
    """网页端公共参数（对齐 video._web_detail_query，去掉 aweme_id 专用项）。"""
    return {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "pc_client_type": "1",
        "version_code": "290100",
        "version_name": "29.1.0",
        "cookie_enabled": "true",
        "screen_width": "1920",
        "screen_height": "1080",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "browser_name": "Chrome",
        "browser_version": "130.0.0.0",
        "browser_online": "true",
        "engine_name": "Blink",
        "engine_version": "130.0.0.0",
        "os_name": "Windows",
        "os_version": "10",
        "cpu_core_num": "12",
        "device_memory": "8",
        "platform": "PC",
        "downlink": "10",
        "effective_type": "4g",
    }


def _follow_body(to_user_id: str, sec_user_id: str, action: int) -> str:
    return urlencode(
        {
            "to_user_id": str(to_user_id),
            "sec_user_id": str(sec_user_id),
            "action": str(action),
            "source_type": "1",
        }
    )


def _commit_follow(
    http,
    uid: str,
    sec_uid: str,
    action: int,
    timeout: int = 8,
) -> dict:
    """关注/取关（action 1/2）。成功返回 {"ok":True}，失败 {"ok":False,"detail":...}。"""
    try:
        _ensure_web_identity(http)
        query_wire = urlencode(_web_follow_query())
        body_wire = _follow_body(uid, sec_uid, action)
        abogus = generate_jumpbyte_abogus(
            query=query_wire, body=body_wire, user_agent=http.get_user_agent()
        )
        url = f"{FOLLOW_URL}?{query_wire}&a_bogus={quote(abogus, safe='')}"
        data = http.request_json(
            url,
            "POST",
            headers={
                "x-tt-argus": "1",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body=body_wire,
            timeout=timeout,
        )
    except (RuntimeError, TypeError, ValueError, KeyError, ConnectionError, OSError) as e:
        return {"ok": False, "detail": f"关注请求失败: {e}"}
    status = data.get("status_code", -1)
    if status == 0:
        return {"ok": True, "detail": "已关注" if action == ACTION_FOLLOW else "已取消关注"}
    return {"ok": False, "detail": f"关注返回 status_code={status}: {str(data)[:200]}"}


def follow_user(http, uid: str, sec_uid: str, timeout: int = 8) -> dict:
    """回关好友（关注）。"""
    return _commit_follow(http, uid, sec_uid, ACTION_FOLLOW, timeout)


def unfollow_user(http, uid: str, sec_uid: str, timeout: int = 8) -> dict:
    """取消关注好友。"""
    return _commit_follow(http, uid, sec_uid, ACTION_UNFOLLOW, timeout)
