"""限流：全局 + 按发送者，滑动窗口计数。"""
from __future__ import annotations

import time


class _Window:
    def __init__(self, max_per_min: int):
        self.max = max(1, max_per_min)
        self.stamps: list[float] = []

    def allow(self) -> bool:
        now = time.time()
        self.stamps = [t for t in self.stamps if now - t < 60]
        if len(self.stamps) >= self.max:
            return False
        self.stamps.append(now)
        return True


class RateLimiter:
    def __init__(
        self,
        global_enabled: bool = True,
        global_max_per_min: int = 30,
        sender_enabled: bool = True,
        sender_max_per_min: int = 10,
    ):
        self.global_enabled = global_enabled
        self.sender_enabled = sender_enabled
        self.sender_max_per_min = max(1, sender_max_per_min)
        self._global = _Window(global_max_per_min)
        self._senders: dict[str, _Window] = {}

    def allow(self, peer_id: str | None) -> bool:
        if self.global_enabled and not self._global.allow():
            return False
        if self.sender_enabled and peer_id:
            key = str(peer_id)
            window = self._senders.get(key)
            if window is None:
                window = _Window(self.sender_max_per_min)
                self._senders[key] = window
            if not window.allow():
                return False
        return True
