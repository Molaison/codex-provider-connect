#!/usr/bin/env bash
# Published at releases/latest/download/install.sh; all payloads stay on one release.
# Configure the official codex command. The maintenance helper is not a daily CLI.
set -euo pipefail

main() {
    local release="${CODEX_CONNECT_REF:-v0.1.8}"
    local base="https://github.com/Molaison/codex-provider-connect/releases/download/${release}"
    # Preserve explicit ref overrides, including older releases without assets.
    if [[ -n "${CODEX_CONNECT_REF:-}" ]]; then
        base="https://raw.githubusercontent.com/Molaison/codex-provider-connect/${release}"
    fi
    base="${CODEX_CONNECT_BASE:-$base}"
    local root="${CODEX_HOME:-${HOME}/.codex}/provider-connect"
    local destination="${root}/codex_provider.py"
    local temporary damaged_helper=false
    for command in curl python3; do
        if ! command -v "$command" >/dev/null 2>&1; then
            printf '缺少 %s；请安装后重跑同一命令。\n' "$command" >&2
            return 1
        fi
    done
    for argument in "$@"; do
        case "$argument" in
            --client|--client-sha256|--patch-catalog-limit)
                printf '%s 不属于原生接入；此安装器不修改 Codex 二进制。\n' "$argument" >&2
                return 1 ;;
        esac
    done
    if [[ -e "$destination" ]] && ! grep -q 'codex-provider-connect' "$destination"; then
        if [[ ! -L "$destination" ]] && python3 -c 'import json,sys; assert json.load(open(sys.argv[1])).get("integration") == "native"' "$root/connection.json" 2>/dev/null; then
            damaged_helper=true
        else
            printf '拒绝覆盖无关文件：%s\n' "$destination" >&2
            return 1
        fi
    fi
    mkdir -p "$root"
    chmod 700 "$root"
    temporary=$(mktemp -d "${root}/.installer.XXXXXX")
    trap 'rm -rf -- "${temporary:-}"' EXIT
    printf '正在安装、更新或修复 %s；沿用已保存的连接。\n' "$release" >&2
    curl --fail --silent --show-error --location --retry 2 "${base}/codex_provider.py" -o "$temporary/codex_provider.py"
    curl --fail --silent --show-error --location --retry 2 "${base}/model_catalog.json" -o "$temporary/model_catalog.json"
    if [[ "$release" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] \
       && ! grep -q "VERSION = \"${release#v}\"" "$temporary/codex_provider.py"; then
        printf '下载的安装助手与 %s 不一致；未覆盖现有文件。\n' "$release" >&2
        return 1
    fi
    python3 -c 'import json,sys; x=json.load(open(sys.argv[1])); assert isinstance(x.get("models"),list) and x["models"], "Invalid model catalog"' "$temporary/model_catalog.json"
    chmod 600 "$temporary/codex_provider.py" "$temporary/model_catalog.json"
    if $damaged_helper; then
        local backup
        mkdir -p "$root/backups"
        chmod 700 "$root/backups"
        backup=$(mktemp "$root/backups/damaged-helper.XXXXXX")
        cp -- "$destination" "$backup"
        chmod 600 "$backup"
    fi
    mv -f -- "$temporary/model_catalog.json" "$root/model_catalog.json"
    mv -f -- "$temporary/codex_provider.py" "$destination"
    rmdir "$temporary"
    trap - EXIT
    python3 "$destination" _native-setup "$@"
    printf '\n[READY] 原生配置、模型菜单和真实只读工具自检通过。\n'
    if [[ "$(command -v codex || true)" == "${HOME}/.local/bin/codex" ]]; then
        printf '以后直接运行：codex\n'
    else
        printf '启动：%s/.local/bin/codex\n' "$HOME"
        printf '若 codex 指向其他版本，请将 ~/.local/bin 放到 PATH 前面并运行 hash -r。\n'
    fi
    printf '安装、更新或修复：重跑同一固定下载命令；更换 key 加 --reconfigure。\n'
    printf '已通过的自检会复用；需要强制重测时加 --repair。\n'
    printf '已有 server 有任务时不重启；需要更新时，空闲并确认后才调用官方重启命令。\n'
}

main "$@"
