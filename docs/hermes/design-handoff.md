# Handoff: Hermes Agent 工作台（集成到 Open WebUI）

## Overview
将 NousResearch/hermes-agent 的核心能力作为一个新的一级入口「Agent 工作台」集成进 open-webui/open-webui。包含 4 个界面：
1. **Agent 对话** — 流式工具调用、危险命令审批、中断并重定向
2. **技能库** — 自动生成 / 自我改进的技能（SKILL.md，兼容 agentskills.io）
3. **定时任务** — 自然语言创建 cron，投递到任意消息平台
4. **消息网关** — Telegram / Discord / Slack / WhatsApp / Signal / Email 单进程网关与跨平台会话

## About the Design Files
本包中的文件是 **用 HTML 制作的设计参考**（可交互原型），展示目标外观和行为，**不是可直接上线的生产代码**。任务是在 Open WebUI 现有前端（SvelteKit + Tailwind，`src/lib/components/…`）中按其既有模式与组件 **重新实现** 这些设计；后端通过 Hermes 的 Python API / gateway 进程对接。
直接用浏览器打开 `Agent 工作台.dc.html`（需同目录 `support.js`）即可交互预览。

## Fidelity
**高保真（hifi）**：新增页面的颜色、字号、间距、交互均为最终意图。外层框架（侧栏、顶栏、输入框）是近似示意 —— **实现时应沿用 Open WebUI 现有的 Sidebar / Navbar / MessageInput 组件与样式**，只新增「Agent 工作台」分组与 4 个子页面。

## 信息架构
- 侧栏在「新对话 / 搜索 / 笔记 / 工作区」之下新增分组 **Agent 工作台**（右侧 `hermes` 小标签）
  - 子项：Agent 对话、技能库（数量）、定时任务（启用数）、消息网关（已连接/总数）
  - 选中态：背景 `#ebebee`，字重 500
- 分组下方「最近会话 · 跨平台」：每行左侧来源徽标（Web / TG / Slack / DC / Cron），等宽 10px，1px `#e4e4e7` 描边，圆角 4px
- 路由建议：`/agent`、`/agent/skills`、`/agent/cron`、`/agent/gateway`

## Screens / Views

### 全局布局
- 根：`display:flex; height:100vh`
- 侧栏：宽 248px，背景 `#f8f8f9`，右边框 1px `#ececef`，内边距 12px 10px；导航项 padding 7px 10px，圆角 8px，hover `#efeff1`
- 顶栏：高 56px，下边框 1px `#ececef`，左右 padding 20px。左：面包屑「Agent 工作台 / {页面名}」（前段 `#a1a1aa`，分隔符 `#d4d4d8`，页面名 600）。右：两个胶囊（1px `#e4e4e7`，圆角 999px，padding 4px 12px，13px，nowrap）—— 「● hermes-4-405b · OpenRouter」（6px 绿点 `#2f9e6a`）、「ssh · prod-1」（等宽）

### 1. Agent 对话
布局：中间对话列 `flex:1`（内容最大宽 760px 居中，消息间距 20px，上 padding 28px）+ 右侧上下文面板 260px（min 220px，左边框）。

组件：
- **用户消息**：右对齐，最大宽 80%，背景 `#f4f4f5`，圆角 16px，padding 10px 14px
- **Agent 头部行**：18px 黑色圆点头像 + 「Hermes」(500) + 技能徽标「技能 nginx-log-triage v3」（`#3b7dd8` 字，`#eaf2fc` 底，圆角 4px，可点击跳技能库）+「已载入」
- **工具调用卡**：1px `#ececef`，圆角 10px。标题行背景 `#fafafa`（hover `#f4f4f5`），padding 8px 12px，内容：7px 状态点（完成 `#2f9e6a`）、工具名（12px 500 `#52525b`）、命令（等宽 12px，单行省略）、耗时（12px `#a1a1aa`）、▸/▾。点击展开 `<pre>` 输出（等宽 12px，行高 1.6，padding 10px 14px，上边框）
- **审批卡**（核心交互）：
  - pending：底 `#fffaf0`，边 `#f0dcb4`，标题「等待审批」`#a5650f`；右侧说明「危险命令 · 匹配规则 sudo *」
  - 命令框：白底等宽 12px，1px `#ececef`，圆角 6px
  - 按钮：「允许一次」（黑底白字）、「本会话始终允许」（白底描边）、「拒绝」（红字 `#c9443a`）；圆角 8px，padding 6px 14px，13px
  - approved/always：底 `#f4fbf7`，边 `#cfe8da`，字 `#257a52`；denied：底 `#fafafa`，字 `#71717a`；按钮隐藏，下方总结文案随状态变化
- **结果卡**（两列 auto-fit minmax 240px）：「已创建定时任务 → 跳定时任务」「技能已自我改进 v3 → v4（待确认）→ 跳技能库」；hover 边框 `#cfd9e8`
- **中断分隔线**：用户在运行中发送消息时插入「已中断当前步骤，按新指令重定向」（12px `#a1a1aa`，两侧 1px 线）+ 新用户消息 + 「收到，正在调整计划…」
- **输入区**：状态行（运行中：蓝点 + 「等待审批 · 发送新消息将中断并重定向」+「停止」小按钮）；输入框容器 1px `#e4e4e7`，圆角 18px，阴影 `0 1px 2px rgba(0,0,0,.03)`；斜杠命令胶囊 `/skills /model /compress`；发送按钮黑底胶囊，运行中文案变为「中断并发送」，placeholder 变为「输入新指令，Hermes 会停下当前步骤并转向…」
- **右侧面板**（区块间距 22px，区块标题 12px 500 `#71717a`）：
  - 执行轨迹：8px 状态点（完成绿 / 等待 `#d48a2c` / 未开始 `#d4d4d8`）+ 标题 13px + 元信息 11px
  - 运行环境：4 格分段（本地 / Docker / SSH / Modal），选中 `#eaf2fc` 底 `#b9cde9` 边 `#2a63b3` 字（Hermes 实际支持 7 种后端：local、Docker、SSH、Singularity、Modal、Daytona、Vercel Sandbox，可用下拉扩展）
  - 工具集：可切换胶囊（开启黑底白字，关闭白底灰字）——终端、文件、网页搜索、浏览器、视觉、子代理
  - 上下文：「48.6k / 128k」+ 4px 进度条 `#3b7dd8`（对应 `/compress`、`/usage`）
  - 投递到：Telegram · @linchuan + 「网关设置」链接

### 2. 技能库
布局：左列表 380px（右边框）+ 右详情（padding 24px 28px，最大宽 720px）。
- 顶部：搜索框（1px `#e4e4e7`，圆角 8px）+ 分段筛选「全部 / 自动生成 / 手动 / Hub」（容器 `#f4f4f5` 圆角 8px padding 3px；选中白底 + `0 1px 2px rgba(0,0,0,.08)`）
- **新技能草稿横幅**：虚线 1px `#b9cde9`，底 `#f5f9fe`，圆角 10px；按钮「收录 / 查看 / 丢弃」
- 列表项：padding 10px 12px，圆角 8px，选中 `#f0f0f2`；名称等宽 13px 500 + 版本；描述 12px 单行省略；元信息 11px（来源：自动生成 `#3b7dd8`，其他 `#71717a`；使用次数；更新时间）
- 详情：标题（等宽 20px）+ 描述；右上「允许自我改进」开关
- 4 格属性条（来源 / 版本 / 使用 / 触发 `/skill-name`），1px 分隔网格，圆角 10px
- SKILL.md 预览：`<pre>` 等宽 12.5px，行高 1.7，底 `#fcfcfd`，圆角 10px
- 改进记录：44px 版本徽标 + 说明 + 元信息；待确认版本徽标 `#fff4e0` 底 `#a5650f` 字

### 3. 定时任务
布局：主区（padding 24px 28px，最大宽 820px）+ 右详情 320px。
- **自然语言创建卡**：1px `#e4e4e7`，圆角 14px；输入框 15px 无边框；下方「解析为」标签：cron 表达式（等宽）、人类可读时间、投递目标、运行环境（`#f4f4f5` 底，圆角 6px）；「创建任务」→ 成功后变绿「已创建」，并插入列表顶部
- **任务表**：列 `2.2fr 1.2fr 1fr 72px 44px`（任务 / 投递 / 下次运行 / 上次 / 开关）；表头 `#fafafa` 12px `#a1a1aa`；行 padding 11px 16px，选中 `#f7f9fc`，停用行 opacity .55；上次状态：成功 `#257a52`，失败 `#c9443a`
- **详情**：名称、时间·投递、提示词（`#fafafa` 卡）、运行记录（状态点 + 日期 + 耗时 + 「会话」链接 → 跳到该次运行产生的对话）、「立即运行 / 编辑」
- 与 Open WebUI 现有 Automations / Calendar 合并：任务运行应同步显示在日历上

### 4. 消息网关
布局：单列，最大宽 980px。
- **进程状态条**：状态点 + 「网关进程 运行中」+「已运行 6 天 4 小时 · 今日消息 128 条」+「重启」；停止态红点、「启动」
- **平台卡网格**：auto-fill minmax 150px，gap 10px；卡片圆角 12px，选中边 `#3b7dd8` + `0 0 0 3px #eaf2fc`；30px 字母图标块（`#f4f4f5`，圆角 8px，实现时替换为官方平台图标）；状态：已连接 `#257a52` / 已暂停 / 未配置 `#a1a1aa`
- **配置卡**：启用开关、Bot Token（掩码，等宽）、允许的用户（胶囊）+「生成配对码」（DM 配对）、主频道（定时任务默认投递 = Hermes `/sethome`）、语音消息自动转写开关
- **跨平台会话卡**：每行来源徽标组（如 TG + Web）+ 标题 + 时间，点击跳对话

## Interactions & Behavior
- 侧栏子项、技能徽标、结果卡、运行记录、跨平台会话 → 切换页面（无动画，即时）
- 工具卡点击展开/收起输出
- 审批：pending → approved / always / denied；状态驱动审批卡样式、执行轨迹第 5 步、总结文案、输入区运行状态
- 运行中（pending）发送消息 = 中断并重定向（Hermes：发送新消息即中断）；回车发送；「停止」= `/stop`
- 运行环境单选；工具集多选
- 技能筛选；草稿收录 → 插入列表顶部并选中；丢弃 → 隐藏横幅
- 开关组件：34×20，圆角 999px，padding 2px，开 `#3b7dd8` / 关 `#e4e4e7`，16px 白色圆钮 + `0 1px 2px rgba(0,0,0,.2)`；建议加 150ms ease 过渡
- 定时任务行点击选中；开关点击需 stopPropagation
- 所有胶囊/标签/小按钮 `white-space:nowrap`；窄屏时顶栏右侧胶囊可裁切/隐藏，右侧面板可折叠

## State Management
```
screen: 'chat' | 'skills' | 'cron' | 'gateway'
chat: { toolCalls[{id,name,cmd,dur,output,status}], openToolIds, approval: 'pending'|'approved'|'always'|'denied', running, draft, redirects[], env, toolsets{} }
skills: { filter, selected, pendingDraft, autoImprove }
cron: { nlInput, parsed{cron,human,deliverTo,env}, jobs[{name,cron,deliverTo,next,lastStatus,enabled,prompt,runs[]}], selected }
gateway: { processRunning, platforms{name:{enabled,token,allowedUsers[],home,configured}}, selected, voiceTranscribe, threads[] }
```
数据来源（建议后端桥接，经 Open WebUI 后端代理）：
- 对话流：Hermes agent loop 的流式事件（tool_start / tool_output / approval_required / message_delta）→ WebSocket
- 审批：命令审批规则（Hermes Security：command approval / allowlist）
- 技能：`~/.hermes/skills/` 读写 + 改进 diff
- 定时任务：Hermes cron scheduler；NL → cron 解析由 LLM 完成，前端展示解析结果供确认
- 网关：`hermes gateway` 进程状态与平台配置；DM pairing

## Design Tokens
颜色：
- 文本：`#18181b`（主）、`#27272a`、`#3f3f46`、`#52525b`、`#71717a`（次）、`#a1a1aa`（弱）
- 边框/分隔：`#ececef`、`#e4e4e7`、`#f2f2f4`、`#d4d4d8`
- 表面：`#ffffff`、`#fafafa`、`#fcfcfd`、`#f8f8f9`（侧栏）、`#f4f4f5`、`#f0f0f2`、`#ebebee`（选中）、`#efeff1`（hover）
- 强调：`#3b7dd8`、hover/深 `#2a63b3`、浅底 `#eaf2fc`、`#f5f9fe`、`#f7f9fc`、浅边 `#b9cde9`、`#cfd9e8`
- 成功：`#2f9e6a`（点）、`#257a52`（字）、`#f4fbf7` / `#cfe8da`
- 警告：`#d48a2c`（点）、`#a5650f`（字）、`#fffaf0` / `#fff4e0` / `#f0dcb4`
- 危险：`#c9443a`

字体：
- 无衬线：`-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, sans-serif`（实现时用 Open WebUI 现有字体）
- 等宽：`"JetBrains Mono", ui-monospace, monospace`（400/500）
- 字号：11 / 12 / 12.5 / 13 / 14（正文，行高 1.5）/ 15 / 20；字重 400 / 500 / 600

圆角：4（徽标）、6（小按钮/代码框）、8（导航/按钮/输入）、10（卡片）、12（大卡）、14（创建卡）、16（用户气泡）、18（输入容器）、999（胶囊/开关）
间距：2 / 4 / 6 / 8 / 10 / 12 / 14 / 16 / 18 / 20 / 22 / 24 / 28
阴影：`0 1px 2px rgba(0,0,0,.03)`（输入框）、`0 1px 2px rgba(0,0,0,.08)`（分段选中）、`0 0 0 3px #eaf2fc`（选中卡光圈）

## Assets
无图片资源。头像为纯色圆；平台图标为字母占位块 —— 实现时替换为各平台官方图标。所有数据为示例。

## Files
- `Agent 工作台.dc.html` — 完整可交互原型（模板 + 逻辑类，内含全部示例数据与状态逻辑）
- `support.js` — 原型运行时（仅用于预览，不需移植）

## 参考
- https://github.com/open-webui/open-webui
- https://github.com/NousResearch/hermes-agent
