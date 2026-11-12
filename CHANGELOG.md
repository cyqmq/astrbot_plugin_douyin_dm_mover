# Changelog

本项目所有值得记录的变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

## [1.3.0] - 2026-11-12

当前阶段成果收尾（登录后端改造推迟，待更合适方案）。自 1.2.64 起累计：

- **BDTicket 产票改造**（探针实测复刻）：登录前发布公钥 + 解析 `Bd-Ticket-Guard-Server-Data` 响应头产票；`bd_ticket_headers` 修 `ree-public-key`（客户端公钥）+ `web-sign-type`（pub.→hmac）两错。
- **www cookie 导入免私钥**：`bd-web-sign-page-guard` cookie 自带完整材料（ts_sign + ree_public_key + web_version + web_sign_type）直抄，无需私钥/重签。
- **域隔离**：imdesktop 与 www 两个登录系统；`friends` 分域——familiar 用 imdesktop 主登录态，following/follower 用 www 登录态（`session.save_www`/`load_www` 独立存储）；`import_login` 不覆盖主登录态。
- **一条路由卡连多个目标卡**：`Route.targets[]` + `_route_diff` 比较列表；前端 `targets[]` 贯穿 + 旧 `target` 归一化迁移。
- **登录/保存/登出/前端系列修复**：Vue Proxy structured clone、刷新二维码代次计数、登出清 `worker_config.json`、`session.save` 保留 www/sec_uid、路由卡对象引用、`Delete` 断开、familiar 软失败等。

## [1.2.73] - 2026-11-12

### Added
- **一条路由卡连多个目标卡**：`Route` 增加 `targets: list[str]`（`target` 保留兼容旧配置）；`resolve` 对每命中路由产出全部 targets（`forward_manager._resolve_targets` 已支持多对不变）；`_route_diff` 比较 `targets` 列表。前端 `r.target → r.targets[]`：`addRoute`/`onConnect`(push)/`onEdgesDelete`(splice)/`buildEdges`(遍历 + 边 id 含目标下标)/`delTarget`/`updateTarget` 全改；`loadConfig` 归一化旧 `target` → `targets: [target]`（兼容既有配置）。

## [1.2.72] - 2026-11-12

### Fixed
- **路由卡删错卡（位置索引失效）**：`RouteNode` 用节点构建时的 `store.routes` 位置索引（`data.index` 快照）做删/移/边/连接；`moveRoute` 原地交换后 watcher（只在 `routes.length`/`targets` 拼接串等变化时 `build()`）不触发——长度不变、target 相同时 join 不变 → 节点 `data.index` 依旧 → 交换后点 A 卡 `×` 删 `routes[0]`（实为 B）。修复：路由卡删/移/边删除/连接/拖拽全改用**路由对象引用**（`indexOf(route)`/`data.route`），不再用位置索引。

## [1.2.71] - 2026-11-12

### Fixed
- **连线断不开（删除键不匹配）**：`TopologyFlow.vue` 提示「选中连线按 `Delete` 断开」但 `<VueFlow>` 未配 `delete-key-code`，`@vue-flow/core` 默认删除键是 `Backspace`——按 `Delete` 不被识别，`edges-delete`/`onEdgesDelete` 不触发（删除链路本身通，卡在按键一环）。修复：补 `:delete-key-code="'Delete'"` + `delete-key-code-prevent-default`（与提示一致）。

## [1.2.70] - 2026-11-12

### Fixed
- **`session.save` 覆盖丢失 www 登录态 + sec_uid 空**：每次登录重建整个 data dict 覆盖 session.json——`www` 键丢失 → `load_www()` 返回 `{}` → `dashboard.friends` 的 `www_http=None` → `fetch_contact_lists` `with_www=False` → following/follower 整段跳过（静默）；www 登录（`alemonjs_www`）不带 sec_uid → save 落空 → `if with_www and uid and sec_uid` 不满足 → 跳过。修复：`save` 保留旧值兜底（uid/sec_uid 空时保留旧值）+ 保留 `www` 键（域隔离独立存储）。

## [1.2.69] - 2026-11-12

### Fixed
- **following/follower 不显示（sec_uid 未持久化）**：`dashboard.friends` 的 uid/sec_uid 靠 profile 实时拿；familiar 8（风控）时 profile 也失败 → `sec_uid=""` → `fetch_contact_lists` 的 `if with_www and uid and sec_uid` 不满足 → following/follower 整段跳过（不是失败，是没执行）。修复：`session.save`/`build_auth` 持久化 `sec_uid`；`AlemonjsResult` 加 `sec_uid`（profile 提取）+ `gateway`/`subprocess_gateway` alemonjs 分支 `auth.sec_uid = result.sec_uid`；`dashboard.friends` profile 失败时 fallback session 的 uid/sec_uid（不只 uid）。

## [1.2.68] - 2026-11-12

### Changed
- **去重 + 精简（低风险）**：`fetch_friend_list` 内联构造用户项改用 `_user_entry`（去 ~25 行重复）；删 REL 调试 `logger.info`（每好友一行，三态已定生产噪音）；`CERT_HEADERS`/`COOKIE_KEYS` 诊断日志降 `debug`（探针残留）。
- **删 bd_ticket.py 死代码**：`_pem_body`/`_server_pub_point`/`_hkdf_sha256`/`derive_ecdh_key`/`get_req_sign`/`get_req_sign_hmac`（约 60 行 ECDH/HMAC 签名残留——只读 4 头不签名，回关 follow 走 imdesktop 也不用）+ 连带 `_P256_SPKI_PREFIX`/`hashlib`/`hmac`/`VerifyingKey`/`sigencode_der` import。

## [1.2.67] - 2026-11-12

### Fixed
- **familiar 失败阻断整个 friends**：`fetch_contact_lists` 的 `fetch_friend_list(http)` 无 try 包裹——familiar 失败（如 status_code=8）抛异常阻断整个 friends，following/follower 也不执行。修复：familiar 软失败（记 `http.familiar_error`），与 following/follower 的 `www_errors` 对称；`dashboard.friends` detail 透出 `familiar_error`/`www_errors`（两者都失败时合并提示）。

## [1.2.66] - 2026-11-12

### Changed
- **域隔离改造（探针决定性验证复刻）**：imdesktop 与 www 是两个登录系统，alemonjs（imdesktop）sessionid 不能被 www 接口识别。`friends` 按 cookie 来源分域：familiar 用 imdesktop 主登录态（现状），following/follower 用 www 登录态（`session.load_www`，导入的 www cookie + `bd-web-sign-page-guard` 免私钥 4 头），合并返回；无 www cookie 时 following/follower 提示「需导入 www cookie」。`import_login`（worker + SubprocessGateway）改存 www 独立（`session.save_www`），不覆盖主登录态、不重启 worker（WS/familiar 保持 imdesktop）；`fetch_contact_lists` 加 `www_http` 参数（分域）。

## [1.2.65] - 2026-11-12

### Changed
- **www cookie 导入免私钥（探针决定性验证复刻）**：只读接口（following/follower）4 头无需私钥、无需 HMAC——`bd-web-sign-page-guard` cookie 自带完整材料（ts_sign + ree_public_key 客户端公钥 + web_version + web_sign_type），直接抄字段即可，浏览器私钥不导出也不影响。`import_www_session` 优先 `extract_page_guard`（cookie 提取）；无该 cookie 回退发布公钥重签。`bd_ticket_headers` 支持 guard 型（直抄 ree_public_key，无 client-data）+ ECDH 型（私钥派生）。`session.py`/`gateway.import_login` 持久化 `ree_public_key/web_version/web_sign_type`。

## [1.2.64] - 2026-11-12

### Changed
- **BDTicket 产票改造（探针实测复刻）**：imdesktop 流从不 set `bd_ticket_guard_ts_sign_id`（Set-Cookie 只有 reg-store-region 清理 + `bd_ticket_guard_server_data`），原 `build_bd_ticket` 读错键永远产票失败。改为：登录前 `publish_public_key`（写 `bd_ticket_guard_client_data` cookie 发布客户端公钥，缺了它扫码成功但服务端不签发票据）+ confirmed/get_client_cert 后解析响应头 `Bd-Ticket-Guard-Server-Data`（或 Set-Cookie `bd_ticket_guard_server_data`，base64 URL→JSON `{ticket,ts_sign,client_cert,log_id,create_time}`）。`qr.login_by_qrcode` 取码前 `publish_public_key`；`import_www_session` 同样发布公钥 + 解析 Server-Data 产票（供 www 票据生成复用）。

### Fixed
- **只读 4 头两个错误（探针实测）**：`bd_ticket_headers` 的 `bd-ticket-guard-ree-public-key` 应为**客户端公钥**（`get_ree_key(private_key)`，非服务端 `client_cert`）；`web-sign-type` 反了——应为 `1` if client_cert 有 `pub.` 前缀（hmac）else `0`（ecdsa），原 `pub.`→`0` 错。无 `private_key` 返回 `{}`。

## [1.2.63] - 2026-11-11

### Fixed
- **familiar/list `status_code=8`（a_bogus 风控）**：`dashboard.py` 三处 `set_device({"deviceId": dev, "installId": "0", "guid": "0"})` 硬编码 `guid="0"` 覆盖 `__init__` 的随机 guid（`random_desktop_hex(32)`）→ `awemeim_guid=0` 进 a_bogus 签名，抖音现校验 guid 不能为 "0" → 签名无效 `status_code=8`（旧版接受 "0"）。修复：只设 `deviceId`，`guid` 保留随机 32 位 hex（`install_id` 默认 "0"，若仍风控再提有效 iid）。

## [1.2.62] - 2026-11-11

### Fixed
- **刷新二维码只能生成一次**：`SubprocessGateway.login` 开头 `if self._logging_in: 返回"已有登录进行中"`——第二次点刷新被拦，页面永远停在第一个二维码；`gateway.py`（worker）用 `_login_lock` 非阻塞 acquire 同样拦截。修复：`_kick_login` 保存登录任务、刷新时 cancel 旧任务；两个 `login` 用代次计数（刷新时强制停止当前接收器重新开始；被 cancel 的旧任务 finally 因代次不等不覆盖新任务的 `_logging_in`/锁）；`except asyncio.CancelledError: raise` 透传取消。

## [1.2.61] - 2026-11-11

### Fixed
- **登出漏清 `worker_config.json` 致重载自动登录**：登出只清了 3 处（session.json、内存 dict、AstrBot 主配置），漏 `_write_config()` → `worker_config.json` 仍留旧 `douyin_cookies`；重载时新 worker 读它自动登录。且 `save_config()` 用 revision 乐观锁（登出后 worker 自动登录写更高 revision → 清空被跳过不提交）。修复：`subprocess_gateway.logout` 补调 `_write_config()` 强制清空 `worker_config.json`，不依赖 revision 机制。

## [1.2.60] - 2026-11-11

### Fixed
- **inprocess 网关 `alemonjs_www` 不生效**：`subprocess_gateway` 有 `alemonjs_www` 分支（www 扫码产票），但 `gateway.py`（inprocess）没有，`alemonjs_www` 落 `else` → vendored `qrcode_login`（不产票）。修复：`gateway.py` 补 `alemonjs_www` 分支（与 subprocess 对称），登录后同步票据（ticket/ts_sign/private_key/client_cert/server_cert）到运行态 `_auth`。
- **移除 `alemonjs_node` 死选项**：commit `7117950` 已删 Node 桥接代码，但 `store.js` SELECTS 还留着 `alemonjs_node` 选项，选中后落 `else`（与 `douyin_spider` 同）误导用户。移除。

## [1.2.59] - 2026-11-11

### Fixed
- **保存失败：Vue Proxy 无法 structured clone**（`请求失败: Failed to execute 'postMessage'...could not be cloned`）：`ConfigTab.pick()` 从 `store.cfg` 取的对象/数组字段是 Vue 响应式 Proxy（`sources`/`routes` 等），`postMessage` structured clone 无法克隆 Proxy → 保存永远失败。修复：`pick()` 用 `JSON.parse(JSON.stringify(...))` 深拷贝剥离 Proxy（治本）+ `saveConfig` 入口统一克隆兜底（防其他调用方踩坑）。

## [1.2.58] - 2026-11-11

### Fixed
- **bridge 失败被吞**（`apiPostBody` catch 返回 `{}`，`saveConfig` 再弹"保存失败"，真实错误被掩盖）：`apiGet`/`apiPost`/`apiPostBody` catch 统一返回 `{ok:false, detail:'请求失败: ...'}`（不再 swallow 成 `{}`；apiGet/apiPost 保留 toast，apiPostBody 不 toast 由调用方弹）；`saveConfig` 改 `toast(d.ok ? '已保存' : (d.detail || '保存失败'))`——失败弹真实错误可见。

## [1.2.57] - 2026-11-11

### Fixed
- **`_diagnose_config` 读盘 BOM 误判**：AstrBot `save_config` 写盘是 `utf-8-sig`（带 BOM），`_diagnose_config` 用 `utf-8` 读 config → `Unexpected UTF-8 BOM` → `disk_routes=-2` 误判"解析失败"（只影响诊断日志显示，不影响保存）。读改用 `utf-8-sig`。

## [1.2.56] - 2026-11-11

### Fixed
- **登出写回 AstrBot 主配置文件**（内存 dict 与主配置文件是两份，登出只清内存那份）：`subprocess_gateway.logout` 清 `self._config` 三键后**没写回主配置**——`build_gateway` 的 subprocess 分支原不传 `config_obj`（`SubprocessGateway(config)`），AstrBot 主配置文件里的 `douyin_cookies` 还在 → 更新插件 terminate/load 从主配置读回自动登录。现：`build_gateway` subprocess 分支传 `config_obj`；`SubprocessGateway.__init__` 存 `_config_obj`；`logout` 清 `self._config` + `_config_obj` 三键并 `save_config()` 落盘。

## [1.2.55] - 2026-11-11

### Fixed
- **`save_config` 失败诊断**（用户"保存失败"但日志空）：`dashboard.config_set` 的 `save_config()` except 之前只返回 `detail` 不打 `[dyf]` 日志——现打 `[dyf] save_config 异常: {e!r} config_path={...}`（带异常详情 + `config_path` 空/权限判断），`detail` 也带 `config_path`——定位是 `config_path` 空/权限不足还是 JSON 序列化失败。

## [1.2.54] - 2026-11-11

### Added
- **登录后端变更日志**：`dashboard.config_set` 保存配置时若 `login_backend` 值变化，打 `[dyf] 登录后端变更: 旧 -> 新（需重载插件生效，重载后登录卡片显示生效值）`——改设置页选项后日志立即可见变更。

## [1.2.53] - 2026-11-11

### Fixed
- **父进程登出清 AstrBot 配置**（用户登出走 `subprocess_gateway.logout`，与 worker `gateway.logout` 不同步）：`subprocess_gateway.logout` 只 `session.clear()`，没清 `self._config` 的 `douyin_cookies/self_uid/device_id`——`_write_config:106` 保留 config 里的 `douyin_cookies` → worker 重启读它自动登录（更新插件触发重启 → 自动登录回去）。现在父进程登出同步清 `self._config` 三键（与 `gateway.logout` 1.2.43 保持一致，两处都清）。

## [1.2.52] - 2026-11-11

### Added
- **登录卡片显示当前登录后端**：`dashboard.status` 加 `login_backend_active`（gateway 运行时实际生效值，与配置页 `login_backend` 区分）；OverviewTab pills 加「登录后端」——显示生效值 + 友好名（`@alemonjs/douyin`/`www 扫码（自动产票）`/`Node 桥接`/`旧 vendored`）；若生效值 ≠ 配置值显示「配置未生效，需重载插件」（黄色告警）——改设置页选项后立刻看清是否生效。

## [1.2.51] - 2026-11-11

### Added
- **`login_backend` 前端加 `alemonjs_www` 选项**（设置页可切 www 产票——原前端缺选项，后端 1.2.50 已支持但无法配置）。
- **票据缺失软失败提示**：`dashboard.friends` 无 `ts_sign` 时返回 `detail`（"未配置 BDTicket（仅显示互关 familiar）——请用 alemonjs_www 登录或好友页「导入 Cookie」"）；有票据但 following/follower 失败时透出 `http.www_errors`（`fetch_contact_lists` 记录到 `http.www_errors`）——不再静默空，界面可见。

## [1.2.50] - 2026-11-11

### Added
- **www 扫码登录（自动产票）**：新增登录后端 `alemonjs_www`——复用 vendored DouYin_Spider 链（`bootstrap_auth` 取码前写 `bd_ticket_guard_client_data` cookie（公钥交服务端）+ `apply_ticket_guard` 每跳解析响应头 `bd-ticket-guard-server-data` → ticket/ts_sign/client_cert）；`www_login.py`（vendored DYLoginApi.qrcode_login + on_qrcode 转 PNG data URL）；`AlemonjsResult` 加 `ticket`；`subprocess_gateway.login` 加 `alemonjs_www` 分支（存 ticket/ts_sign/private_key/client_cert 到 session）；`_conf_schema.json` `login_backend` 加 `alemonjs_www` 选项。**IM/WS 保持 imdesktop**（此登录只产票，不切 WS）。

### Notes
- imdesktop 扫码（alemonjs）不产票据，仅 familiar 可用；要关注/粉丝/回关走 `alemonjs_www`（www 扫码，响应头产票）。
- 切换 `login_backend=alemonjs_www` 后自测：www 扫码 → 确认 `session.json` 有 `ticket/ts_sign/client_cert/private_key` → following/follower 通。

## [1.2.49] - 2026-11-11

### Fixed
- **`contact._fetch_www_user_list` query 校准**（following/follower 走通）：`max_time` 用**毫秒**（原秒，抖音要毫秒）；query 补全 9 个缺失参数（`device_platform=webapp`/`aid=6383`/`channel=channel_pc_web`/`offset=0`/`min_time=0`/`gps_access=0`/`address_book_access=0`/`is_top=1`/`pc_client_type=1`）——原缺参直接 `status_code=8`（a_bogus 风控）。

## [1.2.48] - 2026-11-11

### Fixed
- **BDTicket 4 头/数据流修正**（手动导入票据走通后的校准）：
  - `bd_ticket_headers`：`ree-public-key` 改用 `client_cert`（去 `pub.` 前缀，原用私钥算公钥）；`web-sign-type` 修正（`pub.` 前缀→`0` ecdsa，原反了）；无 `ts_sign/client_cert` 返回 `{}`（无私钥也能带 4 头，只读列表用 client_cert 不用私钥）；
  - `session.load_bd_ticket` 补 `ticket` 字段；
  - `http._apply_bd_ticket` 去掉 `private_key` 强制（4 头用 ts_sign/client_cert）；
  - `contact._fetch_www_user_list`：query 加 `max_time=当前时间戳` + `source_type=1`（防"推荐"分支空）；响应字段改 `followings`/`followers`（原读 `user_list` 错）；
  - `dashboard.friends`：**uid 从 profile 拿**（原用 `uid_tt` 加密值当 uid 是 bug，直接导致 following 空），profile 失败才 fallback `auth.uid`，绝不读 `uid_tt`。

### Notes
- 私钥只回关（写接口 `bd-ticket-guard-client-data`）要；4 头只读不用私钥。
- 票据有生命周期，过期需重新登录拿；`cookie + private_key` 敏感不入 git。

## [1.2.47] - 2026-11-11

### Added
- **手动网页 Cookie 导入**（BDTicket 兜底，票据真源是 www 登录响应头 `bd-ticket-guard-server-data`，imdesktop 扫码不产生）：`bd_ticket.import_www_session`（校验 sessionid → 从 cookie 解析 `bd_ticket_guard_ts_sign_id`（浏览器登录后写入）→ `build_bd_ticket`（fetch_server_cert + 生成私钥/证书）；也可直接补填完整票据 ts_sign/private_key/client_cert/server_cert）；`gateway.import_login`（写配置/session + 重启 worker）；dashboard 加 `douyin_dm_mover/import_cookies`（POST）；前端好友页加「导入 Cookie」弹窗（cookie_str + 可选票据字段）。

## [1.2.46] - 2026-11-11

### Fixed
- **登出断连（`logout` 没真正停 receiver）**：`logout()` `self._stop_receiver()` 没 `await`（receiver 还在收消息，消费循环处理时 `_enrich_video` 访问已被置 None 的 `self._auth.cookie_str` → `'NoneType' object has no attribute 'cookie_str'`）；改 `await self._stop_receiver()`；`login()` 同样漏 await 一并补上。
- **`_enrich_video` 兜底**：开头 `if self._auth is None: return`（即使队列有残留，不再崩）。

## [1.2.45] - 2026-11-11

### Added
- **响应头诊断**（找 `bd-ticket-guard-server-data`——ts_sign 真源）：登录 confirmed 响应头打 `[dyf] LOGIN_HEADERS: {...}`（`check_qrconnect`，仅 confirmed 时）；`fetch_server_cert` 打 `[dyf] CERT_HEADERS: {...}`——看哪个响应头带 `bd-ticket-guard-server-data`（base64 JSON → `["ts_sign"]`），据此改 `build_bd_ticket` 取 ts_sign。

## [1.2.44] - 2026-11-11

### Fixed
- **BDTicket 建票据顺序**（@alemonjs 扫码本身不产生 `bd_ticket_guard_ts_sign_id`，ts_sign 来自 `get_client_cert` 响应 Set-Cookie）：`build_bd_ticket` 改为**先调 `fetch_server_cert`**（触发 set-cookie 并 merge 进 jar）**再读 ts_sign**；cookie 未 set 票据返回 `{"error": "get_client_cert 未 set bd_ticket_guard_ts_sign_id"}`（不再提前返回 `{}` 连证书都不调）；`qr._session_from_confirmed` 只在有 `ts_sign` 时存 `bd_ticket`，`error` 转 `bdTicketError` 供诊断。

## [1.2.43] - 2026-11-11

### Fixed
- **登出清 AstrBot 配置**（重启/更新插件自动恢复登录的根因）：`logout()` 只清了 `session.json`，漏清配置层的 `douyin_cookies/self_uid/device_id`（登录时 `_persist_login_config` 写入 AstrBot 配置并落盘，启动逻辑 `gateway.py:43` 优先读配置的 `douyin_cookies` 重建会话）——登出现在同步清 `self._config` + `config_obj` 并 `save_config`，两路（配置 + session.json）都空，重启不再自动登录；顺带 `self._auth` 置空（避免旧对象持 cookie 致二次登出误判已登录），`logout` 开头用 `getattr(self._auth, "sessionid", None)` 防 `_auth` 为 None。

## [1.2.42] - 2026-11-11

### Added
- **BDTicket 票据移植**（DouYin_Spider `utils/bd_ticket.py` + `builder/header.py:with_bd_readonly`）：新建 `alemonjs_py/bd_ticket.py`（ECDH/HKDF/`get_ree_key`/`get_req_sign`/`ticket_guard_version`/`fetch_server_cert`/`build_bd_ticket`/`bd_ticket_headers`）。
- **登录建票据**：`qr._session_from_confirmed` 登录 confirmed 后从 cookie 取 `bd_ticket_guard_ts_sign_id`（ts_sign）→ `fetch_server_cert`（POST `www.douyin.com/passport/ticket_guard/get_client_cert/`，body `server_data=1,aid=6383` 逗号分隔）→ 生成客户端 P-256 私钥 + 证书（`pub.<b64 公钥点>`）→ session 带 `bd_ticket`。
- **票据持久化**：`AlemonjsResult` 加 `ts_sign/private_key/client_cert/server_cert`；`subprocess_gateway` 登录后塞进 auth；`session.py` save/load 加 `server_cert` + 新增 `load_bd_ticket()`。
- **请求自动加 4 头**：`http.request_raw` 对 `www.douyin.com`/`imdesktop.douyin.com` 且挂有票据时自动加 `bd-ticket-guard-ree-public-key/-version:2/-web-version/-web-sign-type`（`bd_ticket_headers`，无 client-data）；`DouyinHttpPy` 加 `bd_ticket` 属性 + `set_bd_ticket()`。
- **following/follower 接入**：`contact.py` 加 `_fetch_www_user_list`（www `user/following/list/`+`follower/list/`，4 头自动加 + Referer 用户主页）+ `fetch_contact_lists`（familiar 互关 + following 关注 + follower 粉丝，按 uid 去重，familiar 优先）；`dashboard.friends` 改用它并挂票据（uid 取 auth/uid_tt，sec_uid 从 self profile）；`profile.fetch_desktop_self_profile` 加 `sec_uid`；`dashboard.follow` 也挂票据。

### Notes
- **重登录一次**走新流程建证书：登录后 COOKIE_KEYS 应出现 `bd_ticket_guard_ts_sign_id`（cookie 键），票据建成功才有 4 头——follow/following/follower 才能通过风控；若 cookie 无该键则 `build_bd_ticket` 返回 `{}`（不建票据），仅 familiar 可用。

## [1.2.41] - 2026-11-11

### Fixed
- **好友三态字段/判断**（实测：`follow_status=2`（2=已关注，非1）+ `follower_status=1`（他关注我））：`contact.py` 透传改 `follower_status`/`relation_label`（原 `is_following` 不存在）；前端 `stateOf` 改 `fs>=1`（已关注是 1 或 2，不能只判 ===1）+ `follower_status` 判互关——互关显示「互关」（无回关按钮）、未回关显示回关按钮。

### Notes
- **BDTicket 缺失**（COOKIE_KEYS 无 `bd_ticket`）：follow/user（imdesktop 需票据）、following/follower（www 需 bd-ticket-guard）都走不通；只有 familiar/list（a_bogus）可用。需重扫二维码登录（@alemonjs 桌面扫码会建 `bd_ticket`）后 COOKIE_KEYS 出现 `bd_ticket` 再测回关。

## [1.2.40] - 2026-11-11

### Added
- **登录态 cookie 键诊断**：`dashboard.friends` 拉好友前打 `[dyf] COOKIE_KEYS: ...`——看登录态有没有 `bd_ticket_guard`/`__ac_nonce`/`BDticket`，决定 follow/following/follower 能否走通（缺票据则需重扫二维码）。

## [1.2.39] - 2026-11-11

### Fixed
- **follow 404 Janus 根因**：接口改到 `imdesktop.douyin.com/aweme/v1/web/commit/follow/user/`（www 的 `item/follow` 已废弃，Janus 不认）。参数**全在 query**（非 body）：`user_id`/`secUid`（camelCase）/`type`（1 关注 / 0 取关，非 `action`）/`tag=frienddetail`/`verifyFp=verify_{device_id}`；body 空；`Referer: https://imdesktop.douyin.com`；复用 `desktop_rest_base_query`（imdesktop 公共参数含 device_id）。`follow_user`/`unfollow_user` 改用 `followed` bool；dashboard 调用不变（`action==1`→关注）。

## [1.2.38] - 2026-11-11

### Changed
- **REL 诊断聚焦关系字段**：`contact.py` 只打 `follow`/`relation`/`is_` 字段值（去 `cancel`）——不截断，一次拉好友页看每个好友 `follow_status`/`is_following`/`relation` 实际值，定三态映射。

## [1.2.37] - 2026-11-11

### Fixed
- **好友列表漏未回关**：`contact.py` 原 `if u.get("user_canceled"): continue` 把未回关（他关注我、我没关注他，可能 `user_canceled=1`）的滤掉了 → 只显示互关的。放宽为 `user_canceled and follow_status != 0` 才滤（未回关 `follow_status=0` 保留显示）。

### Changed
- **诊断改 REL**：`contact.py` FRIEND_KEYS 改为 `[dyf] REL: ...`（只打 `follow`/`relation`/`is_`/`cancel` 字段值）——一次拉好友页看每个好友 `follow_status`/`user_canceled` 实际值，校准过滤与三态。

## [1.2.36] - 2026-11-11

### Added
- **follow 302 诊断**：`http.py request_raw` 加 `allow_redirects=True` 参数；`follow.py _commit_follow` 改用 `request_raw(..., allow_redirects=False)` + `logger.warning("[dyf] follow status=... location=...")`——不跟随 302，看 `Location` 确认跳向（imdesktop→a_bogus/cookie 问题；passport→缺登录态），定位 404 Janus 根因。

### Notes
- `contact.py` FRIEND_KEYS 诊断已是 `astrbot.api.logger.info`（1.2.35，非 print）；若仍无输出，需好友页 `?refresh=1` 强制重拉（300s 缓存可能挡触发）。

## [1.2.35] - 2026-11-11

### Changed
- **follow 失败日志措辞**：`[dyf] 关注请求失败` → `[dyf] follow 请求失败`（诊断对齐）。
- **好友字段诊断**：`contact.py fetch_friend_list` 循环加 `logger.info("[dyf] FRIEND_KEYS: ...")`——拉一次好友页即输出 familiar/list 真实字段名（看 `follow_status` 是否存在/实际叫什么），定位三态恒 0。

## [1.2.34] - 2026-11-11

### Fixed
- **内部重载清子模块缓存更精准**：`main.py` 顶部 + `_purge_own_modules` 两处清 `sys.modules` 裸名包前缀，改为 `_is_own_module(key)` 精确匹配（`key == 包名 or key.startswith(包名 + '.')`）——不再误清 `dyf_gateway_extra` 等第三方同名前缀；确保内部重载后 `dyf_gateway/*`、`dyf_core/*` 重新 import 新代码。

### Changed
- **follow 失败日志**：`follow.py` except 加 `logger.warning(f"[dyf] 关注请求失败: {e}")`——重载生效验证标记（内部重载后点回关，日志出现新行 = 子模块已换新）。

## [1.2.33] - 2026-11-11

### Fixed
- **回关 404 Janus**：`follow.py` headers 缺 `Referer`/`Origin`——www 登录接口要求完整请求头，缺则 302 重定向到 imdesktop（Janus，不支持 `/aweme/v1/web/...`）→ 404 Unsupported path(Janus)。补 `Referer: https://www.douyin.com/` + `Origin: https://www.douyin.com`。
- **好友回关状态三态**：`contact.py fetch_friend_list` 透传 `follow_status`/`is_following`/`relation`（此前丢弃）；`FriendsTab.vue` 用持久 `follow_status` 判断——`1 && is_following` → 互关、`1` → 已关注（隐藏回关按钮）、`0` → 未回关（显示回关按钮）；`followed` 仅作点完即时乐观更新。

## [1.2.32] - 2026-11-11

### Changed
- **统一查询串拆分**：`store.js` 抽 `_splitQuery(endpoint) -> [path, params]`，`apiGet`/`apiPost`/`apiPostBody` 三处复用——后续新增带查询参数的调用自动拆开（endpoint 不再含 `?`，bridge 校验通过），避免重复踩坑；POST 带查询串时 params 作为 `V.apiPost(path, body, params)` 第三参。

## [1.2.31] - 2026-11-11

### Fixed
- **bridge SDK endpoint invalid**：`apiGet` 把查询串塞进 endpoint（`friends?refresh=1`、`groups?platform_id=...`），astrbot 4.29 `plugin_page_bridge.js` 校验 endpoint 不含 `?`/`://`/`#`/`\` → 抛「Plugin bridge endpoint is invalid」，好友页/群列表整页报错。改 `store.js apiGet`：自动把 `?a=1&b=2` 拆成 `path` + `params` 单独传（`V.apiGet(path, params)`），调用点无需改动。

## [1.2.30] - 2026-11-11

### Added
- **好友页**：新增「好友」tab（侧边栏 + 移动导航，TITLES/Sidebar/MobileNav/App 接入）——`FriendsTab.vue`：搜索框（昵称/备注/UID 子串过滤）+「↻ 刷新」+ 好友列表（昵称/备注/UID/sec_uid）+「回关」按钮（`followFriend`，成功显「已回关」、会话内不重复）；首次进入自动拉取（未加载或缓存超 300s）。

### Changed
- **回关按钮移出来源卡**：`SourceNode.vue` 移除下拉项「回关」按钮（回到纯好友选择），回关操作集中到好友页。

## [1.2.29] - 2026-11-11

### Added
- **回关好友（follow）**：新增 `dyf_gateway/douyin/follow.py`——`follow_user`/`unfollow_user`，走抖音网页版 `POST /aweme/v1/web/commit/item/follow/`（body `to_user_id/sec_user_id/action/source_type` + 网页端参数 + `a_bogus` 签名 + `x-tt-argus:1` + UIFID 预热），复用现有登录态 cookie，零 proto 逆向。
- **API `POST douyin_dm_mover/follow`**：`{uid, sec_uid, action=1关注/2取关}`，未登录/无 cookie 返回 detail。
- **前端来源卡好友下拉「回关」按钮**：点击调 `followFriend`（成功后显示「已回关」，本会话标记不重复）。

### Notes
- 好友 `fetch_friend_list` 已含 `sec_uid`（关注必需）；回关为网页 REST（低于 proto 命令风控风险）。

## [1.2.28] - 2026-11-11

### Added
- **配置项 `log_level`**（下拉 DEBUG/INFO/WARNING/ERROR，默认 INFO）：运行日志页只显示不低于该级别，低于级别隐藏。`LogRing` 加 `min_level`（构造参数 + `set_min_level()`，`emit` 里 `levelno < min_level` 丢弃）；`main.py` 启动读 `cfg.get("log_level","INFO")`。设置页新增「运行」组（`log_level` 下拉）。

### Changed
- **receiver 未知类型 dump 降级**：`proto N:` 调试 dump 由 `info` 改为 `debug`——默认 INFO 下不再显示，设 DEBUG 可临时看全部（含调试 dump）。

## [1.2.27] - 2026-11-11

### Fixed
- **新建来源顶掉旧卡（TopologyFlow）**：`addSource` 固定从 `src1` 起（模块级 `srcSeq`），加载时旧卡 `id` 保留（如 `src1`）→ 新来源 id 冲突被 VueFlow 复用节点顶掉。改为 `while (ids.has('src' + n)) n++` 动态分配唯一 id。

### Changed
- **来源卡常态显示好友下拉（SourceNode）**：`open` 默认 `ref(true)` 且删 `@blur` 关闭——下拉始终展开，搜索框直接过滤，无需先点输入框。
- **刷新按钮**：「↻」→「↻ 刷新」（title「强制重拉好友列表，跳过 300s 缓存」）。
- **搜索匹配**：昵称/备注/UID 子串匹配（`includes`，大小写不敏感，中间几个字也命中）。

前端 Vite 重建，旧哈希清除。

## [1.2.26] - 2026-11-11

### Security
- **TLS 校验收紧**：`vendored/login/**`（builder/auth.py、dy_apis/login_api.py、utils/{http_client,dy_util,dtrait,bd_ticket,mstoken}.py）及 `login/mfa.py` 全部 `verify=False` → `verify=True`（26 处），不再绕过证书校验；`vendored/login` 为无 import 引用的第三方遗留代码，收紧仅消隐患，登录/接收/转发主链路不受影响。

### Changed
- **持久化目录收敛**：`DEFAULT_DATA_DIR` 由 `data/dyf` 改为 `data/plugin_data/douyin_dm_mover`，`gateway/subprocess_gateway/worker/forward_manager` 的 `_data_dir` 缺失兜底统一引用 `DEFAULT_DATA_DIR`（不再各自硬编码 `data/dyf`）；`main.py` 迁移源固定旧路径字面量 `data/dyf`（不随常量漂移），保证旧登录态仍能迁移到新目录。

## [1.2.25] - 2026-11-11

### Fixed
- **安装失败 `No module named 'dyf_gateway.douyin.login.alemonjs'`**：`alemonjs_py_login.py` 仍 `from .alemonjs import AlemonjsResult`（模块已于 1.2.20 删除）→ 安装后 import 链 `gateway → alemons_py_login → .alemonjs` 崩溃。改为内联 `AlemonjsResult` dataclass（cookie_str/uid/device_id/user_data/profile），彻底去掉已删模块引用。

## [1.2.24] - 2026-11-11

### Changed
- **来源卡重写**：删「最近发石者」列（只显示抖音好友）；加搜索框（昵称/备注/UID 即时过滤）+ 好友下拉（点击选中写 uid+nickname+实时保存）+「↻ 刷新」强制重拉（`?refresh=1` 跳 300s 缓存）+ 聚焦搜索框时好友空或距上次拉取超 30s 自动强制重拉（`friendsLoadedAt`）。`store.friendsLoadedAt`、`loadFriends` 成功写时间戳；style.css 加 `.src-dropwrap/.src-search/.src-drop` 下拉样式。前端 Vite 重建，旧哈希清除。

## [1.2.23] - 2026-11-11

### Fixed
- **总览「搬运」多条重复**：`forward_manager.handle` 的 `add_record` 在 media 分批循环内——图集多图 > `max_media_per_batch` 分批转发，每批一条记录（type/peer/target 相同）。`add_record` 移到 batches 循环外（每 target 一条，合并批结果：`ok=target_ok>0`、`error` 合并）；全局 `ok_count`/`fail_count` 保留（delivery 收口）。
- （`add_sender` 去重后已修于 1.2.21，总览「发石者」随同归正。）

## [1.2.22] - 2026-11-11

### Fixed
- **FloatLog 拖拽触屏失效**：`FloatLog.vue` 只监听鼠标事件（`mousedown`/`mousemove`/`mouseup`），手机触摸触发 `touch*` 不响应——胶囊与展开面板头部无法拖动。改为 **Pointer Events**（`pointerdown`/`pointermove`/`pointerup`，`clientX/clientY` 通用，统一鼠标+触屏+笔）；`.fl-head` 加 `touch-action:none`（`.fl-ball` 已有）防触摸拖动时页面滚动抢事件。前端 Vite 重建，旧哈希产物清除。

## [1.2.21] - 2026-11-11

### Fixed
- **发石者明细两份/转发一份**：`forward_manager.handle` 的 `add_sender` 在去重检查之前——抖音推两帧（视频卡/图集，server_message_id 不同）两条都记录明细、第二条被去重拦（转发一次）。`add_sender` 移到去重检查之后：被去重拦的帧不记录，明细一份、转发一份。

## [1.2.20] - 2026-11-11

### Removed
- **Node 桥接登录后端（默认已不走）**：删 `login/alemonjs.py` + `alemonjs_bridge.mjs` + 根 `package.json`/`package-lock.json`（@alemonjs/douyin Node 依赖，仅显式 `login_backend=alemonjs_node` 用，默认纯 Python 移植）。同步删 `gateway.py`/`subprocess_gateway.py` 的 `AlemonjsLogin` import + `alemonjs_node` 分支 + `install_login_backend` 方法；`dashboard.py` 删 `install-alemonjs` 路由 + `install_alemonjs` + `_alemonjs_installed` + status 字段；`README.md` 登录后端改默认纯 Python（无 Node 依赖）；`_conf_schema.json` `login_backend` 去掉 Node hint（选项收窄 alemonjs 纯 Python / douyin_spider）。

## [1.2.19] - 2026-11-11

### Changed
- **77/110 分享分支加 share_item_id 守卫**：无 `share_item_id` 落 OTHER（dump 待分类，不空转发）——110 实测带 `share_item_id`（作品分享，`content={}` + proto9 `a:share_item_id` + 详情拉 `/video/` 或 `/note/`），无 si 可能是新类型/命令层，不误转。

## [1.2.18] - 2026-11-11

### Changed
- **未知类型 dump 收敛**：`receiver._handle_frame` 的 `[dyf] proto N: ...` 仅对真正未知类型（非 7/8/27/5/17/50001/50002/77/110）dump——已处理类型（77/110 图集/作品分享、50002 更新扩展）不再 dump，减少噪音；未知类型仍保留（发现新分享类型用）。

## [1.2.17] - 2026-11-11

### Added
- **新版作品分享类型 110 支持**：`_classify` 加 110（与 77 同分支，带 `share_item_id`）——此前 110 落 OTHER 转发空。

### Changed
- **`_enrich_video` 的 `is_album` 由详情判定**：`detail.images` 非空即图集（`/note/`），否则视频（`/video/`）——110 视频/图集链接自动正确。
- **`_classify` 77/110 不再预拼链接**（text="分享"），`_enrich_video` 统一拼正确链接（`/note/` 或 `/video/`），desc 空时也补链接。

## [1.2.16] - 2026-11-11

### Fixed
- **图集详情 IndexError：list index out of range**：`_p_bit_rates` 空 `bit_rate`（图集详情无 `video`/`bit_rate=[]`）→ `bit_rates[0]` 越界；`parse_video_info` 空 `urls` → `video_url, *backup_urls` unpack 失败（`fetch_aweme_detail` except 不捕获 IndexError → 整帧异常丢弃）。加两处守卫：`bit_rate` 空返回 `([],0,0)`；`urls` 空返回空 `video_url`（图集只有 images，无播放直链）。`_p_play_addr` 用 `.get` 防御。

## [1.2.15] - 2026-11-11

### Fixed
- **详情接口 Argus 403（Uifid Not Found）**：www.douyin.com 详情被 Argus 网关拦——缺匿名设备标识。加 `x-tt-argus: 1` 头（网关基础校验当前不校验取值）+ `_ensure_web_identity` 预热：首次 GET `https://www.douyin.com/` 让服务端签发 UIFID/UIFID_TEMP/ttwid 设备 cookie（幂等、进程内一次、失败不致命）。详情请求带该头 + jar 设备 cookie。

## [1.2.14] - 2026-11-11

### Changed
- **详情接口切 www.douyin.com（公开、游客可访问）**：`DETAIL_URL` imdesktop → `www.douyin.com/aweme/v1/web/aweme/detail/`；query 改用网页端参数 `_web_detail_query`（24 项，对齐 ParseHub `fetch_one_video`：aid=6383、device_platform=webapp、浏览器指纹等）；a_bogus 签名保留（www 有效）。登录态零改动（内容详情独立走 www）。
- **images 兜底**：`image_post_info.images`（新版图集格式）+ `images` 两处提取。
- **desc 兜底**：`desc` 空时试 `text`/`title`。

### Added
- **`gateway._enrich_video` 失败日志**：`detail.get("error")` 时打 `[dyf] 详情拉取失败 {item_id}: {error}`（不再静默空，可定位 www 接口风控/拒绝原因）。

## [1.2.13] - 2026-11-10

### Fixed
- **视频简介发两遍**：`_enrich_video` 的 `if desc:` 加 `and desc not in msg.text`——详情 desc 与视频卡 content_title 相同（都是简介）时不再追加，text 保持 `简介\n链接`。
- **图集发两遍（去重失效）**：`_dedup_key` 的 IMAGE 分支先按 `album:{share_item_id}` 去重（抖音推两帧、`media_urls` 可能未填充时两帧 message_id 不同拦不住），有 share_item_id 即按图集 id 去重，否则回退内容指纹/message_id。

## [1.2.12] - 2026-11-10

### Fixed
- **阻断 1（alemonjs 登录同步 requests 阻塞事件循环）**：`alemonjs_py_login.qrcode_login_async` 的 `get_qrcode` 与 `alemonjs_py/qr.py` 的 `check_qrconnect`/`send_qr_mfa_code`/`validate_qr_mfa_code`（poll_qr_confirm / _up_sms_mfa_flow 内）全部包 `asyncio.to_thread`，不再阻塞事件循环。
- **阻断 2（set_self_uid 同步 urlopen）**：`SelfIdentityResolver.resolve_async` 改为 `await asyncio.to_thread(self.resolve, auth)`（整段含 urlopen 放线程）；`DouyinGateway.set_self_uid` 改 async（await resolve_async）；`MessageGateway` 基类加 async `set_self_uid` 默认 no-op、`SubprocessGateway.set_self_uid` 改 async；`main.py` `/dyf uid` 调用处 `await`。
- **次要 1**：`worker.py` 删冗余 `logging.basicConfig`（子进程日志走 astrbot.api logger）。
- **次要 2**：`requirements.txt` 删 `loguru>=0.7.0`（无实际 import，仅注释/文档提及）。

## [1.2.11] - 2026-11-10

### Fixed
- **路由页来源/目标卡不保留**：`_conf_schema.json` 缺 `custom_sources`/`custom_targets`/`simple_targets`/`advanced_target_cards`/`float_log_enabled`——AstrBot `check_config_integrity` 读盘时删这些 schema 之外的磁盘键，重载后来源/目标卡与连线（`pos`/连接关系在卡内）清空。已补全 5 键（list/bool），设备更新重启后不再删，来源/目标卡及布局恢复。

## [1.2.10] - 2026-11-10

### Added
- **77（图集分享）转发**：`receiver._extract_share_item_id` 从 `proto 9` 找 `a:share_item_id`（图集 id）；`converter._classify` 加 77 分支（`IM_SHARE_PHOTOS` → `IMAGE`，文本 `图集分享\n/note/` 链接，card 带 share_item_id）；`fetch_aweme_detail` 补 `images`（图集图片 url_list）；`gateway` 放宽 enrich 条件（IMAGE+share_item_id 也补详情）、itemId 取 share_item_id、图集用 `/note` 链接 + 填 images。
- **50002 跳过**：`MESSAGE_TYPE_UPDATE_MESSAGE_EXT` 非独立媒体，`_SKIP_TYPES={50001,50002}`（converter 层再拦一道）。

## [1.2.9] - 2026-11-10

### Fixed
- **路由丢失根因**：`_conf_schema.json` 从未定义 `routes`——AstrBot `check_config_integrity` 读盘时把磁盘 config 里 schema 之外的键（`routes`）删掉，重载后路由页读空（`disk_routes=-2` / `runtime_routes=0`）。已补 `"routes": {"type": "list", "default": []}`；设备更新插件重启后 `check_config_integrity` 不再删磁盘 routes。

## [1.2.8] - 2026-11-10

### Changed
- **未知类型 dump 去截断**：`receiver._handle_frame` 的 `[dyf] proto N: ...` 从 `str(_fv)[:150]` 改全长 `_fv!s`——77（分享图集）的 `proto 9`（`a:xxx` 嵌套，含 `itemId`）完整可见，供定位图集 itemId 字段。

### Added
- **50002 跳过**：`MESSAGE_TYPE_UPDATE_MESSAGE_EXT = 50002`（douyin-im/DouYin_Spider 均不视作视频消息，是消息更新扩展）与 50001 一起跳过，不再 dump/误转。

## [1.2.7] - 2026-11-10

### Fixed
- **AstrBot 官方审查日志规范合规**：全插件统一改用 `from astrbot.api import logger`（子进程经 stdout 协议回传日志）——`dyf_core/logs.py`（loguru sink → `logging.Handler` 挂 astrbot.api.logger）、`dyf_gateway/douyin/self_uid.py` 与 `worker.py`（`logging.getLogger` → astrbot.api.logger）、`vendored/login/dy_apis/login_api.py`（loguru → astrbot.api.logger）。
- **self_uid 同步阻塞网络 I/O**：`SelfIdentityResolver` 新增 `resolve_async`（`urllib.request.urlopen` 兜底经 `asyncio.to_thread`）；`gateway._apply_session_or_config` 改 async，启动路径用 `await resolve_async`，不再阻塞事件循环。同步 `resolve` 保留（子进程 worker / set_self_uid 同步上下文用）。

## [1.2.6] - 2026-11-10

### Fixed
- **图片合集/未知类型帧全部丢弃（`frame decode error: 0` 根因）**：`receiver._handle_frame` 的 dump 分支误把已是 dict 的 `msg_body` 传给 `decode_fields`（期望 bytes）→ `_read_varint` 取 `data[0]` 抛 `KeyError: 0` → 整帧被丢弃（77/50002 从未转发）。改为直接 `msg_body.items()`——未知类型帧不再崩，且 dump 出 77/50002 字段（图片 URL 位置）供补 `_classify`。

## [1.2.5] - 2026-11-10

### Added
- **配置落盘/读回特征诊断日志**：`config_set` 保存后与 `_do_reload` 完成后打 `[dyf] 配置诊断(落盘后/重载后): schema_routes=... disk=... disk_routes=... runtime_routes=...`——自动对比「schema 是否含 routes / 落盘文件实际 routes / 运行时 routes」，免手动翻文件定位路由丢失（disk 无 routes → 落盘问题；disk 有但 runtime 空 → schema 删键）。

## [1.2.4] - 2026-11-10

### Fixed
- **浮窗串台（其它插件加载失败文案）**：`_do_reload` 的 `sm.reload` 错误信息被 AstrBot 聚合所有 failed 插件——只关注本插件（`douyin_dm_mover` in err 才 error），其它插件失败改 warning 注明无关，不再串进浮窗。

## [1.2.3] - 2026-11-10

### Changed
- **帧解码错误带完整栈**：`receiver._on_message` 的 `except` 打 `traceback.format_exc()`（`frame decode error: 0` 只见 `0`，加栈定位 `_handle_frame` 内抛的 `ValueError("0")`/`IndexError` 源头）。

## [1.2.2] - 2026-11-10

### Fixed
- **更新路由后「无匹配路由 VIDEO_CARD」**：`config_set` 更新 `routes` 后即时重建 `ForwardManager.router`（此前 router 只在 `__init__` 建一次，更新路由目标不生效——`RouteResolver` 里空 target 被过滤 → 无匹配路由）。
- **视频详情 `desc_len=0`**：`_enrich_video` 的 desc 为空时用视频卡自带标题（`content_title`/`title`）兜底，不再正文缺失。

## [1.2.1] - 2026-11-10

### Fixed
- **重载卡死（join 阻塞事件循环）**：`gateway._stop_receiver` 改 async，`thread.join` 用 `asyncio.to_thread`（不再同步阻塞事件循环 + 阻塞 `sm.reload` 的 `_pm_lock`）；`gateway.stop` `await` 之。多次重载不再累积卡死。
- **重载超时保护**：`dashboard._do_reload` 的 `sm.reload` 加 `asyncio.wait_for(..., 30)`，超时打日志（提示可能卡在 terminate/load），不再永久挂起。

## [1.2.0] - 2026-11-10

### Added
- **视频详情规范化（摘取 ParseHub）**：`video.py` 内嵌 ParseHub 的 `parse_video_info`/`remove_video_watermark`（MIT，Copyright 2024 梓澪）——去水印（playwm→play）、bit_rate 编码过滤（bytevc1）回退、宽高提取；`fetch_aweme_detail` 补 `play_url`/`backup_urls`/`width`/`height`/`duration`，封面优先用 `thumb_url`（取 url_list 末位）。README/LICENSE 注明来源与 MIT 许可。

## [1.1.2] - 2026-11-10

### Fixed
- **好友列表/档案 status_code=8（签名失败）**：`contact.fetch_friend_list`（familiar/list）与 `profile.fetch_desktop_self_profile` 补 `a_bogus` 签名（`generate_jumpbyte_abogus`，同 `video.fetch_aweme_detail` 路径）——桌面 REST 需签名，无签名返回 `status_code=8`。

## [1.1.1] - 2026-11-10

### Fixed
- **安装报错「不受支持的配置类型 number」**：`_conf_schema.json` 的 `max_media_per_batch`、`retry_interval_seconds`、`retry_max_attempts` 类型 `number` 改为 `int`（AstrBot 支持集为 `int/float/bool/string/text/list/file/object/template_list/dict`，不含 `number`），安装校验通过。

## [1.1.0] - 2026-11-10

### Added
- **media 分批转发**：图集按 `max_media_per_batch`（默认 9，0=不分批）分批发送，正文/卡片只进第一批，某批失败即停（不重发部分成功）。
- **重试次数上限**：`retry_max_attempts`（默认 5），超限丢弃失败消息（防无限重试）；`RetryManager` 内存态计数。

### Changed
- **delivery 失败记账收口**：发送循环统计成功/失败数，`ok() == 至少一成功`——全失败才 `AlertService.notify` 告警（到告警目标），部分成功只记日志不误报。
- **失败提示反馈**：`AlertService.notify` 通用业务反馈（转发全失败提示到告警目标；未配置则仅日志）。

## [1.0.0] - 2026-11-10

### Changed
- **正式发布**：主版本升至 1.0.0（登录/转发/路由/信息卡片/去重/限流/重试/配置台链路已验证可用，从开发期 0.x 转入正式）。

## [0.63.0] - 2026-11-10

### Fixed
- **视频卡重复转发**：去重 key 从 `message_id` 改为作品 `itemId`（`video:{itemId}`）——抖音 WS 同一视频推两帧（`server_message_id` 不同、conv 一标准一纯数字），key 不同导致转两遍；同视频窗口内只转一次。
- **图集重复转发**：`IMAGE` 去重 key 改用内容指纹（`img:md5(排序 media_urls)`）——两帧图集 url 相同 → 同 key 拦截。

## [0.62.0] - 2026-11-10

### Added
- **信息卡片图渲染**：借鉴 nonebot-plugin-parsehub 的 `card/`（App Store「Today」风格）——视频/图集转发时渲染一张卡图（封面按比例裁切聚焦 28% + 竖直渐变遮罩 + 平台名「抖音」+ 标题 + 类型标签），替代纯文本/裸图转发；新增 `dyf_core/card.py`（纯 Pillow，渐变遮罩不用 numpy），`message_builder.build_chain` 支持 `card_image` 替换首媒体，`forward_manager` 在消费循环 `asyncio.to_thread` 同步渲染。
- **card_enabled 配置**：转发开关（默认开）；无中文字体或渲染失败自动退回文本转发（`card.available()` 探测）。metadata 依赖加 `pillow>=10.0.0`；schema/前端设置页加 `card_enabled`。

## [0.61.0] - 2026-11-10

### Fixed
- **视频卡标题未显示**：`converter._classify` 的 title 提取加 `content_title` 优先（视频卡 content 无 `title`/`desc`，实际字段是 `content_title`，如 `#恋爱技巧`），转发显示真实卡内标题而非默认「抖音视频」（不依赖 `aweme/detail`）。

## [0.60.0] - 2026-11-10

### Fixed
- **图片合集 77 崩溃（content 为 `"0"`）**：`receiver._handle_frame` 的 `content_json` 解析改为 `json.loads(content)` 成功但非 dict（如 `json.loads("0")=0`）时置 `{}`，避免 converter `content.get()` 抛异常导致 `frame decode error: 0`。
- **视频详情两层嵌套**：`video.fetch_aweme_detail` 响应为 `{"data":{"aweme_detail":{...}}}` 时，先取顶层 `aweme_detail`，无则进 `data` 再取 `aweme_detail`（原 `or data.get("data")` 拿到包装 dict 导致 `desc_len=0 cover=无`）。
- **纯数字短 id conv peer 兜底**：`converter.convert` 的 `resolve_peer` 失败（conv 为纯数字短 id 如 `7569533068915081774`）且 `sender != self_uid` 时，peer_id 兜底用 `str(sender)`，转发不再 `peer=None`。

## [0.59.0] - 2026-11-10

### Fixed
- **视频卡转发崩溃（requests 响应属性误用）**：`alemonjs_py/http.py:254` 用 `resp.status`（`requests.Response` 无此属性）改为 `resp.status_code`。此前视频详情/封面接口返回非 2xx（403 防盗链）时抛 `AttributeError`（不在 `fetch_aweme_detail` 捕获元组内）→ 崩到 listener 的「处理消息异常」。修复后非 2xx 走 `RuntimeError("HTTP <code> ...")`，被 `fetch_aweme_detail:44` 捕获返回 error dict，`_enrich_video` 不崩（标题+链接照发，封面缺失）。

## [0.58.0] - 2026-11-10

### Added
- **未知消息 proto 字段 dump**：`receiver._handle_frame` 对非已知 msg_type（50002/77 分享卡等）临时 dump `decode_fields(msg_body)` 每字段（`[dyf] proto {fn}: {str(v)[:150]}`），供获取 proto 未解析字段的完整样本（含嵌套 bytes），定位 50002/77 数据后修复。

## [0.57.0] - 2026-11-10

### Fixed
- **浮窗日志滚动保持相对位置**：新日志在顶部，滚动不再自动滚底——在顶部则保持顶部看最新，已滚动则按 `scrollHeight` 增量补偿 `scrollTop`（视觉内容不跳动）。

## [0.56.0] - 2026-11-10

### Changed
- **处理消息异常带上下文**：`listener.consume_messages` 异常日志改为 `[dyf] 处理消息异常: {Type}: {e} raw={msg.raw[:500]}`（此前仅固定文案无异常详情），handle 抛错时能直接看到异常类型 + 消息完整原始字段（含 77 分享卡数据）。

## [0.55.0] - 2026-11-10

### Changed
- **未知消息诊断升级为完整 raw dump**：非白名单消息（如视频分享卡 77、图片合集）日志改为 `[dyf] raw full: {json.dumps(raw)[:500]}`，含全部字段（itemId/标题/封面/sender/conv），供定位 77 content 实际位置与 peer 解析。

## [0.54.0] - 2026-11-10

### Fixed
- **发送者昵称回填（remark_name 优先）**：`_on_raw_message` convert 后，若 `peer_name` 仍为 uid（文本消息 content 无 name），用 `_lookup_friend_name(peer_id)` 从好友缓存（`friends_cache.json`，`remark_name` 优先 fallback `nickname`）回填——文本/视频消息 header 显示好友备注/昵称，不再裸 uid；好友不在列表保持 uid。

## [0.53.0] - 2026-11-10

### Added
- **图片合集/未知消息临时诊断**：`converter.convert` 对非白名单消息（`MessageType.OTHER`，图片合集/链接/分享候选）记录 `[dyf] raw: msg_type/conv/content(前200)`，供复现后确定真实 msg_type、多图结构与 conversation_id 字段，再精准修复 `_classify`/`resolve_peer`。

## [0.52.0] - 2026-11-10

### Fixed
- **正文紧贴 header**：`build_chain` 正文前加换行（`Plain("\n"+body)`），AstrBot 拼接多个 Plain 无换行，正文不再显示为 `header1`（如 `· 17:061`）。
- **发送者昵称显示 uid**：`converter` 昵称回退链改为 `content.name/nick_name → nickname_provider(sender)（查好友缓存）→ peer_id`；gateway 提供 `_lookup_nickname`（查 `_friends`）。不再裸显示 uid。
- **重启后来源/目标卡丢失**：`_conf_schema.json` 追加 `custom_sources`/`custom_targets`/`simple_targets`（`type:"list"`），AstrBot `check_config_integrity` 不再删除 schema 未声明的运行时字段。

## [0.51.0] - 2026-11-10

### Fixed
- **发送失败原因空白**：`message_sender.send` 用 `err = str(e) or type(e).__name__`——异常 `str(e)` 为空时至少暴露异常类型，日志/重试队列不再空白。
- **日志自动清空（重载重建）**：`LogRing` 落盘持久化（`data/<插件>/logs.jsonl` JSONL，append + 启动加载最近 maxlen 条，>2MB 重写截断，clear 截断文件）——插件自动重载不再清空日志，重载后恢复最近 200 条。

## [0.50.0] - 2026-11-10

### Fixed
- **心跳文本帧解码错误**：`_handle_frame` 开头按类型分流——`isinstance(message, str)` 时心跳应答 `'hi'`/`'ok'` 直接返回（非业务），其它文本帧仅记录 info；不再被 `decode_fields` 按 protobuf varint 解码导致 `str & int` TypeError（此前每 15s 报 frame decode error，心跳保活形同失效）。

## [0.49.0] - 2026-11-10

### Fixed
- **视频详情不再阻塞接收线程**：`_on_raw_message`（receiver 线程）移除同步 `_enrich_video`，改为 `listener.consume_messages`（async 消费循环）里 `gateway.enrich_video(msg)`（`asyncio.to_thread`，内部校验 `video_detail_enabled` 与 VIDEO_CARD）。接收线程立即入队不阻塞；单条视频补详情最多 ~8s 延迟，不影响后续帧/心跳/断线检测。

## [0.48.0] - 2026-11-10

### Fixed
- **头像回退 logo + 每次重拉**：`profile` 端点落盘缓存 `data/dyf/profile_cache.json`（含 ts，TTL 300s），重载后（内存清空）读文件直接返回，不再每次重新拉取；前端 Sidebar 头像 `@load` 写 localStorage、`@error` 回退本地缓存的头像（仅一次防循环）——URL 失效/防盗链不再立刻变 logo。

## [0.47.0] - 2026-11-10

### Fixed
- **接收端心跳保活**：`receiver` 补应用层心跳（douyin-im ws-client 协议），`_on_open` 后每 15s `ws.send('hi')` 文本帧，`_on_close`/`_on_error`/`stop` 停止，重连后 `_on_open` 自动重启——修复服务器 ~30s 无心跳断开、1s 重连又断的死循环。
- **路由目标群号为空**：前端连接路由→目标时校验 UMO 会话 id，为空则告警「目标未填写群号/OpenID」且不连接；`scheduleLiveSave` 落盘前清空会话为空的 target（形如 `adapter:GroupMessage:`），避免发送必失败。

## [0.46.0] - 2026-11-10

### Fixed
- **配置回滚（路由重置）**：`config_set` 改 `cfg=dict(config)` 副本后补 `self._config_obj.update(updates)` 同步写本体（AstrBotConfig 是 dict 子类），再 `save_config()`——重载后读回正确配置，路由表不再回滚。
- **好友列表每次重拉**：`gw._friends` 落盘 `data/dyf/friends_cache.json`（含时间戳），重载后（内存清空）读文件缓存，<TTL(300s) 直接返回；超 TTL 或 `?refresh=1` 才重新全量拉取。

## [0.45.0] - 2026-11-10

### Added
- **平台实例级联选择（多机器人）**：后端新增 `platforms` 端点（`platform_manager.get_insts()` → `[{id,type,name}]`）；`groups` 支持 `?platform_id=` 按实例拉取群列表（实例级 `get_group_list`/helper 多来源防御，未指定回退统一 `context.get_group_list()`）。前端目标卡平台下拉改用平台实例列表（value=实例 id 作 UMO 前缀，显示 `name(type)`），选中实例级联加载该实例群列表；`groupsPlatform` 跟踪群列表所属实例防串台；新增目标默认取第一个实例 id；启动加载 `platforms`。多实例部署可精准区分「平台 → 会话」发送。

## [0.44.0] - 2026-11-10

### Fixed
- **浮窗胶囊可拖动**：`.fl-ball` 悬浮球加 `@mousedown` 拖动（`cursor:grab`、`touch-action:none`），拖动后抑制 click 防误展开（`suppressClick`）。
- **清空日志即时反馈**：清屏改为乐观清空（立即置空）+ 请求序号 `pullSeq` 使进行中的轮询结果过期，避免旧数据回填；POST 完成后重新拉取与后端同步。

### Removed
- **浮窗「× 关闭」按钮**：移除 `close()`（含 `saveConfig({float_log_enabled:false})`），关闭全局浮动调试日志只保留设置页开关；浮窗仅保留 折叠（–）/清屏（清）。

## [0.43.0] - 2026-11-10

### Added
- **视频详情 L2 增强**：新增 `video.fetch_aweme_detail`（`GET /aweme/v1/web/aweme/detail/`，a_bogus 签名），视频卡转发前补拉 `desc`（视频文案）+ 详情封面，转发内容变 `标题 + desc + 链接 + 封面图`（卡内无 desc）。开关 `video_detail_enabled`（默认开，关闭则仅 标题+链接+卡内封面）；失败/无 Cookie 优雅回退原内容。

## [0.42.0] - 2026-11-10

### Added
- **视频卡转发带封面图**：`converter` 视频卡分支提取封面（`content.cover_url.url_list[0]` 或 `content.coverUrl` 直链）加入 `media_urls`；`message_builder` 的 `VIDEO_CARD` 媒体 URL 也走 `Image.fromURL`（原先仅 `IMAGE`），转发不再是「标题+链接」无封面。

## [0.41.0] - 2026-11-10

### Fixed
- **看门狗静默误报**：`DouyinReceiver` 新增 `on_frame` 回调，`_handle_frame` 入口对任意帧（含心跳/控制帧）触发，gateway `_on_any_frame` 刷新 `_last_frame_ts`；`_start_receiver` 起始即初始化时间戳。无私信（私信机器人）不再误报「连接僵死」。
- **重试队列永久卡死**：`retry_failed` 捕获 `(TypeError, ValueError, KeyError)`，`failed_sends.json` 单条坏数据（如非法 type 抛 ValueError）不再中断整批重试，重试队列不卡死。
- **限流发送者窗口无上限**：`RateLimiter` 新增 `prune()`，`allow()` 懒触发（>100 窗口且距上次清理 >60s）回收 60s 无活跃的发送者窗口，防长期内存增长。

## [0.40.0] - 2026-11-10

### Fixed
- FloatLog 关闭按钮现在调用 `saveConfig({ float_log_enabled: false })`，刷新后不再重新弹出，且 SettingsTab checkbox 与配置保持一致。
- TopologyFlow 新增路由名改用时间戳+序号唯一后缀，删除中间路由后再添加不再与现有 name 冲突（`_route_diff` 按 name 匹配不再误判）。

## [0.39.0] - 2026-11-10

### Added
- `config_set` 对 `routes` 做结构化 diff（`_route_diff`，按路由 name 匹配）：新增 `+ 路由 "r" → target`、删除 `- 路由 "r"`、目标变更 `~ 路由 "r" 目标: old → new`、来源连接 `~ 路由 "r" 来源 +uid`/`-uid`、类型 `~ 路由 "r" 类型 +t`/`-t`；`pos` 忽略不产生日志。路由表创建/连接/断连/目标/类型操作（全部经 `config/set`）现可在浮窗监控。

## [0.38.0] - 2026-11-10

### Added
- `gateway._on_status` 连接健康日志（进 LogRing）：重连 `[dyf] 连接重连中`、断开 `[dyf] 连接断开`（warning）、错误 `[dyf] 连接错误`（warning）、失效判定 `[dyf] 连接失效判定`（warning）。浮窗可监控连接健康。

## [0.37.0] - 2026-11-10

### Added
- 全局浮窗日志新增两条活动日志（均进 LogRing，浮窗可见）：`config_set` 记录 `[dyf] 配置已更新: [key列表]`（值省略防刷屏）；`RouteResolver.resolve` 改为返回 `(路由名, target)`，转发命中时记录 `[dyf] 命中路由 {name} -> {target}`。浮窗现在可看到消息流转、命中、配置修改、登录态、告警，无需新增接口。

## [0.36.0] - 2026-11-10

### Added
- 高级设置新增「全局浮动调试日志」开关（`float_log_enabled`）：右下角半透明悬浮球，点击展开 320×260 深色日志面板；面板可拖动（位置 localStorage 记住）、可折叠、可关闭；复用 `apiGet('logs')` 数据源，展开时每 3s 轮询、折叠即停；自动滚动到底、清屏按钮、错误/警告行标红；`position:fixed; z-index:40`（高于画布、低于登录弹窗 50）。

## [0.35.0] - 2026-11-10

### Fixed
- 时间戳丢失（发石者记录时间 = 转发时刻、header 时间不对）：`vendored/receiver.py::_handle_frame` 漏取 MessageBody 字段 10 `create_time`，已补入 raw；`message_builder._header` 改用 `msg.timestamp`（消息原始私信时刻）而非 `datetime.now()`。`converter._timestamp_of` 兜底保留作防御。

## [0.34.0] - 2026-11-10

### Fixed
- 好友缓存不过期：`dashboard.friends()` 加 300s TTL（`gateway._friends_ts`），过期自动重拉；`?refresh=1` 强制刷新（来源卡下拉旁新增 ↻ 刷新按钮）。
- 来源卡换 uid 位置跳变：来源节点 id 改用来源对象稳定 `id`（不再含 uid），改来源后位置保留（含未拖过时不再落回默认列）；旧数据无 id 自动迁移。

## [0.33.0] - 2026-11-10

### Fixed
- 来源→路由连接线不即时出现（延迟到下次拖拽才重绘）：内容 watch 漏掉 `match.senders_include`，连接/断开后不触发重建；已补回 `senders_include` 到内容 watch，并在 `onConnect`/`onEdgesDelete` 后直接 `buildEdges()` 立即重绘。

## [0.32.0] - 2026-11-10

### Fixed
- 连接桩抖动导致来源连不上路由：移除 `hover { transform:scale(1.15) }` 与 `-8px` 外移偏移（缩放引起边界变化→鼠标离开→缩小→循环抖动，拖拽连接无法稳定启动）；连接桩加 title 提示连接方向（来源右桩→路由左桩→目标左桩）。

## [0.31.0] - 2026-11-10

### Changed
- 画布移除「来源 / 路由 / 目标群」列标签（卡片自身已标识类型，连线表达关系）。
- 连接桩 Handle 加大（16px + 白边 + z-index 40 + crosshair），连接更易命中；未选来源即拖连路由时提示「请先在来源卡选择来源」。

## [0.30.0] - 2026-11-10

### Added
- 目标卡群聊模式下群号改为下拉选择真实群列表：新端点 `douyin_dm_mover/groups` 调用 AstrBot 适配器统一 `context.get_group_list()`，归一化 `{group_id, group_name}`；下拉 value=群号、label=群名（群号）。无群列表（版本/平台不支持）优雅降级为手动输入，附刷新按钮。

## [0.29.0] - 2026-11-10

### Changed
- 目标卡（默认模式）改为：平台下拉（OneBot / 官方机器人）+ 目标类型下拉（群聊 / 私聊）+ 目标 ID/号码输入（群号 / OpenID）。官方机器人时「私聊」置灰不可选（UI 层切断错误逻辑，切平台时自动回退群聊）。
- 高级目标卡适配器下拉同步改为 OneBot / 官方机器人。

## [0.28.0] - 2026-11-10

### Removed
- 黑白名单机制整体移除：全局 `senders_whitelist`/`senders_blacklist` 过滤（`SenderFilterRule`）、配置 schema 项、路由 `senders_exclude`、前端策略/监控/总览的 +白/+黑 与名单字段。

### Changed
- 路由页改为手动连接（Cloudflare 绑定风格）：从连接桩拖到另一连接桩建立连接（来源→路由→目标），选中连线按 Delete 断开；不再自动连线。
  - 来源→路由连接 = 该来源 uid 加入路由 `match.senders_include`（仅这些来源转发）；路由→目标连接 = 设 `target`。
- 卡片位置持久化：拖拽节点触发实时保存（存 `pos`），刷新后布局保持。
- 目标列分模式：默认仅 QQ群/私聊（`simple_targets`）；「设置 → 高级 → 目标群卡片（高级）」启用后改用适配器+群号高级卡片（`custom_targets`）。
- 路由卡精简：去掉目标下拉与发送者包含/排除输入，仅名称/类型/上移/下移/删除。

## [0.27.0] - 2026-11-10

### Changed
- 来源卡移除「+白/+黑」黑白名单快捷按钮（保留下拉选择来源 + 昵称 + 删除）。

### Fixed
- 侧栏账户头像：已登录但无档案缓存时 `/profile` 主动拉取一次并缓存（此前登录时刻未拉到则一直空，回退显示 logo）；头像加载失败回退 logo。

## [0.26.0] - 2026-11-10

### Changed
- 目标群改为独立实体（`custom_targets`）：+ 添加目标 生成独立目标卡（适配器/群号可编辑、可删除），不再等价于添加路由；路由卡目标改为下拉选择已有目标，删除目标会清空引用它的路由目标。
- 来源卡优雅化：卡片内下拉选择来源（optgroup「最近发石者 / 抖音好友」，好友懒加载），选中后显示昵称+uid 并支持 +白/+黑，可删除；来源列不再直接平铺动态来源。

## [0.25.0] - 2026-11-10

### Changed
- 路由页三个添加按钮改为直接生成对应列卡片（与「+ 添加路由」一致）：+ 添加来源 生成可编辑来源卡（昵称/uid 失焦提交，可移除），+ 添加目标 生成可编辑目标卡（适配器/群号）。移除内联表单。

## [0.24.0] - 2026-11-10

### Added
- 路由页拓扑工具条统一为三个添加按钮：来源 / 路由 / 目标（内联表单：来源填昵称+uid、目标选适配器+群号）。
- 自定义来源（`custom_sources`）持久化，刷新后仍显示；来源卡片可一键移除。
- 实时保存：路由/来源改动防抖 1.2s 静默落盘（`config/set` 新增 `no_reload` 跳过自动重载），状态栏显示「已保存 HH:MM:SS」。

## [0.23.0] - 2026-11-10

### Changed
- 路由页拓扑改用 Vue Flow（@vue-flow/core 1.48.2）：Cloudflare Workers 风格绑定视图——来源/路由/目标群为带连接桩（Handle）的节点，贝塞尔曲线连线（含动画、命中/排除着色、箭头），节点可拖拽布局，画布可缩放平移。
- 纯 DOM 拓扑渲染（topo-svg/topoPos/drawEdgesDom）移除；路由/目标卡片编辑保留（群号失焦提交避免重建丢焦点）。

## [0.22.0] - 2026-11-10

### Added
- 路由页来源列支持切换「最近发石者 / 抖音好友」（familiar-list 全量）：好友卡片显示昵称+备注+头像，点「+白/+黑」加入名单，连线按 uid 匹配路由发送者包含/排除。

## [0.21.0] - 2026-11-10

### Changed
- 响应式（手机/电脑识别）：`useMediaQuery`/`store.isMobile` 监听 `(max-width:768px)`；手机端隐藏侧栏、启用底部导航 `MobileNav`，主区全宽。
- 排布交给 CSS `@media`：手机端 `grid2`/`stats`/`label.f` 单列、拓扑三列→单列、弹窗近全屏（`100dvh`+滚动）、二维码 `min(210px,62vw)` 不再撑爆、日志 `50vh`、`safe-area-inset-bottom`。
- `vite.config` `base:'./'` 校验：产物引用相对 `./assets/`，可嵌入任意路径的 AstrBot WebUI。

## [0.20.0] - 2026-11-10

### Added
- 账户档案：`alemonjs_py/profile.py::fetch_desktop_self_profile`（GET `/aweme/v1/web/user/profile/self/`，昵称/头像），登录 confirmed 后自动拉取一次存登录态；Web 侧栏已登录时显示昵称+头像。
- 好友列表：`alemonjs_py/contact.py::fetch_friend_list`（familiar-list 全量分页，`version_code=21.6.0`，count≤100 循环 cursor，过滤 `user_canceled=0`/空 uid），`alemonjs_py` 导出。
- 后端 API：`douyin_dm_mover/profile`（GET）、`douyin_dm_mover/friends`（GET，未登录返回空，已登录用会话 Cookie+桌面设备拉取）。
- 桌面 REST 通用指纹 `desktop_rest_base_query`（device_platform=win32、screen 1707x1067、UA 去 Mozilla/ 作 browser_version、did/iid/awemeim_guid、channel=0，无 a_bogus）。

## [0.19.0] - 2026-11-10

### Changed
- 前端重构为 Vue 3 + Vite 单页应用：`web/` 源码目录（`App.vue` + `Sidebar`/`LoginModal`/`ConfigField` 组件 + 6 个 Tab 组件），按职责拆分组件（二维码、拓扑图、侧边栏、配置表单等）。
- 构建产物输出到 `views/status/`（`index.html` + 哈希化 `assets/index-*.js/css/logo`，约 96KB JS / 37KB gzip），AstrBot 页面服务直接服务，加载速度更快。
- 拓扑编辑保持纯 DOM（SVG 连线层 + 三列 HTML 卡片），Vue 响应式驱动，目标群/结构变化自动重连。
- 配置字段统一为 `ConfigField.vue`（select/bool/int/umo/senderlist/json 类型），设置/策略分组渲染。

## [0.18.2] - 2026-11-10

### Fixed
- 修复自适应布局失效：`main` 移除 `max-width:1000px` 并加 `min-width:0`（flex 项不撑破容器）；`.app` 加 `width:100%`；`.topo` 加 `width:100%; box-sizing:border-box`；`.td-cols` 改 `1fr 1.4fr 1fr`（各列 `min-width:0`）自适应 iframe 宽度；`.topo-svg` 不再强制 CSS 宽高（随内容 scrollWidth/scrollHeight 扩展），画布/节点随之拉伸。

## [0.18.1] - 2026-11-10

### Fixed
- 路由拓扑画布遮罩问题：弃用 X6（`shape:'html'` 节点渲染遮罩/不可靠），改为纯 DOM 实现——SVG 连线层 + 三列真实 HTML 卡片（来源只读、路由/目标可编辑），卡片为真实表单，无任何遮罩层。
- 移除 X6 外部脚本引用与 484KB `x6.js` 本地资源，减少加载体积。

## [0.18.0] - 2026-11-10

### Changed
- 左上角 logo 换成仓库 logo.png（`assets/logo.png`，256×256 圆角展示）。
- 路由页实现真正的图上卡片编辑：拓扑中的路由节点改为 X6 HTML 节点（真实表单卡片），直接在画布上编辑名称/目标适配器+群号/类型多选/发送者包含排除/上移/下移/删除；目标群卡片同样可编辑（修改后同步到所有指向该群的路由）；移除独立编辑弹窗。
- 卡片输入时只刷新连线（不重建节点，保持输入焦点）；仅目标群变化/结构变化才整图重建。

## [0.17.0] - 2026-11-10

### Changed
- 路由页去掉独立「路由项」编辑列表：编辑功能并入拓扑画布——点击/双击路由节点弹出编辑弹窗（名称/目标适配器+群号/类型多选/发送者包含排除/上移/下移/删除），画布改为大尺寸（min-height 440px）并占满卡片，布局更紧凑、画布更宽敞。
- 路由编辑态改为 JS 数组 `_routes`，节点点击直接编辑，编辑实时预览拓扑。

## [0.16.1] - 2026-11-10

### Fixed
- **更新插件后登录态显示「未知」**：启动加载已保存会话后乐观置为已登录（连接实际失败才降级 EXPIRED），不再长期停留 UNKNOWN；并新增旧 `data/dyf` → `plugin_data/douyin_dm_mover` 登录态迁移，升级插件不再丢 session.json/device.json。
- **路由拓扑图（AntV X6）交互修复**：禁止节点拖动与画布背景平移（只保留 Ctrl/⌘+滚轮缩放）；自动刷新不再重建拓扑图（数据签名判重，保留视口），不再每 5 秒闪回初始态；无路由时中间列显示「暂无路由」虚线占位 + 提示；容器最小高度提高，不再过小。
- **路由页合并单卡**：转发拓扑与编辑路由合并为一张卡片，去掉重复「编辑路由」标题。
- **保存配置自动重载插件**：`config/set` 落盘后自动触发插件重载，免手动点「重载插件」。

## [0.16.0] - 2026-11-09

### Changed
- AntV X6 改为本地打包：`views/status/assets/x6.js`（UMD 484KB，无外部 CDN 依赖），视图用相对路径 `./assets/x6.js` 引用；消除外部 CDN 被 CSP 拦截风险与在线依赖。

## [0.15.0] - 2026-11-09

### Changed
- 路由拓扑图改用 **AntV X6**（纯 JS 图编辑引擎，CDN `@antv/x6@2.18.1`）：平滑阶梯连线、拖拽平移、Ctrl+滚轮缩放、自定义节点样式、点击路由节点定位编辑卡片；X6 加载失败自动回退手写 SVG。

## [0.14.0] - 2026-11-09

### Changed
- 路由页改为「拓扑图 + 编辑」架构图风格：上部 SVG 拓扑图展示转发链路（抖音来源 → 路由 → 目标群 三层节点 + 曲线连线，连线按发送者包含/排除命中高亮/虚线），点击路由节点定位对应编辑卡片；下部保留路由编辑卡片（增删改/↑↓ 排序），编辑实时预览拓扑。

## [0.13.1] - 2026-11-09

### Fixed
- **更新插件掉登录**：登录会话/设备持久化目录改锚定到 AstrBot 数据目录 `data/plugin_data/douyin_dm_mover`（`get_astrbot_data_path()`，取不到回退绝对化 `data/dyf`），不再相对 CWD 落到插件目录内，插件更新/重装不再覆盖 `session.json`/`device.json`。
- **扫码后设置页登录 Cookie 为空**：登录成功后将 `douyin_cookies`/`self_uid`/`device_id` 写回 AstrBot 配置并 `save_config()` 落盘，配置页可见且配置层有兜底（此前只写 `session.json`，配置层从未回写）。
- `main.py` register 插件版本号 0.6.1 → 0.13.0（与 metadata.yaml 对齐）。

## [0.13.0] - 2026-11-09

### Changed
- 已登录时点击左下角卡片弹窗切换为「账号信息」视图（显示 uid / 已连接，隐藏刷新二维码），不再误入扫码页；未登录时才显示扫码登录。
- 配置页增强：设置/策略按语义分组卡片（登录/转发/限流/去重/重试/过滤/告警与适配），每字段显示 schema hint 说明文字，告别单薄配置表。
- 路由表改为卡片式编辑器：每条路由一张卡片（名称 + 目标两段式适配器下拉/群号 + 类型多选 chips + 发送者包含/排除），支持 ↑↓ 排序与删除，替代简陋单表格。

## [0.12.1] - 2026-11-09

### Fixed
- 登录弹窗二维码白底溢出弹窗边界（盒子模型失控）：img 原尺寸渲染未受 `.qr` 包裹类约束，改为 `#mQr` 作用域固定 210×210 + `object-fit:contain` + `overflow:hidden`，右侧按钮不再被挤压，弹窗圆角与视觉平衡恢复。

## [0.12.0] - 2026-11-09

### Changed
- 移除顶部「扫码登录」按钮：登录入口统一到左下角用户卡片弹窗，消除重复入口。
- 登录态展示改为三态明确文案：未登录 / 已登录（uid）/ 登录失效，不再只显示「未知」。
- 设置/策略配置项改为下拉选择，免手填：登录后端、网关模式、MFA 模式、QQ 适配器（enum 下拉 + 中文 label）。
- 默认目标群 / 告警目标改为两段式（适配器下拉 + 群号输入），自动拼接 `adapter:GroupMessage:group`，不再手填完整 UMO。
- 发送者白/黑名单改为 chips 名单（可增删），并支持在监控页/总览点击发石者「+白/+黑」一键加入名单，免手填 uid。
- 保留 AstrBot 深浅主题跟随风格与侧栏布局。

## [0.11.0] - 2026-11-09

### Changed
- 登录入口融合到侧栏左下角：底部用户卡片默认显示「未登录」（带状态指示点），加 hover 效果与 cursor-pointer，点击弹出居中登录弹窗。
- 新增居中登录弹窗（Modal）：半透明模糊遮罩（rgba 黑 60% + backdrop-blur）、深色弹窗本体、右上角关闭 X；内容含标题、左侧二维码占位图、右侧「刷新二维码」按钮、下方「短信验证码」输入框 +「提交」按钮；点击遮罩或 X 关闭（useState 等价显隐控制）。
- 移除侧栏「登录」Tab（登录入口统一到左下角卡片与弹窗，顶部「扫码登录」按钮同样打开弹窗）。
- 设置 / 策略 / 路由页配置项改为中文标签展示（英文 key 经 LABELS 映射），路由表表头改为中文（名称/目标/类型/发送者包含/发送者排除）。
- 保持原 AstrBot 深浅主题跟随风格，未强制暗黑。

## [0.10.0] - 2026-11-09

### Changed
- 配置页重构为侧边栏布局（参考原型骨架，不套用硬编码）：左侧栏 7 个 Tab（总览/登录/路由/策略/监控/日志/设置）+ 主区内容区；所有数据接真实 API，移除硬编码 uid/指标/路由行。
- 总览：状态胶囊 + 4 指标卡（发石者/搬运/路由/去重）+ 最近两列；侧栏底部连接状态卡。
- 登录：二维码 + 喂码 + 刷新/登出/重载独立 Tab。
- 路由：路由表编辑器独立 Tab；策略：限流/去重/过滤/告警表单；设置：登录/转发/来源表单；监控：发石者/记录明细；日志：运行日志。
- 保留 AstrBot 深浅主题 CSS 变量（未引入 Tailwind CDN）。

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
