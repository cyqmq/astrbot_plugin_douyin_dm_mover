"""规则抽象与内置规则。对齐 sowing_discord 的 Rule.evaluate()->bool 模式。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from core.model import InboundMessage, MessageType


class BaseRule(ABC):
    """全局门规则：evaluate 返回 False 则丢弃该消息。"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def evaluate(self, msg: InboundMessage) -> bool:
        raise NotImplementedError


class MessageTypeRule(BaseRule):
    """按消息类型开关（来源 + 类型维度）。"""

    def __init__(self, enabled_types: set[MessageType]):
        super().__init__("MessageTypeRule")
        self.enabled_types = enabled_types

    def evaluate(self, msg: InboundMessage) -> bool:
        return msg.type in self.enabled_types


class SenderFilterRule(BaseRule):
    """发送者白/黑名单。peer_id 为 None 时：黑名单不拦，白名单拦。"""

    def __init__(self, whitelist: set[str] | None = None, blacklist: set[str] | None = None):
        super().__init__("SenderFilterRule")
        self.whitelist = whitelist or set()
        self.blacklist = blacklist or set()

    def evaluate(self, msg: InboundMessage) -> bool:
        pid = str(msg.peer_id or "")
        if self.blacklist and pid in self.blacklist:
            return False
        if self.whitelist:
            return pid and pid in self.whitelist
        return True


class KeywordFilterRule(BaseRule):
    """命中关键词（如广告/无关词）则丢弃。空列表不过滤。"""

    def __init__(self, keywords: list[str] | None = None):
        super().__init__("KeywordFilterRule")
        self.keywords = [k.lower() for k in (keywords or []) if k]

    def evaluate(self, msg: InboundMessage) -> bool:
        if not self.keywords:
            return True
        hay = (msg.text or "").lower()
        return not any(k in hay for k in self.keywords)


class ComposeRule(BaseRule):
    """AND 组合多个规则。"""

    def __init__(self, rules: list[BaseRule]):
        super().__init__("ComposeRule")
        self.rules = rules

    def evaluate(self, msg: InboundMessage) -> bool:
        return all(r.evaluate(msg) for r in self.rules)
