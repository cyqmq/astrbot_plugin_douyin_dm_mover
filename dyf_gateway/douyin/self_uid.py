"""self_uid 解析：配置 → 缓存 → 尽力自动。

优先级：
1. 配置显式 self_uid（最高）
2. data/self_uid.json 缓存（自动获取成功后写盘）
3. 尽力自动获取（无签名轻量请求，失败非致命，记一次告警）
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.request

from astrbot.api import logger as _log

from .vendored.auth import DouyinAuth

_CACHE_FILE = "self_uid.json"


class SelfIdentityResolver:
    def __init__(self, data_dir: str, configured_uid: str | int | None = None):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.configured_uid = self._norm(configured_uid)
        self._cache_path = os.path.join(data_dir, _CACHE_FILE)
        self._auto_attempted = False

    @staticmethod
    def _norm(value) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _load_cache(self) -> int | None:
        try:
            if os.path.exists(self._cache_path):
                with open(self._cache_path, encoding="utf-8") as f:
                    return self._norm(json.load(f).get("uid"))
        except Exception:
            pass
        return None

    def cache(self, uid: int | None) -> None:
        if uid is None:
            return
        try:
            with open(self._cache_path, "w", encoding="utf-8") as f:
                json.dump({"uid": int(uid)}, f, ensure_ascii=False)
        except Exception as e:
            _log.warning(f"[dyf] 缓存 self_uid 失败: {e}")

    def resolve(self, auth: DouyinAuth | None = None) -> int | None:
        if self.configured_uid is not None:
            return self.configured_uid
        cached = self._load_cache()
        if cached is not None:
            return cached
        if not self._auto_attempted:
            self._auto_attempted = True
            uid = self._auto_fetch(auth)
            if uid is not None:
                self.cache(uid)
                return uid
            _log.warning(
                "[dyf] self_uid 未能自动获取。请在插件配置填写 self_uid，"
                "或使用 /dyf uid <你的uid> 手动设置（用于判定私信对端）。"
            )
        return None

    async def resolve_async(self, auth: DouyinAuth | None = None) -> int | None:
        """async 版本：整段 resolve（含 urlopen 兜底）放线程，不阻塞事件循环。"""
        return await asyncio.to_thread(self.resolve, auth)

    @staticmethod
    def _auto_fetch(auth: DouyinAuth | None) -> int | None:
        """无签名轻量尝试 query/user。多数情况会被风控拒绝，仅作兜底。"""
        if auth is None or not auth.cookie:
            return None
        try:
            cookie_header = auth.cookie_str
            req = urllib.request.Request(
                "https://www.douyin.com/aweme/v1/web/query/user/"
                "?publish_video_strategy_type=2&device_platform=webapp",
                headers={
                    "Cookie": cookie_header,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Referer": "https://www.douyin.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            uid = data.get("user_uid")
            if uid:
                return int(uid)
        except Exception as e:
            _log.debug(f"[dyf] self_uid 自动获取失败: {e}")
        return None
