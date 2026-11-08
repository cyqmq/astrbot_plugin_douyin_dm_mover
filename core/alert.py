"""AlertService：登录态失效 / 网关异常 → 告警到管理员目标。"""
from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain

from core.model import GatewayEvent


class AlertService:
    def __init__(self, context, alert_target: str = "", alert_only_once: bool = True):
        self.context = context
        self.alert_target = alert_target or ""
        self.alert_only_once = bool(alert_only_once)
        self._sent_auth_alert = False

    async def on_event(self, ev: GatewayEvent) -> None:
        if ev.kind == "auth_failure":
            if self.alert_only_once and self._sent_auth_alert:
                return
            self._sent_auth_alert = True
            await self._push(
                f"⚠️ 抖音登录态失效：{ev.detail or '需要更新 cookie'}\n"
                "请重新登录抖音并更新插件配置中的 douyin_cookies。"
            )
        elif ev.kind == "error":
            await self._push(f"⚠️ 抖音网关异常：{ev.detail}")

    async def _push(self, text: str) -> None:
        if not self.alert_target:
            return
        try:
            await self.context.send_message(self.alert_target, MessageChain([Plain(text)]))
        except Exception as e:
            logger.error(f"[dyf] 告警发送失败: {e}")
