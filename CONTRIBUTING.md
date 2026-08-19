# Contributing

感谢参与 Math Book Translator。提交代码前，请确认改动属于当前 reader-first 产品范围，并遵守现有服务边界。

## 开发环境

需要 Python 3.10+、Node.js 22.12+ 和 npm。

```bash
./install.sh
```

普通运行可执行 `./run.sh`；前后端热更新请按[安装与运行指南](docs/DEPLOYMENT.md#11-开发模式)分别启动 FastAPI 和 Vite。Windows 使用对应的 PowerShell 命令。本仓库维护命令统一通过 mise 使用 Node.js 22：

```bash
mise exec node@22 -- npm --prefix frontend ci
```

## 架构约束

- Router 只负责 HTTP 校验、依赖和错误映射；工作流放在 service。
- 所有模型 SDK 调用经过 `TranslatorService`。
- 所有书籍文件路径经过 `BookStorage`。
- 数据库模型变更必须同时提供新的 Alembic migration 和测试。首次公开发布后，不得重写 `20260805_0009` 基线。
- 前端沿用 Vue Composition API 和 Pinia，不随意引入新的全局状态。
- 翻译和生成 Markdown 必须保留 KaTeX 兼容数学定界符。

完整结构见 [ARCHITECTURE.md](ARCHITECTURE.md)。

## 测试

后端：

```bash
cd backend
source .venv/bin/activate
pytest
```

Windows：

```powershell
Set-Location backend
.\.venv\Scripts\Activate.ps1
pytest
```

前端构建：

```bash
cd frontend
mise exec node@22 -- npm run build
```

前端测试是独立的 `*.test.mjs` Node 脚本。至少运行与改动相关的文件：

```bash
cd frontend
mise exec node@22 -- node src/utils/readerTree.test.mjs
```

涉及共享 reader 行为时，建议运行全部测试：

```bash
cd frontend
for test_file in $(rg --files src | rg '\.test\.mjs$' | sort); do
  mise exec node@22 -- node "$test_file" || exit 1
done
```

## 提交要求

1. 一个提交聚焦一个可解释的改动。
2. 不提交数据库、日志、`storage/`、密钥配置、虚拟环境或 `frontend/dist/`。
3. API 或数据结构变化同步更新测试和文档。
4. UI 改动至少执行前端构建和相关脚本测试。
5. 提交说明包含用户可见行为、验证命令和兼容性影响。

提交安全问题前请先阅读 [SECURITY.md](SECURITY.md)。
