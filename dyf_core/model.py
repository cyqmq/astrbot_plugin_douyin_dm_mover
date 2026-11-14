"""平台中立的数据模型。core/ 只依赖本文件与 gateway/base.py 接口。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MessageType(str, Enum):
    """归一化消息类型。抖音 msg_type → MessageType 映射见 gateway/douyin/converter.py。"""

    TEXT = "text"
    IMAGE = "image"
    VIDEO_CARD = "video_card"
    EMOJI = "emoji"
    VOICE = "voice"
    OTHER = "other"


class AuthState(Enum):
    """登录态。OK=正常；EXPIRED=鉴权失败（禁止静默重连）；UNKNOWN=未知。"""

    OK = "ok"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


@dataclass
class InboundMessage:
    """平台中立入站消息，由各 Gateway 产出，转发核心只处理本结构。"""

    source_platform: str
    message_id: str
    conversation_id: str
    peer_id: str | None
    peer_name: str
    type: MessageType
    text: str
    media_urls: list[str] = field(default_factory=list)
    card: dict | None = None
    timestamp: int = 0
    is_outgoing: bool = False
    raw: dict = field(default_factory=dict)
    conversation_type: int = 1  # 1=单聊 c2c, 2=群聊 group
    group_id: str | None = None  # 群聊时为群 ID（纯数字 conversation_id）
    sender_id: str | None = None  # 发送者 uid（群聊时=群成员）
    sender_sec_uid: str | None = None  # 发送者 sec_uid（批量拉昵称/头像接口用）

    def to_dict(self) -> dict:
        """返回可 JSON 序列化的 dict（枚举 → 字符串）。"""
        d = {
            "source_platform": self.source_platform,
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "peer_id": self.peer_id,
            "peer_name": self.peer_name,
            "type": self.type.value,
            "text": self.text,
            "media_urls": list(self.media_urls),
            "card": self.card,
            "timestamp": int(self.timestamp),
            "is_outgoing": self.is_outgoing,
            "raw": self.raw,
            "conversation_type": int(self.conversation_type),
            "group_id": self.group_id,
            "sender_id": self.sender_id,
            "sender_sec_uid": self.sender_sec_uid,
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> InboundMessage:
        """从 to_dict() 产物还原，type 字符串 → 枚举。"""
        d = dict(data)
        t = d.get("type")
        d["type"] = t if isinstance(t, MessageType) else MessageType(str(t))
        return cls(**d)


@dataclass
class GatewayEvent:
    """网关上报给插件的状态/告警事件。"""

    kind: str  # started | message | auth_failure | disconnect | reconnect | error | stopped
    detail: str = ""


class DeliveryResult:
    """单目标投递结果。"""

    def __init__(self, target: str, ok: bool, error: str = ""):
        self.target = target
        self.ok = ok
        self.error = error

    def __repr__(self) -> str:
        return f"DeliveryResult(target={self.target!r}, ok={self.ok}, error={self.error!r})"


# ---- 积木（推送模板/消息草稿）----
BLOCK_TYPES = ("text", "heading", "media", "link", "button", "divider")


def validate_block(b: dict) -> str | None:
    """校验单个积木：type 白名单 + 按类型必填字段。返回错误信息或 None。"""
    if not isinstance(b, dict):
        return "积木必须是对象"
    t = b.get("type")
    if t not in BLOCK_TYPES:
        return f"非法积木类型: {t!r}（允许: {', '.join(BLOCK_TYPES)}）"
    d = b.get("data") or {}
    if not isinstance(d, dict):
        return f"积木 {t} 的 data 必须是对象"
    if t == "text" and not str(d.get("text", "")).strip():
        return "text 积木缺少 text"
    if t == "heading" and not str(d.get("title", "")).strip():
        return "heading 积木缺少 title"
    if (
        t == "media"
        and not str(d.get("image", "")).strip()
        and not str(d.get("title", "")).strip()
    ):
        return "media 积木需 image 或 title 至少其一"
    if t == "link" and not str(d.get("text", "")).strip():
        return "link 积木缺少 text"
    if t == "button" and not str(d.get("text", "")).strip():
        return "button 积木缺少 text"
    return None
