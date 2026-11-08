"""InboundMessage → MessageChain 构建（含 [转发] 前缀、净化、截断）。"""
from __future__ import annotations

from datetime import datetime

from astrbot.api.event import MessageChain
from astrbot.api.message_components import Image, Plain

from dyf_core.model import InboundMessage, MessageType

_SANITIZE_CHARS = ["**", "`", "~~", "*"]
_SOURCE_LABEL = {"douyin": "抖音"}


def _sanitize(text: str) -> str:
    if not text:
        return ""
    for ch in _SANITIZE_CHARS:
        text = text.replace(ch, "")
    return text


def _truncate(text: str, max_length: int) -> str:
    if max_length <= 0 or len(text) <= max_length:
        return text
    return text[: max(max_length - 3, 0)] + "..."


class MessageBuilder:
    def __init__(
        self,
        header_template: str = "[转发] {source} {peer_name} · {time}",
        include_link: bool = True,
        max_length: int = 1000,
    ):
        self.header_template = header_template or "[转发] {source} {peer_name} · {time}"
        self.include_link = include_link
        self.max_length = int(max_length or 1000)

    def _header(self, msg: InboundMessage) -> str:
        source = _SOURCE_LABEL.get(msg.source_platform, msg.source_platform)
        peer = msg.peer_name or "未知用户"
        now = datetime.now().strftime("%H:%M")
        try:
            return _sanitize(
                self.header_template.format(source=source, peer_name=peer, time=now)
            )
        except (KeyError, IndexError):
            return _sanitize(f"[转发] {source} {peer} · {now}")

    def _body(self, msg: InboundMessage) -> str:
        text = _sanitize(msg.text or "")
        if msg.type == MessageType.VIDEO_CARD and self.include_link and msg.card:
            item_id = str(
                msg.card.get("itemId") or msg.card.get("item_id") or ""
            )
            link = f"https://www.douyin.com/video/{item_id}"
            if item_id and link not in text:
                text = f"{text}\n{link}".strip()
        return _truncate(text, self.max_length)

    def build_chain(self, msg: InboundMessage) -> MessageChain | None:
        parts = [Plain(self._header(msg))]
        body = self._body(msg)
        if body:
            parts.append(Plain(body))
        for url in msg.media_urls:
            if not url:
                continue
            if msg.type == MessageType.IMAGE:
                try:
                    parts.append(Image.fromURL(url))
                except Exception:
                    parts.append(Plain(f"\n[图片] {url}"))
            else:
                parts.append(Plain(f"\n[附件] {url}"))
        if len(parts) <= 1:
            return None
        return MessageChain(parts)
