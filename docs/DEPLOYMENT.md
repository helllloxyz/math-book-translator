# 安装与运行指南

本文档面向个人电脑和个人服务器。项目只需要 Python、Node.js 和 npm，不需要 Docker，也不要求配置代理软件。

普通用户只需要记住两个命令：

```text
install = 安装依赖并构建网页
run     = 升级数据库并启动应用
```

应用启动后，网页和 API 共用一个进程、一个端口，默认地址为 `http://127.0.0.1:8000`。

## 1. 环境要求

- Python 3.10 或更高版本，推荐 Python 3.12。
- Node.js 22.12 或更高版本，推荐 Node.js 22 LTS。
- npm（安装 Node.js 时会一并安装）。
- Git（仅通过 Git 下载和更新源码时需要）。

Python 依赖会安装到项目内的 `backend/.venv`，不会修改系统 Python。应用调用外部 LLM 服务，不要求本机安装 GPU 环境。

## 2. 获取源码

```bash
git clone <your-repository-url>
cd math-book-translator
```

建议放在当前用户有读写权限的目录中，不要使用 root 或管理员账户日常运行。

## 3. Linux / macOS

先确认环境：

```bash
python3 --version
node --version
npm --version
```

首次安装：

```bash
chmod +x install.sh run.sh
./install.sh
```

启动：

```bash
./run.sh
```

浏览器通常会自动打开 `http://127.0.0.1:8000`。在终端按 `Ctrl+C` 停止应用。

## 4. Windows

建议从 [Python 官网](https://www.python.org/) 安装 Python，并启用 Python Launcher；从 [Node.js 官网](https://nodejs.org/) 安装 Node.js 22 LTS。

打开 PowerShell，在项目目录执行：

```powershell
python --version
node --version
npm --version
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
.\run.ps1
```

`-Scope Process` 只对当前 PowerShell 窗口生效，不会永久改变系统策略。应用默认打开 `http://127.0.0.1:8000`，按 `Ctrl+C` 停止。

如果 npm 因 Windows 路径过长而安装失败，可把项目放到较短路径，例如 `C:\src\math-book-translator`。

## 5. 两个脚本分别做什么

### install

`install.sh` 和 `install.ps1` 会依次：

1. 检查 Python、Node.js 和 npm。
2. 创建或更新 `backend/.venv`。
3. 安装后端 Python 依赖。
4. 使用 `npm ci` 安装锁定的前端依赖。
5. 构建网页到 `frontend/dist`。

首次下载或 `git pull` 更新代码后执行一次即可。重复执行不会删除数据库、图书、设置或模型密钥。

### run

`run.sh` 和 `run.ps1` 会依次：

1. 检查虚拟环境和前端构建是否存在。
2. 自动执行 Alembic 数据库迁移。
3. 启动 FastAPI，由它同时提供网页和 API。
4. 打开浏览器。

运行阶段不再启动 Vite，也不需要 Node.js 常驻进程。

## 6. 配置

### 6.1 普通用户不需要 `.env`

项目不创建也不要求 `backend/.env`。常用参数已经有合理默认值；模型 API Key 在网页的“偏好设置 → 模型与存储”中填写，并保存在本机的凭据文件中。

需要临时修改端口或数据位置时，直接给启动脚本设置环境变量即可，不必再维护配置文件。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_HOST` | `127.0.0.1` | 监听地址 |
| `APP_PORT` | `8000` | 网页和 API 共用端口 |
| `OPEN_BROWSER` | `1` | 设为 `0` 时不自动打开浏览器 |
| `VENV_PATH` | `backend/.venv` | Python 虚拟环境位置 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./database.db` | 数据库地址 |
| `STORAGE_DIR` | `storage` | 图书文件目录 |
| `SETTINGS_FILE` | `settings.json` | 应用设置文件 |
| `LLM_CREDENTIALS_FILE` | `backend/config/llm_credentials.json` | 模型凭据文件 |
| `QUICK_INPUTS_FILE` | 项目内 `config/quick-inputs.json` | 快捷输入配置 |
| `TRANSLATION_CONCURRENCY` | `5` | 同时翻译的章节数 |
| `IMPORT_PREFLIGHT_LLM` | `0` | 是否启用可选的 LLM 导入预检 |
| `APP_LOG_LEVEL` | `INFO` | 日志级别 |
| `APP_ACCESS_LOG` | `errors` | `all` 显示全部访问日志 |

Linux / macOS 示例：

```bash
APP_PORT=8010 OPEN_BROWSER=0 ./run.sh
```

Windows PowerShell 示例：

```powershell
$env:APP_PORT = "8010"
$env:OPEN_BROWSER = "0"
.\run.ps1
```

这些变量只在当前终端中生效。个人电脑通常完全不需要修改它们。

### 6.2 默认数据位置

启动脚本以 `backend` 为工作目录，因此默认数据位于：

```text
backend/database.db
backend/settings.json
backend/config/llm_credentials.json
backend/storage/
```

`llm_credentials.json` 含有明文 API Key，不得提交到 Git，也不要分享给他人。

### 6.3 使用独立数据目录（可选）

长期运行时可以把数据放到易于备份的位置。Linux 示例：

```bash
DATABASE_URL=sqlite+aiosqlite:////srv/math-book-translator/database.db \
STORAGE_DIR=/srv/math-book-translator/storage \
SETTINGS_FILE=/srv/math-book-translator/settings.json \
LLM_CREDENTIALS_FILE=/srv/math-book-translator/llm_credentials.json \
./run.sh
```

Windows PowerShell 示例：

```powershell
$env:DATABASE_URL = "sqlite+aiosqlite:///C:/MathBookTranslatorData/database.db"
$env:STORAGE_DIR = "C:/MathBookTranslatorData/storage"
$env:SETTINGS_FILE = "C:/MathBookTranslatorData/settings.json"
$env:LLM_CREDENTIALS_FILE = "C:/MathBookTranslatorData/llm_credentials.json"
.\run.ps1
```

修改路径前先停止应用并备份原数据。改变配置不会自动搬迁旧文件。

## 7. 从其他设备访问（可选）

默认只允许本机访问。若要在可信局域网中使用：

Linux / macOS：

```bash
APP_HOST=0.0.0.0 ./run.sh
```

Windows PowerShell：

```powershell
$env:APP_HOST = "0.0.0.0"
.\run.ps1
```

随后使用 `http://主机IP:8000` 访问，并按操作系统要求放行该端口。

> 应用没有内置账户、密码和多用户权限。只应在可信网络中开放；如果使用外部代理软件，访问控制由该软件负责。

## 8. 后台运行（可选）

个人电脑可以保持终端窗口打开。需要在 Linux 服务器长期运行时，可以使用 systemd。

创建 `/etc/systemd/system/math-book-translator.service`，替换真实用户和项目路径：

```ini
[Unit]
Description=Math Book Translator
After=network-online.target

[Service]
Type=simple
User=mathbook
WorkingDirectory=/opt/math-book-translator
Environment=APP_HOST=127.0.0.1
Environment=OPEN_BROWSER=0
ExecStart=/opt/math-book-translator/run.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now math-book-translator
sudo systemctl status math-book-translator
```

Windows 可在“任务计划程序”中执行：

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\完整路径\run.ps1"
```

先在普通 PowerShell 中成功运行一次，再创建后台任务。建议为后台启动设置 `OPEN_BROWSER=0`。

## 9. 更新

先停止正在运行的应用，然后执行：

Linux / macOS：

```bash
git pull --ff-only
./install.sh
./run.sh
```

Windows：

```powershell
git pull --ff-only
.\install.ps1
.\run.ps1
```

安装脚本会更新依赖并重新构建网页；运行脚本会自动升级数据库。

## 10. 备份与恢复

完整备份至少包括：

- `backend/database.db`：图书、章节、笔记和 Quiz 数据。
- `backend/storage/`：原文、译文、导读、图片和学习画像。
- `backend/settings.json`：模型选择和存储设置。
- `backend/config/llm_credentials.json`：模型密钥，需要加密保护。
- 修改过的 `config/quick-inputs.json`。

备份前先停止应用，再复制这些文件。恢复时先安装项目，把文件放回原位置，然后执行 `run`；数据库迁移会自动完成。单本图书包适合迁移书籍，但不能替代整个实例备份。

## 11. 开发模式

普通使用不需要开发模式。需要前后端热更新时，分别打开两个终端。

后端：

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm run dev
```

开发网页为 `http://localhost:5173`，API 为 `http://localhost:8000`。Windows 在后端终端使用 `.venv\Scripts\Activate.ps1` 激活虚拟环境。

## 12. 常见问题

### 找不到 Python

Linux 确认 `python3 --version` 至少为 3.10。Windows 运行 `py -3 --version`；重新安装 Python 时启用 Launcher。

### Node.js 版本不满足要求

安装 Node.js 22 LTS，重新打开终端后检查 `node --version`。

### PowerShell 禁止执行脚本

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 前端构建不存在

重新执行 `install.sh` 或 `install.ps1`。不要直接双击打开 `frontend/dist/index.html`。

### 端口已被占用

改用其他端口：

```bash
APP_PORT=8010 ./run.sh
```

### 页面能打开但功能报错

检查 `http://127.0.0.1:8000/health` 和 `http://127.0.0.1:8000/docs`。需要更多日志时设置 `APP_ACCESS_LOG=all` 或 `APP_LOG_LEVEL=DEBUG` 后重启。

### 模型功能提示未配置

进入“偏好设置 → 模型与存储”，确认已填写服务商 API Key、Base URL 和模型名，并已选择默认模型。

### 翻译限流或超时

降低并发后重新启动，例如：

```bash
TRANSLATION_CONCURRENCY=2 ./run.sh
```

已成功写入的译文不会被补全操作覆盖。
