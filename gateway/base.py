"""MessageGateway 抽象接口：core/ 与具体平台之间唯一依赖边界。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from core.model import AuthState, GatewayEvent, InboundMessage


class MessageGateway(ABC):
    """接入层抽象。新增平台只需实现本接口并在 build_gateway 注册。"""

    @abstractmethod
    async def start(self) -> None:
        """启动后台 worker（线程或子进程）。"""

    @abstractmethod
    def stream(self) -> AsyncIterator[InboundMessage]:
        """归一化入站消息流。"""

    @abstractmethod
    def events(self) -> AsyncIterator[GatewayEvent]:
        """状态/告警事件流（auth_failure/disconnect/reconnect/error）。"""

    @abstractmethod
    async def stop(self) -> None:
        """停止 worker，清理资源。"""

    @property
    def auth_state(self) -> AuthState:
        return AuthState.UNKNOWN
