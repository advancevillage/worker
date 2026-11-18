---
name: localhost
description: 初始化或更新 macOS 的 zsh 本地开发环境，配置中科大 Homebrew 源、softpart.cn 代理绕过规则，安装 ripgrep、Go、Node、npm 版 Codex 并准备 Neovim 配置。用于本地设备初始化，不用于服务器部署。
---

# 本地设备初始化

执行入口为 `scripts/bootstrap.sh`，支持 `--check`（默认，只读预检查）、`--apply`（初始化并验证）、`--verify`（检查实际配置和工具）。使用 Bash 执行，适配 macOS Apple Silicon 和 Intel。

先运行预检查。用户要求执行初始化时再运行 `--apply`；仅要求计划或检查时不要修改设备。遇到沙箱权限限制，按执行环境规则申请授权，不通过改变安装目录绕过限制。

初始化范围：

- 保留原有 zsh 设置，以带标记的区块维护 `assets/zshrc.zsh` 中的设置；修改前备份。默认写入 `~/.zshrc`，存在 `ZDOTDIR` 时使用它。
- 使用 `127.0.0.1:7890` HTTP 代理。`NO_PROXY` 和 `no_proxy` 均为 `softpart.cn,.softpart.cn`，表示主域名和子域名；不要写成兼容性不一致的 `*.softpart.cn`。
- 安装或复用 Homebrew，设置中科大 brew、bottles 和 API 源。只安装或升级 ripgrep、go、node 及其必要依赖；保留现有工具链的其他配置。
- 通过 `npm install -g @openai/codex@latest` 安装 Codex，不通过 Homebrew 安装，不执行登录。出现其他安装渠道的命令冲突时报告并停止，不强制覆盖。
- 将 `https://github.com/advancevillage/nvim.git` 克隆到 `~/.config/nvim`。已有同源干净仓库仅快进更新；本地改动或不同来源目录保留并报告。不安装 Neovim 本体。

若缺少 Command Line Tools，报告需要安装后重试；不自动触发 GUI。缺少 Homebrew 时使用官方安装脚本，安装可能需要终端交互。代理不可用或网络请求失败时报告，不擅自切换代理或镜像。

执行失败时停止依赖该步骤的后续操作；修复原因后可重复运行。输出实际版本、命令路径、备份路径和保留项。镜像索引可能滞后，不将其版本等同于上游最新发布；Codex 以 npm 的 latest 标签为准。

验证技能：运行 skill-creator 的 `quick_validate.py`。验证脚本配置更新时，在临时目录中 source 脚本并调用 `configure_zsh <临时目录>/.zshrc`，不要为了测试反复修改真实用户配置。实际运行后检查 `--verify`，并检查新交互 zsh 中的有效变量；不要输出完整用户环境或凭据。
