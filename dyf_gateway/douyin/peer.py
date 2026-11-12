"""conversation_id 对端解析。

conversation_id 格式为 "0:{type}:{uidA}:{uidB}"，uid 顺序不固定。
对端 = 两个 uid 中 ≠ self_uid 的那个；均等于 self_uid 视为自己发给自己。
"""
from __future__ import annotations

import re

_CONV_RE = re.compile(r"^0:\d+:(\d+):(\d+)$")
_CONV_NUMERIC = re.compile(r"^\d+$")


def resolve_peer(conversation_id: str, self_uid: int | None) -> str | None:
    """返回对端 uid；无法判定（格式异常或 self_uid 未知）返回 None。"""
    if not conversation_id:
        return None
    m = _CONV_RE.match(conversation_id)
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    if self_uid is None:
        return None
    self_s = str(self_uid)
    if a == self_s and b == self_s:
        return None
    return b if a == self_s else a


def resolve_conv(conversation_id: str) -> tuple[int, str | None]:
    r"""按 conversation_id 形态判定会话类型。

    alemonjs receiver.js 推断规则：纯数字 `^\d+$` → 群聊(type=2, group_id=该值)；
    `0:1:uid:secuid` → 单聊(type=1, group_id=None)。互斥、无歧义；形态不匹配
    回退单聊(type=1)（兜底不丢消息）。
    """
    cid = conversation_id or ""
    if cid and _CONV_NUMERIC.match(cid):
        return 2, cid
    return 1, None


def is_outgoing(sender_id: int | None, self_uid: int | None) -> bool:
    """sender 与 self_uid 相等 → 本端发出消息。"""
    if sender_id is None or self_uid is None:
        return False
    return str(sender_id) == str(self_uid)
