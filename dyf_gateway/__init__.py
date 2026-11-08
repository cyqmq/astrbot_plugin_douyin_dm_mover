"""Gateway 工厂：按配置选择接入层实现。新增平台在此注册。

注意：本模块顶层不得 import astrbot，否则子进程 worker（`python -m
gateway.douyin.worker`）在导入 `gateway` 包时会被 astrbot 拖垮。
astrbot 依赖仅在 build_gateway 内延迟导入。
"""
from __future__ import annotations

from dyf_core.model import InboundMessage  # noqa: F401  (接口约定)

from .base import MessageGateway


def build_gateway(config: dict) -> MessageGateway:
    from astrbot.api import logger  # 延迟导入，保持包顶层无 astrbot 依赖

    mode = str(config.get("gateway_mode") or "inprocess")
    if mode == "subprocess":
        from .subprocess_gateway import SubprocessGateway

        return SubprocessGateway(config)
    from .douyin.gateway import DouyinGateway

    if mode != "inprocess":
        logger.warning(f"[dyf] 未知 gateway_mode={mode!r}，回退到 inprocess")
    return DouyinGateway(config)
