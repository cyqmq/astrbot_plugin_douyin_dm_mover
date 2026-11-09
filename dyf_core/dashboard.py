"""DashboardApi：向 AstrBot WebUI 注册插件可视化 API。

视图（views/status/index.html）通过 bridge SDK 调用这些接口：
- status：连接状态/配置摘要
- senders：最近给 bot 发过消息的人
- records：最近搬运记录
- qrcode：当前登录二维码（PNG data URL）
- qrcode/refresh：触发刷新登录二维码（后台任务，不阻塞请求）
- login / logout / records/clear
"""
from __future__ import annotations

import asyncio
import base64
import io
import time

import qrcode

from dyf_core.logs import LogRing


def _qr_data_url(content: str) -> str | None:
    """把二维码内容渲染成 PNG data URL；失败返回 None。"""
    try:
        img = qrcode.make(content)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception:
        return None


class DashboardApi:
    def __init__(self, context, gateway, forward_manager, logring: LogRing | None = None):
        self.context = context
        self.gateway = gateway
        self.fm = forward_manager
        self.logring = logring or LogRing()
        self._last_refresh_ts = 0.0

    # ---- 注册 ----
    def register(self) -> None:
        reg = self.context.register_web_api
        reg("douyin_dm_mover/status", self.status, ["GET"], "dyf 连接状态")
        reg("douyin_dm_mover/senders", self.senders, ["GET"], "dyf 最近发石者")
        reg("douyin_dm_mover/records", self.records, ["GET"], "dyf 最近搬运记录")
        reg("douyin_dm_mover/qrcode", self.qrcode, ["GET"], "dyf 登录二维码")
        reg("douyin_dm_mover/qrcode/refresh", self.qrcode_refresh, ["POST"], "dyf 刷新登录二维码")
        reg("douyin_dm_mover/login", self.login, ["POST"], "dyf 开始登录")
        reg("douyin_dm_mover/logout", self.logout, ["POST"], "dyf 登出")
        reg("douyin_dm_mover/records/clear", self.clear_records, ["POST"], "dyf 清空搬运记录")
        reg("douyin_dm_mover/logs", self.logs, ["GET"], "dyf 运行日志")
        reg("douyin_dm_mover/logs/clear", self.clear_logs, ["POST"], "dyf 清空日志")

    # ---- 接口实现 ----
    async def status(self):
        fm = self.fm
        cfg = fm.config
        sources = cfg.get("sources") or {}
        src = sources.get("douyin", {}) if isinstance(sources, dict) else {}
        if not isinstance(src, dict):
            src = {}
        return {
            "auth_state": self.gateway.auth_state.value,
            "login_in_progress": bool(getattr(self.gateway, "login_in_progress", False)),
            "self_uid": self.gateway.self_uid,
            "gateway_mode": str(cfg.get("gateway_mode") or "inprocess"),
            "douyin_enabled": bool(src.get("enabled", True)),
            "routes": len(fm.router.routes),
            "default_target_group": str(fm.default_target_group or ""),
            "dedup": bool(fm.dedup_enabled),
            "rate_limit_global": bool(cfg.get("rate_limit_global_enabled", True)),
            "retry_enabled": bool(cfg.get("retry_enabled", True)),
            "failed_cache": len(fm.cache.get_failed()),
            "alert_target": str(cfg.get("alert_target", "") or ""),
            "mfa_mode": str(cfg.get("mfa_mode") or "auto_sms"),
            "senders_count": len(fm.tracker.senders()),
            "records_count": len(fm.tracker.records()),
        }

    async def senders(self):
        return {"senders": self.fm.tracker.senders()}

    async def records(self):
        return {"records": self.fm.tracker.records()}

    async def qrcode(self):
        content = self.gateway.last_qr_content
        if not content:
            return {"qr": None, "detail": "尚未生成二维码，请点击「刷新登录二维码」"}
        if content.startswith("data:image"):
            return {"qr": content, "detail": "ok"}
        return {"qr": _qr_data_url(content), "detail": "ok"}

    async def qrcode_refresh(self):
        now = time.time()
        if now - self._last_refresh_ts < 2:
            return {"ok": False, "detail": "请求过于频繁，请稍候"}
        self._last_refresh_ts = now
        self._kick_login()
        return {"ok": True, "detail": "已触发登录，二维码稍后出现"}

    async def login(self):
        self._kick_login()
        return {"ok": True, "detail": "已触发登录"}

    async def logout(self):
        ok = await self.gateway.logout()
        return {"ok": ok, "detail": "已登出并清除会话" if ok else "当前未登录，无需登出"}

    async def clear_records(self):
        self.fm.tracker.clear()
        return {"ok": True, "detail": "已清空"}

    async def logs(self):
        return {"logs": self.logring.entries()}

    async def clear_logs(self):
        self.logring.clear()
        return {"ok": True, "detail": "已清空"}

    def _kick_login(self) -> None:
        """后台启动扫码登录，不阻塞请求；二维码经 qrcode 接口轮询获取。"""
        timeout = int(self.fm.config.get("login_timeout", 300))
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        asyncio.create_task(self.gateway.login(timeout))
