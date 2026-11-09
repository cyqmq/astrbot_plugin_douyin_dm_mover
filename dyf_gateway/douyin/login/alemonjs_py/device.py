"""桌面设备身份（@alemonjs/douyin auth/device-profile.js 回退路径移植）。

官方 setupDesktopDevice：已存身份刷新注册；无身份时硬件注册签发 DID；失败回退
GUID 哈希（十进制）。非 Windows 部署无 WMI，readDesktopHardware 抛错走回退路径
——此处实现回退路径（guidDeviceId + device.json 持久化 + saved 复用），与官方在
Linux/Docker 下的实际行为一致，保证 check_qrconnect 携带非零 device_id（避免限频）。
"""
from __future__ import annotations

import json
import os
import uuid


def guid_device_id(guid: str) -> str:
    """Eo(app.getGuid()) 兜底：GUID → 非零十进制 deviceId。"""
    h = 0
    for ch in guid:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    return str(h)


def random_guid() -> str:
    return uuid.uuid4().hex


def setup_desktop_device(device_file: str, http) -> dict:
    """登录前的桌面设备身份：读取/生成身份（device.json），回退 GUID 哈希。

    与官方非 Windows 行为一致：readDesktopHardware 不可用 → 直接回退
    guidDeviceId(guid)，并持久化到 device_file，后续登录复用。
    """
    saved = None
    try:
        with open(device_file, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except Exception:
        saved = None
    guid = (saved or {}).get("guid") or random_guid()
    if saved and saved.get("deviceId"):
        identity = {
            "deviceId": str(saved["deviceId"]),
            "installId": str(saved.get("installId") or "0"),
            "guid": str(saved.get("guid") or guid),
        }
    else:
        identity = {"deviceId": guid_device_id(guid), "installId": "0", "guid": guid}
    try:
        os.makedirs(os.path.dirname(device_file) or ".", exist_ok=True)
        with open(device_file, "w", encoding="utf-8") as f:
            json.dump(identity, f)
    except Exception:
        pass
    if http is not None:
        http.set_device(identity)
    return identity
