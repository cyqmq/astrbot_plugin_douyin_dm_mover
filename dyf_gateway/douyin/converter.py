"""Douyin 原始帧 → InboundMessage 类型白名单映射。

Douyin msg_type → 自有 MessageType（与 douyin_recv_msg.py 一致）：
7 文本 / 8 分享视频卡片 / 27 图片 / 5 表情 / 17 语音 / 50001 已读(跳过)
"""
from __future__ import annotations

from dyf_core.model import InboundMessage, MessageType

from .peer import is_outgoing, resolve_peer

_SKIP_TYPES = {50001}  # 对方已读

VIDEO_CARD_TYPES = {8}


def _first_url(obj) -> str:
    if isinstance(obj, dict):
        url_list = obj.get("url_list") or obj.get("origin_url_list") or []
        if isinstance(url_list, list) and url_list:
            return str(url_list[0])
        u = obj.get("url")
        if isinstance(u, str):
            return u
    return ""


class DouyinConverter:
    """按当前 self_uid 把原始帧转成 InboundMessage。"""

    def __init__(self, self_uid_provider):
        # self_uid_provider: callable -> int | None（每次调用取最新解析值）
        self._uid_provider = self_uid_provider

    @property
    def self_uid(self) -> int | None:
        try:
            return self._uid_provider()
        except Exception:
            return None

    def convert(self, raw: dict) -> InboundMessage | None:
        msg_type = raw.get("message_type")
        if msg_type in _SKIP_TYPES:
            return None
        content = raw.get("content") or {}
        self_uid = self.self_uid
        conversation_id = raw.get("conversation_id", "")
        sender = raw.get("sender")

        mtype, text, media_urls, card = self._classify(msg_type, content)

        peer_id = resolve_peer(conversation_id, self_uid)
        peer_name = str(content.get("name") or content.get("nick_name") or peer_id or "")

        return InboundMessage(
            source_platform="douyin",
            message_id=str(raw.get("server_message_id", "")),
            conversation_id=conversation_id,
            peer_id=peer_id,
            peer_name=peer_name,
            type=mtype,
            text=text,
            media_urls=media_urls,
            card=card,
            timestamp=int(raw.get("index_in_conversation", 0)) or 0,
            is_outgoing=is_outgoing(sender, self_uid),
            raw=raw,
        )

    @staticmethod
    def _classify(msg_type, content) -> tuple[MessageType, str, list[str], dict | None]:
        if msg_type == 7:  # 文本
            return MessageType.TEXT, str(content.get("text", "")), [], None
        if msg_type in VIDEO_CARD_TYPES:  # 分享视频卡片
            item_id = str(content.get("itemId") or content.get("item_id") or "")
            title = str(content.get("title") or content.get("desc") or "抖音视频")
            link = f"https://www.douyin.com/video/{item_id}" if item_id else ""
            text = f"{title}\n{link}".strip()
            return MessageType.VIDEO_CARD, text, [], content
        if msg_type == 27:  # 图片
            url = (
                content.get("resource_url", {}).get("origin_url_list")
                or content.get("resource_url", {}).get("url_list")
                or [""]
            )
            urls = [str(u) for u in url if u]
            return MessageType.IMAGE, "", urls, None
        if msg_type == 5:  # 表情
            u = _first_url(content.get("url") or content)
            return MessageType.EMOJI, "", [u] if u else [], None
        if msg_type == 17:  # 语音
            u = _first_url(content.get("resource_url") or content)
            return MessageType.VOICE, "", [u] if u else [], None
        return MessageType.OTHER, str(content.get("text", "")), [], None
