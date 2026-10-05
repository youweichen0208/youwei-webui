# 交付状态

2026-10-06：普通聊天金融卡片与工具过程已实现并进行隔离验证；范围、开关及验证命令见 [聊天增强](hermes/CHAT.md)。尚未生产切换；下表保留既有发布证据。

核对日期：2026-10-05。个人入口沿用 Open WebUI v0.11.4 fork；金融工具由助手加载独立 trading_core，未为此修改 WebUI 运行代码。

| 证据入口 | 含义 |
| --- | --- |
| [工作台历史验收](hermes/VERIFICATION.md) | 隔离 Python、前端、原生 mock 与当次检查限制 |
| [平台实施计划](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/IMPLEMENTATION_PLAN.md) | 工作台与跨仓任务的逐次交付 |
| [当前版本登记](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/UPSTREAMS.md) | 已部署镜像和候选的区别 |
| [金融上线记录](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/ops/trading-core-20261005.md) | 保持 WebUI 镜像，验证鉴权、工作台和助手工具 |

源码 HEAD 与生产镜像可能不同，具体身份查部署登记。历史类型检查失败仍按原记录保留；mock 验收不代表真实付费模型选择工具的质量，也不代表正式前向评估通过。本次补齐文档不改变服务或部署状态。
