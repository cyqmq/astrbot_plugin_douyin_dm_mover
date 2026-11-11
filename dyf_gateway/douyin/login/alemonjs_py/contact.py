"""好友列表（douyin-im familiar-list 全量移植）。

GET /aweme/v1/web/familiar/list/，移动端 familiar-list 形状（version_code=21.6.0），
分页 count≤100、cursor 循环拉全量；过滤 user_canceled=0、uid 非空非 0。
依赖 Cookie + 桌面参数 + a_bogus 签名，复用 ``profile.desktop_rest_base_query``。
"""
from __future__ import annotations

from urllib.parse import quote, urlencode

from astrbot.api import logger

from .abogus import generate_jumpbyte_abogus
from .http import DouyinHttpPy
from .profile import desktop_rest_base_query

FAMILIAR_URL = "https://imdesktop.douyin.com/aweme/v1/web/familiar/list/"


def fetch_friend_list(
    http: DouyinHttpPy, cursor: str = "0", count: int = 100, max_pages: int = 100
) -> list[dict]:
    """拉取全量好友。

    Returns: [{"uid","nickname","sec_uid","remark_name","signature","avatar"}, ...]
    """
    friends: list[dict] = []
    cur = cursor or "0"
    page = 0
    while page < max_pages:
        query = desktop_rest_base_query(http)
        query.update(
            {
                "version_code": "21.6.0",
                "cursor": cur,
                "count": str(min(100, count)),
                "order_by": "1",
                "need_all_friend": "1",
                "recommend_type": "22",
                "vcd_count": "0",
                "hotsoon_has_more": "0",
                "only_total": "0",
            }
        )
        query_wire = urlencode(query)
        abogus = generate_jumpbyte_abogus(
            query=query_wire, body="", user_agent=http.get_user_agent()
        )
        data = http.request_json(
            f"{FAMILIAR_URL}?{query_wire}&a_bogus={quote(abogus, safe='')}", "GET"
        )
        if data.get("status_code") not in (0, None):
            raise RuntimeError(f"familiar/list status_code={data.get('status_code')}")
        for u in data.get("user_list") or []:
            # 诊断：familiar/list 真实字段名（看 follow_status 是否存在/叫什么）
            logger.info(f"[dyf] FRIEND_KEYS: {sorted(u.keys())}")
            uid = (
                u.get("uid")
                or (str(u["user_id"]) if u.get("user_id") not in (None, "") else "")
                or ""
            )
            if u.get("user_canceled"):
                continue
            if not uid or uid in ("0", 0):
                continue
            thumb = u.get("avatar_thumb") or {}
            url_list = thumb.get("url_list") or []
            friends.append(
                {
                    "uid": str(uid),
                    "nickname": u.get("nickname") or "",
                    "sec_uid": u.get("sec_uid") or "",
                    "remark_name": u.get("remark_name") or "",
                    "signature": u.get("signature") or "",
                    "avatar": url_list[0] if url_list else "",
                    # 关系状态透传（供好友页三态展示）：
                    # follow_status 我是否已关注他（0 未 / 1 已）；is_following 他是否已关注我；
                    # relation 位掩码（1 他关注我 / 2 我关注他 / 3 互关）。
                    "follow_status": u.get("follow_status", 0),
                    "is_following": u.get("is_following", 0),
                    "relation": u.get("relation", 0),
                }
            )
        has_more = bool(data.get("has_more"))
        cur = str(data.get("cursor") or cur)
        page += 1
        if not has_more:
            break
    return friends
