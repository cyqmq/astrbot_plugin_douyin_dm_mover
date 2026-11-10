"""卡片渲染：视频/图集转发时生成 App Store「Today」风格卡图。

纯 Pillow 实现（渐变遮罩不用 numpy，用 L 模式图一次生成），封面下载 + 渲染
全部同步阻塞，调用方必须放进线程池（``asyncio.to_thread``）。任何失败（无字体、
无封面、异常）返回 ``None``，调用方退回文本转发。

设计借鉴 nonebot-plugin-parsehub 的 ``card/``：三段式布局（封面 → 渐变 → 平台名 +
标题 + 元信息行），封面按比例裁切聚焦在纵向 28%。
"""
from __future__ import annotations

import io
import time
from functools import lru_cache
from typing import Any

# ---- 版面参数（与 parsehub layout.py 对齐） ----
WIDTH = 1080  # 卡片宽度
INSET = 48  # 四周留白
TITLE_SIZE = 58  # 标题字号
META_SIZE = 27  # 元信息行字号
KICKER_SIZE = 27  # 平台名一行（kicker）字号
TITLE_LINE_HEIGHT = 70  # 标题行高
TITLE_META_GAP = 8  # 标题块与元信息行之间
META_BOTTOM = 34  # 元信息行下方预留
FADE_RESERVE = 50  # 文字区上方的渐变额外预留
KICKER_TOP_GAP = 44  # 平台名相对标题块的上方间距
MIN_RATIO = 0.62  # 封面允许的最小宽高比
MAX_RATIO = 1.25  # 封面允许的最大宽高比
COVER_FOCUS = 0.28  # 封面裁剪聚焦在画面纵向 28% 处
FADE_START = 0.34  # 渐变从封面 34% 高度处开始
FADE_PEAK = 200  # 文字区上缘的不透明度
FADE_BOTTOM = 252  # 渐变结束时的不透明度
FADE_COLOR = (6, 6, 10)  # 渐变颜色

PLATFORM = "抖音"  # kicker 平台名（无 logo 资源，仅文字）
_TYPE_LABEL = {"video": "视频", "image": "图集", "multimedia": "图文"}

# 系统中文字体（按优先级）。都没有则卡片功能关闭，退回文本转发。
SYSTEM_FONTS = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "C:/Windows/Fonts/msyh.ttc",
)


def _pil() -> Any:
    """延迟导入 Pillow，缺失时由调用方处理 ImportError。"""
    from PIL import Image, ImageDraw, ImageFont

    return Image, ImageDraw, ImageFont


@lru_cache(maxsize=1)
def _font_path() -> str | None:
    """找一份可用的中文字体文件（不下载）。"""
    for path in SYSTEM_FONTS:
        try:
            with open(path, "rb"):
                return path
        except OSError:
            continue
    return None


def available() -> bool:
    """卡片功能是否可用（有 Pillow 且有字体）。"""
    try:
        _pil()
        return _font_path() is not None
    except ImportError:
        return False


def _font(size: int) -> Any:
    """取字体对象。"""
    _, _, ImageFont = _pil()
    path = _font_path()
    if path is None:
        raise RuntimeError("没有可用的中文字体")
    return ImageFont.truetype(path, size)


def _vertical_mask(
    width: int, height: int, start: int, end: int, *, peak: int, floor: int, curve: float
) -> Any:
    """竖直渐变遮罩（L 模式）。纯 Pillow：按行算 alpha，一次 frombytes + resize。

    Args:
        width: 遮罩宽度。
        height: 遮罩高度。
        start: 开始变深的位置。
        end: 达到 peak 的位置。
        peak: 最大不透明度。
        floor: 起始不透明度。
        curve: 曲线指数，越大起步越缓。
    """
    Image, _, _ = _pil()
    span = max(1, end - start)
    alphas = bytearray()
    for y in range(height):
        if y < start:
            alphas.append(0)
        else:
            ramp = min(1.0, (y - start) / span)
            alphas.append(int(floor + (peak - floor) * (ramp**curve)))
    return Image.frombytes("L", (1, height), bytes(alphas)).resize(
        (width, height), Image.BILINEAR
    )


def _advance(text: str, font: Any) -> float:
    """算一段文字的像素宽度（去零宽控制字符）。"""
    cleaned = "".join(ch for ch in text if ch not in ("\u200b", "\ufeff"))
    return float(font.getlength(cleaned))


def _wrap_title(text: str, font: Any, max_w: int, max_lines: int) -> list[str]:
    """按词折行（话题标签/网址不劈开），超出 max_lines 时末行加省略号。"""
    import re

    def width(part: str) -> float:
        return _advance(part, font)

    lines: list[str] = []
    for para in text.split("\n"):
        if not para:
            continue
        cur = ""
        for token in re.findall(r"\S+\s*", para):
            if width(cur + token) <= max_w:
                cur += token
                continue
            if cur.strip():
                lines.append(cur.rstrip())
                cur = ""
                if len(lines) == max_lines:
                    break
            if width(token) > max_w:
                piece = ""
                for char in token:
                    if width(piece + char) <= max_w:
                        piece += char
                    else:
                        lines.append(piece)
                        piece = char
                        if len(lines) == max_lines:
                            break
                cur = piece
            else:
                cur = token
            if len(lines) == max_lines:
                break
        if len(lines) == max_lines:
            break
        if cur.strip():
            lines.append(cur.rstrip())
    lines = lines[:max_lines]
    flat_all = "".join("".join(lines).split())
    flat_src = "".join(text.split())
    if lines and len(flat_all) < len(flat_src):
        lines[-1] = lines[-1][: max(1, len(lines[-1]) - 1)] + "…"
    return lines


def _cover_image(cover_url: str, timeout: int = 8) -> Any:
    """下载封面并转为 RGB，返回 None 表示失败。"""
    Image, _, _ = _pil()
    import requests

    resp = requests.get(cover_url, timeout=timeout)
    resp.raise_for_status()
    if not resp.content:
        return None
    try:
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    except Exception:
        return None


def _title_of(msg: Any) -> str:
    """卡片标题：优先卡内 content_title，否则取正文首行（去链接）。"""
    card = getattr(msg, "card", None) or {}
    title = str(card.get("content_title") or card.get("title") or card.get("desc") or "")
    if title.strip():
        return title.strip()
    text = str(getattr(msg, "text", "") or "")
    first = text.split("\n", 1)[0].strip()
    if first and "http" not in first:
        return first
    return "(无标题)"


def _type_label(msg: Any) -> str:
    """元信息类型标签。"""
    t = str(getattr(msg, "type", ""))
    if t.startswith("MessageType."):
        t = t.rsplit(".", 1)[-1]
    return _TYPE_LABEL.get(t.lower(), "媒体")


def render_card(msg: Any, cover_url: str | None = None) -> bytes | None:
    """渲染视频/图集为 JPEG 卡图字节。

    Args:
        msg: InboundMessage（含 type/text/card/media_urls）。
        cover_url: 封面直链；缺省取 ``msg.media_urls[0]``。

    Returns:
        JPEG 字节；失败（无字体/无封面/异常）为 ``None``，调用方退回文本。
    """
    Image, ImageDraw, _ = _pil()
    if not available():
        return None

    cover_url = cover_url or (getattr(msg, "media_urls", None) or [None])[0]
    if not cover_url:
        return None
    cover = _cover_image(str(cover_url))
    if cover is None:
        return None

    ratio = min(max(cover.height / cover.width, MIN_RATIO), MAX_RATIO)
    card_w = WIDTH
    card_h = int(card_w * ratio)
    scale = max(card_w / cover.width, card_h / cover.height)
    big = cover.resize(
        (int(cover.width * scale), int(cover.height * scale)), Image.BICUBIC
    )
    left = (big.width - card_w) // 2
    top = int((big.height - card_h) * COVER_FOCUS)
    pic = big.crop((left, top, left + card_w, top + card_h))

    title_font = _font(TITLE_SIZE)
    meta_font = _font(META_SIZE)
    kicker_font = _font(KICKER_SIZE)
    title_lines = _wrap_title(_title_of(msg), title_font, card_w - INSET * 2, 3)
    meta = f"{PLATFORM} · {_type_label(msg)}"

    text_top = (
        card_h
        - INSET
        - len(title_lines) * TITLE_LINE_HEIGHT
        - TITLE_META_GAP
        - META_BOTTOM
        - FADE_RESERVE
    )
    start = max(0, int(card_h * FADE_START))
    ramp_end = max(start + 1, text_top)
    upper = _vertical_mask(card_w, ramp_end, start, ramp_end, peak=FADE_PEAK, floor=0, curve=1.25)
    lower = _vertical_mask(card_w, card_h - ramp_end, 0, card_h - ramp_end, peak=FADE_BOTTOM, floor=FADE_PEAK, curve=1.0)
    layer = Image.new("RGB", (card_w, ramp_end), FADE_COLOR)
    pic.paste(layer, (0, 0), upper)
    layer = Image.new("RGB", (card_w, card_h - ramp_end), FADE_COLOR)
    pic.paste(layer, (0, ramp_end), lower)

    canvas = pic.convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    y = card_h - INSET - len(title_lines) * TITLE_LINE_HEIGHT - TITLE_META_GAP - META_BOTTOM
    kicker_y = y - KICKER_TOP_GAP
    draw.text((INSET, kicker_y), PLATFORM, font=kicker_font, fill=(226, 226, 232))
    for line in title_lines:
        draw.text((INSET, y), line, font=title_font, fill=(255, 255, 255))
        y += TITLE_LINE_HEIGHT
    draw.text((INSET, y + TITLE_META_GAP), meta, font=meta_font, fill=(214, 214, 222))

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "JPEG", quality=92)
    return buf.getvalue()


def render_card_safe(msg: Any, cover_url: str | None = None) -> bytes | None:
    """render_card 的兜底包装：任何异常返回 None，不向上抛。"""
    try:
        return render_card(msg, cover_url)
    except Exception:
        return None


if __name__ == "__main__":  # 手动验证：python3 -m dyf_core.card
    class _Msg:
        def __init__(self):
            self.type = "video"
            self.text = "这个城市需要一个英雄!\nhttps://www.douyin.com/video/1"
            self.card = {"content_title": "这个城市需要一个英雄!", "itemId": "1"}
            self.media_urls = []

    print("available:", available())
    t0 = time.time()
    out = render_card_safe(_Msg(), cover_url=None)
    print(f"render ok={out is not None} in {time.time()-t0:.2f}s len={len(out) if out else 0}")
