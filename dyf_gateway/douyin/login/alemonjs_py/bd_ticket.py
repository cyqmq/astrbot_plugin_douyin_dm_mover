"""BDTicket 安全票据（DouYin_Spider/utils/bd_ticket.py + builder/header.py with_bd_readonly 移植）。

只读接口的 bd-ticket-guard 4 个头（不含 client-data）：
    bd-ticket-guard-ree-public-key / -version: 2 / -web-version / -web-sign-type

依赖：Cookie 里的 ``bd_ticket_guard_ts_sign_id``（登录后 desktop 扫码写入）、
服务端 ecies 证书（get_client_cert）、客户端 P-256 私钥。缺票据时相关接口
（follow/following/follower）无法通过风控。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from urllib.parse import urlencode

from astrbot.api import logger
from ecdsa import NIST256p, SigningKey, VerifyingKey
from ecdsa.util import sigencode_der

from .abogus import generate_jumpbyte_abogus
from .http import DouyinHttpPy
from .sign import random_ms_token_128

# P-256 的 SubjectPublicKeyInfo 前缀，其后紧跟 64 字节裸公钥点（X||Y）。
_P256_SPKI_PREFIX = bytes.fromhex(
    "3059301306072a8648ce3d020106082a8648ce3d03010703420004"
)

GET_CLIENT_CERT_API = "/passport/ticket_guard/get_client_cert/"
TICKET_COOKIE = "bd_ticket_guard_ts_sign_id"


def _load_signing_key(prv) -> SigningKey:
    if "-----BEGIN" in prv:
        return SigningKey.from_pem(prv)
    return SigningKey.from_string(bytes.fromhex(prv), curve=NIST256p)


def _pem_body(pem: str) -> bytes:
    body = "".join(
        line for line in pem.strip().splitlines() if "-----" not in line
    )
    return base64.b64decode(body)


def _server_pub_point(server_cert: str) -> bytes:
    """从服务端证书里取出 65 字节未压缩公钥点（含 0x04 前缀）。"""
    if server_cert.startswith("pub."):
        return base64.b64decode(server_cert[4:])
    der = _pem_body(server_cert)
    idx = der.find(_P256_SPKI_PREFIX)
    if idx < 0:
        raise ValueError("服务端证书中未找到 P-256 公钥")
    start = idx + len(_P256_SPKI_PREFIX)
    return b"\x04" + der[start : start + 64]


def _hkdf_sha256(ikm: bytes, length: int = 32, salt: bytes = b"", info: bytes = b"") -> bytes:
    if not salt:
        salt = b"\x00" * hashlib.sha256().digest_size
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    okm, block, counter = b"", b"", 1
    while len(okm) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        okm += block
        counter += 1
    return okm[:length]


def derive_ecdh_key(prv: str, server_cert: str) -> bytes:
    """ECDH(客户端私钥, 服务端证书公钥) -> HKDF-SHA256 -> 32 字节 HMAC 密钥。"""
    sk = _load_signing_key(prv)
    vk = VerifyingKey.from_string(_server_pub_point(server_cert), curve=NIST256p)
    shared_point = sk.privkey.secret_multiplier * vk.pubkey.point
    shared = shared_point.x().to_bytes(32, "big")
    return _hkdf_sha256(shared)


def get_ree_key(prv) -> str:
    sk = _load_signing_key(prv)
    vk = sk.get_verifying_key()
    return base64.b64encode(b"\x04" + vk.to_string()).decode()


def get_req_sign(e, prv) -> str:
    if isinstance(e, (dict, list)):
        e = json.dumps(e, ensure_ascii=False, separators=(",", ":"))
    sk = _load_signing_key(prv)
    signature = sk.sign(e.encode("utf-8"), hashfunc=hashlib.sha256, sigencode=sigencode_der)
    return base64.b64encode(signature).decode()


def get_req_sign_hmac(e, ecdh_key: bytes) -> str:
    if isinstance(e, (dict, list)):
        e = json.dumps(e, ensure_ascii=False, separators=(",", ":"))
    return base64.b64encode(
        hmac.new(ecdh_key, e.encode("utf-8"), hashlib.sha256).digest()
    ).decode()


def ticket_guard_version(ts_sign: str) -> int:
    """web-version 由 ts_sign 前缀决定：ts.1 -> 1，其余 -> 2。"""
    return 1 if (ts_sign or "").startswith("ts.1") else 2


def fetch_server_cert(http: DouyinHttpPy, aid: str = "6383") -> tuple[str, str]:
    """取服务端 ecies 证书（www get_client_cert）。返回 (server_cert, server_sn)。

    body 的键值对用 ``,`` 连接（非 ``&``，对齐 SDK）。
    """
    query = {
        "aid": aid,
        "is_from_ttaccountsdk": "1",
        "msToken": http.get_ms_token() or random_ms_token_128(),
    }
    query_wire = urlencode(query)
    query["a_bogus"] = generate_jumpbyte_abogus(
        query=query_wire, body="", user_agent=http.get_user_agent()
    )
    url = f"https://www.douyin.com{GET_CLIENT_CERT_API}?{urlencode(query)}"
    headers = {
        "Referer": "https://www.douyin.com/",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    csrf = (
        http.jar.get("passport_csrf_token")
        or http.jar.get("passport_csrf_token_default")
        or ""
    )
    if csrf:
        headers["x-secsdk-csrf-token"] = csrf
    resp = http.request_raw(
        url, "POST", headers=headers, body=f"server_data=1,aid={aid}", timeout=20
    )
    # 诊断：get_client_cert 响应头（找 bd-ticket-guard-server-data —— ts_sign 真源）
    logger.info(f"[dyf] CERT_HEADERS: {dict(resp.headers)}")
    res_json = resp.json()
    if res_json.get("message") != "success":
        raise RuntimeError(f"获取服务端证书失败: {res_json}")
    data = res_json.get("data") or {}
    cert, sn = data.get("server_cert", ""), data.get("server_sn", "")
    if not cert:
        raise RuntimeError(f"服务端证书为空: {res_json}")
    return cert, sn


def build_bd_ticket(http: DouyinHttpPy) -> dict:
    """登录后建 BDTicket：先取服务端证书（get_client_cert 可能 set-cookie ts_sign），再读 ts_sign。

    Returns: {"ts_sign", "private_key", "client_cert", "server_cert", "server_sn"}
    或 {"error": "..."}（fetch_server_cert 失败 / cookie 仍未 set 票据）。
    """
    try:
        server_cert, server_sn = fetch_server_cert(http)
    except Exception as e:
        return {"error": f"fetch_server_cert: {e}"}
    ts_sign = http.jar.get(TICKET_COOKIE) or ""
    if not ts_sign:
        return {"error": "get_client_cert 未 set bd_ticket_guard_ts_sign_id"}
    sk = SigningKey.generate(curve=NIST256p)
    private_key = sk.to_string().hex()
    client_cert = "pub." + get_ree_key(private_key)
    return {
        "ts_sign": ts_sign,
        "private_key": private_key,
        "client_cert": client_cert,
        "server_cert": server_cert,
        "server_sn": server_sn,
    }


def bd_ticket_headers(ticket: dict) -> dict:
    """只读接口的 bd-ticket-guard 4 个头（with_bd_readonly，无 client-data）。

    无 private_key 返回 {}（此时不带票据头，接口大概率被风控拦）。
    """
    private_key = (ticket or {}).get("private_key") or ""
    if not private_key:
        return {}
    client_cert = (ticket or {}).get("client_cert") or ""
    return {
        "bd-ticket-guard-ree-public-key": get_ree_key(private_key),
        "bd-ticket-guard-version": "2",
        "bd-ticket-guard-web-version": str(
            ticket_guard_version((ticket or {}).get("ts_sign") or "")
        ),
        "bd-ticket-guard-web-sign-type": "1" if client_cert.startswith("pub.") else "0",
    }
