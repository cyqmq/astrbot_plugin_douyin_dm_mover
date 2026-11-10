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


# ---- 摘取自 ParseHub（MIT License, Copyright (c) 2024 梓澪）parsers/parser/douyin.py ----
# 视频信息规范化：去水印（playwm→play）、bit_rate 编码过滤（bytevc1）回退、宽高。
# 保留上游版权与 MIT 许可（https://github.com/z-mio/ParseHub/blob/master/LICENSE）。
def remove_video_watermark(url: str) -> str:
    """移除抖音视频水印标识 (playwm -> play)。"""
    return url.replace("playwm", "play")


def _p_play_addr(video_data: dict) -> tuple[list[str], int, int]:
    play_addr = video_data["play_addr"]
    return play_addr["url_list"], play_addr.get("width", 0), play_addr.get("height", 0)


def _p_bit_rates(video_data: dict, filter_bytevc1: bool = False) -> tuple[list[str], int, int]:
    bit_rates: list = video_data.get("bit_rate", [])
    if filter_bytevc1:
        bit_rates = list(filter(lambda i: i.get("is_bytevc1", 0) == 0, bit_rates))
    bit_rates.sort(
        key=lambda x: (
            x.get("play_addr", {}).get("width", 0) * x.get("play_addr", {}).get("height", 0),
            x.get("play_addr", {}).get("data_size", 0),
            x.get("bit_rate", 0),
        ),
        reverse=True,
    )
    best_quality = bit_rates[0]
    play_addr = best_quality.get("play_addr", {})
    return play_addr.get("url_list", []), play_addr.get("width", 0), play_addr.get("height", 0)


def parse_video_info(video_data: dict) -> dict:
    """规范化视频信息：直链（去水印）、封面、宽高、时长。"""
    is_app = video_data.get("is_bytevc1", None) is not None  # 只有 app 接口带 is_bytevc1 参数
    if is_app:
        urls, w, h = _p_play_addr(video_data)
        if not urls:
            urls, w, h = _p_bit_rates(video_data, True)
    else:
        urls, w, h = _p_bit_rates(video_data)

    video_url, *backup_urls = dict.fromkeys(remove_video_watermark(u) for u in urls)

    cover = video_data.get("cover", {})
    thumb_url_list = cover.get("url_list", [])
    thumb_url = thumb_url_list[-1] if thumb_url_list else None

    return {
        "video_url": video_url,
        "backup_urls": backup_urls,
        "thumb_url": thumb_url,
        "duration": video_data.get("duration", 0),
        "width": w,
        "height": h,
    }
# ---- ParseHub 摘取结束 ----


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
    except (RuntimeError, TypeError, ValueError, KeyError, ConnectionError, OSError) as e:
        return {"desc": "", "cover": "", "play_url": "", "error": str(e)}
    detail = data.get("aweme_detail") or {}
    if not detail:
        _d = data.get("data") or {}
        detail = _d.get("aweme_detail") if isinstance(_d, dict) else {}
    if not isinstance(detail, dict):
        return {"desc": "", "cover": "", "play_url": "", "error": "no detail"}
    video = detail.get("video") or {}
    vi = parse_video_info(video) if isinstance(video, dict) and video else {}
    return {
        "desc": str(detail.get("desc") or ""),
        "cover": vi.get("thumb_url")
        or _first_url(video.get("cover"))
        or _first_url(video.get("origin_cover")),
        "play_url": vi.get("video_url") or "",
        "backup_urls": vi.get("backup_urls", []),
        "width": vi.get("width", 0),
        "height": vi.get("height", 0),
        "duration": vi.get("duration", 0),
        "error": "",
    }
