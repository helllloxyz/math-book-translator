# Math Book Translator

Math Book Translator 是一个面向 Markdown 数学书的交互式阅读工具。它把长篇 Markdown 拆分成可导航章节，通过 LLM 翻译并保留数学公式，同时提供导读、上下文问答、笔记、标注、Quiz 和学习画像。

## 主要能力

- 导入单个 `.md` 文件、服务器上的书籍目录，或本项目导出的 `.zip` 图书包。
- 在导入前检查章节结构，并调整目录层级和拆分粒度。
- 按章翻译，保留 KaTeX 兼容的数学定界符。
- 原文/译文对照阅读，渲染 Markdown、公式、Mermaid 和相对路径图片。
- 根据章节正文生成章节、目录和全书导读。
- 针对章节或选中文本进行流式问答，并整理为学习笔记。
- 创建高亮、下划线、章节笔记和对话笔记。
- 使用章节 Quiz、全书 Quiz 和学习画像检查理解程度。
- 导出包含原文、译文、导读、笔记、画像和图片的可迁移图书包。

## 快速开始

环境要求：Python 3.10+、Node.js 22.12+、npm。无需 Docker。

Linux / macOS：

```bash
git clone <your-repository-url>
cd math-book-translator
./install.sh
./run.sh
```

Windows PowerShell：

```powershell
git clone <your-repository-url>
Set-Location math-book-translator
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
.\run.ps1
```

浏览器默认打开 `http://127.0.0.1:8000`。第一次使用时，在“偏好设置 → 模型与存储”中添加模型 API Key 并选择默认模型。

项目只有两个用户脚本：`install` 安装依赖并构建网页，`run` 迁移数据库并启动完整应用。不需要 `.env`、Docker 或额外的部署步骤。局域网监听、后台运行、升级、备份和可选配置见[安装与部署指南](docs/DEPLOYMENT.md)。

> 当前应用不包含用户登录和权限隔离。不要直接暴露到不受信任的公网；访问控制应由部署环境或代理软件负责。

## 文档

- [安装与部署指南](docs/DEPLOYMENT.md)：Windows/Linux 安装、生产运行、配置、升级、备份和排障。
- [完整使用手册](docs/USER_GUIDE.md)：从模型配置、导入、翻译到阅读、Quiz、笔记和迁移。
- [系统架构](ARCHITECTURE.md)：后端边界、数据流和运行时文件布局。
- [贡献指南](CONTRIBUTING.md)：开发环境、测试方式和提交要求。
- [安全说明](SECURITY.md)：部署边界、密钥和漏洞报告建议。
- [开源发布检查表](docs/OPEN_SOURCE_RELEASE_CHECKLIST.md)：正式公开仓库前的维护者清单。

## 技术栈

- Backend：FastAPI、SQLAlchemy Async、Alembic、SQLite
- Frontend：Vue 3、Pinia、Vue Router、Vite
- Rendering：Markdown-It、KaTeX、Mermaid
- LLM：OpenAI-compatible、Gemini、Anthropic 适配层

## 开发验证

本仓库使用 Node.js 22。维护者通过 `mise` 固定 Node 运行时：

```bash
cd backend
source .venv/bin/activate
pytest

cd ../frontend
mise exec node@22 -- npm run build
mise exec node@22 -- node src/utils/readerTree.test.mjs
```

更多命令和工程约定见[贡献指南](CONTRIBUTING.md)。
