"""抖音 imdesktop 好友关注/取关（REST，零 proto 逆向）。

实测有效接口：``POST imdesktop.douyin.com/aweme/v1/web/commit/follow/user/``
（www 的 ``item/follow`` 已废弃，Janus 不认）。参数全在 query（非 body）：
``user_id``/``secUid``（camelCase）/``type``（1 关注 / 0 取关）/``tag``/``verifyFp``，
body 为空；``a_bogus`` 签名 + desktop 指纹参数（``desktop_rest_base_query``）。
"""
from __future__ import annotations

from urllib.parse import quote, urlencode

from astrbot.api import logger

from .login.alemonjs_py.abogus import generate_jumpbyte_abogus
from .login.alemonjs_py.profile import desktop_rest_base_query
from .video import _ensure_web_identity

FOLLOW_URL = "https://imdesktop.douyin.com/aweme/v1/web/commit/follow/user/"


def _commit_follow(
    http,
    uid: str,
    sec_uid: str,
    followed: bool,
    timeout: int = 8,
) -> dict:
    """关注/取关（followed True/False）。成功 {"ok":True}，失败 {"ok":False,"detail":...}。"""
    try:
        _ensure_web_identity(http)
        query = desktop_rest_base_query(http)  # imdesktop 公共参数（含 device_id 等）
        query.update(
            {
                "user_id": str(uid),
                "secUid": str(sec_uid),  # 注意 camelCase，不是 sec_user_id
                "type": "1" if followed else "0",  # 1 关注 / 0 取关
                "tag": "frienddetail",
                "verifyFp": f"verify_{query.get('device_id', '')}",
            }
        )
        query_wire = urlencode(query)
        abogus = generate_jumpbyte_abogus(
            query=query_wire, body="", user_agent=http.get_user_agent()
        )
        url = f"{FOLLOW_URL}?{query_wire}&a_bogus={quote(abogus, safe='')}"
        data = http.request_json(
            url,
            "POST",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://imdesktop.douyin.com",
            },
            body="",  # 参数全在 query，body 空
            timeout=timeout,
        )
    except (RuntimeError, TypeError, ValueError, KeyError, ConnectionError, OSError) as e:
        logger.warning(f"[dyf] follow 请求失败: {e}")
        return {"ok": False, "detail": f"关注请求失败: {e}"}
    status = data.get("status_code", -1)
    if status == 0:
        return {"ok": True, "detail": "已关注" if followed else "已取消关注"}
    return {"ok": False, "detail": f"关注返回 status_code={status}: {str(data)[:200]}"}


def follow_user(http, uid: str, sec_uid: str, timeout: int = 8) -> dict:
    """回关好友（关注）。"""
    return _commit_follow(http, uid, sec_uid, True, timeout)


def unfollow_user(http, uid: str, sec_uid: str, timeout: int = 8) -> dict:
    """取消关注好友。"""
    return _commit_follow(http, uid, sec_uid, False, timeout)
