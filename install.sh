#!/usr/bin/env bash
# codex-provider-connect: install the pinned launcher, then configure its connection.
#
# 可选参数（其余参数原样传给 codex-provider configure）：
#   --client <URL 或路径>       同时安装补丁客户端（例如移除 1 MiB 目录上限的 Codex）
#   --client-sha256 <校验和>    远程 --client 必填
# 环境变量：CODEX_CONNECT_REF(默认 v0.1.4) CODEX_CONNECT_BASE(默认 GitHub raw 地址)
set -euo pipefail

main() {
    local release="${CODEX_CONNECT_REF:-v0.1.4}"
    local base="${CODEX_CONNECT_BASE:-https://raw.githubusercontent.com/Molaison/codex-provider-connect/${release}}"
    local destination="${HOME}/.local/bin/codex-provider"
    local temporary
    local client_source="" client_sha256=""
    local -a passthrough=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --client)
                client_source="${2:-}"
                [[ -n "$client_source" ]] || { printf '--client 需要一个 URL 或路径。\n' >&2; return 1; }
                shift 2 ;;
            --client-sha256)
                client_sha256="${2:-}"
                [[ -n "$client_sha256" ]] || { printf '--client-sha256 需要一个校验和。\n' >&2; return 1; }
                shift 2 ;;
            *)
                passthrough+=("$1")
                shift ;;
        esac
    done
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
    # 可选: 安装补丁客户端(移除 1 MiB 目录上限), 官方 Codex 不改动。
    if [[ -n "$client_source" ]]; then
        if [[ -n "$client_sha256" ]]; then
            "$destination" client install "$client_source" --sha256 "$client_sha256" --force
        else
            "$destination" client install "$client_source" --force
        fi
    fi
    "$destination" configure ${passthrough[@]+"${passthrough[@]}"}
    printf '\n启动命令：%s\n' "$destination"
    printf '官方 codex 保持原样；本工具不会重启已有会话。\n'
}

main "$@"
