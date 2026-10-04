# 工作台验收记录

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
