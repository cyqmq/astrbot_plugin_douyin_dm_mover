"""ForwardManager：转发编排。流程见 DESIGN.md §6.3。"""
from __future__ import annotations

import hashlib
import time

from astrbot.api import logger

from dyf_core.alert import AlertService
from dyf_core.cache_manager import CacheManager
from dyf_core.card import render_card_safe
from dyf_core.message_builder import MessageBuilder
from dyf_core.message_sender import MessageSender
from dyf_core.model import InboundMessage, MessageType
from dyf_core.ratelimit import RateLimiter
from dyf_core.retry_manager import RetryManager
from dyf_core.router import RouteResolver
from dyf_core.rules import ComposeRule, KeywordFilterRule
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
            max_attempts=config.get("retry_max_attempts", 5),
        )
        self.card_enabled = bool(config.get("card_enabled", True))
        self.max_media_per_batch = int(config.get("max_media_per_batch", 9) or 0)
        self.alert = AlertService(
            context,
            alert_target=config.get("alert_target", ""),
            alert_only_once=config.get("alert_only_once", True),
        )
        self.require_peer = bool(config.get("require_peer", False))
        self.global_filter = ComposeRule(
            [
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
        # 视频卡：抖音 WS 同一作品推两帧（server_message_id 不同、conv 一标准一纯数字），
        # 用作品 itemId 去重（同视频窗口内只转一次）
        if msg.type == MessageType.VIDEO_CARD and msg.card:
            item = str(msg.card.get("itemId") or msg.card.get("item_id") or "")
            if item:
                return f"video:{item}"
        # 图片合集：两帧 media_urls 相同，内容指纹去重
        if msg.type == MessageType.IMAGE and msg.media_urls:
            return "img:" + hashlib.md5(
                "|".join(sorted(str(u) for u in msg.media_urls)).encode()
            ).hexdigest()
        if msg.message_id:
            return msg.message_id
        return hashlib.md5(
            f"{msg.source_platform}:{msg.peer_id}:{msg.type}:{msg.text}".encode()
        ).hexdigest()

    def _resolve_targets(self, msg: InboundMessage) -> list[tuple[str, str]]:
        hits = self.router.resolve(msg)
        if hits:
            return hits
        if self.default_target_group:
            return [("default", self.sender.build_origin(self.default_target_group))]
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

        card_image = None
        if self.card_enabled and msg.type in (MessageType.VIDEO_CARD, MessageType.IMAGE):
            import asyncio

            card_image = await asyncio.to_thread(render_card_safe, msg)

        ok_count = 0
        fail_count = 0
        fail_errors: list[str] = []
        # media 分批：每批 max_media_per_batch 个（0=不分批）；正文/卡片只进第一批
        batch = self.max_media_per_batch
        batches: list[tuple[list[str], bool]] = []
        if batch > 0 and len(msg.media_urls) > batch:
            for i in range(0, len(msg.media_urls), batch):
                batches.append((msg.media_urls[i : i + batch], i == 0))
        else:
            batches.append((list(msg.media_urls), True))
        for name, target in targets:
            logger.info(f"[dyf] 命中路由 {name} -> {target}")
            if target in self._in_flight:
                continue
            self._in_flight.add(target)
            try:
                for media_slice, is_first in batches:
                    chain = self.builder.build_chain(
                        msg,
                        card_image if is_first else None,
                        media_slice,
                        with_text=is_first,
                    )
                    if chain is None:
                        continue
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
                        ok_count += 1
                        logger.info(
                            f"[dyf] 转发成功 -> {target} ({msg.type.value})"
                        )
                    else:
                        fail_count += 1
                        fail_errors.append(f"{target}: {err}")
                        self.cache.add_failed(target, msg.to_dict())
                        logger.warning(
                            f"[dyf] 转发失败入缓存 -> {target}: {err}"
                        )
                    if not ok:
                        break  # 本批失败，后续批次不再发（避免重发部分成功）
            finally:
                self._in_flight.discard(target)
        # delivery 结果收口：至少一成功判定，全失败才告警（部分成功不误报）
        if ok_count == 0 and fail_count:
            summary = "; ".join(fail_errors)
            logger.warning(
                f"[dyf] 全部转发失败 {fail_count}/{len(targets)}: {summary}"
            )
            await self.alert.notify(
                f"抖音转发全部失败 {fail_count}/{len(targets)}: {summary}"
            )
        elif fail_count:
            logger.info(f"[dyf] 部分转发成功 {ok_count}/{len(targets)}，失败 {fail_count}")
