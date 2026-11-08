"""最小 Protobuf wire-format 解码器。

DouYin_Spider 用 google.protobuf 生成 pb2 解析 PushFrame/Response/MessageBody。
本模块用纯 Python 解析所需字段，避免引入 google.protobuf 与整套 pb2 生成文件，
从而让 vendored 子集更小、更易整体替换（协议变更只改这里）。
"""
from __future__ import annotations

from typing import Any


def _read_varint(data: bytes, i: int) -> tuple[int, int]:
    result = 0
    shift = 0
    start = i
    while True:
        b = data[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return result, i - start


def decode_fields(data: bytes) -> dict[int, list[Any]]:
    """把二进制消息解码为 {field_number: [value,...]}。

    wire_type 0=varint, 1=64bit, 2=length-delimited, 5=32bit。
    未知 wire_type 直接跳过（向前兼容协议漂移）。
    """
    fields: dict[int, list[Any]] = {}
    i = 0
    n = len(data)
    while i < n:
        tag, adv = _read_varint(data, i)
        i += adv
        field_num = tag >> 3
        wire_type = tag & 0x07
        if wire_type == 0:  # varint
            v, adv = _read_varint(data, i)
            i += adv
            fields.setdefault(field_num, []).append(v)
        elif wire_type == 1:  # 64-bit
            fields.setdefault(field_num, []).append(data[i : i + 8])
            i += 8
        elif wire_type == 2:  # length-delimited
            ln, adv = _read_varint(data, i)
            i += adv
            fields.setdefault(field_num, []).append(data[i : i + ln])
            i += ln
        elif wire_type == 5:  # 32-bit
            fields.setdefault(field_num, []).append(data[i : i + 4])
            i += 4
        else:
            # 未知类型，安全跳过：无法知道长度，放弃剩余（协议漂移容错）
            break
    return fields


def field(fields: dict[int, list[Any]], num: int, default: Any = None) -> Any:
    vals = fields.get(num)
    if not vals:
        return default
    return vals[0]


def field_str(fields: dict[int, list[Any]], num: int, default: str = "") -> str:
    v = field(fields, num, default)
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8", errors="replace")
        except Exception:
            return default
    return v if isinstance(v, str) else default


def field_int(fields: dict[int, list[Any]], num: int, default: int = 0) -> int:
    v = field(fields, num, default)
    if isinstance(v, bytes):
        try:
            return int.from_bytes(v, "little")
        except Exception:
            return default
    return int(v) if isinstance(v, (int, float)) else default


def field_bytes(fields: dict[int, list[Any]], num: int, default: bytes = b"") -> bytes:
    v = field(fields, num, default)
    return v if isinstance(v, bytes) else default


def field_sub(fields: dict[int, list[Any]], num: int) -> dict[int, list[Any]]:
    """取 length-delimited 子消息并递归解码。"""
    b = field_bytes(fields, num)
    if not b:
        return {}
    try:
        return decode_fields(b)
    except Exception:
        return {}
