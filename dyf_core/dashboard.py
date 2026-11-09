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
from astrbot.api import logger

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
    def __init__(self, context, gateway, forward_manager, logring: LogRing | None = None, config_obj=None):
        self.context = context
        self.gateway = gateway
        self.fm = forward_manager
        self.logring = logring or LogRing()
        self._config_obj = config_obj
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
        reg("douyin_dm_mover/install-alemonjs", self.install_alemonjs, ["POST"], "dyf 安装 @alemonjs/douyin 登录依赖")
        reg("douyin_dm_mover/reload", self.reload_plugin, ["POST"], "dyf 重载插件（刷新深层代码）")
        reg("douyin_dm_mover/mfa", self.submit_mfa, ["POST"], "dyf 提交短信验证码")
        reg("douyin_dm_mover/config/get", self.config_get, ["GET"], "dyf 读取配置 + schema")
        reg("douyin_dm_mover/config/set", self.config_set, ["POST"], "dyf 保存配置")
        reg("douyin_dm_mover/profile", self.profile, ["GET"], "dyf 账户昵称/头像")
        reg("douyin_dm_mover/friends", self.friends, ["GET"], "dyf 好友列表（familiar-list）")

    async def install_alemonjs(self):
        """一键安装 @alemonjs/douyin（Node 依赖）。"""
        ok, msg = await self.gateway.install_login_backend()
        return {"ok": ok, "detail": msg}

    async def reload_plugin(self):
        """后台重载本插件：终止当前实例并重新加载，使深层代码（dyf_gateway 等）生效。"""
        sm = getattr(self.context, "_star_manager", None)
        if sm is None:
            return {"ok": False, "detail": "未找到 AstrBot 插件管理器，无法重载"}
        asyncio.create_task(self._do_reload(sm))
        return {"ok": True, "detail": "正在重载插件，稍候生效"}

    async def _do_reload(self, sm) -> None:
        try:
            result = await sm.reload("astrbot_plugin_douyin_dm_mover")
            ok = result[0] if isinstance(result, tuple) else bool(result)
            err = result[1] if isinstance(result, tuple) else None
            if not ok:
                from astrbot.api import logger

                logger.error(f"[dyf] 插件重载失败: {err}")
        except Exception as e:
            from astrbot.api import logger

            logger.error(f"[dyf] 插件重载异常: {e}")

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
            "login_backend": str(cfg.get("login_backend") or "alemonjs"),
            "alemonjs_installed": self._alemonjs_installed(),
            "senders_count": len(fm.tracker.senders()),
            "records_count": len(fm.tracker.records()),
        }

    @staticmethod
    def _alemonjs_installed() -> bool:
        from dyf_gateway.douyin.login.alemonjs import _NODE_MODULE

        return bool(_NODE_MODULE.exists())

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

    async def submit_mfa(self):
        """接收 Web 配置页提交的短信验证码，喂给登录 MFA 流程。"""
        try:
            from astrbot.api.web import request as web_request

            data = await web_request.json(default={}) or {}
        except Exception:
            data = {}
        code = str((data or {}).get("code") or "").strip()
        if not code:
            return {"ok": False, "detail": "缺少验证码"}
        self.gateway.submit_mfa_code(code)
        return {"ok": True, "detail": "验证码已提交"}

    @staticmethod
    def _load_schema() -> dict:
        import json as _json
        import os

        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_conf_schema.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            return {}

    async def config_get(self):
        """读取当前配置与 schema（配置页渲染表单用）。"""
        return {"config": dict(self.fm.config), "schema": self._load_schema()}

    async def config_set(self):
        """保存配置：合并更新到运行配置并写回 AstrBot 配置，提示重载生效。"""
        try:
            from astrbot.api.web import request as web_request

            data = await web_request.json(default={}) or {}
        except Exception:
            data = {}
        updates = (data or {}).get("config") or {}
        if not isinstance(updates, dict) or not updates:
            return {"ok": False, "detail": "缺少 config 更新"}
        cfg = self.fm.config
        for k, v in updates.items():
            cfg[k] = v
        if self._config_obj is not None:
            save = getattr(self._config_obj, "save_config", None)
            if save is not None:
                try:
                    save()
                except Exception as e:
                    return {"ok": False, "detail": f"配置保存失败: {e}"}
        # 配置已落盘，自动重载插件使深层代码/运行时配置生效（免手动点「重载插件」）
        self._schedule_reload()
        return {"ok": True, "detail": "已保存并自动重载插件，稍候生效"}

    def _schedule_reload(self) -> None:
        """后台自动重载本插件，让配置/深层代码即时生效。"""
        try:
            sm = getattr(self.context, "_star_manager", None)
            if sm is None:
                return
            import asyncio

            asyncio.create_task(self._do_reload(sm))
        except Exception as e:
            logger.warning(f"[dyf] 自动重载失败（可手动点「重载插件」）: {e}")

    async def profile(self):
        """账户档案（昵称/头像）：登录后缓存于 gateway，未登录返回空。"""
        p = getattr(self.gateway, "_profile", None) or {}
        if p:
            return {"profile": p}
        # 未登录/无缓存：回退到登录态基本字段
        uid = getattr(self.gateway, "self_uid", None)
        return {"profile": {"uid": str(uid or ""), "nickname": "", "avatar": ""}}

    async def friends(self):
        """好友列表（familiar-list 全量）：未登录返回空；已缓存直接返回。"""
        gw = self.gateway
        if gw.auth_state.value != "ok":
            return {"friends": [], "detail": "未登录"}
        cached = getattr(gw, "_friends", None) or []
        if cached:
            return {"friends": cached, "cached": True}
        try:
            from dyf_gateway.douyin.login.alemonjs_py import (
                DouyinHttpPy,
                fetch_friend_list,
            )

            auth = getattr(gw, "_auth", None)
            cookie_str = getattr(auth, "cookie_str", "") or ""
            if not cookie_str:
                return {"friends": [], "detail": "无会话 Cookie"}
            dev = getattr(gw, "_device_id", "") or "0"
            http = DouyinHttpPy(cookie_str)
            http.set_device({"deviceId": dev, "installId": "0", "guid": "0"})
            friends = await asyncio.to_thread(fetch_friend_list, http)
            gw._friends = friends
            return {"friends": friends}
        except Exception as e:
            logger.warning(f"[dyf] 拉取好友列表失败: {e}")
            return {"friends": [], "detail": f"拉取失败: {e}"}

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
