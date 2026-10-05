# 发布与运维

本仓库负责镜像构建；部署组合、凭证、持久卷、备份和回滚由平台维护。develop 推送触发 [镜像发布工作流](../.github/workflows/youwei-release.yml)，生成镜像不等于切换生产。

发布时记录源码 SHA、上游版本、构建架构和真实 registry digest。平台固定 digest 后验收兼容组合；不能用分支 HEAD、浮动标签或本地 image ID 代替已部署身份。当前指针见 [状态](STATUS.md)。

配置与端点见 [工作台指南](hermes/README.md)。所有者 ID、内部服务 URL 与 API 凭证仅由服务端配置；不提交展开后的 Compose 或环境文件，不在浏览器保存助手密钥。只读技能服务使用同一助手镜像和只读 profile。

升级前备份 WebUI 数据库、附件与配置，在隔离副本完成上游迁移、登录和旧聊天验证。回滚必须考虑数据库迁移兼容，不能只换回旧镜像。助手会话、个人知识与 Core 数据各有权威存储，恢复 WebUI 不恢复正式 Ledger。

具体执行步骤以平台 [个人助手运维](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/ops/hermes-personal-assistant.md)、[上游登记](https://github.com/youweichen0208/youwei-trading-agent/blob/develop/docs/UPSTREAMS.md) 为准。同机备份演练不证明独立故障域恢复能力。
