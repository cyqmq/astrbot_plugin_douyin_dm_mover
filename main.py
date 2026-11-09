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

# 重载兜底：AstrBot 清理 sys.modules 可能不彻底，主动清理本插件名前缀的
# 残留模块缓存，确保加载的是新代码而非旧缓存。只清本插件前缀，避免误伤
# 其它插件共享的裸名模块（config/core/utils 等）。
_PLUGIN_KEY = os.path.basename(_PLUGIN_ROOT)
for _key in list(sys.modules):
    if _key.startswith(_PLUGIN_KEY + "."):
        sys.modules.pop(_key, None)

from dyf_config import DEFAULT_DATA_DIR, DEFAULT_SOURCES
from dyf_core.dashboard import DashboardApi
from dyf_core.forward_manager import ForwardManager
from dyf_core.listener import MessageListener
from dyf_core.logs import LogRing
from dyf_gateway import build_gateway


@register(
    "astrbot_plugin_douyin_dm_mover",
    "cyqmq",
    "把抖音 Bot 账号收到的私信视频/分享卡片，自动搬进指定 QQ 群。",
    "0.6.1",
    "https://github.com/cyqmq/astrbot_plugin_douyin_dm_mover",
)
class DouyinForwardPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self._purge_own_modules()
        self.config = config if config is not None else {}
        cfg = dict(config or {})
        cfg.setdefault("_data_dir", DEFAULT_DATA_DIR)
        if not cfg.get("sources"):
            cfg["sources"] = DEFAULT_SOURCES
        self._cfg = cfg
        self.gateway = build_gateway(cfg)
        self.forward_manager = ForwardManager(context, cfg)
        self.listener = MessageListener(self.gateway, self.forward_manager)
        self.logring = LogRing()
        self.dashboard = DashboardApi(context, self.gateway, self.forward_manager, self.logring)
        self.dashboard.register()
        self._tasks: list[asyncio.Task] = []

    def _purge_own_modules(self) -> None:
        """清理本插件可能残留的模块缓存，确保重载时加载的是新代码。

        只清理 ``douyin_dm_mover.`` 前缀的子模块，不动裸名模块，
        避免误伤其它插件（其 config/core/utils 等可能与裸名冲突）。
        """
        key = "douyin_dm_mover"
        for _k in list(sys.modules):
            if _k.startswith(key + "."):
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
        self.gateway.set_self_uid(v)
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
