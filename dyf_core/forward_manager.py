"""ForwardManager：转发编排。流程见 DESIGN.md §6.3。"""
from __future__ import annotations

import hashlib
import time

from astrbot.api import logger

from dyf_config import DEFAULT_DATA_DIR
from dyf_core.alert import AlertService
from dyf_core.cache_manager import CacheManager
from dyf_core.card import render_card_safe
from dyf_core.message_builder import MessageBuilder
from dyf_core.message_sender import MessageSender, is_qq_official_group_target
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
        self.data_dir = config.get("_data_dir") or DEFAULT_DATA_DIR
        self._migrate_templates(config)

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
        # qq_official 仅群聊（私聊主动消息受限）：配置加载时剔除非群聊 UMO
        for k in ("default_target_group", "alert_target"):
            v = str(config.get(k, "") or "")
            if v and not is_qq_official_group_target(v):
                logger.warning(
                    f"[dyf] {k} 含 qq_official 非群聊 UMO，已忽略（官方机器人私聊受限）"
                )
                config[k] = ""
        self.default_target_group = str(config.get("default_target_group", "") or "")
        self.builder = MessageBuilder(
            header_template=config.get("header_template", ""),
            include_link=config.get("include_link", True),
            max_length=config.get("max_message_length", 1000),
        )
        self.sender = MessageSender(
            context,
            qq_adapter_id=config.get("qq_adapter_id", "aiocqhttp"),
            markdown_enabled=bool(config.get("markdown_enabled", True)),
        )
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

    @staticmethod
    def _migrate_templates(config: dict) -> None:
        version = int(config.get("template_version") or 0)
        if version >= 1:
            return
        legacy = str(config.get("header_template") or "").strip()
        markdown = bool(config.get("markdown_enabled", True))
        existing = config.get("templates")
        if not existing and legacy:
            config["templates"] = [
                {
                    "id": "default",
                    "name": "默认模板",
                    "content": legacy,
                    "markdown": markdown,
                    "for_media": False,
                }
            ]
        config["template_version"] = 1
        logger.info("[dyf] 模板结构已迁移至 v1（header_template → templates[0]）")

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
        # 图片合集：图集按分享 id 去重（抖音推两帧、media_urls 可能未填充）；
        # 否则两帧 media_urls 相同用内容指纹
        if msg.type == MessageType.IMAGE:
            si = str((msg.card or {}).get("share_item_id") or "")
            if si:
                return f"album:{si}"
            if msg.media_urls:
                return "img:" + hashlib.md5(
                    "|".join(sorted(str(u) for u in msg.media_urls)).encode()
                ).hexdigest()
        if msg.message_id:
            return msg.message_id
        # 会话聚合：群聊按群聚合、单聊按对端聚合（群内多成员不被当多来源）
        conv = msg.group_id or msg.peer_id or ""
        return hashlib.md5(
            f"{msg.source_platform}:{conv}:{msg.type}:{msg.text}".encode()
        ).hexdigest()

    def _resolve_targets(self, msg: InboundMessage) -> list[tuple[str, str]]:
        hits = self.router.resolve(msg)
        if hits:
            return hits
        if self.default_target_group:
            # 兼容 UMO（含冒号，如 aiocqhttp:GroupMessage:123456）/纯群号/qq:group
            origin, _ = self.sender.normalize_target(self.default_target_group)
            if origin:
                return [("default", origin)]
        return []

    async def handle(self, msg: InboundMessage) -> None:
        if msg.is_outgoing:
            return
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
        # 去重后才记录发石者：抖音推两帧（视频卡/图集，server_message_id 不同）
        # 第二帧被去重拦，不应计入明细（否则明细两份、转发一份）
        self.tracker.add_sender(msg)
        if not self.rate.allow(msg.group_id or msg.peer_id):
            logger.warning(f"[dyf] 限流跳过: conv={msg.group_id or msg.peer_id}")
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
            # qq_official 仅群聊：发送前跳过私聊目标（官方机器人私聊主动消息受限）
            if not is_qq_official_group_target(target):
                logger.warning(f"[dyf] 跳过 qq_official 私聊目标: {target}")
                continue
            logger.info(f"[dyf] 命中路由 {name} -> {target}")
            if target in self._in_flight:
                continue
            self._in_flight.add(target)
            target_ok = 0
            target_fail = 0
            target_errors: list[str] = []
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
                    if ok:
                        ok_count += 1
                        target_ok += 1
                        logger.info(
                            f"[dyf] 转发成功 -> {target} ({msg.type.value})"
                        )
                    else:
                        fail_count += 1
                        target_fail += 1
                        target_errors.append(err)
                        fail_errors.append(f"{target}: {err}")
                        self.cache.add_failed(target, msg.to_dict())
                        logger.warning(
                            f"[dyf] 转发失败入缓存 -> {target}: {err}"
                        )
                    if not ok:
                        break  # 本批失败，后续批次不再发（避免重发部分成功）
                # 每 target 一条搬运记录（合并批结果；图集分批不产生多条）
                self.tracker.add_record(
                    ts=int(time.time()),
                    msg_type=msg.type.value,
                    peer=msg.peer_id,
                    target=target,
                    ok=target_ok > 0,
                    error="; ".join(target_errors),
                )
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
