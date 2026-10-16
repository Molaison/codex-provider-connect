# Codex Provider Connect

**默认复用已有 API 地址和 key，配置原生 `codex`，并验证一次真实工具调用。** 使用官方原版客户端，不打补丁，不新增日常 CLI。

## 安装后直接用 `codex`

使用这个**固定入口**，无需克隆仓库或填写版本号：

```bash
(set -o pipefail; curl --http1.1 -fsSL --retry 2 https://github.com/Molaison/codex-provider-connect/releases/latest/download/install.sh | bash)
```

默认沿用本工具保存的连接；首次接入时，自动读取现有 config.toml 的当前 provider，复用其 key、env_key 或 auth.command。没有可用连接才询问地址和 key，不再要求重复输入。命令式鉴权每次重新取 key，不使用过期缓存。

新用户也可显式加 --url 指定维护者提供的 endpoint。指定地址时，只复用同地址的凭据，绝不把旧服务的 key 发到另一地址。自动化显式提供的 CODEX_PROVIDER_API_KEY 优先；--reconfigure 强制重新输入。不要把 key 写进命令行。

入口始终选择最新正式发布版。每次安装的助手和目录都锁定在同一发布包，不混用不同版本；下载失败不会覆盖已有助手和目录。命令中的 `pipefail` 让入口下载失败也返回非零，避免空下载被误当成安装成功。

下载使用 HTTP/1.1，兼容 HTTP/2 流不稳定的代理；仍使用原代理和 TLS 校验。GitHub 下载需能访问 `github.com` 和 `release-assets.githubusercontent.com`。若原代理已停止，先恢复它或由用户明确允许这些域名直连，再重跑；安装器不会擅改代理。

安装器会准备固定版本的**官方 Codex 0.162.1**，检查地址和密钥权限，写入原生配置，再用只读工具读取随机文件并核对完整回答。无需先装 Codex、npm 或手动编辑 TOML。

**只有 `[READY]`、退出码 0 才表示真实自检通过。** 菜单能显示、网络可达或 `--skip-check` 都不算通过。首次安装通常需要下载时间和一次模型响应；前台自检最多等待 10 分钟。

安装成功后，打开新终端：

```bash
codex
```

在原生 `/model` 菜单选择模型；`codex resume` 等官方命令照常使用。`~/.local/bin/codex` 直接指向官方可执行文件，不是包了一层的启动器。当前终端尚未刷新 PATH 时，可直接运行 `~/.local/bin/codex`。

Linux/macOS/WSL 安装入口需要 Python 3.8+ 和 curl，无需管理员权限。目前新方案的实机证据来自 Linux；macOS、Windows 未完成本轮实机验收。Windows 使用对应的固定 [install.ps1 下载入口](https://github.com/Molaison/codex-provider-connect/releases/latest/download/install.ps1)，每次维护都重新下载；已有 Windows server 的安全重载尚未覆盖。

## 已有 server：忙时保留，空闲确认后重启

官方 server 会保留启动时的目录和连接，单纯写配置不会刷新它。安装器发现需要重载时：

1. 检查已有 server 的任务；有任务或状态不能确认时，返回 `SERVER_BUSY`，不重启、不提交模型自检。
2. 空闲时询问一次；确认后执行官方 `codex app-server daemon restart`，再检查新 server 和模型菜单。
3. 完成真实工具自检后才报告 `READY`。已连接的终端可能需要重新连接。

不确认或非交互环境会返回 `SERVER_RESTART_REQUIRED`。自动化可在原安装命令后加 `--restart-if-idle`，表示明确允许**空闲时**重启；该参数不能跳过任务检查。

## 更新和修复：重跑同一安装器

安装、更新模型和修复都重跑同一个入口，**不用改版本号，也不用加参数**：

```bash
(set -o pipefail; curl --http1.1 -fsSL --retry 2 https://github.com/Molaison/codex-provider-connect/releases/latest/download/install.sh | bash)
```

沿用已保存的 endpoint/key，取得最新正式发布包，修复本工具拥有的官方副本、`codex` 入口和模型目录。连接或目录变化时执行新的真实自检；失败终态会在这次重跑时重新自检，原失败记录保留。自检仍在进行时只返回原回合状态，不重复提交；结束后再重跑完成更新。入口或私有助手损坏也用这一命令恢复。

未变化且已通过的自检直接复用，避免重复花费。若要强制重测，可额外加 `--repair`；该参数仍不能重投尚未结束的回合。

换地址或 key 时：

```bash
(set -o pipefail; curl --http1.1 -fsSL --retry 2 https://github.com/Molaison/codex-provider-connect/releases/latest/download/install.sh | bash -s -- --reconfigure)
```

模型目录由维护者直接维护在安装包的 `model_catalog.json`，通过官方 `model_catalog_json` 加载。**不依赖上游同步元数据，也不在每次启动时联网刷新目录。** 维护者发布新版后，重跑上面的固定入口就能更新。目录更新采用新文件路径；已有 server 必须完成上述重载，即使模型 ID 没变、只有能力或文案改变。保留旧版安装器只用于回退，不要用旧本地脚本代替固定下载入口。

| 结果 | 下一步 |
| --- | --- |
| `READY` | 该次真实工具自检通过，直接运行 `codex`。 |
| `AUTH` | 同一安装命令加 `--reconfigure`，重新输入 key。 |
| `ACCESS` | 请维护者检查该 key 的模型权限；重装无效。 |
| `NETWORK` | 修正 endpoint、代理或证书后重跑；不要关闭 TLS 校验。 |
| `SERVER_BUSY` | 等任务结束后重跑；不必停止正在用的 server。 |
| `SERVER_RESTART_REQUIRED` | 重跑并确认空闲重启；自动化显式加 `--restart-if-idle`。 |
| `CHECK_PENDING` | 重跑同一安装命令查询原回合，不另开自检。 |
| `UPSTREAM_COMPAT` | 将脱敏报告交给维护者修复服务端；重装客户端无效，修复后重跑同一命令。 |
| `OUTPUT_MISMATCH` / 其他真实调用失败 | 重跑同一命令；仍失败时将脱敏的 `native-installation.json` 给维护者。 |
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
