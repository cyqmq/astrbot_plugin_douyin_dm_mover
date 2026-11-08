"""RetryManager：周期重试失败发送的消息。"""
from __future__ import annotations

import asyncio

from astrbot.api import logger

from core.cache_manager import CacheManager
from core.message_builder import MessageBuilder
from core.message_sender import MessageSender
from core.model import InboundMessage


class RetryManager:
    def __init__(
        self,
        cache: CacheManager,
        sender: MessageSender,
        builder: MessageBuilder,
        interval_seconds: int = 1800,
        enabled: bool = True,
    ):
        self.cache = cache
        self.sender = sender
        self.builder = builder
        self.interval_seconds = max(60, int(interval_seconds or 1800))
        self.enabled = enabled

    async def run(self) -> None:
        if not self.enabled:
            return
        while True:
            await asyncio.sleep(self.interval_seconds)
            try:
                await self.retry_failed()
            except Exception as e:
                logger.error(f"[dyf] 周期重试失败: {e}")

    async def retry_failed(self) -> None:
        for entry in self.cache.get_failed():
            target = entry.get("target", "")
            data = entry.get("msg", {})
            if not target or not data:
                continue
            try:
                msg = InboundMessage.from_dict(data)
            except TypeError:
                continue
            chain = self.builder.build_chain(msg)
            if chain is None:
                continue
            ok, _ = await self.sender.send(target, chain)
            if ok:
                self.cache.remove_failed(target, msg.message_id)
                logger.info(f"[dyf] 重试发送成功: {target}")
