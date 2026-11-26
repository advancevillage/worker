# macOS 桌面软件配置

## Clash Verge Rev

1. 检查设备架构和现有版本。需要安装或升级时，从 [v2.5.10 官方发布页](https://github.com/clash-verge-rev/clash-verge-rev/releases/tag/v2.5.10) 下载对应架构的 macOS DMG，并按发布页的 SHA-256 验证。升级时先退出程序并备份用户配置，再替换应用。已有目标版本可直接复用。
2. 如需新建或更新订阅，由用户在浏览器登录 [订阅站](https://m.mmomm.io/user)，从账户页面复制最新 Clash 订阅链接，在 Clash Verge 的订阅界面粘贴并导入。已有有效订阅可复用。订阅链接视为凭据，只保存在客户端，避免写入仓库、技能、计划、脚本参数或终端输出。
3. 将混合代理端口设为 `7890`，仅监听本地，保持现有系统代理、规则模式和 TUN 偏好。若端口已被占用，先识别监听进程。验证所选订阅可更新，并执行 `curl --noproxy '' --proxy http://127.0.0.1:7890 -fsSL -o /dev/null --max-time 20 https://packagecontrol.io/channel_v3.json` 检查通过代理访问公开插件源。

## Sublime Text 和 Package Control

1. 复用已安装的 Sublime Text。缺失时用 [Homebrew cask](https://formulae.brew.sh/cask/sublime-text) 安装，命令为 `brew install --cask sublime-text`。在 Sublime Text 中按 `⌘⇧P` 运行 `Install Package Control`。如果已安装，直接打开 Package Control 的 Settings – User。必要时按[官方安装说明](https://packagecontrol.io/installation)手动安装。
2. 通过 Settings → Browse Packages 定位 `Packages/User/Package Control.sublime-settings`。更新前备份现有文件，使用 Sublime Text 的设置编辑器合并[配置模板](../assets/Package-Control.sublime-settings)。补齐六个包和官方 channel，设置本地 `http_proxy`，保留其他插件和源。如果官方 channel 同时出现在 `repositories`，仅删除该重复条目。此字段用于具体包仓库地址。若已有 `https_proxy` 覆写且指向其他代理或禁用了继承，将它同步到指定的本地代理。保留 Package Control 已写入的 `bootstrapped` 和 `in_process_packages` 状态。[Package Control 设置说明](https://packagecontrol.io/docs/settings)
3. 保存后检查六个包已安装，必要时重启编辑器。用 PHP 文件检查 LSP-intelephense，打开 Terminus 确认 shell 正常，并检查 SideBarEnhancements 菜单及 SQLExec 命令。

## SQLExec

1. **核对客户端**。检查用户指定的 MySQL 客户端及版本。Apple Silicon 上可用 `/opt/homebrew/bin/mysql --default-character-set=utf8 --version` 检查现有命令。其他设备以实际客户端路径为准。其他数据库命令按用户配置保留。
2. **检查并按需合并**。从 Sublime Text → Settings → Package Settings → SQLExec → Settings – User 打开 `Packages/User/SQLExec.sublime-settings`。核对 `sql_exec.debug` 为 `false`、`sql_exec.commands` 以及 `connections` 中的指定连接。连接字段包括 `type`、`host`、`port`、`username`、`password` 和 `database`。一致时复用。有改动时先备份，再合并指定条目，保留其他连接与设置。
3. **保护凭据**。备份和配置仅保存在当前用户可读的本机文件中。SQLExec 的 MySQL 适配器会把密码放进客户端命令行参数，执行与排查时避免输出完整命令或传播含密码的设置。技能、计划和仓库仅记录非密码参数。
4. **验收**。检查设置可加载、连接选择器可见。用户要求连接验收时，在可访问目标数据库的网络内选中该连接，运行 `SELECT 1;` 并检查返回值。[SQLExec 文档](https://lubriciousdevelopers.github.io/projects/sublime-sql-exec/)
