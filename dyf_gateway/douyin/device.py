"""device_id 解析：配置 → 缓存 → sessionid 派生。

无 astrbot 依赖，inprocess（DouyinGateway）与 subprocess（worker）共用。
"""
from __future__ import annotations

import hashlib
import json
import os

_DEVICE_CACHE = "device_id.json"


def resolve_device_id(config: dict, auth, data_dir: str) -> str:
    """返回数字 device_id：优先配置，其次 data/device_id.json 缓存，最后按 sessionid 稳定派生。

    抖音 WS 握手要求**数字** device_id（如 1226697491），hex（含 a-f）会
    导致握手 400 invalid device id。故配置/缓存值必须 isdigit() 才接受，
    派生路径统一产出 19 位数字。
    """
    cfg = config.get("device_id")
    if cfg and str(cfg).isdigit():
        return str(cfg)
    os.makedirs(data_dir, exist_ok=True)
    cache_path = os.path.join(data_dir, _DEVICE_CACHE)
    try:
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                did = json.load(f).get("device_id")
                if did and str(did).isdigit():
                    return str(did)
    except Exception:
        pass
    seed = getattr(auth, "sessionid", None) or "anonymous"
    # sha256 → 十进制 19 位数字（保持稳定、非 hex）
    did = str(int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % 10**19)
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"device_id": did}, f, ensure_ascii=False)
    except Exception:
        pass
    return did
