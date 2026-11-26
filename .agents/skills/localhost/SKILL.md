---
name: localhost
description: 初始化或迁移 macOS 本地开发环境，包括 zsh、Homebrew、ripgrep、Neovim、Go、Node、Codex、Clash Verge Rev、Sublime Text 和 SQLExec。
---

# 本地设备初始化

## 执行清单

1. **盘点并列计划**。运行 `bash scripts/bootstrap.sh --check`，逐项列出现状、拟改动和验收方式。仅要求计划时到此为止。单项配置直接进入对应步骤。
2. **准备 Clash Verge Rev**。按[桌面软件配置](references/desktop-apps.md)处理 v2.5.10、订阅和本地代理端口 `7890`，验证代理可用。
3. **配置命令行工具**。执行整套命令行初始化时运行 `bash scripts/bootstrap.sh --apply`。脚本备份 `${ZDOTDIR:-$HOME}/.zshrc` 后更新托管区块，使用中科大 Homebrew 源及 `softpart.cn,.softpart.cn` 代理绕过规则，安装或更新 ripgrep、Neovim、Go、Node 和 npm 版 Codex，复用系统 zsh。Codex 安装渠道冲突时保留原安装并报告。Neovim 配置使用 `advancevillage/nvim`，现有同源干净仓库仅快进更新。
4. **配置 Sublime Text**。按[桌面软件配置](references/desktop-apps.md)合并 Package Control 和插件配置。SQLExec 单独核对客户端路径与连接条目，保留现有其他连接。
5. **验收**。命令行用 `bash scripts/bootstrap.sh --verify` 检查，并确认新 zsh 会话配置。桌面应用按相应步骤验证。汇报实际版本、备份、跳过项和未验证项，省略凭据。

缺少 Command Line Tools 时提示用户安装。Homebrew 首装使用官方脚本，可能需要终端交互。某一步失败时暂停依赖它的步骤，修复后重试。技能变更用 `quick_validate.py` 验证，zsh 写入用临时配置测试。
