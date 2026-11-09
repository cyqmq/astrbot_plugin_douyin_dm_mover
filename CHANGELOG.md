# Changelog

本项目所有值得记录的变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [0.9.1] - 2026-11-09

### Changed
- 配置页移除「安装登录依赖」按钮与连接状态「登录后端」行（纯 Python 后端已内置无需安装；后端选择由配置表单 `login_backend` 管理，避免误导）。

## [0.9.0] - 2026-11-09

### Added
- Web 配置页重写：新增 `config/get` + `config/set` 后端端点（读当前配置 + schema、写回 AstrBotConfig 并提示重载生效）。
- 配置表单（33 项分组：登录/转发/限流/去重/重试/过滤/告警）+ **路由表编辑器**（增删改路由项：name/target/types/senders_include/senders_exclude），改配置后点「重载插件」生效。
- 体验优化：登录成功后二维码区显示「已登录」；自动刷新间隔可调（`autoSec`）；发石者/记录项悬停显示原始 detail。

## [0.8.3] - 2026-11-09

### Fixed
- `qr.py` 安全验证判定：`verify_way` 为 `None` 时 `"verify" in None` 抛 `TypeError` 导致登录循环崩溃，改 `(last.get("verify_way") or "")`。
- 发石者时间戳取错字段：`index_in_conversation` 是会话内序号非时间，导致前端 `Invalid Date`/1970；改取 `msg_time`/`create_time` 并统一秒级（毫秒自动换算）。

### Changed
- 发石者列表：类型映射中文（文本/视频卡片/图片/表情/语音/其他），昵称为空回退「用户 `<uid>`」。

## [0.8.2] - 2026-11-09

### Fixed
- `desktop_lite_passport_form_post` 多取一层 `.data`：原版 `requestJson().data`=完整 body，端口返回 `res.get("data")` 丢了顶层 `message`，导致 `send_code` 判不到 `message=="success"`、报"发送短信验证码失败: None"。改返回完整 body，`send_code`/`validate_code` 的 `message`/`data.ticket` 判定恢复。

### Added
- Web 配置页新增「提交验证码」输入框（`POST /douyin_dm_mover/mfa`），可直接喂码给登录 MFA 流程，无需依赖 QQ 群 `/dyf mfa` 指令。

## [0.8.1] - 2026-11-09

### Fixed
- 纯 Python 登录缺少桌面设备注册：此前 `DouyinHttpPy` 默认 `device_id="0"`，`check_qrconnect` 带 0 被抖音反爬限频（`error_code=7`）读不到 `verify_ways`，短信 MFA 永不触发。现移植 `setupDesktopDevice` 回退路径（`device.py`：`guidDeviceId` 十进制 GUID 哈希 + `device.json` 持久化 + saved 复用，与官方非 Windows 行为一致），登录前保证非零 `device_id`。
- `guidDeviceId` 逐字节匹配 Node 参照（`3632482784`）。

## [0.8.0] - 2026-11-09

### Added
- Web 配置页新增「重载插件」按钮（`POST /douyin_dm_mover/reload`）：后台调用 AstrBot `StarManager.reload`，终止当前插件并重新加载，深层代码（`dyf_gateway` 等）无需重启 AstrBot 进程即可生效。

### Fixed
- 重载失效根因：AstrBot 只清 `data.plugins.<dir>.*` 前缀，`main.py` 原清理用 `basename` 前缀——都匹配不到裸名包 `dyf_gateway`/`dyf_core`/`dyf_config`，导致深层模块缓存残留、重载后仍跑旧代码。现改为清裸名包前缀 + 含插件名的模块键。

## [0.7.1] - 2026-11-09

### Fixed
- 自动登录自锁：`login()` 删除 `_login_task` 自检（误判自己刚创建的 task 为"已有登录进行中"），仅保留 `threading.Lock` 并发守卫。
- `get_qrcode` / `check_qrconnect` 响应多取一层 `data`（原版 `requestJson().data`=完整 body，扁平 data 就在 `res["data"]`），修后正常取到 `token`/`qrcode` 与扫码状态。
- `on_status` 未 await（`status()` 与 `_up_sms_mfa_flow` 三处），状态日志不再静默、消除 coroutine 未 await 警告。

## [0.7.0] - 2026-11-09

### Added
- 登录后端迁移为纯 Python：移植 `@alemonjs/douyin` 登录核心（desktop 扫码 + 2046 MFA）到 `dyf_gateway/douyin/login/alemonjs_py/`，含自实现 SM3、jumpbyte `a_bogus`、Passport 签名/表单、CookieJar、HTTP 客户端与扫码轮询编排；登录不再依赖 Node 运行时。
- 新增 `AlemonsPyLogin`（`alemonjs_py_login.py`）作为默认登录后端；Node 桥接保留为可选回退（`login_backend=alemonjs_node`）。
- 「安装登录依赖」入口现提示纯 Python 后端无需安装。

### Verified
- `a_bogus`、`check_qrconnect` URL、desktop-lite MFA URL 逐字节匹配 Node 参照（固定 `nowMs`/`random`）；`buildPassportSignQs` sign/qs 逐字节一致。

## [0.6.1] - 2026-11-09

### Changed
- 登录不再自动安装依赖：点击「登录 / 刷新二维码」仅检测 `@alemonjs/douyin`，未安装时提示「请先到 Web 配置页点击『安装登录依赖』，或手动执行 npm install @alemonjs/douyin」；配置页「安装登录依赖」按钮为唯一安装入口（仍可一键安装）。

## [0.6.0] - 2026-11-09

### Added
- 登录依赖自动安装：插件内置 `package.json`/`package-lock.json`（锁定 `@alemonjs/douyin@2.1.1`），扫码登录前自动检测并 `npm install`（缺装时），零用户操作。
- Web 配置页「安装登录依赖」按钮：`POST /douyin_dm_mover/install-alemonjs` 一键安装/重装；`status` 接口返回 `alemonjs_installed`，视图显示「已安装 / 缺依赖」徽标。
- 登录后端与依赖安装说明写入 README（Node >= 20.19、自动安装、回退 `douyin_spider`）。

## [0.5.0] - 2026-11-09

### Changed
- 登录后端重构：默认改用 `@alemonjs/douyin`（Node 桥接）作为唯一扫码登录后端，其 `getQrcode`/`checkQrconnect`/`sendQrMfaCode`/`validateQrMfaCode` 完整接管扫码 → 2046 短信二次验证 → 会话；内置 `DouYin_Spider` 登录仅作 `login_backend=douyin_spider` 回退。
- 登录实现改为异步 Node 子进程桥接（`alemonjs_bridge.mjs` + `login/alemonjs.py`，NDJSON 行协议），二维码以 SDK 返回的 PNG base64 直接渲染，MFA 沿用 `/dyf mfa <验证码>` 喂码。
- 会话持久化支持 alemons 后端：无 `ticket`/`private_key`（由 cookie 直连建 WS）时 `SessionStore.has_valid()` 放宽。
- 新增配置项 `login_backend`（默认 `alemonjs`）；二维码接口兼容 `data:image` data URL。
- 安装说明补充 Node.js >= 20.19 与 `npm install @alemonjs/douyin`。

## [0.4.1] - 2026-11-08

### Fixed
- 登录按钮冲突：合并「刷新登录二维码 / 登录」为单按钮「登录 / 刷新二维码」，两者此前都触发 `gateway.login()`，第二个因锁返回「已有登录进行中」。
- 登出无状态判断：无有效会话时 `gateway.logout()` 返回 `False`，接口返回「当前未登录，无需登出」，不再无条件报「已登出」；`inprocess`/`subprocess` 两实现同步。
- 登录状态可见性：`status` 接口新增 `login_in_progress`，视图登录态旁显示「登录进行中」徽标。

## [0.4.0] - 2026-11-08

### Added
- 无会话自动扫码登录：插件启动时若无有效会话且未配置 `douyin_cookies`，自动发起扫码登录并生成二维码，无需手动点击「刷新登录二维码」。
- 登录流程日志：扫码启动 / 二维码已生成 / 登录成功失败 各阶段写入运行日志，便于在视图「运行日志」页观察登录进展。

### Fixed
- 2046 二次验证可见性：`auto_sms` 模式发送短信验证码后明确提示「请用 `/dyf mfa <验证码>` 喂码」，此前静默发码并等待喂码，用户不知情导致登录看似卡住。

## [0.3.2] - 2026-11-08

### Fixed
- 唯一名化 `core`/`gateway` 包（→ `dyf_core`/`dyf_gateway`）：`main.py` 的 `from core.dashboard import` 此前可能解析到其它插件同名 `core` 包或残留缓存，导致加载旧签名 `DashboardApi`（`takes 4 positional arguments but 5 were given`）；唯一命名空间彻底隔离，`worker` 启动模块名同步更新。
- `DashboardApi` 业务参数现为 `['context','gateway','forward_manager','logring']`，与 `main.py` 调用匹配。

## [0.3.1] - 2026-11-08

### Changed
- 插件入口自清洁：`main.py` 顶部强制插件目录置 `sys.path` 最前，并清理本插件前缀残留模块缓存，确保 AstrBot 重载时加载新代码而非旧缓存。
- 模块唯一命名：`config.py` 重命名为 `dyf_config.py`，避免与其它插件顶层裸名冲突。
- `DouyinForwardPlugin.__init__` 增加 `_purge_own_modules()`，仅清理 `douyin_dm_mover.` 前缀子模块，不动裸名模块以免误伤其它插件。

## [0.3.0] - 2026-11-08

### Added
- WebUI 视图新增「运行日志」页：展示最近 200 条 `[dyf]` 日志（时间/级别/内容，最新在前），按级别着色，支持刷新/清空，纳入自动刷新；经 `core/logs.py` LogRing 环形缓冲 + loguru sink 捕获插件自身日志。
- 插件 Web API 新增 `logs`(GET) 与 `logs/clear`(POST)，供日志页调用。

### Fixed
- `DouyinForwardPlugin.__init__` 的 `config` 参数可缺省：AstrBot 某些加载路径仅传 `context` 实例化时不再因缺少 `config` 崩溃。

## [0.2.1] - 2026-11-08

### Fixed
- WebUI 视图接口 404：bridge 调用 endpoint 不再含插件名前缀，Python 侧路由注册保留前缀。
- `status` 与 `/dyf status` 对非 dict `sources` 配置的防护（原 `AttributeError` 导致 WebUI 接口 500）。
- 扫码登录 `ModuleNotFoundError: utils.bd_ticket`：补齐 vendored 登录 utils 依赖闭包（12 个模块 + 资源 + `acrawler_runtime/`），登录二维码恢复生成。

## [0.2.0] - 2026-11-08

### Added
- 扫码登录健壮化：复用 DouYin_Spider `login_api.py`（vendored/login 逐字节拷贝，保留 P-256 密钥对与 Cookie 域过滤），不重写原逻辑。
- 2046 风控二次验证独立支路：注入 `check_qrcode`/`_raise_if_blocked` 拦截 error_code=2046，按 token 去重；`mfa_mode` 支持 `auto_sms`/`manual_command`/`alert_wait` 三种模式。
- 会话持久化：登录会话落盘到 `data/dyf/session.json`（cookie/ticket/private_key/device_id 等），登录与私信接收共享同一份 cookie；启动时会话优先。
- 登录管理命令：`/dyf login`、`/dyf logout`、`/dyf mfa [验证码]`；二维码推送到 `alert_target`，MFA 由管理指令喂码。
- WebUI 可视化视图 `views/status/index.html`：展示连接状态、最近发石者、最近搬运记录、登录二维码；支持「刷新登录二维码 / 登录 / 登出 / 清空记录」与自动刷新。
- 插件 Web API：经 `context.register_web_api` 注册 `status`/`senders`/`records`/`qrcode`/`qrcode/refresh`/`login`/`logout`/`records/clear`，供视图通过 bridge SDK 调用。
- 登录二维码渲染为 PNG（`qrcode` + `Pillow` 依赖），此前误用 `Image.fromURL` 抓登录页必然失败。
- `display_name`（"搬搬抖音的石"）。

### Changed
- 版本号 `0.1.0` → `0.2.0`（metadata.yaml 与 `@register` 同步）。

### Fixed
- 插件在 AstrBot 包式导入（`data.plugins.<dir>.main`）下无法加载：`main.py` 导入前自举插件根目录到 `sys.path`，修复 `No module named 'config'`（顶层绝对导入 `config`/`core`/`gateway` 失败）。
- subprocess 网关竞态：worker 发出 `auth_failure` 后随即退出时，`_watch_process` 可能先于 `_read_stdout` 读到退出码，把鉴权失效误判为普通崩溃；现退出后先排空 stdout 状态行再判定。

## [0.1.0] - 2026-11-08

### Added
- 初始发布：抖音个人号私信（含视频/分享卡片）自动搬进指定 QQ 群。
- 接入层：复用 DouYin_Spider WebSocket 协议（vendored 子集），支持 `inprocess` 线程与 `subprocess` 子进程两种网关模式。
- 转发核心：多来源/多类型路由、去重（缓存窗口）、限流（全局 + 按发送者）、关键词/黑白名单过滤、失败重试缓存。
- 登录态失效主动检测与告警（关闭码 + 关键字 + 看门狗），不静默重连。
- `self_uid` 配置/缓存/自动三级解析；协议变更局部替换边界清晰（vendored 目录）。
- 管理命令：`/dyf status`、`/dyf uid`、`/dyf test`。

[0.2.0]: https://github.com/cyqmq/astrbot_plugin_douyin_dm_mover/releases/tag/v0.2.0
[0.1.0]: https://github.com/cyqmq/astrbot_plugin_douyin_dm_mover/releases/tag/v0.1.0
