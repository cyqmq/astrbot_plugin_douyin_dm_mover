"""LogRing：WebUI 日志页的环形缓冲（落盘持久化）。

捕获插件自身（消息含 ``[dyf]`` 前缀）的日志，保留最近若干条，
供视图「运行日志」页展示。落盘 JSONL（persist_path），插件重载后
新 LogRing 启动时加载最近若干条，避免日志被自动重载清空。

AstrBot 审查：统一使用 ``astrbot.api.logger``——本类作为标准
``logging.Handler`` 挂在它上面，不再直接使用 loguru sink。
"""
from __future__ import annotations

import json
import logging
import os
from collections import deque

from astrbot.api import logger as _astr_logger

_PERSIST_MAX_BYTES = 2_000_000  # 超过则重写为最近 maxlen 条，防无界增长


class LogRing(logging.Handler):
    def __init__(self, maxlen: int = 200, persist_path: str | None = None):
        super().__init__()
        self.setLevel(logging.DEBUG)
        self._items: deque = deque(maxlen=maxlen)
        self._attached = False
        self._persist_path = persist_path
        self._persist_size = 0
        if persist_path:
            self._load()

    # ---- logging.Handler ----
    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if "[dyf]" not in msg:
            return
        item = {
            "ts": int(record.created),
            "level": str(record.levelname or "INFO").lower(),
            "msg": str(msg)[:1000],
        }
        self._items.append(item)
        self._persist(item)

    # ---- 生命周期 ----
    def attach(self) -> None:
        if not self._attached:
            _astr_logger.addHandler(self)
            self._attached = True

    def detach(self) -> None:
        if self._attached:
            try:
                _astr_logger.removeHandler(self)
            finally:
                self._attached = False

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
