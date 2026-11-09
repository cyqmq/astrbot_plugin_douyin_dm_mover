"""SM3 哈希（jumpbyte a_bogus 用）。

对齐 @alemonjs/douyin a-bogus.js 内嵌 SM3：Tj 低段常量 0x79cc4519 / 0x7a879d8a
（与国标 SM3 一致），rotl/ff/gg/expand 逐行等价。
"""
from __future__ import annotations

_IV = [
    0x7380166F, 0x4914B2B9, 0x172442D7, 0xDA8A0600,
    0xA96F30BC, 0x163138AA, 0xE38DEE4D, 0xB0FB0E4E,
]


def _rotl(x: int, n: int) -> int:
    n %= 32
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF


def _tj(j: int) -> int:
    return 0x79CC4519 if j < 16 else 0x7A879D8A


def _ff(j: int, a: int, b: int, c: int) -> int:
    if j < 16:
        return (a ^ b ^ c) & 0xFFFFFFFF
    return (a & b | a & c | b & c) & 0xFFFFFFFF


def _gg(j: int, a: int, b: int, c: int) -> int:
    if j < 16:
        return (a ^ b ^ c) & 0xFFFFFFFF
    return (a & b | (~a) & c) & 0xFFFFFFFF


def _expand(block: bytes) -> list[int]:
    w = [0] * 132
    for i in range(16):
        w[i] = (
            (block[4 * i] << 24)
            | (block[4 * i + 1] << 16)
            | (block[4 * i + 2] << 8)
            | block[4 * i + 3]
        ) & 0xFFFFFFFF
    for i in range(16, 68):
        t = (w[i - 16] ^ w[i - 9] ^ _rotl(w[i - 3], 15)) & 0xFFFFFFFF
        t = (t ^ _rotl(t, 15) ^ _rotl(t, 23)) & 0xFFFFFFFF
        w[i] = (t ^ _rotl(w[i - 13], 7) ^ w[i - 6]) & 0xFFFFFFFF
    for i in range(64):
        w[i + 68] = (w[i] ^ w[i + 4]) & 0xFFFFFFFF
    return w


def sm3(data: bytes) -> bytes:
    """SM3 摘要，返回 32 字节。"""
    bit_len = len(data) * 8
    msg = bytearray(data)
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += bit_len.to_bytes(8, "big")
    reg = list(_IV)
    for off in range(0, len(msg), 64):
        block = bytes(msg[off : off + 64])
        w = _expand(block)
        r = list(reg)
        for j in range(64):
            o = _rotl(
                (_rotl(r[0], 12) + r[4] + _rotl(_tj(j), j)) & 0xFFFFFFFF, 7
            )
            i_ = (o ^ _rotl(r[0], 12)) & 0xFFFFFFFF
            u = (_ff(j, r[0], r[1], r[2]) + r[3] + i_ + w[j + 68]) & 0xFFFFFFFF
            c = (_gg(j, r[4], r[5], r[6]) + r[7] + o + w[j]) & 0xFFFFFFFF
            r[3] = r[2]
            r[2] = _rotl(r[1], 9)
            r[1] = r[0]
            r[0] = u
            r[7] = r[6]
            r[6] = _rotl(r[5], 19)
            r[5] = r[4]
            r[4] = (c ^ _rotl(c, 9) ^ _rotl(c, 17)) & 0xFFFFFFFF
        for a in range(8):
            reg[a] = (reg[a] ^ r[a]) & 0xFFFFFFFF
    out = bytearray(32)
    for i in range(8):
        out[4 * i] = (reg[i] >> 24) & 0xFF
        out[4 * i + 1] = (reg[i] >> 16) & 0xFF
        out[4 * i + 2] = (reg[i] >> 8) & 0xFF
        out[4 * i + 3] = reg[i] & 0xFF
    return bytes(out)
