"""InboundMessage → MessageChain 构建（含 [转发] 前缀、净化、截断、卡片图）。"""
from __future__ import annotations

import base64
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
        templates: list[dict] | None = None,
        markdown_enabled: bool = True,
        sanitize_body: bool = True,
    ):
        self.header_template = header_template or "[转发] {source} {peer_name} · {time}"
        self.include_link = include_link
        self.max_length = int(max_length or 1000)
        self.templates = templates or []
        self.markdown_enabled = bool(markdown_enabled)
        self.sanitize_body = bool(sanitize_body)

    # ---- 模板渲染 ----
    def _context(self, msg: InboundMessage) -> dict:
        source = _SOURCE_LABEL.get(msg.source_platform, msg.source_platform)
        peer = msg.peer_name or "未知用户"
        try:
            t = datetime.fromtimestamp(msg.timestamp) if msg.timestamp else datetime.now()
        except (OSError, ValueError):
            t = datetime.now()
        card = msg.card or {}
        item_id = str(card.get("itemId") or card.get("item_id") or "")
        link = f"https://www.douyin.com/video/{item_id}" if item_id else ""
        return {
            "source": source,
            "peer_name": peer,
            "time": t.strftime("%H:%M"),
            "title": str(card.get("title") or card.get("desc") or ""),
            "desc": str(card.get("desc") or ""),
            "link": link,
            "image_url": str((msg.media_urls or [""])[0]),
        }

    def _render_text(self, content: str, ctx: dict, markdown: bool) -> str:
        """渲染模板内容：.format() 容错回退逐键替换；markdown 关闭时净化 Markdown 字符。"""
        try:
            rendered = content.format(**ctx)
        except (KeyError, IndexError, ValueError):
            rendered = content
            for k, v in ctx.items():
                rendered = rendered.replace("{" + k + "}", str(v))
        if not markdown:
            rendered = _sanitize(rendered)
        return rendered

    def _template_content(self, for_media: bool = False) -> str:
        """模板 content（媒体场景优先 for_media）；空回退 header_template。"""
        for t in (self.templates or []):
            if bool(t.get("for_media")) == for_media:
                return str(t.get("content") or "")
        return self.header_template

    def _template_embeds_image(self, for_media: bool = False) -> bool:
        """模板是否内嵌图片（含 {image_url} 占位符）→ markdown 场景跳过 Image 组件。"""
        return "{image_url}" in self._template_content(for_media)

    def _header(self, msg: InboundMessage) -> str:
        ctx = self._context(msg)
        content = self._template_content()
        rendered = self._render_text(content, ctx, markdown=self.markdown_enabled)
        return _truncate(rendered, self.max_length)

    def _body(self, msg: InboundMessage) -> str:
        text = msg.text or ""
        if self.sanitize_body:
            text = _sanitize(text)
        if msg.type == MessageType.VIDEO_CARD and self.include_link and msg.card:
            item_id = str(
                msg.card.get("itemId") or msg.card.get("item_id") or ""
            )
            link = f"https://www.douyin.com/video/{item_id}"
            if item_id and link not in text:
                text = f"{text}\n{link}".strip()
        return _truncate(text, self.max_length)

    def build_chain(
        self,
        msg: InboundMessage,
        card_image: bytes | None = None,
        media: list[str] | None = None,
        with_text: bool = True,
    ) -> MessageChain | None:
        """构建 MessageChain。

        Args:
            msg: 待转发消息。
            card_image: 卡片图字节（替换首个媒体）；失败退回原媒体。
            media: 指定要发的媒体子集；None 表示全部。
            with_text: 是否带 header + 正文（媒体分批时仅第一批带）。
        """
        parts = [Plain(self._header(msg))] if with_text else []
        body = self._body(msg) if with_text else ""
        if body:
            # 前置换行：AstrBot 拼接多个 Plain 无换行，正文需独立一行（否则紧贴 header）
            parts.append(Plain("\n" + body))
        # markdown + 模板内嵌图片：卡片图/首媒体不再 append（模板已含 ![..](image_url)）
        md_image_inline = self.markdown_enabled and self._template_embeds_image()
        # 卡片图（含封面+标题）替换首个媒体（封面），其余媒体照发；失败退回原媒体
        media_urls = list(media if media is not None else msg.media_urls)
        if card_image:
            if md_image_inline:
                media_urls = media_urls[1:] if media_urls else []
            else:
                try:
                    parts.append(Image.fromBase64(base64.b64encode(card_image).decode()))
                    if media_urls:
                        media_urls = media_urls[1:]
                except Exception:
                    pass  # 卡片图失败退回原媒体列表
        for url in media_urls:
            if not url:
                continue
            if msg.type in (MessageType.IMAGE, MessageType.VIDEO_CARD):
                if md_image_inline:
                    continue  # 模板已内嵌图片，不重复发
                try:
                    parts.append(Image.fromURL(url))
                except Exception:
                    parts.append(Plain(f"\n[图片] {url}"))
            else:
                parts.append(Plain(f"\n[附件] {url}"))
        if len(parts) <= 1:
            return None
        return MessageChain(parts)
