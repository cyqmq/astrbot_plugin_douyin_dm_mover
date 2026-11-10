"""Douyin 原始帧 → InboundMessage 类型白名单映射。

Douyin msg_type → 自有 MessageType（与 douyin_recv_msg.py 一致）：
7 文本 / 8 分享视频卡片 / 27 图片 / 5 表情 / 17 语音 / 50001 已读(跳过)
"""
from __future__ import annotations

import json
import time

from astrbot.api import logger

from dyf_core.model import InboundMessage, MessageType

from .peer import is_outgoing, resolve_peer

_SKIP_TYPES = {50001, 50002}  # 50001 对方已读 / 50002 消息更新扩展，均非独立媒体

VIDEO_CARD_TYPES = {8}


def _timestamp_of(raw: dict) -> int:
    """统一消息时间（秒级）：优先 msg_time/create_time，兼容毫秒，兜底当前时间。"""
    for key in ("msg_time", "create_time", "timestamp", "msg_timestamp"):
        v = raw.get(key)
        if v in (None, ""):
            continue
        try:
            ts = int(v)
        except (TypeError, ValueError):
            continue
        if ts <= 0:
            continue
        return ts // 1000 if ts > 10**11 else ts
    return int(time.time() * 1000) // 1000


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

    def __init__(self, self_uid_provider, nickname_provider=None):
        # self_uid_provider: callable -> int | None（每次调用取最新解析值）
        # nickname_provider: callable uid -> str | None（查发送者昵称，回退昵称而非 uid）
        self._uid_provider = self_uid_provider
        self._nickname_provider = nickname_provider

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

        mtype, text, media_urls, card = self._classify(
            msg_type, content, str(raw.get("share_item_id", "") or "")
        )

        # 临时诊断：非白名单消息（图片合集/分享卡等未知类型）dump 完整 raw，供定位后修复
        if mtype == MessageType.OTHER:
            logger.info(
                f"[dyf] raw full: {json.dumps(raw, ensure_ascii=False)[:500]}"
            )

        peer_id = resolve_peer(conversation_id, self_uid)
        # 纯数字短 id conv 解析失败时用发送者兜底（sender 为对端 uid，非 self）
        if not peer_id and sender and str(sender) != str(self_uid or ""):
            peer_id = str(sender)
        # 昵称：content.name/nick_name → 发送者昵称（好友/会话）→ 才回退 peer_id（不裸显示 uid）
        peer_name = str(content.get("name") or content.get("nick_name") or "")
        if not peer_name and self._nickname_provider is not None:
            try:
                peer_name = str(self._nickname_provider(sender) or "")
            except Exception:
                peer_name = ""
        if not peer_name:
            peer_name = str(peer_id or "")

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
            timestamp=_timestamp_of(raw),
            is_outgoing=is_outgoing(sender, self_uid),
            raw=raw,
        )

    @staticmethod
    def _classify(msg_type, content, share_item_id: str = "") -> tuple[MessageType, str, list[str], dict | None]:
        if msg_type == 7:  # 文本
            return MessageType.TEXT, str(content.get("text", "")), [], None
        if msg_type in (77, 110):  # IM_SHARE_PHOTOS 图集分享 / 新版作品分享（带 share_item_id）
            if not share_item_id:
                # 无分享 id：可能是新类型/命令层，落 OTHER（dump 待分类），不空转发
                return MessageType.OTHER, "", [], None
            card = dict(content)
            card["share_item_id"] = share_item_id
            return MessageType.IMAGE, "分享", [], card
        if msg_type in VIDEO_CARD_TYPES:  # 分享视频卡片
            item_id = str(content.get("itemId") or content.get("item_id") or "")
            title = str(content.get("content_title") or content.get("title") or content.get("desc") or "抖音视频")
            link = f"https://www.douyin.com/video/{item_id}" if item_id else ""
            text = f"{title}\n{link}".strip()
            # 封面：cover_url.url_list[0]（douyin-im）或 coverUrl（cards.ts）直链
            cover_urls: list[str] = []
            cu = content.get("cover_url")
            if isinstance(cu, dict):
                cu = _first_url(cu)
            elif not isinstance(cu, str):
                cu = None
            cu = cu or content.get("coverUrl")
            if isinstance(cu, str) and cu:
                cover_urls = [cu]
            return MessageType.VIDEO_CARD, text, cover_urls, content
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
