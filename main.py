"""astrbot_plugin_douyin_dm_mover：把抖音 Bot 账号收到的私信（含视频/分享卡片）
自动搬进指定 QQ 群。

装配与生命周期见 DESIGN.md §8。
"""
from __future__ import annotations

import asyncio
import os
import sys

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

_PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PLUGIN_ROOT in sys.path:
    sys.path.remove(_PLUGIN_ROOT)
sys.path.insert(0, _PLUGIN_ROOT)

# 重载兜底：AstrBot 清理 sys.modules 只清 data.plugins.<dir>.* 前缀，清不到本插件的
# 裸名包（dyf_gateway/dyf_core/dyf_config）与主模块路径，主动清理残留缓存，确保
# 重载时加载新代码而非旧缓存。只清本插件相关前缀，避免误伤其它插件共享的裸名模块。
_PLUGIN_MODULE_PREFIX = "astrbot_plugin_douyin_dm_mover"
_BARE_PLUGIN_PREFIXES = ("dyf_gateway", "dyf_core", "dyf_config")
for _key in list(sys.modules):
    if (
        _key.startswith(_BARE_PLUGIN_PREFIXES)
        or _PLUGIN_MODULE_PREFIX in _key
    ):
        sys.modules.pop(_key, None)

from dyf_config import DEFAULT_DATA_DIR, DEFAULT_SOURCES
from dyf_core.dashboard import DashboardApi
from dyf_core.forward_manager import ForwardManager
from dyf_core.listener import MessageListener
from dyf_core.logs import LogRing
from dyf_gateway import build_gateway


def _resolve_data_dir() -> str:
    """登录会话/设备等持久化目录：锚定到 AstrBot 数据目录（data/plugin_data/<插件>），
    确保插件更新/重装不会覆盖登录态。取不到 AstrBot 路径时回退到相对 data/dyf（绝对化）。"""
    try:
        from astrbot.core.utils.astrbot_path import get_astrbot_data_path

        target = os.path.join(str(get_astrbot_data_path()), "plugin_data", "douyin_dm_mover")
    except Exception:
        target = os.path.abspath(DEFAULT_DATA_DIR)
    # 迁移：旧版本把会话/设备存在相对 CWD 的 data/dyf，新目录为空时迁移过来，
    # 避免升级插件后登录态「消失」（session.json/device.json 仍在旧位置）。
    # 迁移源固定为旧路径字面量，不随 DEFAULT_DATA_DIR 收敛而漂移。
    old = os.path.abspath(os.path.join("data", "dyf"))
    if os.path.isdir(old) and old != target:
        os.makedirs(target, exist_ok=True)
        for name in ("session.json", "device.json"):
            src = os.path.join(old, name)
            dst = os.path.join(target, name)
            if os.path.isfile(src) and not os.path.isfile(dst):
                try:
                    import shutil

                    shutil.copy2(src, dst)
                except Exception as e:  # 迁移失败不阻断启动
                    logger.warning(f"[dyf] 登录态迁移 {name} 失败: {e}")
    return target


@register(
    "astrbot_plugin_douyin_dm_mover",
    "cyqmq",
    "把抖音 Bot 账号收到的私信视频/分享卡片，自动搬进指定 QQ 群。",
    "0.13.0",
    "https://github.com/cyqmq/astrbot_plugin_douyin_dm_mover",
)
class DouyinForwardPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self._purge_own_modules()
        self.config = config if config is not None else {}
        cfg = dict(config or {})
        cfg.setdefault("_data_dir", _resolve_data_dir())
        if not cfg.get("sources"):
            cfg["sources"] = DEFAULT_SOURCES
        self._cfg = cfg
        self.gateway = build_gateway(cfg, config_obj=config)
        self.forward_manager = ForwardManager(context, cfg)
        self.listener = MessageListener(self.gateway, self.forward_manager)
        self.logring = LogRing(persist_path=os.path.join(_resolve_data_dir(), "logs.jsonl"))
        self.dashboard = DashboardApi(context, self.gateway, self.forward_manager, self.logring, config_obj=config)
        self.dashboard.register()
        self._tasks: list[asyncio.Task] = []

    def _purge_own_modules(self) -> None:
        """清理本插件残留模块缓存，确保重载时加载新代码。

        清裸名包（dyf_gateway/dyf_core/dyf_config）前缀与含插件名的主模块键，
        避免误伤其它插件共享的裸名模块（config/core/utils 等）。
        """
        for _k in list(sys.modules):
            if (
                _k.startswith(_BARE_PLUGIN_PREFIXES)
                or _PLUGIN_MODULE_PREFIX in _k
            ):
                sys.modules.pop(_k, None)

    # ---- 生命周期 ----
    async def initialize(self) -> None:
        self.logring.attach()
        try:
            await self.gateway.start()
        except Exception as e:
            logger.error(f"[dyf] 网关启动失败: {e}")
            return
        self._tasks = [
            asyncio.create_task(self.listener.consume_messages()),
            asyncio.create_task(self.listener.consume_events()),
            asyncio.create_task(self.forward_manager.retry.run()),
        ]
        logger.info("[dyf] 插件已启动")

    async def terminate(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        self.logring.detach()
        try:
            await self.gateway.stop()
        except Exception as e:
            logger.warning(f"[dyf] 停止网关异常: {e}")

    # ---- 命令 ----
    @filter.command_group("dyf")
    def dyf_group(self):
        """抖音私信转发控制"""

    @dyf_group.command("status")
    async def dyf_status(self, event: AstrMessageEvent):
        event.stop_event()
        event.should_call_llm(False)
        st = self.gateway.auth_state.value
        uid = getattr(self.gateway, "self_uid", None)
        sources = self._cfg.get("sources") or {}
        src = sources.get("douyin", {}) if isinstance(sources, dict) else {}
        if not isinstance(src, dict):
            src = {}
        enabled = src.get("enabled", True)
        types = src.get("types", {})
        text = (
            "【dyf 状态】\n"
            f"登录态: {st}\n"
            f"self_uid: {uid or '未设置'}\n"
            f"抖音来源: {'启用' if enabled else '停用'}\n"
            f"类型开关: {types or '默认'}\n"
            f"路由数: {len(self.forward_manager.router.routes)}\n"
            f"失败缓存: {len(self.forward_manager.cache.get_failed())}"
        )
        yield event.plain_result(text).stop_event()

    @dyf_group.command("uid")
    async def dyf_uid(self, event: AstrMessageEvent, uid: str = ""):
        event.stop_event()
        event.should_call_llm(False)
        if not uid:
            yield event.plain_result("用法: /dyf uid <你的数字uid>").stop_event()
            return
        try:
            v = int(uid)
        except ValueError:
            yield event.plain_result("uid 必须是数字").stop_event()
            return
        await self.gateway.set_self_uid(v)
        yield event.plain_result(f"已设置并缓存 self_uid = {v}").stop_event()

    @dyf_group.command("login")
    async def dyf_login(self, event: AstrMessageEvent):
        event.stop_event()
        event.should_call_llm(False)
        timeout = int(self._cfg.get("login_timeout", 300))
        asyncio.create_task(self.gateway.login(timeout))
        yield event.plain_result("开始扫码登录，二维码将推送到告警目标（alert_target）").stop_event()

    @dyf_group.command("logout")
    async def dyf_logout(self, event: AstrMessageEvent):
        event.stop_event()
        event.should_call_llm(False)
        await self.gateway.logout()
        yield event.plain_result("已登出并清除会话").stop_event()

    @dyf_group.command("mfa")
    async def dyf_mfa(self, event: AstrMessageEvent, code: str = ""):
        event.stop_event()
        event.should_call_llm(False)
        if code:
            self.gateway.submit_mfa_code(code)
            yield event.plain_result("已提交验证码，等待登录放行").stop_event()
            return
        self.gateway.trigger_mfa_send()
        yield event.plain_result("已触发发送二次验证码；收到后请回复 /dyf mfa <验证码>").stop_event()

    @dyf_group.command("test")
    async def dyf_test(self, event: AstrMessageEvent, target: str = ""):
        event.stop_event()
        event.should_call_llm(False)
        t = target or self._cfg.get("default_target_group", "")
        if not t:
            yield (
                event.plain_result("未指定目标。用法: /dyf test <群号> 或在配置填 default_target_group")
                .stop_event()
            )
            return
        ok, err = await self.forward_manager.sender.send_raw_text(t, "dyf 测试消息")
        if ok:
            yield event.plain_result(f"测试消息已发送到 {t}").stop_event()
        else:
            yield event.plain_result(f"发送失败: {err}").stop_event()
