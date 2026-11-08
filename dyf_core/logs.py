"""LogRing：WebUI 日志页的环形缓冲。

捕获插件自身（消息含 ``[dyf]`` 前缀）的 loguru 日志，保留最近若干条，
供视图「运行日志」页展示。不落盘——重启即清空，用于实时观察报错。
"""
from __future__ import annotations

import time
from collections import deque

from loguru import logger


class LogRing:
    def __init__(self, maxlen: int = 200):
        self._items: deque = deque(maxlen=maxlen)
        self._sink_id: int | None = None

    # ---- loguru sink（未指定 format 时收到 Message 对象，含 .record）----
    def write(self, message) -> None:
        rec = getattr(message, "record", None)
        if not rec:
            return
        ts = getattr(rec.get("time"), "timestamp", None)
        level = rec.get("level")
        level_name = getattr(level, "name", None)
        if level_name is None and isinstance(level, dict):
            level_name = level.get("name")
        self._items.append(
            {
                "ts": int(ts()) if callable(ts) else int(time.time()),
                "level": str(level_name or "info").lower(),
                "msg": str(rec.get("message", ""))[:1000],
            }
        )

    def filter(self, record) -> bool:
        return "[dyf]" in str(record.get("message", ""))

    # ---- 生命周期 ----
    def attach(self) -> None:
        if self._sink_id is None:
            self._sink_id = logger.add(
                self.write, level="DEBUG", filter=self.filter, enqueue=True
            )

    def detach(self) -> None:
        if self._sink_id is not None:
            try:
                logger.remove(self._sink_id)
            finally:
                self._sink_id = None

    # ---- 查询 ----
    def entries(self, limit: int = 200) -> list[dict]:
        items = list(self._items)
        return items[-limit:][::-1]  # 最新的在前

    def clear(self) -> None:
        self._items.clear()
