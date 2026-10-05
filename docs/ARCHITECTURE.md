# 界面架构

`浏览器 → WebUI 登录与所有者校验 → Hermes gateway / 只读技能服务`

普通聊天与工作台共用现有 WebUI 入口，原聊天历史继续由 WebUI 保存。Core 的报告与持久研究行为通过受控 HTTP 接入，不导入 Core 或 trading_core 的 Python 包。

普通聊天可选启用 [Hermes 金融卡片](hermes/CHAT.md)：专用 Responses 适配器保留完整工具结果，使用仅展示的消息类型；前端从持久化结果渲染，不执行工具或重查供应商。功能由单个服务端连接开关控制，生产启用状态以平台发布记录为准。

| 实现 | 职责 |
| --- | --- |
| [工作台路由](../src/routes/(app)/agent) | 工作台页面入口 |
| [工作台组件](../src/lib/components/agent) | 会话、运行、审批、定时任务和技能展示 |
| [前端 API](../src/lib/apis/hermes) | 调用同源桥接与处理流式事件 |
| [服务端路由](../backend/open_webui/routers/hermes.py) | 登录、所有者验证和允许路径的代理 |
| [服务端客户端](../backend/open_webui/utils/hermes.py) | 助手连接、响应与流式转发 |

助手凭证只保存在服务端，浏览器不能传入任意上游地址。所有者配置使用用户 ID；按钮可见性不能替代后端鉴权。审批由 Hermes 执行，界面不创建永久授权。定时任务沿用 Hermes 存储与调度，技能正文只展示，不执行 shell。

工作台停止运行不等于 Core 任务取消；持久任务以平台状态为准。当前未开放的编辑与管理功能查 [工作台说明](hermes/README.md)，不要以静态占位操作宣称已经实现。
