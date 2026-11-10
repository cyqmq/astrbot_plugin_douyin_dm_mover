"""MessageListener：消费 Gateway 消息流/事件流，喂给 ForwardManager。"""
from __future__ import annotations

from dyf_core.forward_manager import ForwardManager
from dyf_gateway.base import MessageGateway


class MessageListener:
    def __init__(self, gateway: MessageGateway, forward_manager: ForwardManager):
        self.gateway = gateway
        self.forward_manager = forward_manager

    async def consume_messages(self) -> None:
        async for msg in self.gateway.stream():
            try:
                # 视频卡补详情（to_thread）在此执行：接收线程只入队不阻塞，
                # 单条视频最多 ~8s 延迟，不影响后续帧/心跳/断线检测。
                enrich = getattr(self.gateway, "enrich_video", None)
                if enrich is not None:
                    await enrich(msg)
                await self.forward_manager.handle(msg)
            except Exception:
                # 单条消息处理失败不拖垮消费循环
                from astrbot.api import logger

                logger.exception("[dyf] 处理消息异常")

    async def consume_events(self) -> None:
        async for ev in self.gateway.events():
            try:
                await self.forward_manager.alert.on_event(ev)
            except Exception:
                from astrbot.api import logger

                logger.exception("[dyf] 处理事件异常")
