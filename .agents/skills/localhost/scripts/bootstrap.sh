#!/bin/bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BEGIN_MARK='# >>> localhost managed >>>'
END_MARK='# <<< localhost managed <<<'
note() { printf '%s\n' "$*"; }
die() { note "ERROR: $*" >&2; exit 1; }

configure_zsh() {
  local target="$1" staged backup
  [[ ! -L "$target" ]] || die "配置文件为符号链接，请先确认真实目标：$target"
  mkdir -p "$(dirname "$target")"
  staged="$(mktemp "${target}.localhost.XXXXXX")"
  if [[ -f "$target" ]]; then
    if ! awk -v begin="$BEGIN_MARK" -v end="$END_MARK" '
      $0 == begin { if (inside || seen++) exit 2; inside=1; next }
      $0 == end { if (!inside) exit 2; inside=0; next }
      !inside { print }
      END { if (inside) exit 2 }
    ' "$target" > "$staged"; then
      rm -f "$staged"
      die "配置区块标记异常，保留原文件：$target"
    fi
  fi
  printf '%s\n' "$BEGIN_MARK" >> "$staged"
  cat "$SKILL_DIR/assets/zshrc.zsh" >> "$staged"
  printf '%s\n' "$END_MARK" >> "$staged"
  /bin/zsh -n "$staged"
  if [[ -f "$target" ]] && cmp -s "$target" "$staged"; then
    rm -f "$staged"
    note "配置已是最新：$target"
    return
  fi
  if [[ -f "$target" ]]; then
    backup="$(mktemp "${target}.localhost-backup.XXXXXX")"
    cp -p "$target" "$backup"
    chmod "$(stat -f '%Lp' "$target")" "$staged"
    note "配置备份：$backup"
  fi
  mv "$staged" "$target"
  note "配置已更新：$target"
}

load_environment() {
  export HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890
  export NO_PROXY=softpart.cn,.softpart.cn
  export http_proxy="$HTTP_PROXY" https_proxy="$HTTPS_PROXY" no_proxy="$NO_PROXY"
  export HOMEBREW_BREW_GIT_REMOTE=https://mirrors.ustc.edu.cn/brew.git
  export HOMEBREW_BOTTLE_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles
  export HOMEBREW_API_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles/api
  export HOMEBREW_NO_INSTALL_CLEANUP=1
  if [[ -x /opt/homebrew/bin/brew ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x /usr/local/bin/brew ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
}

check() {
  [[ "$(uname -s)" == Darwin ]] || die '仅支持 macOS'
  note "架构：$(uname -m)"
  if ! xcode-select -p; then
    die '缺少 Command Line Tools，请执行 xcode-select --install，安装完成后重试'
  fi
  local tool
  for tool in brew git rg go node npm codex; do
    command -v "$tool" || note "待安装：$tool"
  done
  if /usr/bin/nc -z -w 3 127.0.0.1 7890; then
    note '代理端口可连接：127.0.0.1:7890'
  else
    die '无法连接代理 127.0.0.1:7890，请启动代理后重试'
  fi
}

prepare_nvim() {
  local target="$HOME/.config/nvim" origin branch
  if [[ ! -e "$target" && ! -L "$target" ]]; then
    git clone https://github.com/advancevillage/nvim.git "$target"
    return
  fi
  if [[ -L "$target" || ! -d "$target/.git" ]]; then
    note "保留：$target 不是普通 Git 仓库目录"
    return
  fi
  origin="$(git -C "$target" remote get-url origin 2>/dev/null || true)"
  case "$origin" in
    https://github.com/advancevillage/nvim.git|https://github.com/advancevillage/nvim|git@github.com:advancevillage/nvim.git) ;;
    *) note '保留：nvim 仓库来源与目标不一致'; return ;;
  esac
  if [[ -n "$(git -C "$target" status --porcelain)" ]]; then
    note '保留：nvim 有未提交或未跟踪改动，跳过更新'
    return
  fi
  branch="$(git -C "$target" symbolic-ref --quiet --short HEAD || true)"
  if [[ -z "$branch" ]] || ! git -C "$target" rev-parse --verify '@{upstream}' >/dev/null 2>&1; then
    note '保留：nvim 无当前分支或上游分支，跳过更新'
    return
  fi
  git -C "$target" pull --ff-only
}

verify() {
  local tool prefix installed latest
  /bin/zsh -n "${ZDOTDIR:-$HOME}/.zshrc"
  for tool in brew rg go node npm codex; do
    command -v "$tool" || die "找不到命令：$tool"
  done
  brew --version
  rg --version
  go version
  node --version
  npm --version
  codex --version
  npm list -g @openai/codex --depth=0
  prefix="$(npm prefix -g)"
  [[ "$(command -v codex)" == "$prefix/bin/codex" ]] || die 'Codex 命令与 npm 全局安装目录不一致'
  installed="$(node -p 'require(process.argv[1]).version' "$prefix/lib/node_modules/@openai/codex/package.json")"
  latest="$(npm view @openai/codex@latest version)"
  [[ "$installed" == "$latest" ]] || die "Codex 版本未到 latest：$installed / $latest"
  note "Codex npm latest：$latest"
  note "Homebrew 源：$(git -C "$(brew --repo)" remote get-url origin)"
  if [[ -d "$HOME/.config/nvim/.git" ]]; then
    note "nvim 来源：$(git -C "$HOME/.config/nvim" remote get-url origin)"
    git -C "$HOME/.config/nvim" status --short
  else
    note '未完成：nvim 目标目录不是 Git 仓库'
  fi
  /bin/zsh -ic '
    [[ "$NO_PROXY" == softpart.cn,.softpart.cn && "$no_proxy" == "$NO_PROXY" ]] || exit 1
    [[ "$HTTP_PROXY" == http://127.0.0.1:7890 && "$HTTPS_PROXY" == "$HTTP_PROXY" ]] || exit 1
    [[ "$http_proxy" == "$HTTP_PROXY" && "$https_proxy" == "$HTTPS_PROXY" ]] || exit 1
    [[ "$HOMEBREW_BREW_GIT_REMOTE" == https://mirrors.ustc.edu.cn/brew.git ]] || exit 1
    [[ "$HOMEBREW_BOTTLE_DOMAIN" == https://mirrors.ustc.edu.cn/homebrew-bottles ]] || exit 1
    [[ "$HOMEBREW_API_DOMAIN" == https://mirrors.ustc.edu.cn/homebrew-bottles/api ]] || exit 1
    print "新 zsh 会话配置验证通过；NO_PROXY=$NO_PROXY"
  '
}

apply() {
  local installer formula prefix existing expected
  check
  mkdir -p "$HOME/.config"
  if ! command -v brew >/dev/null 2>&1; then
    installer="$(mktemp -t localhost-brew-install)"
    curl -fsSL --connect-timeout 15 --max-time 120 https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh -o "$installer"
    /bin/bash "$installer"
    rm -f "$installer"
    load_environment
  fi
  configure_zsh "${ZDOTDIR:-$HOME}/.zshrc"
  brew update
  for formula in ripgrep go node; do
    if brew list --versions "$formula" >/dev/null 2>&1; then
      brew upgrade "$formula"
    else
      brew install "$formula"
    fi
  done
  prefix="$(npm prefix -g)"
  export PATH="$prefix/bin:$PATH"
  existing="$(command -v codex || true)"
  expected="$prefix/lib/node_modules/@openai/codex/bin/codex.js"
  if [[ -n "$existing" ]]; then
    if [[ ! -f "$expected" || ! "$existing" -ef "$expected" ]]; then
      die "Codex 已由其他来源安装：$existing；未覆盖，请先处理安装渠道冲突"
    fi
  fi
  npm install -g @openai/codex@latest
  prepare_nvim
  verify
  note '初始化结束；请打开新终端使配置生效。保留项请查看上方输出。'
}

main() {
  case "${1:---check}" in
    --check) load_environment; check ;;
    --apply) load_environment; apply ;;
    --verify) load_environment; verify ;;
    *) die '用法：bootstrap.sh [--check|--apply|--verify]' ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  trap 'printf "初始化失败（行 %s）。已完成操作保留；修复原因后可重新执行。\n" "$LINENO" >&2' ERR
  main "$@"
fi
