"""conversation_id 对端解析。

conversation_id 格式为 "0:{type}:{uidA}:{uidB}"，uid 顺序不固定。
对端 = 两个 uid 中 ≠ self_uid 的那个；均等于 self_uid 视为自己发给自己。
"""
from __future__ import annotations

import re

_CONV_RE = re.compile(r"^0:\d+:(\d+):(\d+)$")


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


def is_outgoing(sender_id: int | None, self_uid: int | None) -> bool:
    """sender 与 self_uid 相等 → 本端发出消息。"""
    if sender_id is None or self_uid is None:
        return False
    return str(sender_id) == str(self_uid)
