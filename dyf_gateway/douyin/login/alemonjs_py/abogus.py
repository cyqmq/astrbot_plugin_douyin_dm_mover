"""jumpbyte-desktop a_bogus（@alemonjs/douyin a-bogus.js 逐行移植）。

供 desktop-lite Passport 表单（2046 MFA send_code/validate_code）与
check_qrconnect 使用。任何常量表 / 位运算不得改动，否则签名失效。
"""
from __future__ import annotations

import math
import random as _random
import time

from .sm3 import sm3

TABLES = {
    "s0": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",
    "s1": "Dkdpgh4ZKsQB80/Mfvw36XI1R25+WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
    "s2": "Dkdpgh4ZKsQB80/Mfvw36XI1R25-WUAlEi7NLboqYTOPuzmFjJnryx9HVGcaStCe=",
    "s3": "ckdp1h4ZKsUB80/Mfvw36XIgR25+WQAlEi7NLboqYTOPuzmFjJnryx9HVGDaStCe",
    "s4": "Dkdpgh2ZmsQB80/MfvV36XI1R45-WUAlEixNLwoqYTOPuzKFjJnry79HbGcaStCe",
}
SALT = "dhzx"

_UA_FINGERPRINT = "784|943|1707|1019|1707|1019|1707|1067|MacIntel"
_CHECKSUM_INDEXES = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 25, 26, 27, 29, 30, 31, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42,
    43, 44, 45, 46, 47, 48, 50, 51, 53, 54,
]
_REORDER = [
    9, 18, 30, 35, 47, 4, 44, 19, 10, 23, 12, 40, 25, 42, 3, 22, 38, 21, 5,
    45, 1, 29, 6, 43, 33, 14, 36, 37, 2, 46, 15, 48, 31, 26, 16, 13, 8, 41,
    27, 17, 39, 20, 11, 0, 34, 7, 50, 51, 53, 54,
]


def encode_utf8_for_sm3(text: str) -> list[int]:
    """encodeURIComponent → percent → charCodeAt，等价 UTF-8 字节序列。"""
    return list(text.encode("utf-8"))


def _byte_at(value: int, index: int) -> int:
    return (value >> (index * 8)) & 0xFF


def _write_int32_le(target: list[int], offset: int, value: int) -> None:
    for i in range(4):
        target[offset + i] = (value >> (i * 8)) & 0xFF


def _lm_str_encode(bytes_: list[int], table: str) -> str:
    """JS lmStrEncode 等价：groupNum=len/3（浮点），会多处理一个补零尾组。

    JS 循环 ``i < len/3`` 对非 3 倍数长度会读越界（undefined & 255 = 0），
    因此用 ceil 组数并对越界字节补 0 复现。
    """
    out = []
    n = len(bytes_)
    group_num = (n + 2) // 3
    for i in range(group_num):
        b1 = bytes_[3 * i] & 0xFF if 3 * i < n else 0
        b2 = bytes_[3 * i + 1] & 0xFF if 3 * i + 1 < n else 0
        b3 = bytes_[3 * i + 2] & 0xFF if 3 * i + 2 < n else 0
        big = (b1 << 16) | (b2 << 8) | b3
        out.append(table[(big & 16515072) >> 18])
        out.append(table[(big & 258048) >> 12])
        out.append(table[(big & 4032) >> 6])
        out.append(table[big & 63])
    s = "".join(out)
    rem = n % 3
    if rem == 1:
        s = s[:-2] + "=="
    elif rem == 2:
        s = s[:-1] + "="
    return s


def _jumpbyte_sbox(key: list[int]) -> list[int]:
    values = [255 - i for i in range(256)]
    previous = 0
    for i in range(256):
        previous = (previous * values[i] + previous + key[i % len(key)]) % 256
        values[i], values[previous] = values[previous], values[i]
    return values


def _jumpbyte_garble(sbox: list[int], input_: list[int]) -> list[int]:
    previous = 0
    out = []
    for index, value in enumerate(input_):
        cursor = (index + 1) % 256
        previous = (previous + sbox[cursor]) % 256
        old = sbox[cursor]
        sbox[cursor] = sbox[previous]
        sbox[previous] = old
        out.append(value ^ sbox[(sbox[cursor] + old) % 256])
    return out


def _jumpbyte_ab_sbox() -> list[int]:
    return _jumpbyte_sbox([211])


def _jumpbyte_ua_sbox(salt: int) -> list[int]:
    return _jumpbyte_sbox([0, 1, salt])


def _jumpbyte_random_prefix(rnd) -> list[int]:
    first = int(rnd() * 65535)
    low = first & 0xFF
    high = (first >> 8) & 0xFF
    second = int(rnd() * 240)
    third = (int(rnd() * 255) & 77) | 178
    return [
        low & 170 | 1,
        low & 85 | 0,
        high & 170 | 0,
        high & 85 | 0,
        second & 170 | 1,
        second & 85 | 0,
        third & 170 | 0,
        third & 85 | 0,
    ]


def _jumpbyte_header(rnd) -> list[int]:
    first = int(rnd() * 65535) & 0xFF
    second = int(rnd() * 40)
    return [
        first & 170 | 1,
        first & 85 | 2,
        second & 170 | 80,
        second & 85 | 2,
    ]


def _jumpbyte_expand(prefix: list[int], input_: list[int], rnd) -> list[int]:
    output = list(prefix)
    i = 0
    while i < len(input_):
        if i + 2 >= len(input_):
            output.extend(input_[i:])
            break
        value = int(rnd() * 1000) & 0xFF
        first = input_[i]
        second = input_[i + 1]
        third = input_[i + 2]
        output.append(value & 145 | first & 110)
        output.append(value & 66 | second & 189)
        output.append(value & 44 | third & 211)
        output.append(first & 145 | second & 66 | third & 44)
        i += 3
    return output


def generate_jumpbyte_abogus(
    query: str,
    body: str,
    user_agent: str,
    now_ms: int | None = None,
    random=None,
) -> str:
    """generateJumpbyteABogus 等价实现。

    ``now_ms``/``random`` 可注入用于测试复现（默认取当前时间与随机）。
    """
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    rnd = random or _random.random
    q = f"{query}{SALT}"
    b = f"{body or ''}{SALT}"
    query_hash = sm3(sm3(q.encode("utf-8")))
    body_hash = sm3(sm3(b.encode("utf-8")))
    ua_hash = sm3(
        bytes(
            encode_utf8_for_sm3(
                _lm_str_encode(
                    _jumpbyte_garble(
                        _jumpbyte_ua_sbox(0), encode_utf8_for_sm3(user_agent)
                    ),
                    TABLES["s3"],
                )
            )
        )
    )
    fixed = encode_utf8_for_sm3(_UA_FINGERPRINT)
    date_bucket = math.trunc((now - 1721836800000) / 1209600000)
    first_time = now
    second_time = first_time - int(rnd() * 10)
    prefix = _jumpbyte_random_prefix(rnd)
    arr = [0] * 55
    arr[0] = 41
    arr[1] = date_bucket
    arr[2] = 5
    arr[3] = (first_time - second_time + 3) & 0xFF
    for i in range(6):
        arr[4 + i] = _byte_at(first_time, i)
    arr[10] = 1
    arr[12] = 1
    arr[14] = 1
    arr[22] = query_hash[9]
    arr[23] = query_hash[18]
    arr[24] = 3
    arr[25] = query_hash[3]
    arr[26] = body_hash[10]
    arr[27] = body_hash[19]
    arr[28] = 4
    arr[29] = body_hash[4]
    arr[30] = ua_hash[11]
    arr[31] = ua_hash[21]
    arr[32] = 5
    arr[33] = ua_hash[5]
    for i in range(6):
        arr[34 + i] = _byte_at(second_time, i)
    arr[40] = 3
    _write_int32_le(arr, 41, 6241)
    _write_int32_le(arr, 45, 6383)
    last_time = encode_utf8_for_sm3(f"{(first_time + 3) & 255},")
    arr[49] = len(fixed)
    arr[50] = len(fixed) & 0xFF
    arr[51] = (len(fixed) >> 8) & 0xFF
    arr[52] = len(last_time)
    arr[53] = len(last_time) & 0xFF
    arr[54] = (len(last_time) >> 8) & 0xFF
    checksum = 0
    for v in prefix:
        checksum ^= v
    for index in _CHECKSUM_INDEXES:
        checksum ^= arr[index]
    payload = _jumpbyte_expand(
        prefix,
        [arr[i] for i in _REORDER] + fixed + last_time + [checksum],
        rnd,
    )
    header = _jumpbyte_header(rnd)
    encrypted = _jumpbyte_garble(_jumpbyte_ab_sbox(), payload)
    return _lm_str_encode(header + encrypted, TABLES["s4"])
