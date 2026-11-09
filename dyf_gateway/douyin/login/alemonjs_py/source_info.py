"""account_sdk_source_info / browser_info 编码（sign/source-info.js + browser-info.js 移植）。"""
from __future__ import annotations

import time


def encode_account_sdk_source_info(plain: str) -> str:
    """JSON 串逐字符 codePoint XOR 5 → JS toString(16) 无补零 hex。"""
    out = []
    for ch in plain:
        out.append(format((ord(ch) ^ 5), "x"))
    return "".join(out)


def encode_browser_info(browser_info: dict) -> str:
    return encode_account_sdk_source_info(_json_dumps(browser_info))


def _json_dumps(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def default_browser_info() -> dict:
    """DEFAULT_BROWSER_INFO（脱敏模板，performance.timeOrigin/browser.t 取当前）。"""
    now = int(time.time() * 1000)
    return {
        "hardwareConcurrency": 10,
        "webdriver": False,
        "chromedriver": False,
        "shelldriver": False,
        "plugins": 5,
        "permissions": [{"name": "notifications", "state": "prompt"}],
        "innerHeight": 982,
        "innerWidth": 1728,
        "outerHeight": 1117,
        "outerWidth": 1728,
        "stoargeStatus": {
            "indexedDB": {
                "idb": "object", "open": "function", "indexedDB": "object",
                "IDBKeyRange": "function", "openDatabase": "undefined",
                "isSafari": False, "hasFetch": True,
            },
            "localStorage": {"isSupportLStorage": True, "size": 0, "write": True},
            "storageQuotaStatus": {"usage": 0, "quota": 10737426463, "isPrivate": False},
        },
        "webgl": {
            "vendor": "Google Inc. (Apple)",
            "renderer": "ANGLE (Apple, ANGLE Metal Renderer: Apple M5, Unspecified Version)",
        },
        "notificationPermission": "default",
        "performance": {
            "timeOrigin": now,
            "usedJSHeapSize": 50000000,
            "navigationTiming": {
                "entryType": "navigation",
                "initiatorType": "navigation",
                "name": "https://creator.douyin.com/creator-micro/home",
            },
        },
        "request_host": "creator.douyin.com",
        "request_pathname": "/creator-micro/home",
        "browser": {"t": str(now), "bit_protocol": "false", "bit_helper": False},
    }
