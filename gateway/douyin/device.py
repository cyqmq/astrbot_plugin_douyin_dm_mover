"""device_id 解析：配置 → 缓存 → sessionid 派生。

无 astrbot 依赖，inprocess（DouyinGateway）与 subprocess（worker）共用。
"""
from __future__ import annotations

import hashlib
import json
import os

_DEVICE_CACHE = "device_id.json"


def resolve_device_id(config: dict, auth, data_dir: str) -> str:
    """返回 device_id：优先配置，其次 data/device_id.json 缓存，最后按 sessionid 稳定派生。"""
    cfg = config.get("device_id")
    if cfg:
        return str(cfg)
    os.makedirs(data_dir, exist_ok=True)
    cache_path = os.path.join(data_dir, _DEVICE_CACHE)
    try:
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as f:
                did = json.load(f).get("device_id")
                if did:
                    return str(did)
    except Exception:
        pass
    seed = getattr(auth, "sessionid", None) or "anonymous"
    did = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:19]
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"device_id": did}, f, ensure_ascii=False)
    except Exception:
        pass
    return did
