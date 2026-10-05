# 普通聊天：Hermes 工具过程与金融卡片

首版通过固定 Hermes `f97608f178d1ffeca59860195ab7da295f7c8e5f` 的 `/v1/responses` 接入，工具仍在助手执行。仅改变 WebUI 展示与传输适配，不安装 trading_core，不修改助手工具权限、研究任务或 `/agent`。

## 启用与回滚

默认关闭。仅在已验证候选镜像上，为现有 Hermes OpenAI 连接设置服务端配置 `hermes_chat: true`、`hermes_owner_id: <已有所有者 ID>`；适配器选择 Responses API，无需修改其他连接的 `api_type`。非所有者返回 403，原始 `/openai/responses` 入口对该连接关闭，避免绕过适配边界。

生产配置由平台 `integrations/openwebui/configure_hermes_chat.py` 离线修改；操作前停止 WebUI 并备份。在同一脚本中设置 `--enabled false` 撤销两个新增键，其余模型、后台任务、凭证和聊天记录保留。源码或 PR 完成不表示生产已经启用。

## 行为与边界

- 服务端仅转发当前分支的 system/user/assistant 消息，不转发客户端工具定义、运行参数或 `previous_response_id`。`X-Hermes-Session-Key` 由登录用户与聊天身份计算，完整历史来自 WebUI。未保存聊天使用独立临时范围。
- 每次请求独立保存完整增量结果。最终摘要不能覆盖完整结果；消息使用 `hermes:tool_call` / `hermes:tool_result` 类型，完全退出 WebUI 本地工具执行和审批流程。
- 刷新直接读取消息 `output`。金融结果上限每次调用 512 KiB、每次响应合计 4 MiB，最多 200 个工具调用；超限给出提示。显示预览截短不影响已接受的完整卡片数据。
- 金融卡片仅识别三个既有工具：日线折线/表格、指标数值、SEC 财务表。缺失值及原因保留，禁止从摘要补数或推导季度；SEC 链接限制到官方申报路径。
- 图表库在卡片进入视口后动态导入；聊天首页没有额外金融请求。旧消息不追溯补卡，重新打开不会查询供应商。
- 停止保留已收到的数据，未完成工具显示中断；停止助手不取消已提交的 Core 任务。知识和研究操作仍可用原聊天工具，没有新增管理按钮或自动轮询。
- Responses 的工具明细可能比 Chat Completions 文本占用更多聊天存储；它们属于个人查询记录，不是正式 PIT、Ledger 或批准的 ResearchRelease。

## 验证

```bash
PYTHONPATH=backend .venv-workbench/bin/python -m pytest -q backend/tests/hermes
npx vitest run --config vitest.hermes-chat.config.ts
npx vitest run src/lib/apis/hermes/index.test.ts src/lib/apis/startup.test.ts
npx vitest run --config vitest.sidebar.config.ts
NODE_OPTIONS=--max-old-space-size=8192 npx vite build
```

使用桥接测试环境的 Python 执行以下脚本；参数必须为上述完整 SHA 的独立 Hermes checkout，内有 `.venv/bin/hermes`。脚本只创建临时 HOME、合成模型和金融工具，不调用供应商或付费模型。

```bash
.venv-workbench/bin/python ops/verify_hermes_chat.py /tmp/hermes-chat-native
# 可选：连接本机一次性 WebUI（会配置合成账户、连接及聊天，禁止指向生产）
.venv-workbench/bin/python ops/verify_hermes_chat.py /tmp/hermes-chat-native \
  --webui-url http://127.0.0.1:8080
```

本次隔离测试、实际 WebUI 聊天/持久化、浏览器与性能结果见平台 `docs/ops/hermes-chat-cards-20261006.md`。全仓既有类型检查错误仍单独报告；没有真实付费模型质量或正式前向评估结论。
