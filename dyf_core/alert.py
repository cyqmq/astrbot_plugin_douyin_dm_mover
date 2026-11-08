"""AlertService：登录态失效 / 网关异常 → 告警到管理员目标。"""
from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Image, Plain

from dyf_core.model import GatewayEvent


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
                f"⚠️ 抖音登录态失效：{ev.detail or '需要重新登录'}\n"
                "请运行 /dyf login 扫码登录，或更新插件配置中的 douyin_cookies。"
            )
        elif ev.kind == "error":
            await self._push(f"⚠️ 抖音网关异常：{ev.detail}")
        elif ev.kind == "mfa":
            await self._push(f"🔐 抖音二次验证：{ev.detail}")
        elif ev.kind == "qr":
            await self._push_qr(ev.detail)
        elif ev.kind in ("login_started", "login_ok", "logout"):
            label = {
                "login_started": "开始扫码登录",
                "login_ok": "登录成功，会话已保存",
                "logout": "已登出并清除会话",
            }[ev.kind]
            await self._push(f"🔑 抖音登录：{label}")

    async def _push(self, text: str) -> None:
        if not self.alert_target:
            return
        try:
            await self.context.send_message(self.alert_target, MessageChain([Plain(text)]))
        except Exception as e:
            logger.error(f"[dyf] 告警发送失败: {e}")

    async def _push_qr(self, url: str) -> None:
        """推送二维码：能取图则发图；否则仅发链接（便于手动打开）。"""
        if not self.alert_target:
            logger.info(f"[dyf] 二维码链接（未配置告警目标，请手动打开）: {url}")
            return
        try:
            chain = MessageChain([Image.fromURL(url)])
            await self.context.send_message(self.alert_target, chain)
        except Exception as e:
            logger.error(f"[dyf] 二维码推送失败: {e}")
            await self._push(f"二维码链接（请打开扫码）：{url}")
