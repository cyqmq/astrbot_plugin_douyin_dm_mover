"""按 sec_uid 批量拉用户昵称/头像（imdesktop 内部接口，无需 a_bogus 签名）。

POST https://imdesktop.douyin.com/aweme/v1/web/im/user/info/
form: sec_user_ids = JSON.stringify([sec_uid, ...])（批量 ≤50/次）
响应 {status_code:0, data:[{uid, sec_uid, nickname, avatar_thumb:{url_list:[url]}}]}
实测：16 成员 sec_uid → status_code=0, data=16, nickname+avatar_thumb 全返回真实值。
"""
from __future__ import annotations

import json
from urllib.parse import urlencode

_USER_INFO_URL = "https://imdesktop.douyin.com/aweme/v1/web/im/user/info/"

_USER_AGENT = (
    "douyinim/1.2.1 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) douyinim/1.2.1 Chrome/130.0.0.0 Electron/33.2.0 Safari/537.36"
)


class UserInfoCache:
    """内存缓存：sec_uid -> {uid, nickname, avatar}（参考 ImUserDirectory.cache）。"""

    def __init__(self):
        self._cache: dict[str, dict] = {}

    def get(self, sec_uid: str) -> dict | None:
        return self._cache.get(sec_uid)

    def put(self, sec_uid: str, profile: dict) -> None:
        if sec_uid:
            self._cache[sec_uid] = profile


def _fingerprint(device_id: str, guid: str = "") -> str:
    """desktopFingerprintParams query（实测字段；无 a_bogus 签名）。"""
    q = {
        "aid": "339757",
        "version_name": "1.2.1",
        "version_code": "1.2.1",
        "device_platform": "linux",
        "os_version": "6.1.0",
        "screen_width": "1728",
        "screen_height": "1117",
        "browser_language": "zh-CN",
        "browser_platform": "MacIntel",
        "browser_name": "Mozilla",
        "browser_version": "5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "browser_online": "true",
        "cookie_enabled": "true",
        "device_id": device_id,
        "did": device_id,
        "iid": "0",
        "awemeim_guid": guid,
        "channel": "0",
    }
    return urlencode(q)


def fetch_user_info(
    http,
    device_id: str,
    guid: str = "",
    sec_uids: list[str] | None = None,
    cache: UserInfoCache | None = None,
    timeout: int = 15,
) -> dict[str, dict]:
    """批量拉昵称/头像。返回 {sec_uid: {uid, nickname, avatar}}。

    去重、≤50/批、命中缓存跳过；失败/缺字段的 sec_uid 不返回（调用方兜底显示 uid）。
    """
    sec_uids = [s for s in dict.fromkeys(sec_uids or []) if s]
    result: dict[str, dict] = {}
    missing = [s for s in sec_uids if not (cache and cache.get(s))]
    for i in range(0, len(missing), 50):
        batch = missing[i : i + 50]
        url = f"{_USER_INFO_URL}?{_fingerprint(device_id, guid)}"
        try:
            resp = http.request_raw(
                url,
                method="POST",
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://imdesktop.douyin.com",
                    "User-Agent": _USER_AGENT,
                },
                body=f"sec_user_ids={json.dumps(batch)}".encode(),
                timeout=timeout,
            )
            if not resp.ok:
                continue
            data = json.loads(resp.content).get("data") or []
        except Exception:
            continue
        for u in data:
            sec = str(u.get("sec_uid") or "")
            if not sec:
                continue
            av = (u.get("avatar_thumb") or {}).get("url_list") or [""]
            profile = {
                "uid": str(u.get("uid") or ""),
                "nickname": str(u.get("nickname") or ""),
                "avatar": str(av[0] or ""),
            }
            if cache:
                cache.put(sec, profile)
            result[sec] = profile
    # 缓存命中项并入
    if cache:
        for s in missing:
            if s not in result and cache.get(s):
                result[s] = cache.get(s)
    return result


