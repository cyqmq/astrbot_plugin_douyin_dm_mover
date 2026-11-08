"""DouyinGateway：MessageGateway 的 Douyin 实现（默认 inprocess 线程模式）。"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from collections.abc import AsyncIterator

from astrbot.api import logger

from core.model import AuthState, GatewayEvent, InboundMessage

from ..base import MessageGateway
from .converter import DouyinConverter
from .detector import AuthFailureDetector
from .device import resolve_device_id
from .self_uid import SelfIdentityResolver
from .vendored.auth import DouyinAuth
from .vendored.receiver import DouyinReceiver

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DouyinGateway(MessageGateway):
    def __init__(self, config: dict):
        self._config = config
        self._data_dir = config.get("_data_dir") or os.path.join("data", "dyf")
        os.makedirs(self._data_dir, exist_ok=True)
        self._auth = DouyinAuth(
            cookie_str=config.get("douyin_cookies", ""),
            web_protect=config.get("douyin_web_protect", ""),
            keys=config.get("douyin_keys", ""),
        )
        self._resolver = SelfIdentityResolver(
            self._data_dir, config.get("self_uid")
        )
        self._detector = AuthFailureDetector(
            close_codes=self._parse_int_list(config.get("auth_failure_close_codes")),
            keywords=self._parse_list(config.get("auth_failure_keywords")),
            watchdog_minutes=config.get("auth_watchdog_minutes", 30),
        )
        self._self_uid: int | None = None
        self._converter = DouyinConverter(lambda: self._self_uid)
        self._receiver: DouyinReceiver | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._msg_queue: asyncio.Queue = asyncio.Queue()
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._state = AuthState.UNKNOWN
        self._last_frame_ts: float | None = None
        self._stopping = False
        self._watchdog_task: asyncio.Task | None = None
        self._device_id = resolve_device_id(config, self._auth, self._data_dir)

    @staticmethod
    def _parse_list(value) -> list[str]:
        if isinstance(value, list):
            return [str(x) for x in value if str(x).strip()]
        if isinstance(value, str):
            return [x.strip() for x in value.split(",") if x.strip()]
        return []

    @staticmethod
    def _parse_int_list(value) -> list[int]:
        out = []
        for x in DouyinGateway._parse_list(value):
            try:
                out.append(int(x))
            except ValueError:
                pass
        return out

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._self_uid = self._resolver.resolve(self._auth)
        self._auth.uid = self._self_uid
        if self._self_uid is None:
            logger.warning("[dyf] self_uid 未解析，对端判定将受限（require_peer 配置生效）")
        else:
            logger.info(f"[dyf] self_uid = {self._self_uid}")

        if not self._auth.sessionid:
            self._emit_event(GatewayEvent("auth_failure", "缺少 sessionid cookie，无法建立连接"))
            self._state = AuthState.EXPIRED
            return

        self._receiver = DouyinReceiver(
            sessionid=self._auth.sessionid,
            device_id=self._device_id,
            cookie_str=self._auth.cookie_str,
            ua=self._config.get("ua") or _DEFAULT_UA,
            on_raw_message=self._on_raw_message,
            on_status=self._on_status,
            auto_reconnect=True,
        )
        self._thread = threading.Thread(
            target=self._receiver.start_blocking, name="dyf-douyin-ws", daemon=True
        )
        self._thread.start()
        self._emit_event(GatewayEvent("started", "Douyin gateway started"))
        self._watchdog_task = asyncio.create_task(self._watchdog())
        logger.info(f"[dyf] DouyinGateway 已启动 (device_id={self._device_id})")

    # ---- 线程回调（经 call_soon_threadsafe 切回事件循环） ----
    def _on_raw_message(self, raw: dict) -> None:
        self._last_frame_ts = time.time()
        msg = self._converter.convert(raw)
        if msg is None:
            return
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._msg_queue.put_nowait, msg)

    def _on_status(self, kind: str, detail: str = "") -> None:
        if kind in ("error", "close") and (
            self._detector.check_error(detail) or self._detector.check_text(detail)
        ):
            self._mark_auth_expired()
            return
        if kind == "reconnect":
            self._emit_event(GatewayEvent("reconnect", detail))
        elif kind == "close":
            self._emit_event(GatewayEvent("disconnect", detail))
        elif kind == "error":
            self._emit_event(GatewayEvent("error", detail))

    def _mark_auth_expired(self) -> None:
        if self._state == AuthState.EXPIRED:
            return
        self._state = AuthState.EXPIRED
        self._emit_event(GatewayEvent("auth_failure", "登录态失效，停止自动重连"))
        logger.error("[dyf] 检测到登录态失效，停止自动重连并告警")
        if self._receiver:
            self._receiver.auto_reconnect = False

    def _emit_event(self, ev: GatewayEvent) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._event_queue.put_nowait, ev)
        else:
            # start 前/停止后的同步兜底：直接入队
            try:
                self._event_queue.put_nowait(ev)
            except Exception:
                pass

    async def _watchdog(self) -> None:
        interval = 60
        while not self._stopping:
            await asyncio.sleep(interval)
            if self._state == AuthState.EXPIRED:
                continue
            if self._detector.check_silence(self._last_frame_ts):
                self._emit_event(
                    GatewayEvent(
                        "error",
                        f"静默 {self._detector.watchdog_seconds // 60} 分钟无帧，疑似连接僵死",
                    )
                )

    # ---- MessageGateway 接口 ----
    def stream(self) -> AsyncIterator[InboundMessage]:
        async def _gen():
            while not self._stopping:
                msg = await self._msg_queue.get()
                yield msg

        return _gen()

    def events(self) -> AsyncIterator[GatewayEvent]:
        async def _gen():
            while True:
                ev = await self._event_queue.get()
                yield ev

        return _gen()

    @property
    def auth_state(self) -> AuthState:
        return self._state

    @property
    def self_uid(self) -> int | None:
        return self._self_uid

    def set_self_uid(self, uid: int | None) -> None:
        """/dyf uid 命令写入：更新解析器缓存与运行态。"""
        self._resolver.cache(uid)
        self._self_uid = self._resolver.resolve(self._auth)

    async def stop(self) -> None:
        self._stopping = True
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._receiver:
            self._receiver.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._emit_event(GatewayEvent("stopped", "Douyin gateway stopped"))
        logger.info("[dyf] DouyinGateway 已停止")
