"""ForwardManager：转发编排。流程见 DESIGN.md §6.3。"""
from __future__ import annotations

import hashlib
import time

from astrbot.api import logger

from dyf_core.alert import AlertService
from dyf_core.cache_manager import CacheManager
from dyf_core.message_builder import MessageBuilder
from dyf_core.message_sender import MessageSender
from dyf_core.model import InboundMessage
from dyf_core.ratelimit import RateLimiter
from dyf_core.retry_manager import RetryManager
from dyf_core.router import RouteResolver
from dyf_core.rules import ComposeRule, KeywordFilterRule, SenderFilterRule
from dyf_core.tracker import RecentStore


def _csv(value) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


class ForwardManager:
    def __init__(self, context, config: dict):
        self.context = context
        self.config = config
        self.data_dir = config.get("_data_dir") or "data/dyf"

        self.dedup_enabled = bool(config.get("dedup_enabled", True))
        self.cache = CacheManager(
            self.data_dir,
            window_seconds=config.get("dedup_window_seconds", 300),
        )
        self.rate = RateLimiter(
            global_enabled=config.get("rate_limit_global_enabled", True),
            global_max_per_min=config.get("rate_limit_global_max_per_min", 30),
            sender_enabled=config.get("rate_limit_sender_enabled", True),
            sender_max_per_min=config.get("rate_limit_sender_max_per_min", 10),
        )
        self.router = RouteResolver(config.get("routes"))
        self.default_target_group = str(config.get("default_target_group", "") or "")
        self.builder = MessageBuilder(
            header_template=config.get("header_template", ""),
            include_link=config.get("include_link", True),
            max_length=config.get("max_message_length", 1000),
        )
        self.sender = MessageSender(context, qq_adapter_id=config.get("qq_adapter_id", "aiocqhttp"))
        self.retry = RetryManager(
            self.cache,
            self.sender,
            self.builder,
            interval_seconds=config.get("retry_interval_seconds", 1800),
            enabled=bool(config.get("retry_enabled", True)),
        )
        self.alert = AlertService(
            context,
            alert_target=config.get("alert_target", ""),
            alert_only_once=config.get("alert_only_once", True),
        )
        self.require_peer = bool(config.get("require_peer", False))
        self.global_filter = ComposeRule(
            [
                SenderFilterRule(
                    whitelist=set(_csv(config.get("senders_whitelist"))),
                    blacklist=set(_csv(config.get("senders_blacklist"))),
                ),
                KeywordFilterRule(_csv(config.get("keyword_filters"))),
            ]
        )
        self._in_flight: set[str] = set()
        self.tracker = RecentStore()

    # ---- 来源/类型开关 ----
    def _source_enabled(self, platform: str) -> bool:
        sources = self.config.get("sources") or {}
        if isinstance(sources, dict) and platform in sources:
            return bool(sources[platform].get("enabled", True))
        return True

    def _type_enabled(self, msg: InboundMessage) -> bool:
        sources = self.config.get("sources") or {}
        if isinstance(sources, dict) and msg.source_platform in sources:
            types = sources[msg.source_platform].get("types") or {}
            if isinstance(types, dict):
                return bool(types.get(msg.type.value, True))
        # 无 sources 配置时回退到顶层 types_* 开关
        key = "types_" + msg.type.value
        return bool(self.config.get(key, True))

    def _dedup_key(self, msg: InboundMessage) -> str:
        if msg.message_id:
            return msg.message_id
        return hashlib.md5(
            f"{msg.source_platform}:{msg.peer_id}:{msg.type}:{msg.text}".encode()
        ).hexdigest()

    def _resolve_targets(self, msg: InboundMessage) -> list[str]:
        targets = self.router.resolve(msg)
        if targets:
            return targets
        if self.default_target_group:
            return [self.sender.build_origin(self.default_target_group)]
        return []

    async def handle(self, msg: InboundMessage) -> None:
        if msg.is_outgoing:
            return
        self.tracker.add_sender(msg)
        if not self._source_enabled(msg.source_platform):
            return
        if not self._type_enabled(msg):
            return
        if self.require_peer and msg.peer_id is None:
            logger.debug("[dyf] 未解析对端且 require_peer=true，跳过")
            return
        if not self.global_filter.evaluate(msg):
            logger.debug("[dyf] 全局过滤命中，跳过")
            return
        if self.dedup_enabled and self.cache.seen(self._dedup_key(msg)):
            logger.debug(f"[dyf] 去重跳过: {msg.message_id}")
            return
        if not self.rate.allow(msg.peer_id):
            logger.warning(f"[dyf] 限流跳过: sender={msg.peer_id}")
            return

        targets = self._resolve_targets(msg)
        if not targets:
            logger.info(f"[dyf] 无匹配路由，跳过: type={msg.type} peer={msg.peer_id}")
            return

        chain = self.builder.build_chain(msg)
        if chain is None:
            return

        for target in targets:
            if target in self._in_flight:
                continue
            self._in_flight.add(target)
            try:
                ok, err = await self.sender.send(target, chain)
                self.tracker.add_record(
                    ts=int(time.time()),
                    msg_type=msg.type.value,
                    peer=msg.peer_id,
                    target=target,
                    ok=ok,
                    error=err,
                )
                if ok:
                    logger.info(f"[dyf] 转发成功 -> {target} ({msg.type.value})")
                else:
                    self.cache.add_failed(target, msg.to_dict())
                    logger.warning(f"[dyf] 转发失败入缓存 -> {target}: {err}")
            finally:
                self._in_flight.discard(target)
