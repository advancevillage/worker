# prompt
export PS1='%F{cyan}%n@%m%F{green} %~%f$ '

# ls color
export CLICOLOR=1
export LSCOLORS=ExGxFxdaCxDaDahbadeche

# language
export LANG=zh_CN.UTF-8

# proxy
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export NO_PROXY="softpart.cn,.softpart.cn"
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"
export no_proxy="$NO_PROXY"

# Homebrew
export HOMEBREW_BREW_GIT_REMOTE=https://mirrors.ustc.edu.cn/brew.git
export HOMEBREW_BOTTLE_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles
export HOMEBREW_API_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles/api
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

# Preserve order while avoiding duplicate PATH entries.
typeset -U path
if command -v go >/dev/null 2>&1; then
  _localhost_gopath="$(go env GOPATH)"
  for _localhost_go_root in "${(@s/:/)_localhost_gopath}"; do
    path+=("$_localhost_go_root/bin")
  done
  unset _localhost_gopath _localhost_go_root
fi
if command -v npm >/dev/null 2>&1; then
  _localhost_npm_prefix="$(npm prefix -g 2>/dev/null)"
  if [[ -n "$_localhost_npm_prefix" ]]; then
    path=("$_localhost_npm_prefix/bin" $path)
  fi
  unset _localhost_npm_prefix
fi
export PATH
