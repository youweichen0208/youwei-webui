# 开发与测试

## 工作台隔离验证

在仓库根目录使用 Python 3.12 和 Node 22。以下 Python 环境仅安装桥接测试依赖，不是完整 Open WebUI 后端运行环境。

```bash
uv venv .venv-workbench --python 3.12
uv pip install --python .venv-workbench/bin/python -r backend/tests/hermes/requirements.txt
PYTHONPATH=backend .venv-workbench/bin/python -m pytest -q backend/tests/hermes
npm ci --ignore-scripts --legacy-peer-deps --no-audit
npx vitest run src/lib/apis/hermes/index.test.ts
NODE_OPTIONS=--max-old-space-size=8192 npx vite build
```

与 [工作台 CI](../.github/workflows/hermes-workbench.yml) 保持一致。桥接测试覆盖身份、请求边界及上游响应；前端测试覆盖 API 行为。Vite 构建不等于 Dockerfile 中完整 Pyodide 下载和镜像构建。

## 原生与完整构建

固定 Hermes 与技能服务的隔离 mock 验收命令见 [工作台指南](hermes/README.md)。只使用临时 HOME、合成模型和测试数据；不连接生产 profile 或真实付费模型。

```bash
docker build --build-arg BUILD_HASH="$(git rev-parse HEAD)" -t youwei-webui:verification .
```

Dockerfile 和锁文件决定完整运行依赖。首次构建含依赖与 Pyodide 下载，应准备相应网络和内存。上游功能开发参考根 README 与 package.json；不要将桥接环境当作完整服务环境。

历史 `svelte-check` 存在上游错误，见 [原始验收](hermes/VERIFICATION.md)；受影响测试通过不能宣称全仓类型检查通过。文档修改检查引用和命令即可，无需重建镜像。
