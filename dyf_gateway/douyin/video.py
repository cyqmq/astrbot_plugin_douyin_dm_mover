"""视频详情：GET /aweme/v1/web/aweme/detail/ 拿 desc/封面/播放地址（L2 增强）。

视频卡（WorkCard）内只有标题/作者/封面，无简介（desc）；视频文案需额外请求
aweme/detail（1 次 HTTP，带 a_bogus 签名）。返回规范化 dict；失败返回 None
（调用方按原「标题+链接+封面」兜底）。
"""
from __future__ import annotations

from urllib.parse import quote, urlencode

from .login.alemonjs_py import DouyinHttpPy
from .login.alemonjs_py.abogus import generate_jumpbyte_abogus
from .login.alemonjs_py.profile import desktop_rest_base_query

DETAIL_URL = "https://imdesktop.douyin.com/aweme/v1/web/aweme/detail/"


def _first_url(obj) -> str:
    if not isinstance(obj, dict):
        return ""
    url_list = obj.get("url_list") or obj.get("origin_url_list") or []
    if isinstance(url_list, list) and url_list:
        return str(url_list[0])
    u = obj.get("url")
    return str(u) if u else ""


def fetch_aweme_detail(http: DouyinHttpPy, aweme_id: str, timeout: int = 8) -> dict | None:
    """拉取视频详情：desc / cover / play_url。

    Returns: {"desc": str, "cover": str, "play_url": str}；失败或超时返回 None。
    """
    if not aweme_id:
        return None
    try:
        query = desktop_rest_base_query(http)
        query["aweme_id"] = str(aweme_id)
        query_wire = urlencode(query)
        abogus = generate_jumpbyte_abogus(
            query=query_wire, body="", user_agent=http.get_user_agent()
        )
        url = f"{DETAIL_URL}?{query_wire}&a_bogus={quote(abogus, safe='')}"
        data = http.request_json(url, "GET", timeout=timeout)
    except (RuntimeError, TypeError, ValueError, ConnectionError, OSError) as e:
        return {"desc": "", "cover": "", "play_url": "", "error": str(e)}
    detail = data.get("aweme_detail") or data.get("data") or {}
    if not isinstance(detail, dict):
        return {"desc": "", "cover": "", "play_url": "", "error": "no detail"}
    video = detail.get("video") or {}
    return {
        "desc": str(detail.get("desc") or ""),
        "cover": _first_url(video.get("cover")) or _first_url(video.get("origin_cover")),
        "play_url": _first_url(video.get("play_addr")) or _first_url(video.get("download_addr")),
        "error": "",
    }
