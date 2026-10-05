# Agent 工作指引

本仓库是 Open WebUI 的个人定制 fork。使用中文沟通，代码标识符沿用英文。

- 修改前读取 [CONTEXT](CONTEXT.md)、[文档索引](docs/README.md)、[状态](docs/STATUS.md) 并检查 `git status --short`；保留已有无关改动。
- 工作台边界与实现入口见 [架构](docs/ARCHITECTURE.md)。任务状态归 Core，会话和运行归 Hermes；界面不复制业务状态机。
- 保留上游版权、许可证和品牌要求；定制代码与上游更新分别组织差异，版本以锁和构建配置为准。
- 浏览器不持助手、模型或 Core 凭证。服务端按已登录用户 ID 校验所有者，只代理明确允许的路径；不绕过审批或执行技能正文。
- 按 [开发指南](docs/DEVELOPMENT.md) 验证受影响行为；隔离测试、完整镜像、目标机与生产验收分别报告，既有检查失败不能写成通过。
- 默认协作分支为 develop，通过 PR 合入，使用 Conventional Commits；只提交任务相关文件。develop 推送可能构建发布镜像，不代表部署。
- 部署、备份与迁移由平台登记，见 [运维](docs/OPERATIONS.md)。不得用新镜像直接打开唯一生产数据库副本来试迁移。
