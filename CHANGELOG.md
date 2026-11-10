# Changelog

本项目所有值得记录的变更都记录在此文件。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
