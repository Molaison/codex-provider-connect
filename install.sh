#!/usr/bin/env bash
# codex-provider-connect: install the pinned launcher, then configure its connection.
set -euo pipefail

main() {
    local release="${CODEX_CONNECT_REF:-v0.1.3}"
    local base="https://raw.githubusercontent.com/Molaison/codex-provider-connect/${release}"
    local destination="${HOME}/.local/bin/codex-provider"
    local temporary
    for command in curl python3 codex; do
        if ! command -v "$command" >/dev/null 2>&1; then
            printf '缺少 %s；请先安装后重试。\n' "$command" >&2
            return 1
        fi
    done
    if [[ -e "$destination" ]] && ! grep -q 'codex-provider-connect' "$destination"; then
        printf '拒绝覆盖非本工具的文件：%s\n' "$destination" >&2
        return 1
    fi
    mkdir -p "${HOME}/.local/bin"
    temporary=$(mktemp "${HOME}/.local/bin/.codex-provider.XXXXXX")
    trap 'rm -f -- "${temporary:-}"' EXIT
    curl --fail --silent --show-error --location --retry 2 "${base}/codex_provider.py" -o "$temporary"
    # 入口脚本自带默认版本；若它指向的载荷不是同一版本，宁可失败也不要静默装旧版。
    if [[ "$release" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] \
       && ! grep -q "VERSION = \"${release#v}\"" "$temporary"; then
        printf '下载到的 codex_provider.py 与入口版本 %s 不一致；已中止，未覆盖 %s。\n' "$release" "$destination" >&2
        return 1
    fi
    chmod 755 "$temporary"
    mv -f -- "$temporary" "$destination"
    trap - EXIT
    "$destination" configure "$@"
    printf '\n启动命令：%s\n' "$destination"
    printf '官方 codex 保持原样；本工具不会重启已有会话。\n'
}

main "$@"
