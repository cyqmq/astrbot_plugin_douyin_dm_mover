"""RecentStore：供 WebUI 视图展示的轻量内存追踪。

只保留最近若干条：谁给 bot 发过消息（发石者）与最近搬运记录。
不落盘——重启即清空，仅用于实时可视化。
"""
from __future__ import annotations

import time
from collections import deque

from dyf_core.model import InboundMessage


def _summary(text: str, limit: int = 80) -> str:
    if not text:
        return ""
    t = " ".join(text.split())
    return t if len(t) <= limit else t[: limit - 1] + "…"


class RecentStore:
    def __init__(self, max_senders: int = 60, max_records: int = 120):
        self._senders: deque = deque(maxlen=max_senders)
        self._records: deque = deque(maxlen=max_records)

    def add_sender(self, msg: InboundMessage) -> None:
        """记录一条入站消息（含发石者、类型、摘要）。"""
        self._senders.append(
            {
                "ts": int(msg.timestamp or time.time()),
                "peer_id": msg.peer_id,
                "peer_name": msg.peer_name or "",
                "type": msg.type.value,
                "text": _summary(msg.text),
                "is_outgoing": bool(msg.is_outgoing),
            }
        )

    def add_record(
        self,
        ts: int,
        msg_type: str,
        peer: str | None,
        target: str,
        ok: bool,
        error: str,
    ) -> None:
        """记录一次搬运结果（每目标一条）。"""
        self._records.append(
            {
                "ts": int(ts),
                "type": msg_type,
                "peer": peer or "",
                "target": target,
                "ok": bool(ok),
                "error": error or "",
            }
        )

    def senders(self, limit: int = 60) -> list[dict]:
        items = list(self._senders)
        return items[-limit:][::-1]  # 最新的在前

    def records(self, limit: int = 120) -> list[dict]:
        items = list(self._records)
        return items[-limit:][::-1]

    def clear(self) -> None:
        self._senders.clear()
        self._records.clear()
