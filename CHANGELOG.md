# Changelog

本项目所有值得记录的变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
