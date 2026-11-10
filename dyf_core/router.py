"""路由表：按序匹配，支持多命中。target 为 unified_msg_origin 或群号简写。"""
from __future__ import annotations

from dataclasses import dataclass, field

from dyf_core.model import InboundMessage, MessageType


@dataclass
class Route:
    name: str
    target: str
    types: set[MessageType] = field(default_factory=set)  # 空=全部
    senders_include: set[str] = field(default_factory=set)  # 已连接来源 uid（空=全部来源）

    def matches(self, msg: InboundMessage) -> bool:
        if self.types and msg.type not in self.types:
            return False
        pid = str(msg.peer_id or "")
        if self.senders_include:
            return pid and pid in self.senders_include
        return True


def _type_set(values) -> set[MessageType]:
    out = set()
    for v in values or []:
        try:
            out.add(MessageType(str(v)))
        except ValueError:
            pass
    return out


def _str_set(values) -> set[str]:
    return {str(v) for v in (values or []) if str(v)}


class RouteResolver:
    """配置驱动路由表。空路由表 → 返回 None（表示未命中）。"""

    def __init__(self, routes_cfg: list[dict] | None = None):
        self.routes: list[Route] = []
        for item in routes_cfg or []:
            if not isinstance(item, dict):
                continue
            target = item.get("target") or ""
            if not target:
                continue
            match = item.get("match") or {}
            self.routes.append(
                Route(
                    name=item.get("name", "route"),
                    target=target,
                    types=_type_set(match.get("types")),
                    senders_include=_str_set(match.get("senders_include")),
                )
            )

    def resolve(self, msg: InboundMessage) -> list[str]:
        targets: list[str] = []
        for r in self.routes:
            if r.matches(msg):
                targets.append(r.target)
        return targets

    def __bool__(self) -> bool:
        return bool(self.routes)
