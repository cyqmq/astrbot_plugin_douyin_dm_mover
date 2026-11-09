"""@alemonjs/douyin 登录后端：Node 桥接子进程（alemonjs_bridge.mjs）。

用 SDK 底层接口（getQrcode / checkQrconnect / sendQrMfaCode / validateQrMfaCode）
完成 扫码 → 2046 短信 MFA → 会话，通过 NDJSON 行协议与 Node 桥接交互。

桥接脚本位于本目录，依赖 Node.js >= 20.19 与插件根目录 node_modules/@alemonjs/douyin。
"""
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).resolve().parents[3]
_BRIDGE = Path(__file__).resolve().parent / "alemonjs_bridge.mjs"


class AlemonjsResult:
    """登录成功结果：cookies 串（"k=v; k=v"）+ uid + 可选 device_id/user_data。"""

    def __init__(self, cookie_str: str, uid: str, device_id: str | None = None, user_data: dict | None = None):
        self.cookie_str = cookie_str
        self.uid = uid
        self.device_id = device_id
        self.user_data = user_data or {}


class AlemonjsLogin:
    """异步登录后端：拉起 node 桥接子进程并交互。"""

    def __init__(self, on_qrcode=None, on_log=None, code_waiter=None):
        self._on_qrcode = on_qrcode or (lambda ev: None)
        self._on_log = on_log or (lambda text: None)
        self._code_waiter = code_waiter

    def _log(self, text: str) -> None:
        try:
            self._on_log(text)
        except Exception:
            pass

    @staticmethod
    async def _send(proc, obj: dict) -> None:
        if proc.stdin is None or proc.returncode is not None:
            return
        try:
            proc.stdin.write((json.dumps(obj) + "\n").encode())
            await proc.stdin.drain()
        except Exception:
            pass

    async def qrcode_login_async(self, timeout: int = 300) -> AlemonjsResult:
        node = shutil.which("node")
        if not node:
            raise RuntimeError("未找到 node：请安装 Node.js >= 20.19")
        if not _BRIDGE.exists():
            raise RuntimeError(f"桥接脚本缺失: {_BRIDGE}")
        self._log("拉起 @alemonjs/douyin 桥接进程")
        proc = await asyncio.create_subprocess_exec(
            node,
            str(_BRIDGE),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_PLUGIN_ROOT),
        )
        state = {"done": False, "data": None, "error": None}

        async def _read() -> None:
            try:
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    try:
                        ev = json.loads(line.decode("utf-8", "replace").strip())
                    except json.JSONDecodeError:
                        continue
                    await self._handle_event(ev, proc, state, timeout)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                state["error"] = str(e)

        async def _readerr() -> None:
            try:
                while True:
                    line = await proc.stderr.readline()
                    if not line:
                        break
                    text = line.decode("utf-8", "replace").strip()
                    if text:
                        self._log(f"[bridge] {text}")
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        reader = asyncio.create_task(_read())
        err_task = asyncio.create_task(_readerr())
        try:
            await self._send(proc, {"cmd": "start", "timeout": int(timeout)})
            while not state["done"]:
                if state["error"]:
                    raise RuntimeError(state["error"])
                if proc.returncode is not None:
                    raise RuntimeError(f"桥接进程异常退出 code={proc.returncode}")
                await asyncio.sleep(0.1)
            if not state["data"]:
                raise RuntimeError("登录未完成")
            return state["data"]
        finally:
            if proc.returncode is None:
                await self._send(proc, {"cmd": "stop"})
                try:
                    proc.kill()
                except Exception:
                    pass
            for task in (reader, err_task):
                task.cancel()

    async def _handle_event(self, ev: dict, proc, state: dict, timeout: int) -> None:
        event = ev.get("event")
        if event == "ready":
            self._log("桥接就绪，等待二维码")
        elif event == "qrcode":
            self._log("二维码已生成")
            self._on_qrcode(ev)
        elif event == "mfa_required":
            self._log("2046 二次验证：请输入短信验证码")
            await self._collect_mfa(proc, ev, timeout)
        elif event == "status":
            self._log(str(ev.get("text") or ""))
        elif event == "login_ok":
            cookies = str(ev.get("cookies") or "").strip()
            uid = str(ev.get("platformUid") or "").strip()
            if not cookies or not uid:
                state["error"] = "登录成功但缺少 cookie / uid"
                state["done"] = True
                return
            state["data"] = AlemonjsResult(
                cookie_str=cookies,
                uid=uid,
                device_id=str(ev["deviceId"]) if ev.get("deviceId") else None,
                user_data=ev.get("userData") or {},
            )
            state["done"] = True
        elif event == "login_expired":
            state["error"] = str(ev.get("detail") or "二维码已过期")
            state["done"] = True
        elif event == "login_failed":
            state["error"] = str(ev.get("error") or "登录失败")
            state["done"] = True
        elif event == "fatal":
            state["error"] = str(ev.get("error") or "桥接致命错误")
            state["done"] = True

    async def _collect_mfa(self, proc, ev: dict, timeout: int) -> None:
        """mfa_required 后阻塞等待喂码（复用 CodeWaiter），取到码后回填桥接。"""
        if self._code_waiter is None:
            self._log("无喂码通道，请在抖音 App 完成验证")
            return
        mobile = ev.get("maskedMobile")
        code = await asyncio.to_thread(
            self._code_waiter.code_source, mobile, lambda: None
        )
        if code:
            self._log("验证码已回填桥接，等待校验")
            await self._send(proc, {"cmd": "mfa_code", "code": code})
        else:
            self._log("未收到验证码，等待在抖音 App 完成验证")
