"""SubprocessGateway：MessageGateway 的 subprocess 实现。

用独立子进程跑 vendored 接收（见 gateway/douyin/worker.py），进程级硬隔离：
崩溃/内存泄漏不拖垮 AstrBot；更新 vendored/ 后重启 worker 即可。协议见 worker.py。

父进程职责：
- 拉起/重启 worker（崩溃 → 指数退避，登录态失效则不重启）
- 解析 stdout JSON 行（frame/message/status），转成统一事件流
- stdin 控制通道（uid 更新 / stop）
- 看门狗：静默检测（复用 AuthFailureDetector）
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from collections.abc import AsyncIterator

from astrbot.api import logger

from dyf_core.model import AuthState, GatewayEvent, InboundMessage

from .base import MessageGateway
from .douyin.detector import AuthFailureDetector


class SubprocessGateway(MessageGateway):
    def __init__(self, config: dict):
        self._config = config
        self._data_dir = config.get("_data_dir") or os.path.join("data", "dyf")
        os.makedirs(self._data_dir, exist_ok=True)
        self._detector = AuthFailureDetector(
            close_codes=self._parse_int_list(config.get("auth_failure_close_codes")),
            keywords=self._parse_list(config.get("auth_failure_keywords")),
            watchdog_minutes=config.get("auth_watchdog_minutes", 30),
        )
        self._msg_queue: asyncio.Queue = asyncio.Queue()
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._state = AuthState.UNKNOWN
        self._last_qr_content: str | None = None
        self._self_uid: int | None = self._norm(config.get("self_uid"))
        self._proc = None
        self._stopping = False
        self._last_frame_ts: float | None = None
        self._restart_delay = 2.0
        self._plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._cfg_path = os.path.join(self._data_dir, "worker_config.json")
        self._tasks: list[asyncio.Task] = []
        self._reader_tasks: list[asyncio.Task] = []
        self._logging_in = False
        # ---- 登录（父进程编排，登录后会话 cookie 注入 worker 配置）----
        from .douyin.login.alemonjs import AlemonjsLogin
        from .douyin.login.alemonjs_py_login import AlemonsPyLogin
        from .douyin.login.flow import LoginFlow
        from .douyin.login.mfa import MfaHandler
        from .douyin.login.waiter import CodeWaiter

        self._mfa_mode = config.get("mfa_mode") or "auto_sms"
        self._code_waiter = CodeWaiter(self._mfa_mode, config.get("login_mfa_timeout", 300))
        self._mfa = MfaHandler(self._mfa_mode, alert=self._mfa_alert, code_source=self._code_waiter.code_source)
        self._login_flow = LoginFlow(
            self._data_dir, mfa_handler=self._mfa, on_qrcode=self._on_qr, on_log=lambda m: None
        )
        # ---- 登录后端：默认纯 Python（@alemonjs/douyin 移植）；可选 Node 桥接 / douyin_spider ----
        self._login_backend = (config.get("login_backend") or "alemonjs").lower()
        self._alemonjs = AlemonjsLogin(
            on_qrcode=self._on_qr_alemonjs, on_log=lambda m: None, code_waiter=self._code_waiter
        )
        self._alemonjs_py = AlemonsPyLogin(
            on_qrcode=self._on_qr_alemonjs, on_log=lambda m: None, code_waiter=self._code_waiter
        )

    @staticmethod
    def _norm(value) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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
        for x in SubprocessGateway._parse_list(value):
            try:
                out.append(int(x))
            except ValueError:
                pass
        return out

    # ---- 启动/停止 ----
    def _write_config(self) -> None:
        cfg = dict(self._config)
        cfg["_data_dir"] = self._data_dir
        # 登录会话优先：worker 直接拿已保存会话的 cookie，保证与登录同源
        sess = self._login_flow.session
        if sess.has_valid() and not cfg.get("douyin_cookies"):
            cfg["douyin_cookies"] = sess.cookie_str()
        with open(self._cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False)

    async def _spawn(self) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = self._plugin_root + os.pathsep + env.get("PYTHONPATH", "")
        self._proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "dyf_gateway.douyin.worker",
            self._cfg_path,
            cwd=self._plugin_root,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )
        self._reader_tasks = [
            asyncio.create_task(self._read_stdout(self._proc)),
            asyncio.create_task(self._read_stderr(self._proc)),
        ]
        logger.info(f"[dyf] worker 已拉起 pid={self._proc.pid}")

    async def start(self) -> None:
        self._write_config()
        await self._spawn()
        self._tasks = [
            asyncio.create_task(self._watch_process()),
            asyncio.create_task(self._watchdog()),
        ]
        self._emit_event(GatewayEvent("started", "Subprocess gateway started"))

    async def stop(self) -> None:
        self._stopping = True
        for t in self._tasks + self._reader_tasks:
            t.cancel()
        self._tasks.clear()
        self._reader_tasks.clear()
        if self._proc:
            if self._proc.stdin:
                try:
                    self._proc.stdin.write(b"stop\n")
                    await self._proc.stdin.drain()
                except Exception:
                    pass
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except Exception:
                try:
                    self._proc.kill()
                    await self._proc.wait()
                except Exception:
                    pass
            self._proc = None
        self._emit_event(GatewayEvent("stopped", "Subprocess gateway stopped"))
        logger.info("[dyf] SubprocessGateway 已停止")

    # ---- worker 输出解析 ----
    async def _read_stdout(self, proc) -> None:
        while not self._stopping and proc.stdout:
            line = await proc.stdout.readline()
            if not line:
                break
            self._handle_line(line.decode("utf-8", "replace").strip())

    async def _read_stderr(self, proc) -> None:
        while not self._stopping and proc.stderr:
            line = await proc.stderr.readline()
            if not line:
                break
            logger.debug(f"[dyf][worker] {line.decode('utf-8', 'replace').rstrip()}")

    def _handle_line(self, line: str) -> None:
        if not line:
            return
        try:
            obj = json.loads(line)
        except Exception:
            return
        kind = obj.get("kind")
        if kind == "message":
            try:
                msg = InboundMessage.from_dict(obj.get("data") or {})
            except Exception:
                return
            self._last_frame_ts = time.time()
            self._msg_queue.put_nowait(msg)
        elif kind == "frame":
            self._last_frame_ts = time.time()
        elif kind == "status":
            d = obj.get("data") or {}
            self._on_status(d.get("kind", ""), d.get("detail", ""))

    def _on_status(self, kind: str, detail: str) -> None:
        if kind == "auth_failure":
            if self._state != AuthState.EXPIRED:
                self._state = AuthState.EXPIRED
                self._emit_event(GatewayEvent("auth_failure", detail))
                logger.error(f"[dyf] 检测到登录态失效: {detail}")
            return
        if kind == "started":
            self._restart_delay = 2.0
            if self._self_uid is None and "self_uid=" in detail:
                try:
                    self._self_uid = int(detail.split("self_uid=", 1)[1].split()[0])
                except Exception:
                    pass
            self._emit_event(GatewayEvent("started", detail))
        elif kind == "reconnect":
            self._emit_event(GatewayEvent("reconnect", detail))
        elif kind == "disconnect":
            self._emit_event(GatewayEvent("disconnect", detail))
        elif kind == "error":
            self._emit_event(GatewayEvent("error", detail))

    def _emit_event(self, ev: GatewayEvent) -> None:
        try:
            self._event_queue.put_nowait(ev)
        except Exception:
            pass

    # ---- 进程守护 ----
    async def _watch_process(self) -> None:
        while not self._stopping and self._proc:
            rc = await self._proc.wait()
            if self._stopping:
                break
            # worker 退出前可能已在 stdout 写出 auth_failure 等状态行；先排空 reader，
            # 避免 _on_status 与进程退出检测竞态导致鉴权失效被误判为普通崩溃。
            for t in self._reader_tasks:
                try:
                    await asyncio.wait_for(t, timeout=2)
                except Exception:
                    pass
            if self._state == AuthState.EXPIRED:
                self._emit_event(GatewayEvent("error", f"worker 退出(rc={rc})，登录态失效不再重启"))
                break
            self._emit_event(
                GatewayEvent("disconnect", f"worker 退出 rc={rc}，{self._restart_delay:.0f}s 后重启")
            )
            await asyncio.sleep(self._restart_delay)
            if self._stopping:
                break
            self._restart_delay = min(self._restart_delay * 2, 60)
            try:
                await self._spawn()
            except Exception as e:
                self._emit_event(GatewayEvent("error", f"重启 worker 失败: {e}"))

    async def _watchdog(self) -> None:
        while not self._stopping:
            await asyncio.sleep(60)
            if self._state == AuthState.EXPIRED:
                continue
            if self._detector.check_silence(self._last_frame_ts):
                self._emit_event(
                    GatewayEvent(
                        "error",
                        f"静默 {self._detector.watchdog_seconds // 60} 分钟无帧，疑似连接僵死",
                    )
                )

    # ---- 登录 / 登出 / MFA（父进程编排，会话 cookie 经 _write_config 注入 worker）----
    async def login(self, timeout: int = 300) -> None:
        if self._logging_in:
            self._emit_event(GatewayEvent("error", "已有登录进行中"))
            return
        self._logging_in = True
        loop = asyncio.get_running_loop()
        self._emit_event(GatewayEvent("login_started", "开始扫码登录"))
        backend = self._login_backend

        try:
            if backend in ("alemonjs", "alemonjs_py", "python"):
                logger.info("[dyf] 登录后端：@alemonjs/douyin 纯 Python 移植")
                result = await self._alemonjs_py.qrcode_login_async(timeout=timeout)
                from .douyin.vendored.auth import DouyinAuth

                auth = DouyinAuth(
                    cookie_str=result.cookie_str,
                    web_protect=self._config.get("douyin_web_protect", ""),
                    keys=self._config.get("douyin_keys", ""),
                )
                auth.uid = int(result.uid) if result.uid else None
                if result.device_id:
                    auth.device_id = str(result.device_id)
                auth._login_backend = "alemonjs"
                self._login_flow.session.save(auth, backend="alemonjs")
            elif backend in ("alemonjs_node", "node"):
                logger.info("[dyf] 登录后端：@alemonjs/douyin（Node 桥接）")
                result = await self._alemonjs.qrcode_login_async(timeout=timeout)
                from .douyin.vendored.auth import DouyinAuth

                auth = DouyinAuth(
                    cookie_str=result.cookie_str,
                    web_protect=self._config.get("douyin_web_protect", ""),
                    keys=self._config.get("douyin_keys", ""),
                )
                auth.uid = int(result.uid) if result.uid else None
                if result.device_id:
                    auth.device_id = str(result.device_id)
                auth._login_backend = "alemonjs_node"
                self._login_flow.session.save(auth, backend="alemonjs_node")
            else:
                auth = await loop.run_in_executor(
                    None, lambda: self._login_flow.qrcode_login(timeout=timeout)
                )
                self._login_flow.session.save(auth)
            self._state = AuthState.OK
            self._emit_event(GatewayEvent("login_ok", "登录成功，会话已保存"))
            await self._restart_worker()
        except Exception as e:
            self._emit_event(GatewayEvent("error", f"登录失败: {e}"))
            logger.error(f"[dyf] 登录失败: {e}")
        finally:
            self._logging_in = False

    async def logout(self) -> bool:
        if self._state != AuthState.OK and not self._login_flow.session.has_valid():
            logger.info("[dyf] 当前未登录，无需登出")
            return False
        self._stopping = True
        for t in self._reader_tasks:
            t.cancel()
        self._reader_tasks.clear()
        if self._proc:
            try:
                self._proc.kill()
                await self._proc.wait()
            except Exception:
                pass
            self._proc = None
        self._login_flow.session.clear()
        self._state = AuthState.UNKNOWN
        self._emit_event(GatewayEvent("logout", "已登出并清除会话"))
        return True

    @property
    def login_in_progress(self) -> bool:
        return self._logging_in

    async def install_login_backend(self) -> tuple[bool, str]:
        backend = self._login_backend
        if backend in ("alemonjs", "alemonjs_py", "python"):
            return True, "登录后端为纯 Python 实现（@alemonjs/douyin 移植），无需安装依赖。"
        from .douyin.login.alemonjs import ensure_alemonjs

        return await ensure_alemonjs(install=True)

    async def _restart_worker(self) -> None:
        self._stopping = False
        if self._proc:
            try:
                self._proc.kill()
                await self._proc.wait()
            except Exception:
                pass
            self._proc = None
        self._write_config()
        await self._spawn()

    def trigger_mfa_send(self) -> None:
        self._code_waiter.trigger_send()

    def submit_mfa_code(self, code: str) -> None:
        self._code_waiter.submit(code)

    def _on_qr(self, url: str) -> None:
        self._last_qr_content = url
        self._emit_event(GatewayEvent("qr", url))

    def _on_qr_alemonjs(self, ev: dict) -> None:
        b64 = str(ev.get("qrcodeBase64") or "").strip()
        data_url = f"data:image/png;base64,{b64}" if b64 else ""
        if data_url:
            self._last_qr_content = data_url
            self._emit_event(GatewayEvent("qr", data_url))

    @property
    def last_qr_content(self) -> str | None:
        """最近一次登录二维码内容（扫码字符串）。"""
        return self._last_qr_content

    def _mfa_alert(self, text: str) -> None:
        self._emit_event(GatewayEvent("mfa", text))
        logger.warning(f"[dyf] {text}")

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
        self._self_uid = uid
        self._config["self_uid"] = uid
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.write(f"uid {int(uid)}\n".encode())
            except Exception:
                pass
