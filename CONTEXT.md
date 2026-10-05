# 领域与边界

| 术语 | 本仓库含义 |
| --- | --- |
| WebUI | 保存登录账户与聊天历史、提供界面的 Open WebUI fork |
| 工作台 | `/agent` 页面与服务端 Hermes HTTP 桥接 |
| 所有者 | 由服务端配置并与登录用户 ID 比对的个人助手使用者 |
| Session / Run | Hermes 管理的会话与运行；不是 Core 持久研究任务 |
| Approval | Hermes 当前待决工具审批；界面不授予永久额外权限 |
| Cron | Hermes 管理的个人定时任务；不另建一套调度器 |
| Skills reader | 助手镜像内只读技能服务，读取文本时关闭预处理 |
| 平台研究 | Core 管理的任务、PIT、Ledger 与评估，另有身份与批准流程 |

停止会话运行不等于取消已经提交的 Core 任务。个人 memory 和知识不自动成为正式研究输入。实现边界见 [架构](docs/ARCHITECTURE.md)，实际交付见 [状态](docs/STATUS.md)。
