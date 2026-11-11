"""DouyinGateway：MessageGateway 的 Douyin 实现（默认 inprocess 线程模式）。"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from collections.abc import AsyncIterator

from astrbot.api import logger

from dyf_config import DEFAULT_DATA_DIR
from dyf_core.model import AuthState, GatewayEvent, InboundMessage, MessageType

from ..base import MessageGateway
from .converter import DouyinConverter
from .detector import AuthFailureDetector
from .device import resolve_device_id
from .login.alemonjs_py import DouyinHttpPy
from .login.alemonjs_py_login import AlemonsPyLogin
from .login.flow import LoginFlow
from .login.mfa import MfaHandler
from .login.waiter import CodeWaiter
from .self_uid import SelfIdentityResolver
from .vendored.auth import DouyinAuth
from .vendored.receiver import DouyinReceiver
from .video import fetch_aweme_detail

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class DouyinGateway(MessageGateway):
    def __init__(self, config: dict, config_obj=None):
        self._config = config
        self._config_obj = config_obj
        self._data_dir = config.get("_data_dir") or DEFAULT_DATA_DIR
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
        self._converter = DouyinConverter(lambda: self._self_uid, self._lookup_nickname)
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
        # ---- 登录后端：默认纯 Python（@alemonjs/douyin 移植）；可选 douyin_spider ----
        self._login_backend = (config.get("login_backend") or "alemonjs").lower()
        self._alemonjs_py = AlemonsPyLogin(
            on_qrcode=self._on_qr_alemonjs,
            on_log=self._log_login,
            code_waiter=self._code_waiter,
            data_dir=self._data_dir,
        )
        self._login_task: asyncio.Task | None = None
        self._login_lock = threading.Lock()
        self._profile: dict = {}          # 账户档案 {uid,nickname,avatar}（登录后拉取）
        self._profile_ts: float = 0.0     # 档案缓存时间戳（TTL 300s）
        self._friends: list[dict] = []    # 好友列表缓存（familiar-list 全量）
        self._friends_ts: float = 0.0     # 好友缓存时间戳（TTL 300s）
        self._http: DouyinHttpPy | None = None  # 视频详情/好友列表 HTTP（懒建，随会话 Cookie）

    def _lookup_nickname(self, uid) -> str:
        """发送者昵称：查好友缓存（{uid,nickname}）；找不到返回空（调用方回退 peer_id）。"""
        if uid in (None, ""):
            return ""
        try:
            suid = str(uid)
            for f in self._friends or []:
                if str(f.get("uid") or f.get("user_id") or "") == suid:
                    return str(f.get("nickname") or f.get("nick_name") or "")
        except Exception:
            return ""
        return ""

    # ---- 好友缓存持久化（重载后内存清空，用文件缓存避免每次全量重拉） ----
    @property
    def _friends_cache_file(self) -> str:
        return os.path.join(self._data_dir, "friends_cache.json")

    def _load_friends_cache(self) -> tuple[list[dict], float]:
        """读落盘好友缓存；无/损坏返回 ([], 0)。"""
        try:
            with open(self._friends_cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return list(data.get("friends") or []), float(data.get("ts") or 0)
        except Exception:
            return [], 0.0

    def _store_friends_cache(self, friends: list[dict], ts: float) -> None:
        try:
            os.makedirs(self._data_dir, exist_ok=True)
            with open(self._friends_cache_file, "w", encoding="utf-8") as f:
                json.dump({"ts": ts, "friends": friends}, f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"[dyf] 好友缓存写入失败: {e}")

    def _lookup_friend_name(self, uid: str) -> str | None:
        """按 uid 查好友缓存昵称（remark_name 优先，fallback nickname）。"""
        friends, _ = self._load_friends_cache()
        for f in friends:
            if str(f.get("uid")) == str(uid):
                return str(f.get("remark_name") or f.get("nickname") or "") or None
        return None

    # ---- 账户档案缓存持久化（重载后读文件，避免每次重新拉取） ----
    @property
    def _profile_cache_file(self) -> str:
        return os.path.join(self._data_dir, "profile_cache.json")

    def _load_profile_cache(self) -> tuple[dict, float]:
        try:
            with open(self._profile_cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            prof = data.get("profile") or {}
            if not isinstance(prof, dict):
                prof = {}
            return prof, float(data.get("ts") or 0)
        except Exception:
            return {}, 0.0

    def _store_profile_cache(self, profile: dict, ts: float) -> None:
        try:
            os.makedirs(self._data_dir, exist_ok=True)
            with open(self._profile_cache_file, "w", encoding="utf-8") as f:
                json.dump({"ts": ts, "profile": profile}, f, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"[dyf] 档案缓存写入失败: {e}")

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
        await self._apply_session_or_config()
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
        # 有有效已保存会话：乐观置为已登录（避免更新/重启后长期显示「未知」）；
        # 若连接实际失败，_on_status -> _mark_auth_expired 会降级为 EXPIRED。
        self._state = AuthState.OK
        self._emit_event(GatewayEvent("started", "Douyin gateway started"))
        self._watchdog_task = asyncio.create_task(self._watchdog())
        logger.info(f"[dyf] DouyinGateway 已启动 (device_id={self._device_id})")

    async def _apply_session_or_config(self) -> None:
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
                self._self_uid = await self._resolver.resolve_async(self._auth)
            if data.get("device_id"):
                self._device_id = str(data["device_id"])
            logger.info("[dyf] 使用已保存的登录会话")
        else:
            self._self_uid = await self._resolver.resolve_async(self._auth)
        self._auth.uid = self._self_uid
        if self._self_uid is None:
            logger.warning("[dyf] self_uid 未解析，对端判定将受限")
        else:
            logger.info(f"[dyf] self_uid = {self._self_uid}")

    def _start_receiver(self) -> None:
        self._last_frame_ts = time.time()
        self._receiver = DouyinReceiver(
            sessionid=self._auth.sessionid,
            device_id=self._device_id,
            cookie_str=self._auth.cookie_str,
            ua=self._config.get("ua") or _DEFAULT_UA,
            on_raw_message=self._on_raw_message,
            on_status=self._on_status,
            on_frame=self._on_any_frame,
            auto_reconnect=True,
        )
        self._thread = threading.Thread(
            target=self._receiver.start_blocking, name="dyf-douyin-ws", daemon=True
        )
        self._thread.start()

    async def _stop_receiver(self) -> None:
        if self._receiver:
            self._receiver.stop()
        thread = self._thread
        if thread and thread.is_alive():
            # join 移出事件循环：reload 期间同步阻塞会卡住 sm.reload + _pm_lock
            await asyncio.to_thread(thread.join, 5)
        self._receiver = None
        self._thread = None

    # ---- 登录 / 登出 / MFA ----
    async def login(self, timeout: int = 300) -> None:
        """扫码登录。默认纯 Python 后端；可回退 Node 桥接 / douyin_spider。"""
        if not self._login_lock.acquire(blocking=False):
            self._emit_event(GatewayEvent("error", "已有登录进行中"))
            return
        try:
            self._state = AuthState.UNKNOWN
            self._emit_event(GatewayEvent("login_started", "开始扫码登录"))
            logger.info("[dyf] 扫码登录已启动，等待二维码")
            backend = self._login_backend
            cookie_str = ""
            uid = None
            dev = None
            auth = None
            saved_backend = None
            if backend in ("alemonjs", "alemonjs_py", "python"):
                logger.info("[dyf] 登录后端：@alemonjs/douyin 纯 Python 移植")
                result = await self._alemonjs_py.qrcode_login_async(timeout=timeout)
                saved_backend = "alemonjs"
                cookie_str = result.cookie_str
                uid = int(result.uid) if result.uid else None
                dev = result.device_id
                auth = DouyinAuth(
                    cookie_str=cookie_str,
                    web_protect=self._config.get("douyin_web_protect", ""),
                    keys=self._config.get("douyin_keys", ""),
                )
                auth.uid = uid
                if dev:
                    auth.device_id = str(dev)
                auth._login_backend = "alemonjs"
            else:
                loop = asyncio.get_running_loop()
                auth = await loop.run_in_executor(
                    None, lambda: self._login_flow.qrcode_login(timeout=timeout)
                )
                cookie_str = "; ".join(
                    f"{k}={v}" for k, v in (auth.cookie or {}).items()
                )
                uid = getattr(auth, "uid", None)
                dev = (auth.cookie or {}).get("device_id") or getattr(auth, "device_id", None)
            await self._stop_receiver()
            self._login_flow.session.save(auth, backend=saved_backend)
            self._auth = DouyinAuth(
                cookie_str=cookie_str,
                web_protect=self._config.get("douyin_web_protect", ""),
                keys=self._config.get("douyin_keys", ""),
            )
            if uid:
                self._self_uid = int(uid)
                self._resolver.cache(self._self_uid)
            if dev:
                self._device_id = str(dev)
            self._auth.uid = self._self_uid
            # 账户档案（昵称/头像）：仅纯 Python 登录会带回，存为登录态附加信息
            if getattr(result, "profile", None):
                self._profile = result.profile
                self._friends = []
                self._friends_ts = 0.0
            # 登录成功：把 cookie/uid/device 写回 AstrBot 配置并落盘，确保配置页可见
            # 且配置层有兜底（session.json 亦在 data/plugin_data 下，更新插件不丢）。
            self._persist_login_config(cookie_str, uid, dev)
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

    def _persist_login_config(self, cookie_str: str, uid, dev) -> None:
        """登录成功后把 cookie/uid/device 写回运行配置与 AstrBot 配置（落盘）。

        session.json 存于 data/plugin_data 下（更新插件不丢），此处再同步到配置层，
        使配置页「登录 Cookie」等字段可见、并在配置层留下兜底。
        """
        if cookie_str:
            self._config["douyin_cookies"] = cookie_str
        if uid:
            self._config["self_uid"] = str(uid)
        if dev:
            self._config["device_id"] = str(dev)
        obj = self._config_obj
        if obj is None:
            return
        try:
            if cookie_str:
                obj["douyin_cookies"] = cookie_str
            if uid:
                obj["self_uid"] = str(uid)
            if dev:
                obj["device_id"] = str(dev)
            save = getattr(obj, "save_config", None)
            if save is not None:
                save()
        except Exception as e:  # 配置写回失败不阻断登录
            logger.warning(f"[dyf] 登录配置写回失败（不影响会话）: {e}")

    async def logout(self) -> bool:
        if not getattr(self._auth, "sessionid", None):
            logger.info("[dyf] 当前未登录，无需登出")
            return False
        await self._stop_receiver()
        self._login_flow.session.clear()
        self._state = AuthState.UNKNOWN        # 清 AstrBot 配置（否则重启/更新插件读配置的 douyin_cookies 自动恢复登录）
        for k in ("douyin_cookies", "self_uid", "device_id"):
            self._config[k] = ""
        obj = self._config_obj
        if obj is not None:
            try:
                for k in ("douyin_cookies", "self_uid", "device_id"):
                    if k in obj:
                        obj[k] = ""
                save = getattr(obj, "save_config", None)
                if save is not None:
                    save()
            except Exception as e:
                logger.warning(f"[dyf] 登出清配置失败: {e}")
        # 置空 _auth，避免旧对象继续持有 cookie（二次登出误判"已登录"）
        self._auth = None
        self._emit_event(GatewayEvent("logout", "已登出并清除会话"))
        logger.info("[dyf] 已登出")
        return True

    @property
    def login_in_progress(self) -> bool:
        """是否正在扫码登录（登录线程持锁期间为 True）。"""
        return bool(self._login_lock.locked())

    def trigger_mfa_send(self) -> None:
        self._code_waiter.trigger_send()

    def submit_mfa_code(self, code: str) -> None:
        self._code_waiter.submit(code)

    def _on_qr(self, url: str) -> None:
        self._last_qr_content = url
        self._emit_event(GatewayEvent("qr", url))
        logger.info("[dyf] 登录二维码已生成，请用抖音扫码登录")

    def _on_qr_alemonjs(self, ev: dict) -> None:
        """Alemons 桥接二维码：qrcodeBase64 为 PNG base64，直接拼 data URL。"""
        b64 = str(ev.get("qrcodeBase64") or "").strip()
        data_url = f"data:image/png;base64,{b64}" if b64 else ""
        if data_url:
            self._last_qr_content = data_url
            self._emit_event(GatewayEvent("qr", data_url))
        logger.info("[dyf] 登录二维码已生成（@alemonjs/douyin），请用抖音扫码登录")

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
    def _on_any_frame(self) -> None:
        # 任意帧（含心跳/控制帧）都刷新看门狗时间戳，避免无私信时误报僵死
        self._last_frame_ts = time.time()

    def _on_raw_message(self, raw: dict) -> None:
        self._last_frame_ts = time.time()
        msg = self._converter.convert(raw)
        if msg is None:
            return
        # 好友昵称回填：content 无昵称时用好友缓存的 remark_name/nickname 替代 uid
        if msg.peer_id and (not msg.peer_name or msg.peer_name == str(msg.peer_id)):
            name = self._lookup_friend_name(msg.peer_id)
            if name:
                msg.peer_name = name
        # 视频详情不再在此同步拉取（会阻塞 receiver 线程）；由监听消费循环 enrich_video 处理
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._msg_queue.put_nowait, msg)

    async def enrich_video(self, msg: InboundMessage) -> None:
        """视频卡/图集分享补详情（消费循环调用）：非媒体分享时直接返回；to_thread 避免阻塞接收。"""
        if not bool(self._config.get("video_detail_enabled", True)):
            return
        if msg.type != MessageType.VIDEO_CARD and not (
            msg.type == MessageType.IMAGE and (msg.card or {}).get("share_item_id")
        ):
            return
        await asyncio.to_thread(self._enrich_video, msg)

    def _get_http(self) -> DouyinHttpPy:
        if self._http is None:
            self._http = DouyinHttpPy(
                initial_cookies=self._auth.cookie_str,
                user_agent=self._config.get("ua") or _DEFAULT_UA,
            )
            if self._device_id and self._device_id.isdigit():
                self._http.set_device({"deviceId": self._device_id, "installId": self._device_id, "guid": ""})
        return self._http

    def _enrich_video(self, msg: InboundMessage) -> None:
        """视频卡/图集分享补详情（L2）：aweme/detail 拿 desc + 封面/图片，转发内容变 标题+desc+链接+媒体。"""
        if self._auth is None:
            return
        card = msg.card or {}
        item_id = str(
            card.get("share_item_id") or card.get("itemId") or card.get("item_id") or ""
        )
        if not item_id:
            return
        if not (self._auth.cookie_str or "").strip():
            return
        detail = fetch_aweme_detail(self._get_http(), item_id)
        if not detail:
            return
        if detail.get("error"):
            logger.info(f"[dyf] 详情拉取失败 {item_id}: {detail['error']}")
            return
        # 图集/视频由详情判定：有 images 即图集（/note/），否则视频（/video/）
        is_album = bool(detail.get("images"))
        desc = (detail.get("desc") or "").strip()
        if not desc:
            # 详情 desc 为空时用视频卡自带标题兜底（content_title）
            desc = (card.get("content_title") or card.get("title") or "").strip()
        link = (
            f"https://www.douyin.com/note/{item_id}"
            if is_album
            else f"https://www.douyin.com/video/{item_id}"
        )
        if desc and desc not in msg.text:
            body = f"{msg.text}\n{desc}".strip() if msg.text else desc
            if link and link not in body:
                body = f"{body}\n{link}".strip()
            msg.text = body
        elif link and link not in msg.text:
            # desc 为空/已含：至少补正确链接（/note/ 或 /video/）
            msg.text = f"{msg.text}\n{link}".strip()
        cover = detail.get("cover") or ""
        if cover and cover not in msg.media_urls:
            msg.media_urls = msg.media_urls + [cover]
        for _img in detail.get("images") or []:
            if _img and _img not in msg.media_urls:
                msg.media_urls = msg.media_urls + [_img]
        logger.info(
            f"[dyf] 视频详情已补: {item_id} desc_len={len(desc)} "
            f"cover={'有' if cover else '无'} images={len(detail.get('images') or [])}"
        )

    def _on_status(self, kind: str, detail: str = "") -> None:
        if kind in ("error", "close") and (
            self._detector.check_error(detail) or self._detector.check_text(detail)
        ):
            logger.warning(f"[dyf] 连接失效判定: {kind} {detail}")
            self._mark_auth_expired()
            return
        if kind == "reconnect":
            logger.info(f"[dyf] 连接重连中: {detail}")
            self._emit_event(GatewayEvent("reconnect", detail))
        elif kind == "close":
            logger.warning(f"[dyf] 连接断开: {detail}")
            self._emit_event(GatewayEvent("disconnect", detail))
        elif kind == "error":
            logger.warning(f"[dyf] 连接错误: {detail}")
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

    async def set_self_uid(self, uid: int | None) -> None:
        """/dyf uid 命令写入：更新解析器缓存与运行态。"""
        self._resolver.cache(uid)
        self._self_uid = await self._resolver.resolve_async(self._auth)

    async def stop(self) -> None:
        self._stopping = True
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._login_task:
            self._login_task.cancel()
        await self._stop_receiver()
        self._emit_event(GatewayEvent("stopped", "Douyin gateway stopped"))
        logger.info("[dyf] DouyinGateway 已停止")
