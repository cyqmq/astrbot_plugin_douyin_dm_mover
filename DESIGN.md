# DESIGN.md — 抖音私信 → QQ 群自动转发插件架构设计

> 插件名：`astrbot_plugin_douyin_dm_mover`（短标识 `douyin_dm_mover`）
> 目标平台：AstrBot（QQ 侧：NapCat / 官方 Bot 均可用）
> 状态：已评审，按本设计实现

---

## 0. 设计目标与非目标

### 目标
- 抖音账号（个人号，WebSocket/Protobuf 非官方接入）收到的私信，自动转发到指定 QQ 群。
- 不同**来源平台**、不同**消息类型**可路由到**不同目标群**，且每类消息可独立开关。
- 后续新增平台 / 调整转发规则 / 替换协议实现时，**核心转发逻辑零改动**。
- 登录态失效**主动告警**（不静默重连）；`self_uid` 可配置或自动获取并缓存；协议变更可**局部替换**。

### 非目标（本次不实现）
- 不回抖音私信（只收不答）。
- 不做抖音主动发送、不模拟客户端行为。
- 不做 QQ → 抖音 反向转发。

---

## 1. 已验证的技术事实（源码级）

### 1.1 抖音接入层（来源：`cv-cat/DouYin_Spider` 仓库）

- 接入文件：`dy_apis/douyin_recv_msg.py`
- WebSocket 端点：`wss://frontier-im.douyin.com/ws/v2`，`Sec-WebSocket-Protocol: binary, base64, pbbp2`
- 协议：Protobuf 帧 `PushFrame` → `Response` → `body.new_message_notify.message`（`MessageBody`）
- `MessageBody` 字段（`Response_pb2.py`）：`conversation_id`(str)、`conversation_type`(int)、`server_message_id`(int)、`index_in_conversation`(int)、`conversation_short_id`(int)、`message_type`(int)、`sender`(int, 发送者 uid)、`content`(str, JSON)
- `content` 是 **JSON 字符串，需二次 `json.loads`**（`douyin_recv_msg.py:59`）
- `auth.uid` 即 Bot 自身 uid，由 `DouyinAPI.get_my_uid()` 写入（`builder/auth.py:1415`）
- `start()` 是**阻塞循环**（`websocket-client.run_forever`），断线指数退避重连（1s 起、上限 30s）
- 认证：`DouyinAuth.perepare_auth(cookies_str, web_protect_str, keys_str)`，`auth.cookie["sessionid"]` 作为 token

### 1.2 消息类型映射（`douyin_recv_msg.py` + `douyin_im_media.py`）

| `msg_type` | 含义 | 关键字段 |
|---|---|---|
| `7` | 文本 | `content["text"]` |
| `8` | **分享视频卡片** | `content["itemId"]`（含 `uid`/`sec_uid`/`name`/`title`/`share_id`） |
| `27` | 图片 | `content["resource_url"]["origin_url_list"][0]` |
| `5` | 表情包 | `content["url"]["url_list"][0]` |
| `17` | 语音 | `content["resource_url"]["url_list"][0]` |
| `50001` | 对方已读 | 跳过 |

### 1.3 AstrBot 主动发消息（来源：AstrBot v4 源码）

- `unified_msg_origin = f"{platform_id}:{message_type.value}:{session_id}"`
  - 验证：`MessageSession.__str__`（`astrbot/core/platform/message_session.py:19`）
  - `MessageSession.from_str` 按 `":"` 分三段（`:25-27`）
  - `MessageType.GROUP_MESSAGE = "GroupMessage"`（`message_type.py:5`）
- `platform_id` 是**适配器实例 id**（`adapter.config["id"]`，WebUI 创建实例时生成），非固定 `aiocqhttp`/`qq_official`
- 主动发送：`await context.send_message(origin, chain)`
- 结论：QQ 群 origin = `f"{adapter_instance_id}:GroupMessage:{group_id}"`，可完全脱离事件、按群号推送

---

## 2. 包结构（分层对齐 turnrig 成熟模式）

```
astrbot_plugin_douyin_dm_mover/
├── main.py                    # Star 插件入口（装配与生命周期）
├── metadata.yaml
├── config.py                  # AstrBotConfig 定义
├── core/                      # ★ 核心：与平台/协议完全无关
│   ├── model.py               #   InboundMessage / GatewayEvent / AuthState / MessageType
│   ├── listener.py            #   MessageListener：消费 InboundMessage 流，全局门，喂给 ForwardManager
│   ├── forward_manager.py     #   ForwardManager：编排——去重/限流→路由→构建→发送→失败重试
│   ├── rules.py               #   Rule 抽象基类 + 内置规则（对齐 sowing Rule）
│   ├── router.py              #   RouteResolver：路由表匹配
│   ├── message_builder.py     #   MessageBuilder：InboundMessage → MessageChain / OneBot 节点
│   ├── message_sender.py      #   MessageSender：实际发送（context.send_message / call_action）
│   ├── cache_manager.py       #   CacheManager：去重窗口 + 失败发送缓存（持久化 data/）
│   ├── retry_manager.py       #   RetryManager：周期重试失败消息
│   ├── ratelimit.py           #   RateLimiter（全局 + 按发送者，信号量 + 间隔）
│   └── alert.py               #   AlertService：登录态失效/网关异常 → 告警
├── gateway/                   # ★ 接入层边界：Gateway 接口（可整体替换）
│   ├── __init__.py            #   build_gateway(config) 工厂
│   ├── base.py                #   MessageGateway 抽象接口
│   ├── douyin/
│   │   ├── gateway.py         #   DouyinGateway（InProcess 默认 / Subprocess 可选）
│   │   ├── self_uid.py        #   SelfIdentityResolver（自动获取 + 缓存）
│   │   ├── peer.py            #   resolve_peer(conversation_id, self_uid)
│   │   ├── converter.py       #   Douyin 原始帧 → InboundMessage（类型白名单映射）
│   │   ├── detector.py        #   AuthFailureDetector（关闭码/关键字/看门狗）
│   │   └── vendored/          #   ★ DouYin_Spider 适配子集（唯一耦合点，可独立更新）
│   │       ├── recv.py        #     包装 douyin_recv_msg（线程/子进程驱动）
│   │       └── ...            #     pb2 / builder / 必要 utils
│   └── other/                 #   未来新平台 gateway
└── data/                      # 运行时数据（self_uid 缓存、去重状态、失败缓存），勿存插件目录
```

**边界原则**：`core/` 只依赖 `gateway/base.py` 接口与 `core/model.py`；`gateway/` 只产出模型、不回依赖 `core/forward_manager`；`vendored/` 是唯一耦合 DouYin_Spider 的目录。协议更新只替换 `vendored/`（+必要时 `converter.py`），`core/` 与 QQ 发送逻辑零改动。

> 分层职责（对应参考插件）：
> - **MessageListener**（turnrig `message_listener.py`）——消费来源消息，做来源/类型开关、自我消息丢弃，喂给 ForwardManager。
> - **ForwardManager**（turnrig `forward_manager.py`）——编排：去重 → 限流 → 路由匹配 → 构建 → 发送 → 失败缓存/重试。
> - **MessageBuilder**（turnrig `message_builder.py`）——InboundMessage → MessageChain / OneBot 转发节点。
> - **MessageSender**（turnrig `message_sender.py`、discord_qq_bridge）——`context.send_message(f"{adapter}:GroupMessage:{gid}", chain)` 或 `call_action("send_group_msg", ...)`。
> - **CacheManager / RetryManager**（turnrig `cache_manager.py`/`retry_manager.py`）——去重窗口、失败缓存、周期重试。
> - **Rule 基类**（sowing `core/evaluation/rules.py`）——`Rule.evaluate(msg) -> bool`，具体规则独立封装。

---

## 3. 核心数据模型（平台中立）

```python
# core/model.py
class MessageType(str, Enum):
    TEXT = "text"; IMAGE = "image"; VIDEO_CARD = "video_card"
    EMOJI = "emoji"; VOICE = "voice"; OTHER = "other"

class AuthState(Enum):
    OK = "ok"; EXPIRED = "expired"; UNKNOWN = "unknown"

@dataclass
class InboundMessage:
    source_platform: str      # "douyin"
    message_id: str           # server_message_id（去重键）
    conversation_id: str      # "0:{type}:{uidA}:{uidB}"
    peer_id: str | None       # resolve_peer 结果；None=未能判定
    peer_name: str            # 昵称
    type: MessageType
    text: str                 # 文本；视频卡片拼接标题+链接
    media_urls: list[str]
    card: dict | None         # 视频卡片 payload（itemId/title/uid...）
    timestamp: int
    is_outgoing: bool         # sender==self_uid → True，丢弃
    raw: dict                 # 原始解码 content

@dataclass
class GatewayEvent:
    kind: str                 # "auth_failure"|"disconnect"|"reconnect"|"error"|"started"
    detail: str = ""
```

---

## 4. Gateway 抽象

```python
# gateway/base.py
class MessageGateway(ABC):
    @abstractmethod
    async def start(self): ...                                   # 启动 worker（线程/子进程）
    @abstractmethod
    def stream(self) -> AsyncIterator[InboundMessage]: ...       # 归一化消息流
    @abstractmethod
    def events(self) -> AsyncIterator[GatewayEvent]: ...         # 状态/告警事件流
    @abstractmethod
    async def stop(self): ...
    @property
    def auth_state(self) -> AuthState: ...
```

### 4.1 两种运行模式（同一接口，可配置切换）

| 模式 | 实现 | 优势 | 场景 |
|---|---|---|---|
| `inprocess`（默认） | `Douyin_Spider.start()` 在**独立 daemon 线程**执行；解码后经 `loop.call_soon_threadsafe` 放入 `asyncio.Queue` | 简单、低开销 | 常规使用 |
| `subprocess` | `asyncio.create_subprocess_exec` 拉起 worker，worker 逐行输出 JSON（`{"kind":..., "data":...}`），父进程用 `StreamReader` 解析；worker 崩溃→退避重启 | 进程级硬隔离，崩溃/内存泄漏不拖垮 AstrBot；更新 `vendored/` 重启 worker 即可 | 强隔离 / 协议高风险期 |

> 因为 `Douyin_Spider.start()` 是**阻塞循环**，不能直接跑在 asyncio 事件循环里，故线程/子进程二选一是必须的。

---

## 5. 三个必设计点

### 5.1 登录态失效处理（主动告警，不静默重连）

`AuthFailureDetector` 检测链：
1. **关闭码/错误判定**（主）：`on_close(code, msg)` / `on_error(e)` 命中配置特征 → `EXPIRED`。默认特征：关闭码 `4010/4011/4012`，或错误文本含 `session`/`token`/`unauthorized`/`auth`。可配置 `auth_failure_close_codes` + `auth_failure_keywords`。
2. **静默看门狗**（辅）：连上后 `auth_watchdog_minutes`（默认 30）无任何帧 → 发 `error` 事件并主动重连一次；重连后仍无帧 → 升级 `EXPIRED`。
3. **行为差异**：`EXPIRED` 时**禁止自动重连**（`auto_reconnect=False`），避免静默循环；`OK` 时按原退避重连。

**告警**：`AlertService` 订阅 `events()` 的 `auth_failure` → ① `logger.error`；② `context.send_message` 推送 `alert_target`（管理员 QQ 群/私聊 origin）；③ 更新 `auth_state` 供 `/dyf status` 查询。`alert_only_once`（默认 true）防刷屏。

### 5.2 self_uid 获取（判定对端的关键）

`conversation_id = "0:{type}:{uidA}:{uidB}"`，uid 顺序不固定。**peer = 两个 uid 中 ≠ self_uid 的那个**。

`SelfIdentityResolver` 三级来源（优先级高→低）：
1. 配置显式 `self_uid`；
2. 登录后自动获取：`DouyinAuth.uid`（`get_my_uid()`）；
3. `data/self_uid.json` 缓存（自动获取成功后写盘）。

`resolve_peer(conversation_id, self_uid)`：
- 正则 `^0:\d+:(\d+):(\d+)$` → 取 `≠ self_uid` 的；两者均等于 self_uid → 返回 `None`。
- self_uid 未解析 → `peer_id=None`；按配置 `require_peer`（默认 false）决定丢弃或照常转发并标 `unknown`。
- `is_outgoing = (sender == self_uid)`，命中则丢弃。

### 5.3 协议变更风险（局部替换）

- `vendored/` 是唯一耦合 DouYin_Spider 的目录；`converter.py` 做 Douyin `msg_type` → 自有 `MessageType` 的**白名单映射**。
- `gateway_mode="subprocess"` 提供进程级隔离；更新 `vendored/` 重启 worker 即可。
- 依赖策略（D4）：**内嵌 `vendored/` 必要子集**（`douyin_recv_msg`、`Live_pb2`、`Response_pb2`、`builder/`、必要 utils），自包含、版本固定；不引整仓 pip 依赖。

---

## 6. 规则与路由（不同来源/类型分群 + 可开关）

### 6.1 配置模型（`AstrBotConfig`）

```yaml
forward:
  enabled: true
  sources:                     # 来源维度
    douyin:
      enabled: true
      types:                   # 类型维度：都要但可开关
        text: true
        image: true
        video_card: true
        emoji: false
        voice: false
        other: true
  routes:                      # 路由表：按序匹配，支持多命中
    - name: video-to-group-a
      match:
        types: [video_card]          # 空=全部
        senders_include: []          # 空=不限
        senders_exclude: []
      target: qq:group:111111
    - name: text-image-to-group-b
      match:
        types: [text, image, other]
      target: qq:group:222222
  dedup:
    enabled: true
    window_seconds: 300
    key: message_id                  # message_id | content_hash
  rate_limit:
    global: {enabled: true, max_per_min: 30}
    per_sender: {enabled: true, max_per_min: 10}
  formatter:
    header: "[抖音] {peer_name} · {time}"
    include_link: true
  auth:
    alert_target: ""                 # 管理员 QQ 群/私聊 origin
    alert_only_once: true
    auth_failure_close_codes: [4010, 4011, 4012]
    auth_failure_keywords: [session, token, unauthorized, auth]
    auth_watchdog_minutes: 30
  self_uid: ""                       # 可选，显式指定（最高优先级）
  gateway_mode: inprocess            # inprocess | subprocess
```

### 6.2 规则接口

```python
# core/rules.py
class ForwardRule(ABC):            # 全局门：来源/类型开关等
    def applies(self, msg: InboundMessage) -> bool: ...

class RouteRule(ABC):              # 路由表匹配
    def match(self, msg: InboundMessage) -> TargetRef | None: ...
```

### 6.3 ForwardManager 流程（对齐 turnrig）

`ForwardManager.handle(msg)`：
`is_outgoing? → 丢弃` → `来源 enabled? → 丢弃` → `类型开关? → 丢弃` → `CacheManager 去重` → `RateLimiter` → `路由表匹配（多命中）` → `MessageBuilder 构建链/节点` → `MessageSender 发送` → 成功则清去重、失败则入失败缓存（RetryManager 周期重试）→ 记日志/投递结果。

**ForwardManager 只面向 `InboundMessage` 与 MessageSender 接口**，与平台/协议完全解耦。

**去重与失败缓存（对齐 turnrig CacheManager）**：
- 去重键：`server_message_id` 或 `content_hash`，窗口内命中则跳过；
- 发送中的并发防重：`in_flight` 集合 + `batch_hash`（md5 摘要）；
- 失败发送入 `data/failed_sends.json`，RetryManager 每 30–60 分钟重试，成功后清除。

**限流（对齐 turnrig）**：全局 + 按发送者，`asyncio.Semaphore` 控制并发 + 条间 `sleep` 间隔，避免触发 QQ 风控。

---

## 7. MessageSender（QQ 群主动推送，已在参考源码验证）

```python
# core/message_sender.py
class MessageSender:
    async def deliver_to_group(self, group_id: str, chain: MessageChain) -> bool:
        # 已验证模式（discord_qq_bridge / turnrig 同款）：
        origin = f"{self.qq_adapter_id}:GroupMessage:{group_id}"
        await self.context.send_message(origin, chain)   # 或 OneBot: client.call_action("send_group_msg", group_id=..., message=...)
        return True
```

**`QQOriginResolver`（已从 AstrBot 源码验证）**：
- 默认 `qq_adapter_id = "aiocqhttp"`（可配置；`unified_msg_origin` 第一段是适配器实例 id，`MessageSession.from_str` 按 `":"` 三段解析）；
- 构造 `f"{adapter_id}:GroupMessage:{group_id}"` → `context.send_message`；
- 失败 `logger.warning` 并跳过（不中断后续消息），且入失败缓存由 RetryManager 重试。

**输出兼容处理（对齐 discord_qq_bridge / qzone 模式）**：
- `[转发]` 前缀 + 头部模板：`formatter.header` 形如 `[转发] 抖音 {peer_name} · {time}`；
- QQ 不支持 markdown：剥 `**`/`` ` ``/`~~`、Discord mention 转 `@用户`（抖音侧无 mention，但保留统一净化）；
- 消息长度截断：`max_message_length`（默认 1000，QQ 单条上限内）；
- 多目标：循环 `target_groups`，逐目标发送，单目标失败不影响其他。

---

## 8. 插件装配与生命周期（main.py）

```python
class DouyinForwardPlugin(Star):
    def __init__(self, context: Context):
        self.gateway = build_gateway(self.config)
        self.engine = ForwardEngine(context, self.config)
        self.alert = AlertService(context, self.config)
        self._bg = asyncio.create_task(self._run())

    async def _run(self):
        await self.gateway.start()
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._consume_messages())
            tg.create_task(self._consume_events())
```

- 命令：`/dyf status`、`/dyf reload`、`/dyf test`
- `terminate()`：`gateway.stop()` + 取消 task
- 持久化只在 `data/`（self_uid 缓存、去重状态），不写插件目录

---

## 9. 已确认的设计决策

| # | 决策 | 结论 |
|---|---|---|
| D1 | 网关模式 | 默认 `inprocess`（线程）；`subprocess` 作为可选硬隔离，同一接口 |
| D2 | 路由匹配 | 按序匹配、支持多命中；`match_all` 开关 |
| D3 | 视频卡片输出 | 文本摘要 + 视频链接（标题 + `douyin.com/video/{itemId}`），可选封面图 |
| D4 | 依赖策略 | 内嵌 `vendored/` 子集，不引整仓 pip 依赖 |

---

## 10. 风险与合规说明

- **非官方接入风险**：个人号 + WebSocket/Protobuf 接收私信属非官方方案，存在抖音风控/封号风险。代码需做好异常捕获与日志，网关异常不拖垮 AstrBot。
- **协议漂移**：抖音可能变更 protobuf/端点，由 `vendored/` + `converter.py` 局部消化；`gateway_mode="subprocess"` 可降低影响面。
- **QQ 侧**：依赖 AstrBot 已部署的 NapCat/官方 Bot，`unified_msg_origin` 构造需匹配实际适配器实例 id。

---

## 11. 实现顺序建议（后续）

1. `core/model.py` + `gateway/base.py`（抽象先行）
2. `gateway/douyin/vendored/` 子集 + `converter.py` + `detector.py` + `self_uid.py` + `peer.py`
3. `core/rules.py`、`core/router.py`、`core/ratelimit.py`、`core/cache_manager.py`
4. `core/message_builder.py`、`core/message_sender.py`（含 origin 解析、截断、净化）
5. `core/forward_manager.py`、`core/retry_manager.py`、`core/alert.py`
6. `config.py` + `main.py` 装配 + `/dyf` 命令

---

## 12. 参考实现映射（已分析源码）

| 参考插件 | 吸收的模式 | 落到本设计 |
|---|---|---|
| `astrbot_plugin_turnrig` | Listener / ForwardManager / MessageBuilder / MessageSender 职责切分；OneBot 节点格式；去重（batch_hash + in_flight）；限流（Semaphore+sleep）；自我消息过滤（self_id 对比）；失败缓存+周期重试 | `core/listener.py`、`forward_manager.py`、`message_builder.py`、`message_sender.py`、`cache_manager.py`、`retry_manager.py` |
| `astrbot_plugin_discord_qq_bridge` | 最小发送链路 `context.send_message(f"aiocqhttp:GroupMessage:{gid}", MessageChain)`；多目标循环；长度截断；markdown 剥除 + mention 转换；`[转发]` 模板 | `core/message_sender.py`、`formatter` 净化与截断 |
| `astrbot_sowing_discord` | 抽象 `Rule.evaluate()->bool` 基类 + 具体规则独立封装；`storage/` 缓存与规则评估分离 | `core/rules.py`、`cache_manager.py` + `data/` |
| `qzone Message Sender`（GitHub 未检索到，以用户描述为准） | 按接收方类型条件路由；`[转发]` 前缀格式化模板 | `router.py`（目标类型条件）、`formatter.header` 前缀模板 |

---

## 13. 登录健壮化（复用 DouYin_Spider login_api.py）

### 13.1 目标
- 不依赖用户手动复制 cookie：扫码登录（QR）产出会话，自动持久化到插件 data 目录。
- 会话持久化：`data/dyf/session.json`（cookie/ticket/ts_sign/client_cert/private_key/dtrait_blob/uid/device_id），
  参考 douyin-im 的 dataDir 与 douyin-chat-mcp-server 的卷映射——便于备份与容器化部署。
- 登录与私信接收共享同一份 cookie：登录成功 → 会话落盘 → 接收端直接读会话 cookie，无两套登录态。
- 2046 二次验证独立支路，登录失败不静默重连。

### 13.2 复用与注入（不重写）
- **vendored/login/**：逐字节拷贝 DouYin_Spider 的 `dy_apis/login_api.py`、`builder/{auth,header,params}.py`、
  `utils/{http_client,dy_util,fingerprint,passport,dtrait_profile,dtrait_features}.py`。保留其 P-256 密钥对
  （`utils/passport.py` 的 `generate_ec_keypair`）与 Cookie 域过滤（`login_api.py` 的 `WWW_ONLY_COOKIES`/
  `LOGIN_EXCLUDED_COOKIES` + `dy_util.CookieDict` + `scoped_cookies`）。依赖：`curl_cffi`、`loguru`、`ecdsa`、`cryptography`。
- **dy_apis/douyin_api.py = 最小 shim**：仅提供 `builder/auth.py` 用到的 `DouyinAPI.get_device_id/get_my_uid`，
  避免整包引入 google-protobuf/lxml/builder.proto（登录链路不需要 IM/HTTP 全量实现）。
- **2046 注入（login/loader.py）**：不修改 login_api.py，patch `DYLoginApi.check_qrcode` 记录当前
  `(auth, token)`，patch `DYLoginApi._raise_if_blocked`（保留 staticmethod 语义）拦截 `error_code=2046`：
  转交注入的 MFA 处理器并吞掉异常 → qrcode_login 继续轮询同一 token 等放行。按 token 去重（哨兵初值）。

### 13.3 MFA 模式（配置 `mfa_mode`）
| 模式 | 行为 |
|---|---|
| `auto_sms` | 自动调 `send_code/` 发码，验证码经 `code_source` 获取（默认 stdin；QQ 下由 `/dyf mfa <code>` 喂入） |
| `manual_command` | 不自动发码，等待管理员 `/dyf mfa` 触发发码后再取码 |
| `alert_wait` | 仅告警，等待用户在抖音 App 完成验证（不发短信） |

请求形状参考 catbus `second-verify.ts`：`POST login.douyin.com/passport/web/{send_code,validate_code}/`，
body=`encrypt_uid, verify_ticket, std_verify_way=mobile_sms_verify, [std_verify_scene], [std_verify_flow_id],
type=22, aid=6383, verify_type=300|301(按 is_safe_mobile)[, code]`；签名/Cookie 复用 DouYin_Spider
（`_sdk_params`+`with_a_bogus`+`_passport_headers`+`scoped_cookies`+`auth.request`）。
交互参考 karin `login.ts`：登录期全局裸消息消费（同一管理会话）喂码，超时 5 分钟。

### 13.4 命令
- `/dyf login`：扫码登录（QR 推送到 `alert_target`），成功保存会话并重启接收端。
- `/dyf logout`：登出并清除会话。
- `/dyf mfa [code]`：无参=触发发码（manual_command）；带码=提交验证码。

### 13.5 文件
`gateway/douyin/login/{loader,session,mfa,waiter,flow}.py`；网关新增 `login/logout/trigger_mfa_send/submit_mfa_code`，
`start()` 会话优先（`_apply_session_or_config`）；`AlertService` 处理 `qr/mfa/login_*` 事件。
