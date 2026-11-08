"""缓存管理：去重窗口 + 失败发送缓存（持久化到 data/）。"""
from __future__ import annotations

import json
import os
import time


class CacheManager:
    def __init__(self, data_dir: str, window_seconds: int = 300, persist: bool = True):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.window_seconds = max(1, int(window_seconds))
        self.persist = persist
        self._seen: dict[str, float] = {}
        self.failed_path = os.path.join(data_dir, "failed_sends.json")
        self._failed: list[dict] = self._load_failed()

    # ---- 去重 ----
    def seen(self, key: str) -> bool:
        """若 key 在窗口内已见 → True；否则记录并返回 False。"""
        now = time.time()
        last = self._seen.get(key)
        if last is not None and now - last < self.window_seconds:
            return True
        self._seen[key] = now
        self._prune(now)
        return False

    def _prune(self, now: float) -> None:
        if len(self._seen) > 10000:
            stale = [k for k, t in self._seen.items() if now - t >= self.window_seconds]
            for k in stale:
                self._seen.pop(k, None)

    # ---- 失败发送 ----
    def _load_failed(self) -> list[dict]:
        try:
            if self.persist and os.path.exists(self.failed_path):
                with open(self.failed_path, encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
        return []

    def add_failed(self, target: str, msg: dict) -> None:
        self._failed.append({"target": target, "msg": msg, "ts": int(time.time())})
        if len(self._failed) > 500:
            self._failed = self._failed[-500:]
        self._save_failed()

    def remove_failed(self, target: str, msg_id: str) -> None:
        before = len(self._failed)
        self._failed = [
            f
            for f in self._failed
            if not (f.get("target") == target and (f.get("msg") or {}).get("message_id") == msg_id)
        ]
        if len(self._failed) != before:
            self._save_failed()

    def get_failed(self) -> list[dict]:
        return list(self._failed)

    def _save_failed(self) -> None:
        if not self.persist:
            return
        try:
            with open(self.failed_path, "w", encoding="utf-8") as f:
                json.dump(self._failed, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
