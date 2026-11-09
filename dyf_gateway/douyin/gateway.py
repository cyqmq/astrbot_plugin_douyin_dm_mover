"""DouyinGateway：MessageGateway 的 Douyin 实现（默认 inprocess 线程模式）。"""
from __future__ import annotations

import asyncio
import os
import threading
import time
from collections.abc import AsyncIterator

from astrbot.api import logger

from dyf_core.model import AuthState, GatewayEvent, InboundMessage

from ..base import MessageGateway
from .converter import DouyinConverter
from .detector import AuthFailureDetector
from .device import resolve_device_id
from .login.flow import LoginFlow
from .login.mfa import MfaHandler
from .login.waiter import CodeWaiter
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
        self._last_qr_content: str | None = None
        self._last_frame_ts: float | None = None
        self._stopping = False
        self._watchdog_task: asyncio.Task | None = None
        self._device_id = resolve_device_id(config, self._auth, self._data_dir)
        # ---- 登录（扫码 + 会话持久化 + 2046 MFA）----
        self._mfa_mode = config.get("mfa_mode") or "auto_sms"
        self._code_waiter = CodeWaiter(self._mfa_mode, config.get("login_mfa_timeout", 300))
        self._mfa = MfaHandler(self._mfa_mode, alert=self._mfa_alert, code_source=self._code_waiter.code_source)
        self._login_flow = LoginFlow(
            self._data_dir,
            mfa_handler=self._mfa,
            on_qrcode=self._on_qr,
            on_log=self._log_login,
        )
        self._login_task: asyncio.Task | None = None
        self._login_lock = threading.Lock()

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
        self._apply_session_or_config()
        if not self._auth.sessionid:
            self._emit_event(
                GatewayEvent(
                    "auth_failure",
                    "缺少登录态（无 sessionid）。请运行 /dyf login 扫码登录，"
                    "或填写 douyin_cookies",
                )
            )
            self._state = AuthState.EXPIRED
            # 首次无会话且未配置 cookie 时自动发起扫码登录（自动出码，无需手动点刷新）
            if not (self._config.get("douyin_cookies") or "").strip():
                logger.info("[dyf] 无登录会话，自动发起扫码登录")
                self._login_task = asyncio.create_task(self.login())
            return
        self._start_receiver()
        self._emit_event(GatewayEvent("started", "Douyin gateway started"))
        self._watchdog_task = asyncio.create_task(self._watchdog())
        logger.info(f"[dyf] DouyinGateway 已启动 (device_id={self._device_id})")

    def _apply_session_or_config(self) -> None:
        """会话优先：有有效 session 用其 cookie/uid/device；否则用配置 cookie。"""
        data = self._login_flow.session.load()
        if data and self._login_flow.session.has_valid():
            cookie_str = data.get("cookie_str") or ""
            self._auth = DouyinAuth(
                cookie_str=cookie_str,
                web_protect=self._config.get("douyin_web_protect", ""),
                keys=self._config.get("douyin_keys", ""),
            )
            if data.get("uid"):
                self._self_uid = int(data["uid"])
                self._resolver.cache(self._self_uid)
            else:
                self._self_uid = self._resolver.resolve(self._auth)
            if data.get("device_id"):
                self._device_id = str(data["device_id"])
            logger.info("[dyf] 使用已保存的登录会话")
        else:
            self._self_uid = self._resolver.resolve(self._auth)
        self._auth.uid = self._self_uid
        if self._self_uid is None:
            logger.warning("[dyf] self_uid 未解析，对端判定将受限")
        else:
            logger.info(f"[dyf] self_uid = {self._self_uid}")

    def _start_receiver(self) -> None:
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

    def _stop_receiver(self) -> None:
        if self._receiver:
            self._receiver.stop()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._receiver = None
        self._thread = None

    # ---- 登录 / 登出 / MFA ----
    async def login(self, timeout: int = 300) -> None:
        """扫码登录（阻塞 qrcode_login 放后台线程）。登录成功自动重启接收端。"""
        if self._login_task and not self._login_task.done():
            self._emit_event(GatewayEvent("error", "已有登录进行中"))
            return
        if not self._login_lock.acquire(blocking=False):
            self._emit_event(GatewayEvent("error", "已有登录进行中"))
            return
        try:
            self._state = AuthState.UNKNOWN
            self._emit_event(GatewayEvent("login_started", "开始扫码登录"))
            logger.info("[dyf] 扫码登录已启动，等待二维码")
            loop = asyncio.get_running_loop()

            def _run():
                return self._login_flow.qrcode_login(timeout=timeout)

            auth = await loop.run_in_executor(None, _run)
            self._stop_receiver()
            self._login_flow.session.save(auth)
            self._auth = DouyinAuth(
                cookie_str="; ".join(f"{k}={v}" for k, v in (auth.cookie or {}).items()),
                web_protect=self._config.get("douyin_web_protect", ""),
                keys=self._config.get("douyin_keys", ""),
            )
            if getattr(auth, "uid", None):
                self._self_uid = int(auth.uid)
                self._resolver.cache(self._self_uid)
            dev = (auth.cookie or {}).get("device_id") or getattr(auth, "device_id", None)
            if dev:
                self._device_id = str(dev)
            self._auth.uid = self._self_uid
            self._state = AuthState.OK
            self._emit_event(GatewayEvent("login_ok", "登录成功，会话已保存"))
            if self._auth.sessionid:
                self._start_receiver()
                self._emit_event(GatewayEvent("started", "接收端已用新会话重启"))
            else:
                self._emit_event(GatewayEvent("error", "登录成功但无 sessionid"))
        except Exception as e:
            self._emit_event(GatewayEvent("error", f"登录失败: {e}"))
            logger.error(f"[dyf] 登录失败: {e}")
        finally:
            self._login_lock.release()

    async def logout(self) -> None:
        self._stop_receiver()
        self._login_flow.session.clear()
        self._state = AuthState.UNKNOWN
        self._emit_event(GatewayEvent("logout", "已登出并清除会话"))
        logger.info("[dyf] 已登出")

    def trigger_mfa_send(self) -> None:
        self._code_waiter.trigger_send()

    def submit_mfa_code(self, code: str) -> None:
        self._code_waiter.submit(code)

    def _on_qr(self, url: str) -> None:
        self._last_qr_content = url
        self._emit_event(GatewayEvent("qr", url))
        logger.info("[dyf] 登录二维码已生成，请用抖音扫码登录")

    @property
    def last_qr_content(self) -> str | None:
        """最近一次登录二维码内容（扫码字符串）。"""
        return self._last_qr_content

    def _mfa_alert(self, text: str) -> None:
        self._emit_event(GatewayEvent("mfa", text))
        logger.warning(f"[dyf] {text}")

    def _log_login(self, text: str) -> None:
        logger.info(f"[dyf] {text}")


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
        if self._login_task:
            self._login_task.cancel()
        self._stop_receiver()
        self._emit_event(GatewayEvent("stopped", "Douyin gateway stopped"))
        logger.info("[dyf] DouyinGateway 已停止")
