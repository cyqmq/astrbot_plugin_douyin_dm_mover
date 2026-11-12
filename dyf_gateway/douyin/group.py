"""抖音 IM 群列表拉取（HTTP protobuf，不走 WS）。

POST https://imapi3-normal.zijieapi.com/v1/conversation/list，cmd=2006。
与私信/群消息同用 imdesktop 域 Cookie + 数字 device_id。
字段号对照 alemonjs proto.js（已在真实账号实测拉群 TYLOO）。

字段号表：
- RequestEnvelope: cmd=1, sdk_version=3, inbox_type=6, build_number=7,
  body=8, device_id=9, device_platform=11, version_code=14, auth_type=18,
  biz=21, access=22
- RequestPayload.conversation_list=2006
- ConversationListRequest{list_type=1,cursor=2,sort_type=3,limit=4}
- ResponseEnvelope{status_code=3,error_desc=4,body=6}
- ResponsePayload.conversation_list=2006
- ConversationListResponse.conversations=1
- Conversation{conversation_id=1,short_id=2,type=3,members=6,ext_info=50}
- ConversationMembers.members=1 -> uid=1
- ConversationExtInfo{name=5,avatar=7}
"""
from __future__ import annotations

import hashlib
from urllib.parse import urlencode

from .vendored.proto import (
    decode_fields,
    enc_bytes_field,
    enc_msg_field,
    enc_str_field,
    enc_varint_field,
    field_int,
    field_str,
    field_sub,
)

_LIST_URL = "https://imapi3-normal.zijieapi.com/v1/conversation/list"

# 群聊 type 值（Conversation.type）：2=群聊
CONV_TYPE_GROUP = 2


def _desktop_im_query(device_id: str) -> str:
    """desktopImQuery 公共参数（aid=339757 专用于 imapi3 IM 接口）。"""
    q = {
        "aid": "339757",
        "app_name": "aweme_im_desktop",
        "did": device_id,
        "device_id": device_id,
        "iid": "0",
        "channel": "0",
        "os_version": "10.0.0",
        "version_code": "1.2.1",
        "version_name": "1.2.1",
        "device_platform": "windows",
        "device_type": "x64",
        "device_brand": "",
    }
    return urlencode(q)


def _build_request(device_id: str) -> bytes:
    """构造 cmd=2006 群列表请求 body（RequestEnvelope 编码）。"""
    list_req = (
        enc_varint_field(1, 1)  # list_type=1（会话列表）
        + enc_varint_field(2, 0)  # cursor
        + enc_varint_field(3, 0)  # sort_type
        + enc_varint_field(4, 50)  # limit
    )
    payload = enc_msg_field(2006, list_req)
    env = (
        enc_varint_field(1, 1)  # cmd=1
        + enc_varint_field(3, 1)  # sdk_version
        + enc_varint_field(6, 1)  # inbox_type=1
        + enc_varint_field(7, 1)  # build_number
        + enc_bytes_field(8, payload)  # body=RequestPayload
        + enc_varint_field(9, int(device_id or 0))  # device_id
        + enc_str_field(11, "windows")  # device_platform
        + enc_varint_field(14, 1)  # version_code
        + enc_varint_field(18, 1)  # auth_type
        + enc_varint_field(21, 1)  # biz
        + enc_varint_field(22, 1)  # access
    )
    return env


def _decode_response(resp) -> list[dict]:
    """解码 ResponseEnvelope → 会话列表（群聊 name/avatar/members）。"""
    env = decode_fields(resp.content)
    if field_int(env, 3) != 0:  # status_code
        raise RuntimeError(
            f"conversation/list status={field_int(env, 3)} err={field_str(env, 4)}"
        )
    payload = field_sub(env, 6)  # body=ResponsePayload
    list_resp = field_sub(payload, 2006)  # conversation_list
    groups: list[dict] = []
    for raw in list_resp.get(1, []) or []:  # conversations（repeated）
        try:
            conv = decode_fields(raw)
        except Exception:
            continue
        if field_int(conv, 3) != CONV_TYPE_GROUP:  # 只留群聊
            continue
        ext = field_sub(conv, 50)  # ConversationExtInfo
        members: list[str] = []
        mem = field_sub(conv, 6)  # ConversationMembers
        for m in mem.get(1, []) or []:  # members（repeated：varint uid 或嵌套 {uid=1}）
            if isinstance(m, int):
                if m:
                    members.append(str(m))
                continue
            try:
                uid = field_int(decode_fields(m), 1)
            except Exception:
                continue
            if uid:
                members.append(str(uid))
        groups.append(
            {
                "group_id": field_str(conv, 1),  # 纯数字 conversation_id
                "short_id": str(field_int(conv, 2)),
                "name": field_str(ext, 5),  # ConversationExtInfo.name
                "avatar": field_str(ext, 7),  # ConversationExtInfo.avatar
                "member_count": len(members),
            }
        )
    return groups


def fetch_group_list(http, device_id: str, limit: int = 50) -> list[dict]:
    """拉取群列表（cmds=2006）。http 为 DouyinHttpPy（已带 imdesktop Cookie）。

    返回 [{group_id, short_id, name, avatar, member_count}]（仅群聊）。
    """
    body = _build_request(device_id)
    url = f"{_LIST_URL}?{_desktop_im_query(device_id)}"
    headers = {
        "Content-Type": "application/x-protobuf",
        "Accept": "application/x-protobuf",
        "x-ss-stub": hashlib.md5(body).hexdigest(),
        "Referer": "imdesktop.douyin.com",
        "User-Agent": (
            "douyinim/1.2.1 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "douyinim/1.2.1 Chrome/130.0.0.0 Electron/33.2.0 Safari/537.36"
        ),
    }
    resp = http.request_raw(
        url, method="POST", headers=headers, body=body, timeout=15
    )
    if not resp.ok:
        raise RuntimeError(f"conversation/list HTTP {resp.status_code}: {resp.text[:200]}")
    return _decode_response(resp)


__all__ = ["_build_request", "_decode_response", "fetch_group_list"]
