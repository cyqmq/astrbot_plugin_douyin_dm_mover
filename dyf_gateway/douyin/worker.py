"""Douyin 私信接收 worker（subprocess 模式）。无 astrbot 依赖。

作为独立子进程运行：python -m gateway.douyin.worker <config_json_path>

stdout 协议（每行一个 JSON）：
  {"kind":"frame"}                                —— 收到任意原始帧（含被转换器过滤者）
  {"kind":"message","data":{...}}                 —— InboundMessage.to_dict()
  {"kind":"status","data":{"kind":"...","detail":"..."}}
                                                 —— started/disconnect/reconnect/error/auth_failure
stdin 控制（每行一个命令）：
  "uid <int>"   更新 self_uid（并写缓存）
  "stop"        优雅退出

日志走 stderr，保持 stdout 纯净为 JSON 行。
"""
from __future__ import annotations

import json
import logging
import os
import signal
import sys
import threading
import time

from astrbot.api import logger as _log

from dyf_gateway.douyin.converter import DouyinConverter
from dyf_gateway.douyin.detector import AuthFailureDetector
from dyf_gateway.douyin.device import resolve_device_id
from dyf_gateway.douyin.self_uid import SelfIdentityResolver
from dyf_gateway.douyin.vendored.auth import DouyinAuth
from dyf_gateway.douyin.vendored.receiver import DouyinReceiver

_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _list(value) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def _int_list(value) -> list[int]:
    out = []
    for x in _list(value):
        try:
            out.append(int(x))
        except ValueError:
            pass
    return out


def _load_config(path: str) -> dict:
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception as e:
            _log.error(f"config 解析失败: {e}")
    return {}


def main() -> int:
    config = _load_config(sys.argv[1] if len(sys.argv) > 1 else "")
    data_dir = config.get("_data_dir") or os.path.join("data", "dyf")
    os.makedirs(data_dir, exist_ok=True)

    auth = DouyinAuth(
        cookie_str=config.get("douyin_cookies", ""),
        web_protect=config.get("douyin_web_protect", ""),
        keys=config.get("douyin_keys", ""),
    )
    device_id = resolve_device_id(config, auth, data_dir)
    resolver = SelfIdentityResolver(data_dir, config.get("self_uid"))
    detector = AuthFailureDetector(
        close_codes=_int_list(config.get("auth_failure_close_codes")),
        keywords=_list(config.get("auth_failure_keywords")),
        watchdog_minutes=config.get("auth_watchdog_minutes", 30),
    )

    state: dict = {"uid": None, "expired": False, "last_frame": None, "stop": False}
    converter = DouyinConverter(lambda: state["uid"])

    def _on_raw_message(raw: dict) -> None:
        state["last_frame"] = time.time()
        _emit({"kind": "frame"})
        msg = converter.convert(raw)
        if msg is None:
            return
        _emit({"kind": "message", "data": msg.to_dict()})

    def _on_frame() -> None:
        state["last_frame"] = time.time()

    def _on_status(kind: str, detail: str) -> None:
        if kind in ("error", "close") and (
            detector.check_error(detail) or detector.check_text(detail)
        ):
            if not state["expired"]:
                state["expired"] = True
                receiver.auto_reconnect = False
                _emit({"kind": "status", "data": {"kind": "auth_failure", "detail": "登录态失效，停止自动重连"}})
            return
        if kind == "reconnect":
            _emit({"kind": "status", "data": {"kind": "reconnect", "detail": detail}})
        elif kind == "close":
            _emit({"kind": "status", "data": {"kind": "disconnect", "detail": detail}})
        elif kind == "error":
            _emit({"kind": "status", "data": {"kind": "error", "detail": detail}})

    receiver = DouyinReceiver(
        sessionid=auth.sessionid,
        device_id=device_id,
        cookie_str=auth.cookie_str,
        ua=config.get("ua") or _DEFAULT_UA,
        on_raw_message=_on_raw_message,
        on_status=_on_status,
        on_frame=_on_frame,
        auto_reconnect=True,
    )

    if not auth.sessionid:
        _emit({"kind": "status", "data": {"kind": "auth_failure", "detail": "缺少 sessionid cookie，无法建立连接"}})
        return 1

    state["uid"] = resolver.resolve(auth)
    auth.uid = state["uid"]
    _emit({"kind": "status", "data": {"kind": "started", "detail": f"self_uid={state['uid']} device_id={device_id}"}})

    def _stdin_loop(st: dict, recv: DouyinReceiver) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            if line == "stop":
                st["stop"] = True
                recv.stop()
                break
            if line.startswith("uid "):
                try:
                    v = int(line.split(" ", 1)[1].strip())
                except ValueError:
                    continue
                st["uid"] = v
                auth.uid = v
                resolver.cache(v)
                _log.info(f"self_uid 已更新为 {v}")

    stdin_thread = threading.Thread(
        target=_stdin_loop, args=(state, receiver), name="dyf-worker-stdin", daemon=True
    )
    stdin_thread.start()

    def _signal_handler(signum, frame):
        state["stop"] = True
        receiver.stop()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    thread = threading.Thread(
        target=receiver.start_blocking, name="dyf-worker-ws", daemon=True
    )
    thread.start()
    while not state["stop"]:
        time.sleep(0.2)
    receiver.stop()
    if thread.is_alive():
        thread.join(timeout=5)
    _log.info("worker 退出")
    return 0


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr, level=logging.INFO)
    sys.exit(main())
