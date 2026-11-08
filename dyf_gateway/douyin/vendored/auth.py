"""最小 DouyinAuth 实现：解析 cookie 字符串，提供 cookie 字典与 cookie 头。

只保留 douyin_recv_msg 所需的字段（sessionid / cookie_str），
不引入 DouYin_Spider 的 builder/auth.py（1416 行）与 curl_cffi 依赖。
"""
from __future__ import annotations


def parse_cookie_str(cookie_str: str) -> dict[str, str]:
    """把 "k1=v1; k2=v2" 解析为字典。容忍空格与空段。"""
    out: dict[str, str] = {}
    if not cookie_str:
        return out
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        out[k.strip()] = v.strip()
    return out


class DouyinAuth:
    """持有所需 cookie 的最小认证对象。"""

    def __init__(self, cookie_str: str = "", web_protect: str = "", keys: str = ""):
        self.raw_cookie_str = cookie_str
        self.web_protect = web_protect
        self.keys = keys
        self.cookie: dict[str, str] = parse_cookie_str(cookie_str)
        self.cookie_str = self._serialize_cookie_str()

    def _serialize_cookie_str(self) -> str:
        """把 cookie 字典重排回 cookie 头字符串。"""
        return "; ".join(f"{k}={v}" for k, v in self.cookie.items())

    @property
    def sessionid(self) -> str:
        return self.cookie.get("sessionid", "")

    @property
    def uid(self) -> int | None:
        """自外部 resolver 填充后的 uid。"""
        return getattr(self, "_uid", None)

    @uid.setter
    def uid(self, value: int | None) -> None:
        self._uid = value
