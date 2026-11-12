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
# 探针实测（2026-11-12）：imdesktop 流从不 set bd_ticket_guard_ts_sign_id（Set-Cookie 只有
# reg-store-region 清理 + bd_ticket_guard_server_data）。正确机制：登录前 publish_public_key
# 写 bd_ticket_guard_client_data cookie（公钥交服务端）→ 服务端 confirmed 响应头
# Bd-Ticket-Guard-Server-Data（base64 URL→JSON {ticket,ts_sign,client_cert,log_id,create_time}）
# 签发完整票据，同时 Set-Cookie 下发 bd_ticket_guard_server_data（同值）。
SERVER_DATA_COOKIE = "bd_ticket_guard_server_data"
SERVER_DATA_HEADER = "bd-ticket-guard-server-data"
CLIENT_DATA_COOKIE = "bd_ticket_guard_client_data"
CLIENT_WEB_DOMAIN_COOKIE = "bd_ticket_guard_client_web_domain"
GUARD_VERSION = "2"
ITERATION_VERSION = "1"


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


def publish_public_key(http: DouyinHttpPy, private_key: str = "") -> str:
    """登录前把客户端 P-256 公钥发布到 bd_ticket_guard_client_data cookie。

    探针实测（2026-11-12）：此步是关键——缺了它扫码依然成功，但服务端不会签发票据。
    ``private_key`` 为空时生成新私钥并缓存到 ``http._bd_ticket_private_key``（与后续
    ``build_bd_ticket`` 共用，保证 ree-public-key 与 ECDH 私钥一致）。返回私钥 hex。
    """
    if private_key:
        sk = _load_signing_key(private_key)
    else:
        private_key = getattr(http, "_bd_ticket_private_key", "") or ""
        if private_key:
            sk = _load_signing_key(private_key)
        else:
            sk = SigningKey.generate(curve=NIST256p)
            private_key = sk.to_string().hex()
            http._bd_ticket_private_key = private_key
    pub = base64.b64encode(b"\x04" + sk.get_verifying_key().to_string()).decode()
    payload = json.dumps(
        {
            "bd-ticket-guard-version": int(GUARD_VERSION),
            "bd-ticket-guard-iteration-version": int(ITERATION_VERSION),
            "bd-ticket-guard-ree-public-key": pub,
            "bd-ticket-guard-web-version": int(GUARD_VERSION),
        },
        separators=(",", ":"),
    )
    from urllib.parse import quote

    http.jar.set(CLIENT_DATA_COOKIE, quote(base64.b64encode(payload.encode("utf-8")).decode()))
    http.jar.set(CLIENT_WEB_DOMAIN_COOKIE, GUARD_VERSION)
    return private_key


def apply_server_data(http: DouyinHttpPy, headers: dict | None = None) -> dict | None:
    """解析服务端签发票据：响应头 bd-ticket-guard-server-data 或 Set-Cookie 同值。

    Returns: {"ticket", "ts_sign", "client_cert", "log_id", "create_time"} 或 None。
    """
    raw = (headers or {}).get(SERVER_DATA_HEADER) or http.jar.get(SERVER_DATA_COOKIE) or ""
    if not raw:
        return None
    from urllib.parse import unquote

    try:
        info = json.loads(base64.b64decode(unquote(raw)).decode("utf-8"))
    except Exception:
        return None
    if not all(info.get(k) for k in ("ticket", "ts_sign", "client_cert")):
        return None
    return info


def build_bd_ticket(http: DouyinHttpPy, headers: dict | None = None) -> dict:
    """登录后建 BDTicket：取服务端证书 + 解析服务端签发的 Server-Data。

    探针实测（2026-11-12）：imdesktop 流从不 set ``bd_ticket_guard_ts_sign_id`` cookie，
    正确入口是响应头 ``Bd-Ticket-Guard-Server-Data``（或 Set-Cookie ``bd_ticket_guard_server_data``，
    登录前需先 ``publish_public_key``）。``headers`` 可传 confirmed/get_client_cert 响应头。

    Returns: {"ticket", "ts_sign", "private_key", "client_cert"(服务端证书), "server_cert",
    "server_sn"} 或 {"error": "..."}。
    """
    try:
        server_cert, server_sn = fetch_server_cert(http)
    except Exception as e:
        return {"error": f"fetch_server_cert: {e}"}
    info = apply_server_data(http, headers)
    if not info:
        return {"error": "get_client_cert 响应无 bd-ticket-guard-server-data"}
    private_key = getattr(http, "_bd_ticket_private_key", "") or (
        SigningKey.generate(curve=NIST256p).to_string().hex()
    )
    return {
        "ticket": info.get("ticket", ""),
        "ts_sign": info.get("ts_sign", ""),
        "private_key": private_key,
        "client_cert": info.get("client_cert", ""),  # 服务端证书（pub. 前缀，web-sign-type 判据）
        "server_cert": server_cert,
        "server_sn": server_sn,
    }


def bd_ticket_headers(ticket: dict) -> dict:
    """只读接口的 bd-ticket-guard 4 个头（with_bd_readonly，无 client-data）。

    探针实测（2026-11-12）：``ree-public-key`` 是**客户端公钥**（``get_ree_key(private_key)``，
    非服务端 client_cert）；``web-sign-type`` = ``1`` if client_cert 有 ``pub.`` 前缀（hmac）
    else ``0``（ecdsa）。无 ts_sign/private_key 返回 {}（只读列表降级仅 familiar 并告警）。
    """
    ts_sign = (ticket or {}).get("ts_sign") or ""
    client_cert = (ticket or {}).get("client_cert") or ""
    private_key = (ticket or {}).get("private_key") or ""
    if not ts_sign or not private_key:
        return {}
    return {
        "bd-ticket-guard-ree-public-key": get_ree_key(private_key),  # 客户端公钥（65B 含 0x04）
        "bd-ticket-guard-version": GUARD_VERSION,
        "bd-ticket-guard-web-version": str(ticket_guard_version(ts_sign)),
        "bd-ticket-guard-web-sign-type": "1" if client_cert.startswith("pub.") else "0",
    }


def import_www_session(
    cookie_str: str,
    ts_sign: str = "",
    private_key: str = "",
    client_cert: str = "",
    server_cert: str = "",
) -> dict:
    """手动网页 Cookie 导入：用户在浏览器 www.douyin.com 登录后复制 Cookie 串。

    探针实测（2026-11-12）：浏览器 www 登录后 Set-Cookie 下发 ``bd_ticket_guard_server_data``
    （服务端已签发票据）；此处先 ``publish_public_key``（发布客户端公钥），再解析 Server-Data
    （jar 里的 ``bd_ticket_guard_server_data`` / get_client_cert 响应头）。也可直接补填完整
    票据（ts_sign/private_key/client_cert/server_cert，从浏览器 localStorage/抓包取）。

    Returns: {"cookie_str", "ts_sign", "private_key", "client_cert", "server_cert"}
    或 {"error": "..."}。
    """
    if not cookie_str or "sessionid=" not in cookie_str:
        return {
            "error": "cookie 缺少 sessionid，请从浏览器 www.douyin.com 登录后复制完整 Cookie 串"
        }
    http = DouyinHttpPy(cookie_str)
    if ts_sign and private_key:
        return {
            "cookie_str": cookie_str,
            "ts_sign": ts_sign,
            "private_key": private_key,
            "client_cert": client_cert,
            "server_cert": server_cert,
        }
    publish_public_key(http)
    ticket = build_bd_ticket(http)
    if ticket.get("ts_sign"):
        return {"cookie_str": cookie_str, **ticket}
    return {
        "error": ticket.get("error")
        or "www 票据生成失败（浏览器登录后应下发 bd_ticket_guard_server_data），或补填完整票据"
    }
