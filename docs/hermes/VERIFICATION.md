# 工作台验收记录

本文保留当次验收结果。当前交付与部署入口见 [状态](../STATUS.md)，不要将历史未部署说明作为当前状态。

日期：2026-10-04；源码基线 Open WebUI 0.11.4 archive，Hermes 固定 `f97608f178d1ffeca59860195ab7da295f7c8e5f`。所有运行与数据均为本机隔离验证。

| 验证 | 实际结果 |
| --- | --- |
| Python 3.12 代理 pytest | 20 passed；登录/所有者、方法与路径允许列表、字段校验、准确审批 ID、禁用永久批准、幂等头、SSE、限长、上游错误脱敏和独立技能 URL |
| Vitest | 4 passed；分片/多行/CRLF SSE、错误帧、日历时间范围/纳秒格式/暂停任务 |
| Node 22 `vite build` | production build 通过（不是完整 Docker / pyodide 资源获取流程） |
| Ruff 新增 Python 文件 | 格式化；`--select F` 检查通过 |
| 原生 gateway + mock 模型 | 会话创建、同键运行重放、SSE 完成、持久会话历史、cron 创建/暂停/恢复/删除通过 |
| 原生技能读取 | 技能目录与正文通过；模板不预处理，测试内联 shell 未执行 |
| 浏览器 mock HTTP：审批 | 等待卡 → 允许一次 → 完成答复；技能正文读取通过 |
| 浏览器 mock HTTP：重定向 | 观测调用顺序 start1 → running → stop → cancelled → start2 → completed |
| 浏览器 mock HTTP：任务 | 创建、暂停及网关状态通过；自然语言解析填入草稿后，确认前创建请求数为 0 |
| 浏览器窄屏 | 390 × 844 下任务详情操作可见，无横向溢出 |
| 完整 svelte-check | 未通过；未修改 archive 基线和当前候选同为 7001 errors / 198 warnings / 344 files；新增工作台文件无诊断错误 |

助手仓库另完成 25 个 pytest、Docker build，以及 `--network none --read-only` 容器中的只读技能文件读取。平台仓库完成 catalog 校验及可选 Compose 合并渲染，没有启动生产服务。

没有调用真实付费模型，没有读写生产 profile、WebUI 数据库或 VM，没有验证实际消息平台投递。审批浏览器测试使用合成的安全事件，并未启用终端工具执行危险命令。没有验证完整技能编辑/自我改进审批、平台管理与运行环境切换；这些能力在本次接口中不开放。

## 2026-10-05 侧栏按路由加载性能切片

普通聊天仅请求工作台 `config`；进入 `/agent` 或子路由后才请求最近会话、技能与任务。在工作台内跳转不重复请求，离开时取消请求并清空详情；重新进入会重新加载。组件销毁取消配置和详情请求，过期响应不得回写。失败保留导航，不自动轮询或重试；`hermes` 增加兼容现有调用的可选第五参数 `AbortSignal`。

隔离验证：先用组件测试复现 7 项失败，再实现；新增侧栏 Vitest 14 项通过，原有 API/SSE/Calendar Vitest 4 项通过，工作台 Python 20 项通过，Node 22 Vite production build 通过。`npm ci --ignore-scripts --legacy-peer-deps --no-audit` 验证锁文件；jsdom 仅用于 DOM 回归测试，既有包版本保持不变。完整 `npm run check` 仍为 7001 errors / 198 warnings（344 files），本次文件无错误，不能视为全仓类型检查通过。

```bash
npx svelte-kit sync
npx vitest run --config vitest.sidebar.config.ts
npx vitest run src/lib/apis/hermes/index.test.ts
PYTHONPATH=backend .venv-workbench/bin/python -m pytest -q backend/tests/hermes
NODE_OPTIONS=--max-old-space-size=8192 npx vite build
```

镜像、目标机、浏览器性能与生产切换另由平台登记；上述本地结果不代表线上性能目标或正式前向评估已通过。

## 热缓存加载后续切片（2026-10-05）

公共配置与 session 校验并行，登录后的配置刷新保留；服务端模型查询与用户设置并行，直连模型仍等待最新设置并受配置开关控制。无持久客户端缓存、无后端/权限/数据库改动。新增 startup 回归先观察 3 项失败，修复后 7 项通过；既有 API 4 项、侧栏 14 项、Python 工作台 20 项通过。本地/CI 前端构建、完整 amd64 镜像、备份副本启动/重启、跨服务 mock 与候选浏览器验证通过，已仅更新生产 WebUI。源码 12298d1d128d45eb9177fb7a01657645253349fb，digest `sha256:8aa9d39f1a5fc1517c9e93e03d3069e44ca041765c074e337810cfb5b5cd168d`。热缓存各 5 次中位数 7.877 → 5.166 秒、最大值 10.050 → 6.924 秒，≤5 秒目标仍未达到；新版本首次下载 15.114 秒单独保留。全仓类型检查仍为既有 7001 errors / 198 warnings；没有付费调用或正式评估。完整原始数据和恢复见平台 `docs/ops/webui-warm-loading-20261005.md` 与 `infra/releases/20261005-webui-warm-loading/`。

镜像 workflow 支持显式 dispatch `publish_candidate=true` 发布所选源码 SHA 标签，默认关闭；仅发布候选，不自动部署，避免在生产主机上编译导致性能测量受负载干扰。
