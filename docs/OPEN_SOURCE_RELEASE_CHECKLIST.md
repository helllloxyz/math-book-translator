# 开源发布检查表

此清单用于维护者第一次公开仓库及后续版本发布。它不由安装脚本自动执行。

## 必须完成

- [ ] 选择与依赖、商业计划和贡献策略一致的开源许可证，并在根目录添加 `LICENSE`。未添加许可证时，公开可见不等于获得开源使用授权。
- [ ] 明确仓库 URL，把 README 中的 `<your-repository-url>` 替换为真实地址。
- [ ] 检查完整 Git 历史，确认没有 API Key、`.env`、数据库、私人书籍、日志或用户数据。
- [ ] 为安全问题配置私有报告入口，并更新 `SECURITY.md` 的联系方式和响应时限。
- [ ] 在干净的 Linux 和 Windows 环境分别执行 `install` 和 `run`，确认网页与 API 正常。
- [ ] 执行完整后端测试、全部前端 `*.test.mjs` 和前端生产构建。
- [ ] 从全新实例完成一次：配置模型 → 上传 Markdown → 翻译 → 阅读 → Chat → Quiz → 导出/导入图书包。
- [ ] 确认 README 截图、功能描述和版本号与发布版本一致。

## 仓库治理

- [ ] 开启 issue 模板：Bug、功能建议、安装问题。
- [ ] 开启 pull request 模板，要求说明验证命令、截图和迁移影响。
- [ ] 配置默认分支保护和必需 CI 检查。
- [ ] 添加 `CODE_OF_CONDUCT.md`，并确定维护者/审核者。
- [ ] 选择版本规则和 changelog 流程，建议使用 Semantic Versioning。
- [ ] 声明支持的 Python、Node、Windows 和 Linux 版本范围。

## CI 建议

- [ ] 后端：Python 3.10 和 3.12 测试矩阵。
- [ ] 前端：Node.js 22，执行 `npm ci`、全部脚本测试和 `npm run build`。
- [ ] Shell：运行 `bash -n`，可选 ShellCheck。
- [ ] PowerShell：在 Windows runner 解析并执行脚本的无副作用检查路径。
- [ ] 依赖和 secret scanning。
- [ ] 检查 Alembic 只有一个 head，全新数据库可升级到 head，且 `alembic check` 没有模型差异。

## 发布前人工检查

- [ ] 默认监听仍为本机地址，README 清楚说明应用没有内置认证。
- [ ] 文档和脚本中没有硬编码 API Key、私人路径或个人数据。
- [ ] `config/llm_provider_options.json` 中的服务商地址和模型名仍有效。
- [ ] 没有提交 `frontend/dist/`、虚拟环境、`storage/` 或测试生成数据。
- [ ] 依赖许可证与所选项目许可证兼容。
- [ ] 对翻译内容、模型输出和图书包分享添加版权与隐私提醒。
