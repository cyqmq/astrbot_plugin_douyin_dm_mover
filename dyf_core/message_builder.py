"""InboundMessage → MessageChain 构建（含 [转发] 前缀、净化、截断、卡片图）。"""
from __future__ import annotations

import base64
import re
from datetime import datetime

from astrbot.api.event import MessageChain
from astrbot.api.message_components import Image, Plain, Video

from dyf_core.model import InboundMessage, MessageType

_SANITIZE_CHARS = ["**", "`", "~~", "*"]
_SOURCE_LABEL = {"douyin": "抖音"}
# 占位符积木类型 → token（转发时由 _render_text 替换为 _context 真实值）
_PLACEHOLDER_TOKEN = {
    "source": "{source}",
    "peer_name": "{peer_name}",
    "time": "{time}",
    "title": "{title}",
    "desc": "{desc}",
    "link": "{link}",
    "image_url": "{image_url}",
    "video_url": "{video_url}",
}


def _sanitize(text: str) -> str:
    if not text:
        return ""
    for ch in _SANITIZE_CHARS:
        text = text.replace(ch, "")
    return text


def _truncate(text: str, max_length: int) -> str:
    if max_length <= 0 or len(text) <= max_length:
        return text
    return text[: max(max_length - 3, 0)] + "..."


class MessageBuilder:
    def __init__(
        self,
        header_template: str = "[转发] {source} {peer_name} · {time}",
        include_link: bool = True,
        max_length: int = 1000,
        templates: list[dict] | None = None,
        markdown_enabled: bool = True,
        sanitize_body: bool = True,
        config: dict | None = None,
    ):
        self.header_template = header_template or "[转发] {source} {peer_name} · {time}"
        self.include_link = include_link
        self.max_length = int(max_length or 1000)
        self.templates = templates or []
        self.markdown_enabled = bool(markdown_enabled)
        self.sanitize_body = bool(sanitize_body)
        # 配置引用（动态读优先）：templates_set 更新 fm.config 后即时生效，无需重载插件
        self.config = config

    # ---- 模板渲染 ----
    def _context(self, msg: InboundMessage) -> dict:
        source = _SOURCE_LABEL.get(msg.source_platform, msg.source_platform)
        peer = msg.peer_name or "未知用户"
        try:
            t = datetime.fromtimestamp(msg.timestamp) if msg.timestamp else datetime.now()
        except (OSError, ValueError):
            t = datetime.now()
        card = msg.card or {}
        # 对齐 _classify（converter.py 取数权威）：图集 id 在 share_item_id；标题补 content_title
        item_id = str(card.get("itemId") or card.get("item_id") or card.get("share_item_id") or "")
        link = (
            str(card.get("_jump_url") or "")
            or (f"https://www.douyin.com/video/{item_id}" if item_id else "")
        )
        return {
            "source": source,
            "peer_name": peer,
            "time": t.strftime("%H:%M"),
            "title": str(card.get("content_title") or card.get("title") or card.get("desc") or ""),
            "desc": str(card.get("desc") or ""),
            "link": link,
            "image_url": str((msg.media_urls or [""])[0]),
            "video_url": msg.video_url or "",
        }

    def _render_text(self, content: str, ctx: dict, markdown: bool) -> str:
        """渲染模板内容：.format() 容错回退逐键替换；markdown 关闭时净化 Markdown 字符。"""
        try:
            rendered = content.format(**ctx)
        except (KeyError, IndexError, ValueError):
            rendered = content
            for k, v in ctx.items():
                rendered = rendered.replace("{" + k + "}", str(v))
        if not markdown:
            rendered = _sanitize(rendered)
        return rendered

    def _config_templates(self) -> list[dict]:
        """模板列表：config 引用动态读优先（templates_set 保存后即时生效），回退 __init__ 副本。"""
        if self.config is not None and self.config.get("templates") is not None:
            return self.config.get("templates") or []
        return self.templates

    def _template(self, for_media: bool = False) -> dict | None:
        """匹配模板（媒体场景优先 for_media）；无匹配 None。"""
        for t in self._config_templates():
            if bool(t.get("for_media")) == for_media:
                return t
        return None

    def _is_user_template(self, tpl: dict | None) -> bool:
        """用户显式设置的模板：积木 blocks 非空且非迁移自动生成（auto）。
        迁移生成的默认模板（header_template → text 积木）不算用户设置，走现有行为。
        """
        return bool(tpl and tpl.get("blocks") and not tpl.get("auto"))

    def _template_content(self, for_media: bool = False) -> str:
        """模板 content（旧结构兼容）；空回退 header_template。"""
        tpl = self._template(for_media)
        return str((tpl or {}).get("content") or self.header_template)

    def _template_embeds_image(self, for_media: bool = False) -> bool:
        """模板是否内嵌图片（image 积木 / 旧 media 积木 / content 含 {image_url}）→ markdown 场景跳过 Image 组件。"""
        tpl = self._template(for_media)
        if not tpl:
            return False
        for b in (tpl.get("blocks") or []):
            if b.get("type") in ("image", "media"):
                return True
        return "{image_url}" in str(tpl.get("content") or "")

    def _render_blocks(self, blocks: list[dict], ctx: dict, markdown: bool = True) -> str:
        """积木序列 → 文本（占位符由 _render_text 统一替换）。"""
        parts = []
        for b in blocks or []:
            t = b.get("type")
            d = b.get("data") or {}
            if t in _PLACEHOLDER_TOKEN:
                # 占位符积木：输出其 token（随后由 _render_text 替换为 _context 真实值）
                parts.append(_PLACEHOLDER_TOKEN[t])
            elif t == "image":
                # 图片积木：markdown 渲染 ![alt](image_url)，位置由积木决定；plain 输出 alt
                alt = str(d.get("alt", "")) or "{title}"
                parts.append(f"![{alt}]({{image_url}})" if markdown else alt)
            elif t == "video":
                # 视频积木：markdown 渲染 [[video:{video_url}]]（_chain_from_markdown 解析成 Video 节点）；plain 输出 alt
                alt = str(d.get("alt", "")) or "视频"
                parts.append("[[video:{video_url}]]" if markdown else alt)
            elif t == "text":
                parts.append(str(d.get("text", "")))
            elif t == "heading":
                title, body = str(d.get("title", "")), str(d.get("body", ""))
                head = f"# {title}" if markdown else title
                parts.append(f"{head}\n{body}" if body else head)
            elif t == "media":
                img, title, desc = (
                    str(d.get("image", "")),
                    str(d.get("title", "")),
                    str(d.get("desc", "")),
                )
                if markdown and img:
                    parts.append(f"![{title}]({img})")
                if title:
                    parts.append(f"# {title}" if markdown else title)
                if desc:
                    parts.append(desc)
            elif t == "link":
                text, url = str(d.get("text", "")), str(d.get("url", ""))
                parts.append(f"[{text}]({url})" if markdown else f"{text} {url}".strip())
            elif t == "button":
                # 按钮不可配置：恒渲染 [[button:打开视频|{link}]]（_markdown_chain_only 提取成 ActionRow）；plain 只出文案
                parts.append("[[button:打开视频|{link}]]" if markdown else "打开视频")
            elif t == "divider":
                parts.append("***" if markdown else "—")
        return "\n\n".join(p for p in parts if p)

    def render_blocks(self, blocks: list[dict], ctx: dict, markdown: bool = True) -> str:
        """公开渲染入口：积木序列 → 文本（占位符统一替换）。
        预览（模拟上下文）与转发（真实上下文）共用，保证同源。
        """
        rendered = self._render_blocks(blocks, ctx, markdown=markdown)
        return self._render_text(rendered, ctx, markdown=markdown)

    def _header(self, msg: InboundMessage, for_media: bool = False) -> str:
        ctx = self._context(msg)
        # 媒体链（视频/语音/文件）强制纯文本：避免 Markdown 语法原样暴露
        markdown = self.markdown_enabled and not for_media
        tpl = self._template(for_media)
        blocks = (tpl or {}).get("blocks")
        if blocks:
            rendered = self.render_blocks(blocks, ctx, markdown=markdown)
        else:
            rendered = self._render_text(self._template_content(for_media), ctx, markdown=markdown)
        return _truncate(rendered, self.max_length)

    def _body(self, msg: InboundMessage, append_link: bool = True) -> str:
        text = msg.text or ""
        if self.sanitize_body:
            text = _sanitize(text)
        if (
            msg.type == MessageType.VIDEO_CARD
            and self.include_link
            and append_link
            and msg.card
        ):
            item_id = str(
                msg.card.get("itemId") or msg.card.get("item_id") or ""
            )
            link = f"https://www.douyin.com/video/{item_id}"
            if item_id and link not in text:
                text = f"{text}\n{link}".strip()
        return _truncate(text, self.max_length)

    def build_chain(
        self,
        msg: InboundMessage,
        card_image: bytes | None = None,
        media: list[str] | None = None,
        with_text: bool = True,
        layout: dict | None = None,
    ) -> MessageChain | list[MessageChain] | None:
        """构建 MessageChain（用户模板含视频积木时返回 list[MessageChain]，拆视频+Markdown 两条）。

        Args:
            msg: 待转发消息。
            card_image: 卡片图字节（替换首个媒体）；失败退回原媒体。
            media: 指定要发的媒体子集；None 表示全部。
            with_text: 是否带 header + 正文（媒体分批时仅第一批带）。
            layout: 画布布局 {id:{x,y,w,h}}；None 时回退模板内嵌 layout（按钮同行分组用）。
        """
        # 媒体链（视频/语音/文件，非图片卡）→ for_media 模板 + 强制纯文本
        is_media_chain = msg.type not in (
            MessageType.IMAGE,
            MessageType.VIDEO_CARD,
        ) and bool(msg.media_urls or media)
        # 用户模板（积木 blocks 非空且非迁移自动生成）= 整条消息：积木渲染即发送内容，
        # 不再附加正文/媒体（占位符积木取视频卡字段，媒体链用 for_media 模板）
        tpl = self._template(for_media=is_media_chain)
        # 视频卡/图集分享卡长链接 → 按钮：按钮不能与媒体同链（富媒体会 pop markdown 丢键盘），拆成第二条 Markdown 链
        auto_btn_url = ""
        if (
            self.include_link
            and self.markdown_enabled
            and msg.card
            and not self._is_user_template(tpl)
        ):
            is_share = msg.type == MessageType.VIDEO_CARD or (
                msg.type == MessageType.IMAGE
                and bool(msg.card.get("share_item_id") or msg.card.get("_jump_url"))
            )
            if is_share:
                auto_btn_url = self._context(msg)["link"]
        if self._is_user_template(tpl):
            ctx = self._context(msg)
            markdown = self.markdown_enabled and not is_media_chain
            content = self.render_blocks(tpl.get("blocks") or [], ctx, markdown=markdown)
            if not content.strip():
                return None
            if markdown:
                video_first = bool(tpl.get("blocks") and tpl["blocks"][0].get("type") == "video")
                btn_ys = self._button_ys(tpl, layout)
                return self._chains_from_markdown(content, video_first, btn_ys)
            return [MessageChain([Plain(content)])]
        parts = [Plain(self._header(msg, for_media=is_media_chain))] if with_text else []
        body = self._body(msg, append_link=not auto_btn_url) if with_text else ""
        if body:
            # 前置换行：AstrBot 拼接多个 Plain 无换行，正文需独立一行（否则紧贴 header）
            parts.append(Plain("\n" + body))
        # markdown + 模板内嵌图片：卡片图/首媒体不再 append（模板已含 ![..](image_url)）
        md_image_inline = (
            self.markdown_enabled and not is_media_chain and self._template_embeds_image(False)
        )
        # 卡片图（含封面+标题）替换首个媒体（封面），其余媒体照发；失败退回原媒体
        media_urls = list(media if media is not None else msg.media_urls)
        if card_image:
            if md_image_inline:
                media_urls = media_urls[1:] if media_urls else []
            else:
                try:
                    parts.append(Image.fromBase64(base64.b64encode(card_image).decode()))
                    if media_urls:
                        media_urls = media_urls[1:]
                except Exception:
                    pass  # 卡片图失败退回原媒体列表
        for url in media_urls:
            if not url:
                continue
            if msg.type in (MessageType.IMAGE, MessageType.VIDEO_CARD):
                if md_image_inline:
                    continue  # 模板已内嵌图片，不重复发
                try:
                    parts.append(Image.fromURL(url))
                except Exception:
                    parts.append(Plain(f"\n[图片] {url}"))
            else:
                parts.append(Plain(f"\n[附件] {url}"))
        if len(parts) <= 1:
            return None
        chain = MessageChain(parts)
        if auto_btn_url:
            # 按钮独立 Markdown 链（富媒体链会丢弃 keyboard，按钮必须单独一条）
            btn_chain = self._markdown_chain_only(f"[[button:打开视频|{auto_btn_url}]]")
            return [chain, btn_chain] if btn_chain else chain
        return chain

    def _button_ys(self, tpl: dict | None, layout: dict | None) -> list:
        """按钮积木保序的 y 列表（按 blocks 顺序，layout 缺项/无 layout → None 独立）。

        按钮标记在 content 里与 blocks 中 button 积木保序（renderBlocks 保序），
        用 y 分组同行连续按钮。layout 缺 id 项（老模板无布局）→ None → 单钮独立。
        """
        layout = layout if isinstance(layout, dict) else (tpl or {}).get("layout")
        layout = layout if isinstance(layout, dict) else {}
        ys = []
        for b in (tpl or {}).get("blocks") or []:
            if isinstance(b, dict) and b.get("type") == "button":
                pos = layout.get(b.get("id"))
                ys.append(pos.get("y") if isinstance(pos, dict) else None)
        return ys

    def _button_groups(self, btn_ys: list, n: int) -> list[list[int]]:
        """按 y 分组连续同 y 按钮（一行多钮）；btn_ys 缺失/长度不足 → 每钮独立。

        组内元素：同 y 合并组为 (y, [idx])，y None / 独立组为 [idx]（单钮）。
        """
        if not btn_ys or len(btn_ys) < n:
            return [[i] for i in range(n)]
        groups: list = []
        for i in range(n):
            y = btn_ys[i]
            if y is None:
                groups.append([i])
            elif groups and isinstance(groups[-1], tuple) and groups[-1][0] == y:
                groups[-1][1].append(i)
            else:
                groups.append((y, [i]))
        return [g if isinstance(g, list) else g[1] for g in groups]

    def _chains_from_markdown(
        self, content: str, video_first: bool = False, btn_ys: list | None = None
    ) -> list[MessageChain] | None:
        """用户模板整条消息：拆视频 + Markdown 两条独立链。

        视频积木（[[video:url]]）拆出 → Video 富媒体链；Markdown 链只含文本/图片/链接。
        顺序由 video_first 决定：True 视频在前，False 视频在后（视频积木必须在首位/末位）。
        """
        m = re.search(r"\[\[video:(https?://[^)\]]+)\]\]", content)
        video_url = m.group(1) if m else ""
        md_content = content[: m.start()] + content[m.end():] if m else content
        md_chain = self._markdown_chain_only(md_content, btn_ys)
        if not video_url:
            return [md_chain] if md_chain else None
        try:
            video_chain = MessageChain([Video.fromURL(video_url)])
        except Exception:
            video_chain = None
        chains = []
        if video_first:
            if video_chain:
                chains.append(video_chain)
            if md_chain:
                chains.append(md_chain)
        else:
            if md_chain:
                chains.append(md_chain)
            if video_chain:
                chains.append(video_chain)
        return chains if chains else None

    def _markdown_chain_only(self, content: str, btn_ys: list | None = None) -> MessageChain | None:
        """Markdown 链：按钮 [[button:文案|地址]] → ActionRow（btn_ys 按 y 分组连续同 y 按钮成一行多钮）；
        图片 ![](url) 有按钮时保留文本内嵌（避免富媒体丢键盘），无按钮时转 Image 组件。"""
        btn_pattern = r"\[\[button:([^\]|]*)\|([^)\]]*)\]\]"
        btn_m = list(re.finditer(btn_pattern, content))
        parts: list = []
        if btn_m:
            # 有按钮：按钮标记从文本移除，图片保留 Markdown 内嵌
            btn_text = re.sub(btn_pattern, "", content).strip()
            if btn_text:
                parts.append(Plain(btn_text))
            try:
                from astrbot.api.message_components import ActionRow, Button
                has_action_row = True
            except Exception:
                has_action_row = False
            # 按 y 分组连续同 y 按钮 → 一行多钮 ActionRow；无 btn_ys / y None → 单钮独立
            groups = self._button_groups(btn_ys or [], len(btn_m))
            for group in groups:
                if has_action_row:
                    try:
                        btns = []
                        for j in group:
                            m = btn_m[j]
                            label, url = m.group(1).strip(), m.group(2).strip()
                            btns.append(Button(
                                id=f"dyf:open:{j}",
                                label=label,
                                action=Button.UrlAction(url=url),
                                style=Button.Style.PRIMARY,
                            ))
                        # 裸 URL 纯文本（非 markdown 语法）：支持 ActionRow 的平台同时渲染按钮，
                        # fallback_text 若带 [label](url) 会被当 markdown 一起发出 → 每钮重复。
                        # 裸 URL 在支持按钮的平台不渲染成第二个可点链接；不支持的平台另走 Plain 分支。
                        fb = " ".join(
                            f"{btn_m[j].group(1).strip()}: {btn_m[j].group(2).strip()}"
                            for j in group
                        )
                        parts.append(ActionRow(buttons=btns, fallback_text=fb))
                        continue
                    except Exception:
                        pass
                # fallback：无 ActionRow → 每钮文本链接
                for j in group:
                    m = btn_m[j]
                    label, url = m.group(1).strip(), m.group(2).strip()
                    parts.append(Plain(f"[{label}]({url})"))
            return MessageChain(parts) if parts else None
        # 无按钮：现状——图片转 Image 组件
        last = 0
        for m in re.finditer(r"!\[[^\]]*\]\((https?://[^)]+)\)", content):
            if m.start() > last:
                parts.append(Plain(content[last:m.start()]))
            try:
                parts.append(Image.fromURL(m.group(1)))
            except Exception:
                parts.append(Plain(content[m.start():m.end()]))
            last = m.end()
        if last < len(content):
            parts.append(Plain(content[last:]))
        return MessageChain(parts) if parts else None
