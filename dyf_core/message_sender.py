"""MessageSender：实际向 QQ 群发送。已验证路径：
context.send_message(f"{adapter_id}:GroupMessage:{group_id}", chain)。
"""
from __future__ import annotations

from astrbot.api import logger
from astrbot.api.event import MessageChain


class MessageSender:
    def __init__(self, context, qq_adapter_id: str = "aiocqhttp"):
        self.context = context
        self.qq_adapter_id = qq_adapter_id or "aiocqhttp"

    def build_origin(self, group_id: str) -> str:
        return f"{self.qq_adapter_id}:GroupMessage:{group_id}"

    def normalize_target(self, target: str) -> tuple[str, str | None]:
        """把路由 target 归一化为 (origin, group_id|None)。

        支持三种写法：
        - 完整 origin："aiocqhttp:GroupMessage:123"
        - 简写："qq:group:123"
        - 纯群号："123"
        """
        t = str(target or "").strip()
        if not t:
            return "", None
        if t.startswith("qq:group:"):
            gid = t.split(":", 2)[2]
            return self.build_origin(gid), gid
        parts = t.split(":")
        if len(parts) == 3 and parts[1].lower().startswith("group"):
            return t, parts[2]
        if len(parts) == 1 and t.isdigit():
            return self.build_origin(t), t
        # 其他形态原样作为 origin
        return t, None

    async def send(self, target: str, chain: MessageChain) -> tuple[bool, str]:
        origin, _ = self.normalize_target(target)
        if not origin:
            return False, "空目标"
        try:
            await self.context.send_message(origin, chain)
            return True, ""
        except Exception as e:
            err = str(e) or type(e).__name__  # str(e) 可能为空，至少暴露异常类型
            logger.warning(f"[dyf] 发送到 {origin} 失败: {err}")
            return False, err

    async def send_raw_text(self, target: str, text: str) -> tuple[bool, str]:
        from astrbot.api.message_components import Plain

        return await self.send(target, MessageChain([Plain(text)]))


def is_qq_official_group_target(target: str) -> bool:
    """QQ 官方机器人仅支持群聊（私聊主动消息受限）；非官方适配器/纯群号放行。

    目标 UMO adapter=qq_official 且类型非 GroupMessage → False（拒绝）。
    aiocqhttp（NapCat）私聊不受限 → True；纯群号（无冒号）→ True。
    """
    parts = str(target or "").split(":")
    if len(parts) >= 3 and parts[0] == "qq_official":
        return parts[1] == "GroupMessage"
    return True
