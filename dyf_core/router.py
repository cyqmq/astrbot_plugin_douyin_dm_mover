"""路由表：按序匹配，支持多命中。target 为 unified_msg_origin 或群号简写。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from dyf_core.model import InboundMessage, MessageType

logger = logging.getLogger(__name__)


@dataclass
class Route:
    name: str
    target: str = ""
    targets: list[str] = field(default_factory=list)  # 多目标（targets 优先，target 兼容旧配置）
    types: set[MessageType] = field(default_factory=set)  # 空=全部
    senders_include: set[str] = field(default_factory=set)  # 好友来源 uid（仅单聊；空=全部单聊）
    groups_include: set[str] = field(default_factory=set)  # 群来源 group_id（仅群聊；空=全部群）
    # 连接级模板卡映射（需求 5.1 重构）：目标 UMO → template_cards 实体 id；缺项=该目标直连。
    tgt_cards: dict = field(default_factory=dict)

    def all_targets(self) -> list[str]:
        return [t for t in (self.targets or []) if t] or ([self.target] if self.target else [])

    def matches(self, msg: InboundMessage) -> bool:
        if self.types and msg.type not in self.types:
            return False
        if msg.conversation_type == 2:  # 群聊：按 group_id，或好友来源按发送者匹配
            if self.groups_include:
                return str(msg.group_id or "") in self.groups_include
            if self.senders_include:
                return str(msg.peer_id or "") in self.senders_include
            return True
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


def _migrate_tgt_cards(config: dict) -> None:
    """路由级 template_card → 连接级 tgt_cards + template_cards 实体（幂等，写回 config）。
    迁移条件：路由有 template_card（{enabled, templates 非空}）且无 tgt_cards 映射 → 生成一个实体，
    该路由所有 targets 的 tgt_cards[umo]=新 id（「一个模板卡连多目标」）。已有 tgt_cards 不重复生成。
    config 的旧 template_card 字段保留（仅作迁移源，转发已切 tgt_cards）。"""
    routes_cfg = config.get("routes")
    if not isinstance(routes_cfg, list):
        return
    cards = config.get("template_cards")
    if not isinstance(cards, list):
        cards = []
        config["template_cards"] = cards
    exist_ids = {str(tc.get("id")) for tc in cards if isinstance(tc, dict) and tc.get("id")}
    seq = len(exist_ids) + 1
    for item in routes_cfg:
        if not isinstance(item, dict):
            continue
        tgt_cards = item.get("tgt_cards")
        if isinstance(tgt_cards, dict) and tgt_cards:
            continue  # 已有映射不重复生成
        tc = item.get("template_card")
        if not isinstance(tc, dict):
            continue
        templates = tc.get("templates")
        if not isinstance(templates, list) or not templates:
            continue
        new_id = f"tcard{seq}"
        while new_id in exist_ids:
            seq += 1
            new_id = f"tcard{seq}"
        seq += 1
        exist_ids.add(new_id)
        cards.append(
            {"id": new_id, "enabled": bool(tc.get("enabled", True)), "templates": list(templates)}
        )
        targets = item.get("targets") or ([item.get("target")] if item.get("target") else [])
        mapping = {str(t): new_id for t in targets if t}
        if mapping:
            item["tgt_cards"] = mapping


class RouteResolver:
    """配置驱动路由表。空路由表 → 返回 None（表示未命中）。"""

    def __init__(self, routes_cfg: list[dict] | None = None, template_cards_cfg: list[dict] | None = None):
        self.routes: list[Route] = []
        # 模板卡实体表（连接级）：id → {enabled, templates}；供 tgt_cards 引用校验
        self.template_cards: dict[str, dict] = {}
        for tc in template_cards_cfg or []:
            if not isinstance(tc, dict) or not tc.get("id"):
                continue
            self.template_cards[str(tc["id"])] = {
                "enabled": bool(tc.get("enabled", True)),
                "templates": [str(t) for t in (tc.get("templates") or []) if str(t)],
            }
        valid_ids = set(self.template_cards)
        for item in routes_cfg or []:
            if not isinstance(item, dict):
                continue
            targets = item.get("targets") or (
                [item.get("target")] if item.get("target") else []
            )
            if not targets:
                continue
            match = item.get("match") or {}
            # tgt_cards 防御解析：非 dict → {}；引用的 tcard_id 不在 template_cards → 该目标直连（跳过）
            tgt_cards: dict[str, str] = {}
            raw_tc = item.get("tgt_cards")
            if isinstance(raw_tc, dict):
                for k, v in raw_tc.items():
                    vid = str(v or "")
                    if vid and vid in valid_ids:
                        tgt_cards[str(k)] = vid
            self.routes.append(
                Route(
                    name=item.get("name", "route"),
                    target=item.get("target") or "",
                    targets=[str(t) for t in targets if t],
                    types=_type_set(match.get("types")),
                    senders_include=_str_set(match.get("senders_include")),
                    groups_include=_str_set(match.get("groups_include")),
                    tgt_cards=tgt_cards,
                )
            )
        logger.info(
            f"[dyf] 路由表构建: {[(r.name, sorted(map(str, r.types)), sorted(r.senders_include), sorted(r.groups_include), r.all_targets()) for r in self.routes]}"
        )

    def resolve(self, msg: InboundMessage) -> list[tuple[Route, str]]:
        """按序命中路由，返回 [(Route, target)]；每命中路由产出全部 targets；未命中返回空。
        Route 携带 tgt_cards（目标→模板卡实体 id），供转发链路按目标取模板卡。"""
        hits: list[tuple[Route, str]] = []
        for r in self.routes:
            if r.matches(msg):
                for t in r.all_targets():
                    hits.append((r, t))
        return hits

    def __bool__(self) -> bool:
        return bool(self.routes)
