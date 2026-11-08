"""DouYin 私信 WebSocket 接收端（内嵌裁剪版）。

来源：DouYin_Spider `dy_apis/douyin_recv_msg.py`（cv-cat/DouYin_Spider）。
关键等价点：
- 端点 wss://frontier-im.douyin.com/ws/v2，aid=6383，device_platform=douyin_pc
- access_key = md5(fpId + appKey + deviceId + "f8a69f1719916z")
- Protobuf：PushFrame(payloadType=7, payload=8) -> Response(body=6) -> new_message_notify(500) -> message(5)
- content 是 JSON 字符串，需二次 json.loads
- start() 是阻塞循环（run_forever），断线指数退避重连（1s 起、上限 30s）

与上游差异：
- 用 vendored/proto.py 最小解码器替代 google.protobuf pb2。
- on_raw_message/on_status 回调替代 print，便于接入层驱动。
"""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable

import websocket
from websocket import WebSocketApp

from .proto import decode_fields, field_bytes, field_int, field_str, field_sub

APP_KEY = "e1bd35ec9db7b8d846de66ed140b1ad9"
FP_ID = "9"
ACCESS_KEY_SALT = "f8a69f1719916z"

RECONNECT_BACKOFF_START = 1.0
RECONNECT_BACKOFF_MAX = 30.0

# 上游对端已读消息类型
MSG_TYPE_READ = 50001


class DouyinReceiver:
    """阻塞式 WebSocket 接收端。在独立线程中调用 start_blocking()。"""

    def __init__(
        self,
        sessionid: str,
        device_id: str,
        cookie_str: str = "",
        ua: str = "",
        on_raw_message: Callable[[dict], None] | None = None,
        on_status: Callable[[str, str], None] | None = None,
        auto_reconnect: bool = True,
    ):
        self.sessionid = sessionid
        self.device_id = str(device_id)
        self.cookie_str = cookie_str
        self.ua = ua
        self.on_raw_message = on_raw_message
        self.on_status = on_status
        self.auto_reconnect = auto_reconnect
        self.ws: WebSocketApp | None = None
        self._should_reconnect = False
        self._stopped = False
        self._opened = False
        self._build_url()

    def _build_url(self) -> None:
        access_key = hashlib.md5(
            f"{FP_ID}{APP_KEY}{self.device_id}{ACCESS_KEY_SALT}".encode()
        ).hexdigest()
        params = {
            "aid": "6383",
            "device_platform": "douyin_pc",
            "fpid": FP_ID,
            "device_id": self.device_id,
            "token": self.sessionid,
            "access_key": access_key,
        }
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        self.url = f"wss://frontier-im.douyin.com/ws/v2?{qs}"

    def _emit(self, kind: str, detail: str = "") -> None:
        if self.on_status:
            try:
                self.on_status(kind, detail)
            except Exception:
                pass

    def _on_open(self, ws) -> None:
        self._opened = True
        self._emit("open", "WebSocket connection open")

    def _on_message(self, ws, message: bytes) -> None:
        try:
            self._handle_frame(message)
        except Exception as e:  # 单帧解析失败不拖垮连接
            self._emit("error", f"frame decode error: {e}")

    def _handle_frame(self, message: bytes) -> None:
        frame = decode_fields(message)
        payload_type = field_str(frame, 7)
        if payload_type == "pb":
            payload = field_bytes(frame, 8)
            response = decode_fields(payload)
            body = field_sub(response, 6)
            notify = field_sub(body, 500)  # new_message_notify
            msg_body = field_sub(notify, 5)  # message
            if not msg_body:
                return
            msg_type = field_int(msg_body, 6)
            if msg_type == MSG_TYPE_READ:
                return  # 已读回执，跳过
            sender = field_int(msg_body, 7)
            content = field_str(msg_body, 8)
            try:
                content_json = json.loads(content)
            except Exception:
                content_json = {}
            self._emit_raw(
                {
                    "message_type": msg_type,
                    "sender": sender,
                    "content": content_json,
                    "conversation_id": field_str(msg_body, 1),
                    "server_message_id": field_int(msg_body, 3),
                    "index_in_conversation": field_int(msg_body, 4),
                    "conversation_short_id": field_int(msg_body, 5),
                }
            )
        elif payload_type == "text/json":
            # 非业务帧（如握手/控制），仅记录
            self._emit("info", f"json frame: {field_str(frame, 8)[:200]}")

    def _emit_raw(self, raw: dict) -> None:
        if self.on_raw_message:
            try:
                self.on_raw_message(raw)
            except Exception:
                pass

    def _on_error(self, ws, error) -> None:
        self._emit("error", str(error))
        if not self.auto_reconnect:
            return
        if isinstance(
            error,
            (ConnectionRefusedError, websocket.WebSocketConnectionClosedException),
        ):
            self._should_reconnect = True

    def _on_close(self, ws, close_status_code, close_msg) -> None:
        self._emit("close", f"status_code={close_status_code}, msg={close_msg}")

    def _new_ws(self) -> WebSocketApp:
        return WebSocketApp(
            url=self.url,
            header={
                "Pragma": "no-cache",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
                "User-Agent": self.ua,
                "Cache-Control": "no-cache",
                "Sec-WebSocket-Protocol": "binary, base64, pbbp2",
                "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits",
            },
            cookie=self.cookie_str,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

    def start_blocking(self) -> None:
        """阻塞运行；断线按退避重连（循环，非递归压栈）。"""
        backoff = RECONNECT_BACKOFF_START
        while not self._stopped:
            self._should_reconnect = False
            self._opened = False
            self.ws = self._new_ws()
            try:
                self.ws.run_forever(origin="https://www.douyin.com")
            except KeyboardInterrupt:
                self._close_ws()
                break
            except Exception as e:
                self._emit("error", f"run_forever: {type(e).__name__}: {e}")
                self._close_ws()
            if self._stopped or not (self.auto_reconnect and self._should_reconnect):
                break
            if self._opened:
                backoff = RECONNECT_BACKOFF_START
            self._emit("reconnect", f"{backoff:.0f}s backoff")
            try:
                time.sleep(backoff)
            except KeyboardInterrupt:
                break
            backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)

    def _close_ws(self) -> None:
        if self.ws is not None:
            try:
                self.ws.close()
            except Exception:
                pass

    def stop(self) -> None:
        self._stopped = True
        self.auto_reconnect = False
        self._close_ws()
