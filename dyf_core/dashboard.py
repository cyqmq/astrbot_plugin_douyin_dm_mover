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
import json
import re
import time

import qrcode
from astrbot.api import logger

from dyf_core.logs import LogRing
from dyf_core.model import validate_block


def _targets_of(r: dict) -> list[str]:
    """路由配置的 targets 列表（targets 优先，target 兼容旧配置）。"""
    ts = r.get("targets") or ([r.get("target")] if r.get("target") else [])
    return [str(t) for t in ts if t]


_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([^{}]+)\}(?!\})")
_ALLOWED_PLACEHOLDERS = {"source", "peer_name", "time", "title", "desc", "link", "image_url"}


def _bad_placeholders(content: str) -> list[str]:
    """返回内容中非法占位符列表（跳过 {{ }} 转义；空=全部合法）。"""
    bad = []
    for m in _PLACEHOLDER_RE.finditer(content):
        key = m.group(1).strip()
        if key not in _ALLOWED_PLACEHOLDERS:
            bad.append(key)
    return bad


def _route_diff(old_list, new_list) -> list[str]:
    """路由表结构化 diff（按 name 匹配）：增/删/目标变更/来源连接±/类型±；忽略 pos。

    返回人类可读行列表（不含 [dyf] 前缀），供 config_set 逐条日志。
    """
    old = {r.get("name"): r for r in old_list or [] if isinstance(r, dict) and r.get("name")}
    new = {r.get("name"): r for r in new_list or [] if isinstance(r, dict) and r.get("name")}
    lines: list[str] = []
    for name, nr in new.items():
        if name not in old:
            lines.append(f'+ 路由 "{name}" → {", ".join(_targets_of(nr)) or "未连接目标"}')
            continue
        orr = old[name]
        ot = _targets_of(orr)
        nt = _targets_of(nr)
        if ot != nt:
            lines.append(
                f'~ 路由 "{name}" 目标: {", ".join(ot) or "(无)"} → {", ".join(nt) or "(无)"}'
            )
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
        reg("douyin_dm_mover/reload", self.reload_plugin, ["POST"], "dyf 重载插件（刷新深层代码）")
        reg("douyin_dm_mover/mfa", self.submit_mfa, ["POST"], "dyf 提交短信验证码")
        reg("douyin_dm_mover/config/get", self.config_get, ["GET"], "dyf 读取配置 + schema")
        reg("douyin_dm_mover/config/set", self.config_set, ["POST"], "dyf 保存配置")
        reg("douyin_dm_mover/profile", self.profile, ["GET"], "dyf 账户昵称/头像")
        reg("douyin_dm_mover/friends", self.friends, ["GET"], "dyf 好友列表（familiar-list）")
        reg("douyin_dm_mover/groups", self.groups, ["GET"], "dyf 机器人可访问群列表（目标平台）")
        reg("douyin_dm_mover/source_groups", self.source_groups, ["GET"], "dyf 抖音源群列表（conversation/list cmd=2006）")
        reg("douyin_dm_mover/umos", self.umos, ["GET"], "dyf 已记录会话 UMO 列表")
        reg("douyin_dm_mover/follow", self.follow, ["POST"], "dyf 回关/取关好友")
        reg("douyin_dm_mover/import_cookies", self.import_cookies, ["POST"], "dyf 手动导入 www 网页登录 Cookie（建 BDTicket）")
        reg("douyin_dm_mover/groups", self.groups, ["GET"], "dyf 可发送群列表（AstrBot get_group_list）")
        reg("douyin_dm_mover/platforms", self.platforms, ["GET"], "dyf 已加载平台实例列表")
        reg("douyin_dm_mover/templates/get", self.templates_get, ["GET"], "dyf 读取推送模板")
        reg("douyin_dm_mover/templates/set", self.templates_set, ["POST"], "dyf 保存推送模板（含校验）")
        reg("douyin_dm_mover/render", self.render, ["POST"], "dyf 积木渲染预览（同源）")
        reg("douyin_dm_mover/messages/draft", self.draft_get, ["GET"], "dyf 读取消息草稿")
        reg("douyin_dm_mover/messages/draft", self.draft_set, ["POST"], "dyf 保存消息草稿")
        reg("douyin_dm_mover/messages/publish", self.publish, ["POST"], "dyf 发布草稿（渲染+发送）")

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
            self._log_config_diagnose("重载后")
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
            "login_backend_active": str(getattr(self.gateway, "_login_backend", "") or ""),
            "senders_count": len(fm.tracker.senders()),
            "records_count": len(fm.tracker.records()),
        }

    async def senders(self):
        return {"senders": self.fm.tracker.senders()}

    async def source_groups(self):
        """抖音源群列表（前端来源卡群下拉）；subprocess 模式无该方法则返回空。"""
        fn = getattr(self.gateway, "fetch_groups", None)
        try:
            g = await fn() if callable(fn) else []
        except Exception:
            g = []
        return {"groups": list(g or [])}

    async def umos(self):
        """已记录会话 UMO 列表（AstrBot SessionManagementService.list_active_umos）。

        进程内调会话服务，免 Dashboard token（不会 401）；display_name 缺失回退完整 umo。
        """
        try:
            from astrbot.api.web import request as web_request

            # proxy 无 app → 取原始 FastAPI request（PluginRequest._request），
            # 与 AstrBot get_service 同一路径：request.app.state.services.sessions
            raw_req = getattr(web_request, "_request", None)
            app = getattr(raw_req, "app", None) if raw_req is not None else None
            services = (
                getattr(getattr(app, "state", None), "services", None)
                if app is not None
                else None
            )
            sessions = getattr(services, "sessions", None)
            if sessions is None or not hasattr(sessions, "list_active_umos"):
                return {"umos": [], "detail": "无 sessions.list_active_umos 服务"}
            raw = await sessions.list_active_umos()  # list_active_umos 是 async
            items = raw.get("umo_infos") or raw.get("umos") or [] if isinstance(raw, dict) else (raw or [])
            infos = []
            for it in items:
                if isinstance(it, dict):
                    umo = str(it.get("umo") or it.get("umo_str") or "")
                    name = str(it.get("display_name") or it.get("name") or "")
                else:
                    umo = str(getattr(it, "umo", "") or "")
                    name = str(getattr(it, "display_name", "") or "")
                if umo:
                    infos.append({"umo": umo, "display_name": name or umo})
            return {"umos": infos}
        except Exception as e:
            logger.warning(f"[dyf] 获取活跃 UMO 失败: {e}")
            return {"umos": [], "detail": str(e)}

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

    def _diagnose_config(self) -> dict:
        """配置落盘/读回特征对比（诊断路由丢失）：免手动翻文件。"""
        import json as _json
        import os

        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "_conf_schema.json",
        )
        schema_has_routes = False
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_has_routes = "routes" in (_json.load(f) or {})
        except Exception:
            pass
        config_path = getattr(self._config_obj, "config_path", "") or ""
        disk_path = ""
        disk_routes = -1  # -1 = 文件不存在
        if config_path and os.path.exists(config_path):
            disk_path = str(config_path)
            try:
                # AstrBot save_config 写盘是 utf-8-sig（带 BOM）——用 utf-8 读会报
                # Unexpected UTF-8 BOM 误判"解析失败"（disk_routes=-2），改用 utf-8-sig
                with open(config_path, "r", encoding="utf-8-sig") as f:
                    disk_routes = len((_json.load(f) or {}).get("routes") or [])
            except Exception:
                disk_routes = -2  # 解析失败
        runtime_routes = len(self.fm.config.get("routes") or [])
        return {
            "schema_has_routes": schema_has_routes,
            "disk_path": disk_path,
            "disk_routes": disk_routes,
            "runtime_routes": runtime_routes,
        }

    def _log_config_diagnose(self, stage: str) -> None:
        d = self._diagnose_config()
        logger.info(
            f"[dyf] 配置诊断({stage}): schema_routes={d['schema_has_routes']} "
            f"disk={d['disk_path'] or '(无)'} disk_routes={d['disk_routes']} "
            f"runtime_routes={d['runtime_routes']}"
        )

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
        old_backend = str(cfg.get("login_backend") or "")
        old_routes = None
        if "routes" in updates:
            import copy
            old_routes = copy.deepcopy(cfg.get("routes") or [])
        for k, v in updates.items():
            cfg[k] = v
        if "login_backend" in updates:
            new_backend = str(updates.get("login_backend") or "")
            if new_backend != old_backend:
                logger.info(
                    f"[dyf] 登录后端变更: {old_backend or '(空)'} -> {new_backend}（需重载插件生效，重载后登录卡片显示生效值）"
                )
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
                    # 诊断：save_config 抛但没打 [dyf] 日志（用户日志空）——带异常详情 + config_path
                    cfg_path = getattr(self._config_obj, "config_path", "") or ""
                    logger.warning(
                        f"[dyf] save_config 异常: {e!r} config_path={cfg_path!r}"
                    )
                    return {
                        "ok": False,
                        "detail": f"配置保存失败: {e}（config_path={cfg_path or '空'}）",
                    }
                self._log_config_diagnose("落盘后")
        # 配置已落盘；no_reload 用于实时静默保存（避免高频自动重载），否则自动重载插件使深层代码/运行时配置生效
        if not bool((data or {}).get("no_reload")):
            self._schedule_reload()
        return {"ok": True, "detail": "已保存并自动重载插件，稍候生效" if not bool((data or {}).get("no_reload")) else "已保存"}

    # ---- 推送模板（编辑器走独立端点，不走 AstrBot 配置页）----
    async def templates_get(self):
        """读取推送模板列表 + 相关配置（编辑器加载用）。"""
        return {
            "ok": True,
            "templates": self.fm.config.get("templates") or [],
            "markdown_enabled": bool(self.fm.config.get("markdown_enabled", True)),
            "sanitize_body": bool(self.fm.config.get("sanitize_body", True)),
            "max_message_length": int(self.fm.config.get("max_message_length", 1000) or 0),
        }

    async def templates_set(self):
        """保存推送模板：积木类型白名单 + block 结构校验，非法拒绝（400 语义走 detail）。"""
        try:
            from astrbot.api.web import request as web_request

            data = await web_request.json(default={}) or {}
        except Exception:
            data = {}
        templates = data.get("templates")
        if not isinstance(templates, list):
            return {"ok": False, "detail": "templates 必须是列表"}
        seen: set[str] = set()
        cleaned = []
        for t in templates:
            if not isinstance(t, dict):
                return {"ok": False, "detail": "模板项必须是对象"}
            tid = str(t.get("id") or "").strip()
            name = str(t.get("name") or "").strip()
            blocks = t.get("blocks")
            if not tid or not name:
                return {"ok": False, "detail": "模板 id/name 不能为空"}
            if tid in seen:
                return {"ok": False, "detail": f"模板 id 重复: {tid}"}
            seen.add(tid)
            if not isinstance(blocks, list) or not blocks:
                return {"ok": False, "detail": f"模板「{name}」blocks 不能为空"}
            for b in blocks:
                err = validate_block(b)
                if err:
                    return {"ok": False, "detail": f"模板「{name}」: {err}"}
            cleaned.append(
                {
                    "id": tid,
                    "name": name,
                    "blocks": blocks,
                    "for_media": bool(t.get("for_media", False)),
                }
            )
        self.fm.config["templates"] = cleaned
        self.fm.config["template_version"] = 2
        if self._config_obj is not None:
            try:
                self._config_obj.update({"templates": cleaned, "template_version": 2})
                save = getattr(self._config_obj, "save_config", None)
                if save is not None:
                    save()
            except Exception as e:
                logger.warning(f"[dyf] 模板落盘失败: {e!r}")
                return {"ok": False, "detail": f"模板保存失败: {e}"}
        logger.info(f"[dyf] 模板已保存: {len(cleaned)} 个")
        # 不自动重载：builder 动态读 config 即即时生效
        return {"ok": True, "detail": f"已保存 {len(cleaned)} 个模板"}

    # ---- 积木渲染预览（预览与转发同源，共用 builder.render_blocks）----
    async def render(self):
        """积木序列 → 渲染文本（模拟上下文；转发用真实上下文，同一 render_blocks）。"""
        try:
            from astrbot.api.web import request as web_request

            data = await web_request.json(default={}) or {}
        except Exception:
            data = {}
        blocks = data.get("blocks")
        if not isinstance(blocks, list):
            return {"ok": False, "detail": "blocks 必须是列表"}
        for b in blocks:
            err = validate_block(b)
            if err:
                return {"ok": False, "detail": err}
        ctx = {
            "source": "抖音",
            "peer_name": "示例用户",
            "time": "14:32",
            "title": "示例标题",
            "desc": "示例描述",
            "link": "https://example.com/video/1",
            "image_url": "https://example.com/cover.jpg",
        }
        content = self.fm.builder.render_blocks(
            blocks, ctx, markdown=bool(data.get("markdown", True))
        )
        return {"ok": True, "content": content}

    # ---- 消息草稿（blocks JSON 字符串存储）----
    async def draft_get(self):
        """读取消息草稿（blocks 数组）。"""
        raw = self.fm.config.get("draft") or ""
        blocks = []
        if raw:
            try:
                blocks = json.loads(raw)
            except Exception:
                blocks = []
        return {"ok": True, "blocks": blocks, "draft": raw}

    async def draft_set(self):
        """保存消息草稿（blocks 校验后 JSON 序列化存储，不重载）。"""
        try:
            from astrbot.api.web import request as web_request

            data = await web_request.json(default={}) or {}
        except Exception:
            data = {}
        blocks = data.get("blocks")
        if not isinstance(blocks, list):
            return {"ok": False, "detail": "blocks 必须是列表"}
        for b in blocks:
            err = validate_block(b)
            if err:
                return {"ok": False, "detail": err}
        raw = json.dumps(blocks, ensure_ascii=False)
        self.fm.config["draft"] = raw
        if self._config_obj is not None:
            try:
                self._config_obj.update({"draft": raw})
                save = getattr(self._config_obj, "save_config", None)
                if save is not None:
                    save()
            except Exception as e:
                return {"ok": False, "detail": f"草稿保存失败: {e}"}
        return {"ok": True, "detail": "草稿已保存"}

    # ---- 发布草稿：积木渲染 → 发送（走现有 sender 链路）----
    async def publish(self):
        """发布：blocks → 渲染文本 → 发送到目标（默认 default_target_group）。"""
        try:
            from astrbot.api.web import request as web_request

            data = await web_request.json(default={}) or {}
        except Exception:
            data = {}
        blocks = data.get("blocks")
        if not isinstance(blocks, list):
            return {"ok": False, "detail": "blocks 必须是列表"}
        for b in blocks:
            err = validate_block(b)
            if err:
                return {"ok": False, "detail": err}
        target = str(data.get("target") or self.fm.default_target_group or "")
        if not target:
            return {"ok": False, "detail": "未指定发布目标（target 或 default_target_group 为空）"}
        ctx = {
            "source": "手动",
            "peer_name": "",
            "time": time.strftime("%H:%M"),
            "title": "",
            "desc": "",
            "link": "",
            "image_url": "",
        }
        ctx.update(data.get("context") or {})
        markdown = bool(data.get("markdown", True))
        content = self.fm.builder.render_blocks(blocks, ctx, markdown=markdown)
        if not content.strip():
            return {"ok": False, "detail": "渲染内容为空"}
        ok, err = await self.fm.sender.send_raw_text(target, content)
        return {"ok": ok, "detail": "" if ok else err, "content": content}

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
        if prof and (time.time() - pts) < 300 and prof.get("avatar"):
            return {"profile": prof, "cached": True}
        # 重取条件：头像缺失或已过期（登录成功时 qr 风控可能写入空头像 dict，
        # 若只按"prof 为空"重拉会跳过——真实头像永远不拉取）
        stale = (time.time() - pts) >= 300
        if gw.auth_state.value == "ok" and (not prof or not prof.get("avatar") or stale):
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
                    http.set_device({"deviceId": dev})
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
                fetch_contact_lists,
                fetch_desktop_self_profile,
            )

            auth = getattr(gw, "_auth", None)
            cookie_str = getattr(auth, "cookie_str", "") or ""
            if not cookie_str:
                return {"friends": [], "detail": "无会话 Cookie"}
            # 诊断：登录态 cookie 键（看有没有 BDTicket/bd_ticket_guard/__ac_nonce）；探针残留，降 debug
            logger.debug(
                "[dyf] COOKIE_KEYS: "
                + ", ".join(
                    sorted(
                        k.split("=")[0].strip()
                        for k in cookie_str.split(";")
                        if "=" in k
                    )
                )
            )
            dev = getattr(gw, "_device_id", "") or "0"
            http = DouyinHttpPy(cookie_str)
            http.set_device({"deviceId": dev})
            # 挂 BDTicket（登录时建证书，ts_sign/private_key/client_cert/server_cert）
            try:
                http.set_bd_ticket(gw._login_flow.session.load_bd_ticket())
            except Exception:
                pass
            # 域隔离（探针 2026-11-12）：following/follower 走 www 登录态（导入的 www cookie，
            # 含 bd-web-sign-page-guard 免私钥材料）；familiar 走主登录(imdesktop) http。
            www_http = None
            try:
                www = gw._login_flow.session.load_www()
            except Exception:
                www = {}
            if (www or {}).get("cookie_str"):
                www_http = DouyinHttpPy(www["cookie_str"])
                www_http.set_device({"deviceId": dev})
                try:
                    www_http.set_bd_ticket(www)
                except Exception:
                    pass
            # following/follower 需要本人真实 uid/sec_uid（uid_tt 是加密值不能当 uid，
            # 用 profile/self 拿真实 uid；profile 失败才 fallback session 持久化的
            # uid/sec_uid，绝不读 uid_tt——否则 www 链路被跳过）
            uid = ""
            sec_uid = ""
            try:
                prof = await asyncio.to_thread(fetch_desktop_self_profile, http)
                uid = prof.get("uid") or ""
                sec_uid = prof.get("sec_uid") or ""
            except Exception as exc:
                logger.warning(f"[dyf] 拉取 self profile 失败(仅 familiar): {exc}")
            # profile 失败或 sec_uid 缺失（风控）：从持久化 session 读 uid/sec_uid，
            # 否则 fetch_contact_lists 的 with_www 条件不满足，following/follower 被跳过
            if not uid or not sec_uid:
                try:
                    sess = gw._login_flow.session.load() or {}
                except Exception:
                    sess = {}
                uid = uid or str(sess.get("uid") or getattr(auth, "uid", None) or "")
                sec_uid = sec_uid or (sess.get("sec_uid") or "")
            friends = await asyncio.to_thread(
                fetch_contact_lists,
                http,
                uid,
                sec_uid,
                bool(www_http),
                www_http,
            )
            gw._friends = friends
            gw._friends_ts = time.time()
            gw._store_friends_cache(friends, gw._friends_ts)
            # 域隔离（探针 2026-11-12）：familiar 走 imdesktop 主登录态；following/follower
            # 走 www 登录态（需 www cookie 导入）。无 www cookie 时 following/follower 缺失提示。
            detail = ""
            fam_err = getattr(http, "familiar_error", "") or ""
            www_err = getattr(www_http, "www_errors", "") if www_http else ""
            if fam_err and www_err:
                detail = f"familiar 拉取失败: {fam_err}; following/follower 拉取失败: {www_err}"
            elif fam_err:
                detail = f"familiar 拉取失败: {fam_err}"
            elif not www_http:
                detail = "following/follower 需 www 登录态——好友页「导入 Cookie」（浏览器 www.douyin.com 登录复制 Cookie 串）"
            elif www_err:
                detail = f"following/follower 拉取失败: {www_err}"
            return {"friends": friends, "detail": detail}
        except Exception as e:
            logger.warning(f"[dyf] 拉取好友列表失败: {e}")
            return {"friends": [], "detail": f"拉取失败: {e}"}

    async def follow(self):
        """回关/取关好友：POST {uid, sec_uid, action=1关注/2取关}。返回 {ok, detail}。"""
        try:
            from astrbot.api.web import request as web_request

            data = await web_request.json(default={}) or {}
        except Exception:
            data = {}
        uid = str((data or {}).get("uid") or "")
        sec_uid = str((data or {}).get("sec_uid") or "")
        action = int((data or {}).get("action") or 1)
        if not uid or not sec_uid:
            return {"ok": False, "detail": "缺少 uid/sec_uid"}
        gw = self.gateway
        if gw.auth_state.value != "ok":
            return {"ok": False, "detail": "未登录"}
        auth = getattr(gw, "_auth", None)
        cookie_str = getattr(auth, "cookie_str", "") or ""
        if not cookie_str:
            return {"ok": False, "detail": "无会话 Cookie"}
        dev = getattr(gw, "_device_id", "") or "0"
        try:
            from dyf_gateway.douyin.follow import follow_user, unfollow_user
            from dyf_gateway.douyin.login.alemonjs_py import DouyinHttpPy

            http = DouyinHttpPy(cookie_str)
            http.set_device({"deviceId": dev})
            try:
                http.set_bd_ticket(gw._login_flow.session.load_bd_ticket())
            except Exception:
                pass
            fn = follow_user if action == 1 else unfollow_user
            return await asyncio.to_thread(fn, http, uid, sec_uid)
        except Exception as e:
            logger.warning(f"[dyf] 关注操作失败: {e}")
            return {"ok": False, "detail": f"关注操作失败: {e}"}

    async def import_cookies(self):
        """手动导入 www 网页登录 Cookie（建 BDTicket）：POST {cookie_str, ts_sign?, private_key?, client_cert?, server_cert?}。"""
        try:
            from astrbot.api.web import request as web_request

            data = await web_request.json(default={}) or {}
        except Exception:
            data = {}
        cookie_str = str((data or {}).get("cookie_str") or "")
        ts_sign = str((data or {}).get("ts_sign") or "")
        private_key = str((data or {}).get("private_key") or "")
        client_cert = str((data or {}).get("client_cert") or "")
        server_cert = str((data or {}).get("server_cert") or "")
        if not cookie_str:
            return {"ok": False, "detail": "缺少 cookie_str（浏览器 www.douyin.com 登录后复制完整 Cookie 串）"}
        try:
            from dyf_gateway.douyin.login.alemonjs_py.bd_ticket import (
                import_www_session,
            )

            res = await asyncio.to_thread(
                import_www_session,
                cookie_str,
                ts_sign,
                private_key,
                client_cert,
                server_cert,
            )
            if res.get("error"):
                return {"ok": False, "detail": res["error"]}
            gw = self.gateway
            await gw.import_login(res["cookie_str"], res)
            return {"ok": True, "detail": "登录态已导入，接收端已用导入会话重启"}
        except Exception as e:
            logger.warning(f"[dyf] 导入登录态失败: {e}")
            return {"ok": False, "detail": f"导入失败: {e}"}

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
                    # 无 metadata 的适配器（如 qq_official：Platform.__init__ 不设 self.metadata）
                    # 回退实例 config.id（manager.load_platform 用 platform_config["id"] 作实例标识），
                    # 否则被 continue 丢弃 → 目标卡永远无该平台（配了也读不到 id）
                    pcfg = getattr(p, "config", None) or {}
                    if isinstance(pcfg, dict):
                        pid = str(pcfg.get("id") or "")
                        ptype = ptype or str(pcfg.get("type") or "")
                        name = name or str(pcfg.get("name") or "")
                    if not pid:
                        continue
                # 高级目标卡（advanced_target_cards）开启才显示 webchat（网页聊天，默认隐藏）
                show_all = bool(
                    (getattr(self, "fm", None) and self.fm.config or {}).get(
                        "advanced_target_cards", False
                    )
                )
                if not show_all and (pid == "webchat" or str(ptype).lower() == "webchat"):
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
        # 刷新：取消当前登录任务，重新触发（否则 _logging_in=True 时 gateway.login 直接返回，不生成新码）
        old = getattr(self, "_login_task", None)
        if old is not None and not old.done():
            old.cancel()
        self._login_task = asyncio.create_task(self.gateway.login(timeout))
