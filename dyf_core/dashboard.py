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


def _route_diff(old_list, new_list) -> list[str]:
    """路由表结构化 diff（按 name 匹配）：增/删/目标变更/来源连接±/类型±；忽略 pos。

    返回人类可读行列表（不含 [dyf] 前缀），供 config_set 逐条日志。
    """
    old = {r.get("name"): r for r in old_list or [] if isinstance(r, dict) and r.get("name")}
    new = {r.get("name"): r for r in new_list or [] if isinstance(r, dict) and r.get("name")}
    lines: list[str] = []
    for name, nr in new.items():
        if name not in old:
            lines.append(f'+ 路由 "{name}" → {nr.get("target") or "未连接目标"}')
            continue
        orr = old[name]
        ot = orr.get("target") or ""
        nt = nr.get("target") or ""
        if ot != nt:
            lines.append(f'~ 路由 "{name}" 目标: {ot or "(无)"} → {nt or "(无)"}')
        om = orr.get("match") or {}
        nm = nr.get("match") or {}
        oinc = set(om.get("senders_include") or [])
        ninc = set(nm.get("senders_include") or [])
        for u in sorted(ninc - oinc, key=str):
            lines.append(f'~ 路由 "{name}" 来源 +{u}')
        for u in sorted(oinc - ninc, key=str):
            lines.append(f'~ 路由 "{name}" 来源 -{u}')
        otypes = set(om.get("types") or [])
        ntypes = set(nm.get("types") or [])
        for t in sorted(ntypes - otypes, key=str):
            lines.append(f'~ 路由 "{name}" 类型 +{t}')
        for t in sorted(otypes - ntypes, key=str):
            lines.append(f'~ 路由 "{name}" 类型 -{t}')
    for name in old:
        if name not in new:
            lines.append(f'- 路由 "{name}"')
    return lines


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
        reg("douyin_dm_mover/groups", self.groups, ["GET"], "dyf 可发送群列表（AstrBot get_group_list）")
        reg("douyin_dm_mover/platforms", self.platforms, ["GET"], "dyf 已加载平台实例列表")

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
            result = await asyncio.wait_for(
                sm.reload("astrbot_plugin_douyin_dm_mover"), timeout=30
            )
            ok = result[0] if isinstance(result, tuple) else bool(result)
            err = result[1] if isinstance(result, tuple) else None
            if not ok:
                from astrbot.api import logger

                err_s = str(err or "")
                # AstrBot 会把所有 failed 插件信息聚合进 error_message；
                # 只关注本插件，避免 LogDeck/Token 的失败文案串进浮窗
                if "douyin_dm_mover" in err_s:
                    logger.error(f"[dyf] 插件重载失败: {err_s}")
                else:
                    logger.warning(
                        f"[dyf] 重载完成；其它插件加载失败与本插件无关: {err_s}"
                    )
        except TimeoutError:
            from astrbot.api import logger

            logger.error(
                "[dyf] 插件重载超时(30s)，可能卡在 terminate/load，请检查 AstrBot 日志"
            )
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
        old_routes = None
        if "routes" in updates:
            import copy
            old_routes = copy.deepcopy(cfg.get("routes") or [])
        for k, v in updates.items():
            cfg[k] = v
        if "routes" in updates:
            for line in _route_diff(old_routes, updates.get("routes") or []):
                logger.info(f"[dyf] {line}")
            # 路由即时生效：router 只在 __init__ 建一次，更新 routes 后需重建
            from dyf_core.router import RouteResolver

            self.fm.router = RouteResolver(updates.get("routes") or [])
        logger.info(f"[dyf] 配置已更新: {sorted(str(k) for k in updates)}")
        if self._config_obj is not None:
            # 同步写本体（AstrBotConfig 是 dict 子类）：cfg=dict(config) 是副本，
            # 仅改副本会让重载后读回旧值（路由回滚）；update 本体后重载读回正确配置。
            try:
                self._config_obj.update(updates)
            except Exception as e:
                logger.warning(f"[dyf] 同步本体配置失败: {e}")
            save = getattr(self._config_obj, "save_config", None)
            if save is not None:
                try:
                    save()
                except Exception as e:
                    return {"ok": False, "detail": f"配置保存失败: {e}"}
        # 配置已落盘；no_reload 用于实时静默保存（避免高频自动重载），否则自动重载插件使深层代码/运行时配置生效
        if not bool((data or {}).get("no_reload")):
            self._schedule_reload()
        return {"ok": True, "detail": "已保存并自动重载插件，稍候生效" if not bool((data or {}).get("no_reload")) else "已保存"}

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
        """账户档案（昵称/头像）：内存/落盘缓存（TTL 300s）内不重拉，超时或缺失才拉取。"""
        gw = self.gateway
        prof = getattr(gw, "_profile", None) or {}
        pts = getattr(gw, "_profile_ts", 0) or 0
        import time
        if not prof:
            # 内存空（如重载后 gateway 重建）→ 读落盘缓存
            prof, pts = gw._load_profile_cache()
            gw._profile = prof
            gw._profile_ts = pts
        if prof and (time.time() - pts) < 300:
            return {"profile": prof, "cached": True}
        if gw.auth_state.value == "ok" and not prof:
            try:
                from dyf_gateway.douyin.login.alemonjs_py import (
                    DouyinHttpPy,
                    fetch_desktop_self_profile,
                )

                auth = getattr(gw, "_auth", None)
                cookie_str = getattr(auth, "cookie_str", "") or ""
                if cookie_str:
                    dev = getattr(gw, "_device_id", "") or "0"
                    http = DouyinHttpPy(cookie_str)
                    http.set_device({"deviceId": dev, "installId": "0", "guid": "0"})
                    prof = await asyncio.to_thread(fetch_desktop_self_profile, http)
                    gw._profile = prof
                    gw._profile_ts = time.time()
                    gw._store_profile_cache(prof, gw._profile_ts)
            except Exception as e:
                logger.warning(f"[dyf] 拉取账户档案失败: {e}")
        p = getattr(gw, "_profile", None) or prof or {}
        if p:
            return {"profile": p}
        # 未登录/无缓存：回退到登录态基本字段
        uid = getattr(gw, "self_uid", None)
        return {"profile": {"uid": str(uid or ""), "nickname": "", "avatar": ""}}

    async def friends(self):
        """好友列表（familiar-list 全量）：未登录返回空；已缓存（TTL 300s）直接返回，?refresh=1 强制重拉。"""
        gw = self.gateway
        if gw.auth_state.value != "ok":
            return {"friends": [], "detail": "未登录"}
        refresh = False
        try:
            from astrbot.api.web import request as web_request
            q = getattr(web_request, "args", None)
            refresh = bool(q and str(q.get("refresh", "0")) in ("1", "true", "True"))
        except Exception:
            refresh = False
        cached = getattr(gw, "_friends", None) or []
        ts = getattr(gw, "_friends_ts", 0) or 0
        import time
        # 内存缓存为空（如重载后 gateway 重建）→ 读落盘缓存（含时间戳）
        if not cached:
            cached, ts = gw._load_friends_cache()
            gw._friends = cached
            gw._friends_ts = ts
        if cached and not refresh and (time.time() - ts) < 300:
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
            gw._friends_ts = time.time()
            gw._store_friends_cache(friends, gw._friends_ts)
            return {"friends": friends}
        except Exception as e:
            logger.warning(f"[dyf] 拉取好友列表失败: {e}")
            return {"friends": [], "detail": f"拉取失败: {e}"}

    async def platforms(self):
        """已加载的平台实例列表（多实例级联选择）。

        返回 [{id, type, name}]：id=实例唯一标识（UMO 前缀），type=适配器类型（aiocqhttp/qq_official），
        name=用户友好名。平台管理器不可用时返回空并附 detail。
        """
        try:
            ctx = getattr(self, "context", None)
            pm = getattr(ctx, "platform_manager", None)
            if pm is None:
                return {"platforms": [], "detail": "当前 AstrBot 版本无 platform_manager，请手动填写适配器"}
            insts = pm.get_insts()
            out = []
            for p in insts or []:
                meta = getattr(p, "metadata", None) or getattr(p, "meta", None) or {}
                if isinstance(meta, dict):
                    pid = meta.get("id") or ""
                    ptype = meta.get("type") or ""
                    name = meta.get("name") or ""
                else:
                    pid = getattr(meta, "id", None) or ""
                    ptype = getattr(meta, "type", None) or ""
                    name = getattr(meta, "name", None) or ""
                pid = str(pid or "")
                if not pid:
                    continue
                out.append({"id": pid, "type": str(ptype or ""), "name": str(name or ptype or pid)})
            return {"platforms": out}
        except Exception as e:
            logger.warning(f"[dyf] 获取平台实例列表失败: {e}")
            return {"platforms": [], "detail": f"获取平台实例列表失败: {e}"}

    async def groups(self):
        """机器人可访问的群列表（AstrBot 适配器统一 get_group_list）。

        可选 ?platform_id=<实例id> 按指定平台实例拉取；未指定则回退统一 context.get_group_list()。
        返回 [{group_id, group_name}]；平台/版本不支持时优雅降级为手动输入。
        """
        try:
            from astrbot.api.web import request as web_request
            q = getattr(web_request, "args", None)
            platform_id = str(q.get("platform_id") or "") if q else ""
        except Exception:
            platform_id = ""
        try:
            ctx = getattr(self, "context", None)
            raw = None
            detail = ""
            if platform_id:
                pm = getattr(ctx, "platform_manager", None)
                inst = None
                if pm is not None:
                    for p in pm.get_insts() or []:
                        meta = getattr(p, "metadata", None) or getattr(p, "meta", None) or {}
                        pid = (meta.get("id") if isinstance(meta, dict) else getattr(meta, "id", None)) or ""
                        if str(pid or "") == platform_id:
                            inst = p
                            break
                if inst is None:
                    return {"groups": [], "detail": f"未找到平台实例 {platform_id}"}
                # 实例级群列表：多来源防御性尝试
                for attr in ("get_group_list", "fetch_group_list"):
                    fn = getattr(inst, attr, None)
                    if fn is not None:
                        try:
                            raw = await fn()
                            break
                        except Exception as e:
                            detail = f"实例 {attr} 失败: {e}"
                if raw is None:
                    helper = getattr(inst, "helper", None) or getattr(inst, "platform_helper", None)
                    fn = getattr(helper, "get_group_list", None) if helper else None
                    if fn is not None:
                        try:
                            raw = await fn()
                        except Exception as e:
                            detail = f"实例 helper 失败: {e}"
            if raw is None:
                gl = getattr(ctx, "get_group_list", None)
                if gl is None:
                    return {"groups": [], "detail": "当前 AstrBot 版本无 get_group_list，请手动输入群号"}
                raw = await gl()
            groups = []
            for item in raw or []:
                if isinstance(item, dict):
                    gid = item.get("group_id") or item.get("id") or item.get("group_id_str")
                    name = item.get("group_name") or item.get("name") or ""
                else:
                    gid = getattr(item, "group_id", None) or getattr(item, "id", None)
                    name = getattr(item, "group_name", None) or getattr(item, "name", None) or ""
                if gid:
                    groups.append({"group_id": str(gid), "group_name": str(name or "")})
            if not groups and detail:
                return {"groups": groups, "detail": detail}
            return {"groups": groups}
        except Exception as e:
            logger.warning(f"[dyf] 获取群列表失败: {e}")
            return {"groups": [], "detail": f"获取群列表失败: {e}"}

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
