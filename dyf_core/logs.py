"""LogRing：WebUI 日志页的环形缓冲（落盘持久化）。

捕获插件自身（消息含 ``[dyf]`` 前缀）的 loguru 日志，保留最近若干条，
供视图「运行日志」页展示。落盘 JSONL（persist_path），插件重载后
新 LogRing 启动时加载最近若干条，避免日志被自动重载清空。
"""
from __future__ import annotations

import json
import os
import time
from collections import deque

from loguru import logger

_PERSIST_MAX_BYTES = 2_000_000  # 超过则重写为最近 maxlen 条，防无界增长


class LogRing:
    def __init__(self, maxlen: int = 200, persist_path: str | None = None):
        self._items: deque = deque(maxlen=maxlen)
        self._sink_id: int | None = None
        self._persist_path = persist_path
        self._persist_size = 0
        if persist_path:
            self._load()

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
        item = {
            "ts": int(ts()) if callable(ts) else int(time.time()),
            "level": str(level_name or "info").lower(),
            "msg": str(rec.get("message", ""))[:1000],
        }
        self._items.append(item)
        self._persist(item)

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

    # ---- 持久化 ----
    def _load(self) -> None:
        try:
            if not os.path.exists(self._persist_path):
                return
            self._persist_size = os.path.getsize(self._persist_path)
            with open(self._persist_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        self._items.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            pass

    def _persist(self, item: dict) -> None:
        if not self._persist_path:
            return
        try:
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            self._persist_size += len(item["msg"]) + 64
            if self._persist_size > _PERSIST_MAX_BYTES:
                self._rewrite()
        except Exception:
            pass

    def _rewrite(self) -> None:
        try:
            with open(self._persist_path, "w", encoding="utf-8") as f:
                f.writelines(
                    json.dumps(item, ensure_ascii=False) + "\n" for item in self._items
                )
            self._persist_size = os.path.getsize(self._persist_path)
        except Exception:
            pass

    # ---- 查询 ----
    def entries(self, limit: int = 200) -> list[dict]:
        items = list(self._items)
        return items[-limit:][::-1]  # 最新的在前

    def clear(self) -> None:
        self._items.clear()
        if self._persist_path:
            try:
                open(self._persist_path, "w").close()  # 截断，非删除
                self._persist_size = 0
            except Exception:
                pass
