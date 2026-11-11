"""登录会话持久化：Cookie/Session 存到插件 data 目录。

参考 douyin-im 的 dataDir 与 douyin-chat-mcp-server 的卷映射设计——会话文件
落在 AstrBot 插件数据目录（data/dyf/session.json），便于备份与容器化部署。

登录成功后把 builder.auth.DouyinAuth 的关键字段落盘；重启时据此重建 auth，
无需用户手动复制 cookie。登录与私信接收共享同一份 cookie（见 gateway.py）。
"""
from __future__ import annotations

import json
import os
import time

from .loader import load_douyin_auth

_SESSION_FILE = "session.json"


class SessionStore:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.path = os.path.join(data_dir, _SESSION_FILE)

    def save(self, auth, backend: str | None = None) -> dict:
        """从登录后的 auth 提取并落盘，返回持久化 dict。

        ``backend`` 标记登录后端（alemonjs / douyin_spider）；alemonjs 会话
        无 ticket/private_key（由 SDK cookie 直接建 WS），has_valid 据此放宽。
        """
        cookie = dict(getattr(auth, "cookie", None) or {})
        data = {
            "cookie": cookie,
            "cookie_str": "; ".join(f"{k}={v}" for k, v in cookie.items()),
            "ticket": getattr(auth, "ticket", None) or "",
            "ts_sign": getattr(auth, "ts_sign", None) or "",
            "client_cert": getattr(auth, "client_cert", None) or "",
            "private_key": getattr(auth, "private_key", None) or "",
            "server_cert": getattr(auth, "server_cert", None) or "",
            "dtrait_blob": getattr(auth, "dtrait_blob", None) or "",
            "uid": getattr(auth, "uid", None),
            "device_id": cookie.get("device_id") or getattr(auth, "device_id", None),
            "backend": backend or getattr(auth, "_login_backend", None) or "douyin_spider",
            "saved_at": int(time.time()),
        }
        self._write(data)
        return data

    def load(self) -> dict | None:
        try:
            if os.path.exists(self.path):
                with open(self.path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("cookie"):
                    return data
        except Exception:
            pass
        return None

    def has_valid(self) -> bool:
        """有效 = 有 sessionid（alemonjs 后端用 cookie 直连即可，其余还需 ticket/private_key）。"""
        data = self.load()
        if not data:
            return False
        cookie = data.get("cookie") or {}
        if not cookie.get("sessionid"):
            return False
        if data.get("backend") == "alemonjs":
            return True
        return bool(data.get("ticket") and data.get("private_key"))

    def build_auth(self):
        """按保存的会话重建 builder.auth.DouyinAuth；无效返回 None。"""
        data = self.load()
        if not data:
            return None
        cookie = data.get("cookie") or {}
        cookie_str = data.get("cookie_str") or "; ".join(
            f"{k}={v}" for k, v in cookie.items()
        )
        auth = load_douyin_auth()()
        auth.perepare_auth(cookie_str, "", "")
        auth.ticket = data.get("ticket") or ""
        auth.ts_sign = data.get("ts_sign") or ""
        auth.client_cert = data.get("client_cert") or ""
        auth.private_key = data.get("private_key") or ""
        auth.server_cert = data.get("server_cert") or ""
        auth.dtrait_blob = data.get("dtrait_blob") or ""
        auth.uid = data.get("uid")
        if data.get("device_id"):
            auth.device_id = data["device_id"]
        return auth

    def cookie_str(self) -> str:
        data = self.load()
        if not data:
            return ""
        return data.get("cookie_str") or "; ".join(
            f"{k}={v}" for k, v in (data.get("cookie") or {}).items()
        )

    def load_bd_ticket(self) -> dict:
        """载入持久化 BDTicket（ts_sign/private_key/client_cert/server_cert）。"""
        data = self.load()
        if not data:
            return {}
        return {
            "ts_sign": data.get("ts_sign") or "",
            "private_key": data.get("private_key") or "",
            "client_cert": data.get("client_cert") or "",
            "server_cert": data.get("server_cert") or "",
        }

    def clear(self) -> None:
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except Exception:
            pass

    def _write(self, data: dict) -> None:
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except Exception:
            pass
