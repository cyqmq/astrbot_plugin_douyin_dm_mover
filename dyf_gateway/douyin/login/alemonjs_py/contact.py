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
WWW_USER_LIST = "https://www.douyin.com/aweme/v1/web/user/"


def _user_entry(u: dict) -> dict:
    """统一解析用户项（familiar 平铺 / www following-follower 嵌套 user_info）。"""
    uid = (
        u.get("uid")
        or (str(u["user_id"]) if u.get("user_id") not in (None, "") else "")
        or ""
    )
    if not uid or uid in ("0", 0):
        return {}
    thumb = u.get("avatar_thumb") or {}
    url_list = thumb.get("url_list") or []
    return {
        "uid": str(uid),
        "nickname": u.get("nickname") or "",
        "sec_uid": u.get("sec_uid") or "",
        "remark_name": u.get("remark_name") or "",
        "signature": u.get("signature") or "",
        "avatar": url_list[0] if url_list else "",
        # 关系状态（实测字段名）：follow_status 我是否已关注他（0 未 / 1,2 已）；
        # follower_status 他是否已关注我（1=是）。
        "follow_status": u.get("follow_status", 0),
        "follower_status": u.get("follower_status", 0),
        "relation_label": u.get("relation_label", ""),
    }


def _fetch_www_user_list(
    http: DouyinHttpPy,
    kind: str,
    uid: str,
    sec_uid: str,
    cursor: str = "0",
    count: int = 100,
    max_pages: int = 50,
) -> list[dict]:
    """www following/follower 分页拉取（bd-ticket-guard 4 头自动加 + Referer 用户主页）。

    响应字段：following/list -> ``followings``，follower/list -> ``followers``（不是 user_list）。
    """
    import time

    path = f"{kind}/list/"
    key = "followings" if kind == "following" else "followers"
    users: list[dict] = []
    cur = cursor or "0"
    page = 0
    while page < max_pages:
        query = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "user_id": str(uid),
            "sec_user_id": sec_uid,
            "offset": "0",
            "min_time": "0",
            "count": str(min(100, count)),
            "cursor": cur,
            "max_time": str(int(time.time() * 1000)),
            "source_type": "1",
            "gps_access": "0",
            "address_book_access": "0",
            "is_top": "1",
            "pc_client_type": "1",
        }
        query_wire = urlencode(query)
        abogus = generate_jumpbyte_abogus(
            query=query_wire, body="", user_agent=http.get_user_agent()
        )
        url = f"{WWW_USER_LIST}{path}?{query_wire}&a_bogus={quote(abogus, safe='')}"
        headers = {"Referer": f"https://www.douyin.com/user/{sec_uid}"}
        data = http.request_json(url, "GET", headers=headers)
        if data.get("status_code") not in (0, None):
            raise RuntimeError(f"{kind}/list status_code={data.get('status_code')}")
        for item in data.get(key) or []:
            if not isinstance(item, dict):
                continue
            # www 形状：user_list[].user_info 嵌套；familiar 形状：平铺。
            info = item.get("user_info") or {}
            entry = _user_entry(info if info else item)
            if entry:
                entry["_src"] = kind
                users.append(entry)
        has_more = bool(data.get("has_more"))
        cur = str(data.get("cursor") or cur)
        page += 1
        if not has_more:
            break
    return users


def fetch_contact_lists(
    http: DouyinHttpPy,
    uid: str = "",
    sec_uid: str = "",
    with_www: bool = True,
    www_http: DouyinHttpPy | None = None,
) -> list[dict]:
    """合并三态：familiar（互关）+ following（我关注）+ follower（粉丝关注我）。

    域隔离（探针 2026-11-12）：familiar 走 imdesktop 会话（``http``）；following/follower 走
    www 登录态（``www_http``，需 www cookie 导入；无则用 ``http`` 向后兼容）。按 uid 去重，
    familiar 优先（互关）。following/follower 失败仅软失败记录（``www_errors``）不阻断 familiar。
    """
    friends = fetch_friend_list(http)
    by_uid = {f["uid"]: {**f, "_src": "familiar"} for f in friends}
    if with_www and uid and sec_uid:
        www = www_http or http
        for kind in ("following", "follower"):
            try:
                for u in _fetch_www_user_list(www, kind, uid, sec_uid):
                    ex = by_uid.get(u["uid"])
                    if ex is None:
                        by_uid[u["uid"]] = u
                    else:
                        # 已互关（familiar 优先），只补缺失的关系字段
                        for k in ("follow_status", "follower_status", "relation_label"):
                            if not ex.get(k):
                                ex[k] = u.get(k)
            except Exception as e:
                # 软失败：记录到 www_http.www_errors（dashboard 透出给界面），不阻断 familiar
                logger.warning(f"[dyf] {kind}/list 拉取失败: {e}")
                msg = f"{kind}: {e}"
                prev = getattr(www, "www_errors", "") or ""
                www.www_errors = f"{prev}; {msg}" if prev else msg
    return list(by_uid.values())


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
            # 诊断：只打关系字段值（follow/relation/is_），不截断——一次拉好友页
            # 看每个好友的 follow_status/is_following/relation 实际值，定三态映射。
            logger.info(
                "[dyf] REL: "
                + " ".join(
                    f"{k}={u.get(k)}"
                    for k in sorted(u.keys())
                    if any(s in k.lower() for s in ("follow", "relation", "is_"))
                )
            )
            uid = (
                u.get("uid")
                or (str(u["user_id"]) if u.get("user_id") not in (None, "") else "")
                or ""
            )
            # 只滤真正无效的（已取消 且 已关注）；未回关的（follow_status=0，即使
            # user_canceled=1）保留显示——familiar/list 返回全部好友含未回关。
            if u.get("user_canceled") and u.get("follow_status", 0) != 0:
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
                    # 关系状态透传（供好友页三态展示，实测字段名）：
                    # follow_status 我是否已关注他（0 未 / 1,2 已）；follower_status 他是否已关注我（1=是）；
                    # relation_label 关系标签（好友/互关等）。
                    "follow_status": u.get("follow_status", 0),
                    "follower_status": u.get("follower_status", 0),
                    "relation_label": u.get("relation_label", ""),
                }
            )
        has_more = bool(data.get("has_more"))
        cur = str(data.get("cursor") or cur)
        page += 1
        if not has_more:
            break
    return friends
