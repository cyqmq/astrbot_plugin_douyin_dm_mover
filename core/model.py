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
