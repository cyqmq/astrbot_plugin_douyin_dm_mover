"""登录态失效检测：关闭码/关键字 + 静默看门狗。"""
from __future__ import annotations

import time


class AuthFailureDetector:
    def __init__(
        self,
        close_codes: list[int] | None = None,
        keywords: list[str] | None = None,
        watchdog_minutes: int = 30,
    ):
        self.close_codes = set(close_codes or [4010, 4011, 4012])
        self.keywords = [k.lower() for k in (keywords or []) if k]
        self.watchdog_seconds = max(0, int(watchdog_minutes or 0)) * 60

    def check_close(self, close_code: int | None, close_msg: str = "") -> bool:
        if close_code is not None and int(close_code) in self.close_codes:
            return True
        return self.check_text(close_msg)

    def check_error(self, error) -> bool:
        return self.check_text(str(error))

    def check_text(self, text: str) -> bool:
        if not text:
            return False
        low = str(text).lower()
        return any(k in low for k in self.keywords)

    def check_silence(self, last_frame_ts: float | None) -> bool:
        """看门狗：长时间无帧视为僵死。None 表示从未有帧。"""
        if self.watchdog_seconds <= 0:
            return False
        if last_frame_ts is None:
            return True
        return (time.time() - last_frame_ts) > self.watchdog_seconds
