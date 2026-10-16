# Codex Provider Connect

**给一个 API 地址和 key，配置现有的 `codex`，并验证一次真实工具调用。** 使用官方原版客户端，不打补丁，不新增日常 CLI。

## 安装后直接用 `codex`

复制下面的 **v0.1.7** 安装命令，无需克隆仓库：

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.7/install.sh | bash -s -- --url https://your-provider.example/v1
```

将地址替换为维护者提供的 endpoint，按提示隐藏输入自己的 key。不要把 key 写进命令行。

安装器会准备固定版本的**官方 Codex 0.162.1**，检查地址和密钥权限，写入原生配置，再用只读工具读取随机文件并核对完整回答。无需先装 Codex、npm 或手动编辑 TOML。

**只有 `[READY]`、退出码 0 才表示真实自检通过。** 菜单能显示、网络可达或 `--skip-check` 都不算通过。首次安装通常需要下载时间和一次模型响应；前台自检最多等待 10 分钟。

安装成功后，打开新终端：

```bash
codex
```

在原生 `/model` 菜单选择模型；`codex resume` 等官方命令照常使用。`~/.local/bin/codex` 直接指向官方可执行文件，不是包了一层的启动器。当前终端尚未刷新 PATH 时，可直接运行 `~/.local/bin/codex`。

Linux/macOS/WSL 安装入口需要 Python 3.8+ 和 curl，无需管理员权限。目前新方案的实机证据来自 Linux；macOS、Windows 未完成本轮实机验收。Windows 入口为 `install.ps1`，已有 Windows server 的安全重载尚未覆盖。

## 已有 server：忙时保留，空闲确认后重启

官方 server 会保留启动时的目录和连接，单纯写配置不会刷新它。安装器发现需要重载时：

1. 检查已有 server 的任务；有任务或状态不能确认时，返回 `SERVER_BUSY`，不重启、不提交模型自检。
2. 空闲时询问一次；确认后执行官方 `codex app-server daemon restart`，再检查新 server 和模型菜单。
3. 完成真实工具自检后才报告 `READY`。已连接的终端可能需要重新连接。

不确认或非交互环境会返回 `SERVER_RESTART_REQUIRED`。自动化可在原安装命令后加 `--restart-if-idle`，表示明确允许**空闲时**重启；该参数不能跳过任务检查。

## 更新和修复：重跑同一安装器

重跑同一入口，加上 `--repair`：

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.7/install.sh | bash -s -- --repair
```

沿用已保存的 endpoint/key，修复本工具拥有的官方副本、`codex` 入口和模型目录，再执行一次真实自检。自检仍在进行时，只返回原回合状态，不重复提交。入口或私有助手损坏也用这一命令恢复。

换地址或 key 时：

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.7/install.sh | bash -s -- --repair --reconfigure
```

模型目录由维护者直接维护在安装包的 `model_catalog.json`，通过官方 `model_catalog_json` 加载。**不依赖上游同步元数据，也不在每次启动时联网刷新目录。** 新模型随维护者提供的新版本安装包交付；重跑旧版本只恢复该版本的目录，不会假装升级到最新目录。目录更新采用新文件路径；已有 server 必须完成上述重载，即使模型 ID 没变、只有能力或文案改变。

| 结果 | 下一步 |
| --- | --- |
| `READY` | 该次真实工具自检通过，直接运行 `codex`。 |
| `AUTH` | 同一安装命令加 `--reconfigure`，重新输入 key。 |
| `ACCESS` | 请维护者检查该 key 的模型权限；重装无效。 |
| `NETWORK` | 修正 endpoint、代理或证书后重跑；不要关闭 TLS 校验。 |
| `SERVER_BUSY` | 等任务结束后重跑；不必停止正在用的 server。 |
| `SERVER_RESTART_REQUIRED` | 重跑并确认空闲重启；自动化显式加 `--restart-if-idle`。 |
| `CHECK_PENDING` | 重跑同一安装命令查询原回合，不另开自检。 |
| `UPSTREAM_COMPAT` | 将脱敏报告交给维护者修复服务端；重装客户端无效，修复后再加 `--repair`。 |
| `OUTPUT_MISMATCH` / 其他真实调用失败 | 同一命令加 `--repair`；仍失败时将脱敏的 `native-installation.json` 给维护者。 |
| `NOT_VERIFIED` | 只配置、未验收。去掉 `--skip-check` 后重跑。 |

报告位于 `${CODEX_HOME:-$HOME/.codex}/provider-connect/native-installation.json`。不要上传整个配置目录、key 文件或原始日志。

## 维护者须知

- endpoint 需支持 Responses 和标准 `/models` 权限查询。`/models` 只用于检查网络、密钥和所选模型权限，不用它生成目录。
- 安装器修改原生 `config.toml` 中的默认 provider/model、目录路径和必要功能设置，并先保留配置备份；旧 provider、项目设置、`auth.json` 和历史记录保留。新连接的默认模型为 `chatgpt-web/gpt-6-tools-temp`，可用 `--model ID` 选择。
- 凭据、目录和恢复记录位于 `$CODEX_HOME/provider-connect/`，默认 `~/.codex/provider-connect/`。key 是受限明文文件，不是系统钥匙串；POSIX 目录 0700、文件 0600，原生 `auth.command` 读取对应凭据文件。旧连接引用的凭据不在更新时删除。
- 自动化通过秘密存储注入 `CODEX_PROVIDER_API_KEY`。不静默绕过环境代理；需要改出口时由用户显式调整目标域名的 `NO_PROXY`。
- 官方下载核验 npm 发布的 SHA512，并验证版本。显式 `CODEX_BINARY` 可指定兼容的官方原生二进制；默认不会从 PATH 沿用未知补丁版。
- 旧 Python 接口保留供原调用方使用；新安装不创建 `codex-provider` / `codex-web` 日常命令。历史合同、恢复和卸载见[技术记录](docs/technical-notes.md)。

Linux 三台真实用户 HOME 已完成安装及只读工具调用，新终端仍直接使用官方 `codex`；另以全新 HOME 验证首次下载、损坏修复和已有 server 重载。验收范围见[技术记录](docs/technical-notes.md)。
