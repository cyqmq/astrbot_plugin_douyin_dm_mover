# astrbot_plugin_douyin_dm_mover

把抖音 Bot 账号收到的私信视频/分享卡片，自动搬进指定 QQ 群。

AstrBot 插件：抖音账号（个人号，非官方 WebSocket/Protobuf 接入）收到私信后，按配置路由将
文本/图片/视频卡片等转发到指定 QQ 群。支持多来源/多类型路由、去重、限流、关键词/黑白名单
过滤、失败重试，以及登录态失效主动告警。

## 功能

- **视频/分享卡片自动搬运**：识别抖音私信中的视频卡片（`msg_type=8`），附带视频链接转发。
- **多类型支持**：文本、图片、表情、语音、视频卡片、图片合集。
- **信息卡片图**：视频/图集转发时渲染 App Store「Today」风格卡图（封面+渐变+标题+类型），无中文字体或渲染失败自动退回文本。
- **视频详情补全**：可拉 `aweme/detail` 补描述与封面（`video_detail_enabled`）。
- **多目标路由**：路由表按序匹配、可多命中，不同来源/类型分群。
- **去重 + 限流**：视频卡按作品 `itemId` 去重、图集按内容指纹（两帧不重复），全局/按发送者限流。
- **过滤**：发送者黑白名单、关键词命中即丢弃。
- **失败重试（含预算）**：发送失败进入持久缓存，周期重试，`retry_max_attempts` 超限丢弃。
- **media 分批**：图集按 `max_media_per_batch` 分批转发（正文/卡片只进首批，失败即停）。
- **delivery 收口**：全转发失败才告警到告警目标（部分成功不误报）。
- **登录态告警**：识别关闭码/关键字判定登录态失效，主动告警且不再静默重连。
- **网关模式**：`inprocess`（默认，线程）或 `subprocess`（独立子进程，崩溃隔离）。
- **Web 配置台**：内置路由拓扑绑定视图、账户/好友/群列表、调试浮窗（`views/status/`）。

## 安装

在 AstrBot 控制台 → 插件管理 → 从 GitHub 安装，填入仓库地址：

```
https://github.com/cyqmq/astrbot_plugin_douyin_dm_mover
```

或将本仓库 `git clone` 到 AstrBot 的插件目录（如 `data/plugins/`）后重启 AstrBot。

> 需要 AstrBot 版本 `>=4.16,<5`。依赖：`websocket-client>=1.6.0`（安装时自动拉取）。

> **登录后端（默认 `@alemonjs/douyin`）**：需 Node.js `>=20.19`。插件内置 `package.json`/`package-lock.json`，扫码登录时自动检测并执行 `npm install @alemonjs/douyin`（或到 Web 配置页点「安装登录依赖」）。若无法安装 Node，可在配置中将 `login_backend` 设为 `douyin_spider` 回退到内置登录层。

## 配置

在插件配置页填写（`_conf_schema.json` 含全部字段与说明）。核心字段：

| 字段 | 说明 |
|------|------|
| `douyin_cookies` | 抖音登录 cookie 字符串，**必须含 `sessionid`**。登录抖音后从浏览器复制 |
| `self_uid` | 本账号数字 uid，用于判定私信对端。留空则尝试缓存/自动获取，或用 `/dyf uid <uid>` 设置 |
| `gateway_mode` | `inprocess`（默认）\| `subprocess` |
| `qq_adapter_id` | QQ 适配器 id，NapCat 为 `aiocqhttp`，官方 Bot 为 `qq_official` |
| `default_target_group` | 路由表未命中时的兜底目标群号 |
| `routes` | 路由表（见下） |
| `senders_blacklist` / `senders_whitelist` | 发送者 uid 黑白名单（逗号分隔） |
| `keyword_filters` | 命中即丢弃的关键词（逗号分隔） |
| `alert_target` | 登录态失效告警目标（如 `aiocqhttp:GroupMessage:123456`），留空仅日志 |
| `card_enabled` | 视频/图集转发是否生成信息卡片图（默认开） |
| `max_media_per_batch` | 图集媒体分批大小（默认 9，0=不分批） |
| `retry_max_attempts` | 失败重试次数上限（默认 5，超限丢弃） |
| `video_detail_enabled` | 是否补拉视频详情（描述+封面，默认开） |

`routes` 示例（按序匹配、可多命中）：

```json
[
  {
    "name": "视频卡片→A群",
    "match": {"types": ["video_card"]},
    "target": "qq:group:123456"
  },
  {
    "name": "文本/图片→B群",
    "match": {"types": ["text", "image"]},
    "target": "aiocqhttp:GroupMessage:654321"
  }
]
```

`target` 支持三种写法：完整 origin（`aiocqhttp:GroupMessage:群号`）、简化（`qq:group:群号`）、纯群号
（使用 `qq_adapter_id` 拼接）。

## 命令

| 命令 | 说明 |
|------|------|
| `/dyf status` | 查看登录态、self_uid、路由数、失败缓存 |
| `/dyf uid <数字uid>` | 手动设置并缓存 self_uid |
| `/dyf test <群号>` | 向指定群发送一条测试消息 |

## 说明与注意

- **接入方式**：本插件复用 [DouYin_Spider](https://github.com/cv-cat/DouYin_Spider) 的私信
  WebSocket 协议（内嵌最小子集到 `gateway/douyin/vendored/`），以个人号登录态连接，非官方推送。
  抖音协议变更时优先更新 `vendored/`。
- **登录态**：`sessionid` 失效后不再自动重连，会向 `alert_target` 告警一次（`alert_only_once`）。
  需重新登录并更新 `douyin_cookies`。
- **subprocess 模式**：独立子进程跑接收端，崩溃/内存泄漏不拖垮 AstrBot；`/dyf uid` 会实时下发到子进程。

## 借鉴与致谢

- **信息卡片渲染 / delivery 失败记账 / media 分批 / budget 与 dedupe / feedback 反馈设计**：
  借鉴 [nonebot-plugin-parsehub](https://github.com/ByteColtX/nonebot-plugin-parsehub)
  （MIT License，Copyright (c) 2026 ByteColtX）的**设计思想与概念**——包括 App Store
  「Today」风格卡片（封面裁切聚焦 + 竖直渐变遮罩 + 平台名/标题/类型标签）、发送收口与
  失败记账、按容量分批合并转发、共享超时预算与窗口去重、表情/提示反馈。本插件的实现为
  **独立重写**：`card` 用纯 Pillow（渐变遮罩不用 numpy），`delivery/media/budget/dedupe/feedback`
  按 AstrBot 上下文重新设计（抖音私信 WS 直收 + AstrBot `send_message` 投递，非 ParseHub
  链接解析/下载）。未复制 parsehub 源码；其完整 MIT 许可见
  [LICENSE](https://github.com/ByteColtX/nonebot-plugin-parsehub/blob/main/LICENSE)。
- **私信 WebSocket 协议**：复用 [DouYin_Spider](https://github.com/cv-cat/DouYin_Spider) 的
  私信 WS/Protobuf 协议（内嵌最小子集到 `gateway/douyin/vendored/`），以个人号登录态连接，
  非官方推送。抖音协议变更时优先更新 `vendored/`。
  **协议注意**：DouYin_Spider **无开源许可文件**（默认保留所有权利），其 README 声明
  「仅供学习与技术研究使用，严禁用于发布不良信息、违法内容」。本插件内嵌的最小子集
  同样**仅限学习与技术研究**，请勿用于商业分发或任何违法/不良场景；如需商用请先取得
  [cv-cat/DouYin_Spider](https://github.com/cv-cat/DouYin_Spider) 授权。
