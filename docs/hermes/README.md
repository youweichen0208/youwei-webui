# Hermes Agent 工作台

基于 Open WebUI 0.11.4，设计参考 [交付说明](design-handoff.md)。四个入口位于 `/agent`、`/agent/skills`、`/agent/cron`、`/agent/gateway`。保留 Open WebUI 原有登录、Sidebar、聊天与数据库。工作台会话由 Hermes 保存，不迁移或覆盖旧聊天。

## 接线

```text
浏览器 → WebUI /api/v1/hermes（现有登录 + 指定 owner）
          ├─ Hermes 原生 HTTP :8642（运行、审批、会话、任务、状态）
          └─ trading-assistant 只读技能服务 :8643（目录、SKILL.md）
```

WebUI 后端环境变量（密钥不进入浏览器）：

- `HERMES_WORKBENCH_URL`：原生 gateway 基址，例如 `http://hermes-assistant:8642`。
- `HERMES_WORKBENCH_KEY`：与 Hermes `API_SERVER_KEY` 一致，至少 16 字符。
- `HERMES_WORKBENCH_OWNER_ID`：现有 WebUI 所有者的用户 ID，不能填邮箱。未指定时关闭；其他用户即使是管理员也不能调用代理。
- `HERMES_WORKBENCH_SKILLS_URL`：只读技能服务基址，例如 `http://hermes-workbench-skills:8643`。

技能服务由助手镜像内 `python /opt/youwei-assistant/workbench.py` 启动，只读挂载相同 Hermes profile。平台仓库的 `infra/compose/chat-workbench.json` 为可选叠加配置。它要求新 WebUI 镜像和含技能服务的助手镜像，不能拿旧已部署 digest 冒充支持工作台的版本。

固定接口基线是 Hermes `v2026.9.24` / `f97608f178d1ffeca59860195ab7da295f7c8e5f`。该版本 `/v1/skills` 向 `_find_all_skills` 传入不存在的 `include_editorial` 参数而返回 500。技能服务复用固定版本读取函数，禁用 SKILL.md 预处理，未修改上游源码。未来升级后重新验证此兼容层是否可移除。

## 行为与边界

- 原生 `/v1/runs` + SSE：文字、工具预览、审批、停止、用量。审批绑定准确 request_id，仅允许一次、会话或拒绝；不提供永久放行。工具输出是上游脱敏/截断的预览，不是完整终端日志。
- 运行中发送新消息先请求停止并等待终态，再提交新消息。请求使用幂等键；未确认收到响应时保存原请求并重试同一键。事件流断开后轮询运行状态，刷新页面恢复本人的活动 run。
- 只读技能搜索、分类、正文预览；正文按文本显示，不执行模板或内联 shell。
- 定时任务由 Hermes 独占调度：自然语言经当前模型生成待确认草稿；创建/修改/暂停/恢复/删除/立即运行均由原生接口处理。自然语言解析和运行会调用模型，测试只用 mock 模型。
- Calendar 展示每个 Hermes 任务最近一次和下一次运行，点击跳到任务；不在 WebUI 数据库复制第二份可执行任务，也不虚构所有历史运行。
- 网关页展示实时健康、各平台上报状态和跨平台历史会话。API 在线不代表 Telegram 等平台已连接。
- 当前保留助手工具允许列表。设计中的技能写入/自我改进审批、环境/工具切换、平台配置写入、配对与网关启停未开放；页面明确说明，不提供假操作或示例计数。
- 输入框采用工作台专用文本 composer，沿用 Open WebUI 的样式。原聊天 MessageInput 绑定 Open WebUI 模型、附件、工具与队列状态，直接复用会显示原生 Hermes 接口未实现的能力，故未将其完整移植到本页。

## 验证

Python 使用 Open WebUI 支持的 3.12；不依赖 Core 或兄弟项目环境：

```bash
uv venv .venv-workbench --python 3.12
uv pip install --python .venv-workbench/bin/python -r backend/tests/hermes/requirements.txt
PYTHONPATH=backend .venv-workbench/bin/python -m pytest -q backend/tests/hermes
```

Node 22：

```bash
npm ci --ignore-scripts --legacy-peer-deps
npx vitest run src/lib/apis/hermes/index.test.ts
NODE_OPTIONS=--max-old-space-size=8192 npx vite build
```

原生验收显式指定已安装固定版本的 Hermes checkout 和助手技能服务文件：

```bash
.venv-workbench/bin/python ops/verify_hermes_workbench.py \
  --hermes-checkout /path/to/pinned-hermes \
  --skills-reader /path/to/trading-assistant/integrations/hermes/workbench.py
```

验收只使用临时 HOME、临时会话和任务及本机 mock 模型，不读取个人配置/凭证，不访问付费模型或 VM。界面浏览器验证使用独立 mock HTTP；不能当成生产端到端验收。

本轮实际结果及未验证项见 [验收记录](VERIFICATION.md)。
