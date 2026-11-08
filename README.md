# astrbot_plugin_douyin_dm_mover

把抖音 Bot 账号收到的私信视频/分享卡片，自动搬进指定 QQ 群。

AstrBot 插件：抖音账号（个人号，非官方 WebSocket/Protobuf 接入）收到私信后，按配置路由将
文本/图片/视频卡片等转发到指定 QQ 群。支持多来源/多类型路由、去重、限流、关键词/黑白名单
过滤、失败重试，以及登录态失效主动告警。

## 功能

- **视频/分享卡片自动搬运**：识别抖音私信中的视频卡片（`msg_type=8`），附带视频链接转发。
- **多类型支持**：文本、图片、表情、语音、视频卡片。
- **多目标路由**：路由表按序匹配、可多命中，不同来源/类型分群。
- **去重 + 限流**：按消息 id 去重（可调窗口），全局/按发送者限流。
- **过滤**：发送者黑白名单、关键词命中即丢弃。
- **失败重试**：发送失败进入持久缓存，周期重试。
- **登录态告警**：识别关闭码/关键字判定登录态失效，主动告警且不再静默重连。
- **网关模式**：`inprocess`（默认，线程）或 `subprocess`（独立子进程，崩溃隔离）。

## 安装

在 AstrBot 控制台 → 插件管理 → 从 GitHub 安装，填入仓库地址：

```
https://github.com/cyqmq/astrbot_plugin_douyin_dm_mover
```

或将本仓库 `git clone` 到 AstrBot 的插件目录（如 `data/plugins/`）后重启 AstrBot。

> 需要 AstrBot 版本 `>=4.16,<5`。依赖：`websocket-client>=1.6.0`（安装时自动拉取）。

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
