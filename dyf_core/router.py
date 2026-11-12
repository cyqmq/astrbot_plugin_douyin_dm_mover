"""路由表：按序匹配，支持多命中。target 为 unified_msg_origin 或群号简写。"""
from __future__ import annotations

from dataclasses import dataclass, field

from dyf_core.model import InboundMessage, MessageType


@dataclass
class Route:
    name: str
    target: str = ""
    targets: list[str] = field(default_factory=list)  # 多目标（targets 优先，target 兼容旧配置）
    types: set[MessageType] = field(default_factory=set)  # 空=全部
    senders_include: set[str] = field(default_factory=set)  # 好友来源 uid（仅单聊；空=全部单聊）
    groups_include: set[str] = field(default_factory=set)  # 群来源 group_id（仅群聊；空=全部群）

    def all_targets(self) -> list[str]:
        return [t for t in (self.targets or []) if t] or ([self.target] if self.target else [])

    def matches(self, msg: InboundMessage) -> bool:
        if self.types and msg.type not in self.types:
            return False
        if msg.conversation_type == 2:  # 群聊：按 group_id 匹配（好友来源路由不接群聊）
            if self.groups_include:
                return str(msg.group_id or "") in self.groups_include
            return not self.senders_include
        # 单聊：按 peer_id 匹配（群来源路由不接单聊）
        pid = str(msg.peer_id or "")
        if self.senders_include:
            return pid and pid in self.senders_include
        return not self.groups_include


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
            targets = item.get("targets") or (
                [item.get("target")] if item.get("target") else []
            )
            if not targets:
                continue
            match = item.get("match") or {}
            self.routes.append(
                Route(
                    name=item.get("name", "route"),
                    target=item.get("target") or "",
                    targets=[str(t) for t in targets if t],
                    types=_type_set(match.get("types")),
                    senders_include=_str_set(match.get("senders_include")),
                    groups_include=_str_set(match.get("groups_include")),
                )
            )

    def resolve(self, msg: InboundMessage) -> list[tuple[str, str]]:
        """按序命中路由，返回 [(路由名, target)]；每命中路由产出全部 targets；未命中返回空。"""
        hits: list[tuple[str, str]] = []
        for r in self.routes:
            if r.matches(msg):
                for t in r.all_targets():
                    hits.append((r.name, t))
        return hits

    def __bool__(self) -> bool:
        return bool(self.routes)
