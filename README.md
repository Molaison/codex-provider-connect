# Codex Provider Connect

**一条命令接入 Provider；模型目录自动同步，不手工编辑 catalog。**

适用于原生 Windows、Linux、macOS、WSL。先安装官方 Codex。
Linux/macOS/WSL 还需要 Python 3.8+ 和 curl；Windows 安装器自动准备经过 SHA256 校验的用户私有 Python 3.13.7，不要求管理员或手装 Python。
保留官方 Codex，不修改其二进制，不覆盖现有配置，也不重启现有会话。

## 安装并连接

**原生 Windows：在 PowerShell 中执行一条命令。**

```powershell
irm https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.0/install.ps1 | iex
```

**Linux / macOS / WSL：**

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.0/install.sh | bash
```

按提示输入 Provider API 地址（通常以 `/v1` 结尾）和 API key；密钥隐藏输入。
也可在同一条命令里提供非敏感地址：

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.0/install.sh | bash -s -- --url https://your-provider.example/v1
```

这是执行远程安装脚本的命令。入口固定到版本标签；需要审阅时，先下载该脚本及同版本的 `codex_provider.py`。

## 使用

Windows PowerShell：

```powershell
& "$env:USERPROFILE\.local\bin\codex-provider.cmd"
```

Linux / macOS / WSL：

```bash
~/.local/bin/codex-provider
```

每次启动先向 Provider 获取新目录，再启动官方 Codex。之后在 `/model` 中选择模型。
如果 `~/.local/bin` 已在 PATH 中，可以直接输入 `codex-provider`。

```bash
codex-provider -m DeepSeek-V4.1-Flash       # 参数继续交给官方 Codex
codex-provider resume                    # 续接原有会话
codex-provider sync                      # 仅同步，不启动会话
codex-provider configure --url https://your-provider.example/v1
codex-provider -- --help                 # 官方 Codex 的帮助
```

**以后通过 `codex-provider` 启动，而不是裸 `codex`。** 裸命令不会触发本工具的自动同步。
已经打开的会话不会被强制切换模型或刷新菜单；重新通过入口启动即可。

## 工作方式和边界

- 请求 `BASE_URL/models?client_version=已安装的Codex版本`，使用该 Provider 的 Bearer key。
- Provider 必须提供非空的 Codex 格式 `{"models":[...]}`，而不只是 OpenAI 的 `data/id` 列表。
- 完整保留服务器的模型 ID、能力、上下文窗口、可见性和隐藏条目。不硬编码模型名单，也不伪造能力。
- 自动生成本地 catalog，再用命令行覆盖参数交给 Codex；**不是修改原版 Codex 的原生发现机制**。
- 不改写现有 `config.toml`、`auth.json`、`models_cache.json`。用户后置传入的 Codex 参数仍由 Codex 处理。
- 获取失败会明确退出；只对连接错误和临时 HTTP 错误做最多三次尝试，不静默退回旧目录。401/403 不重试。
- Windows 支持官方原生可执行程序或全局 npm 安装；npm 场景直接调用官方 Node 入口，避免 cmd.exe 改写 TOML 参数。运行时为 x64，ARM 设备需要系统的 x64 兼容能力。其他 Codex 版本需要兼容 Provider 返回的元数据。

凭据和生成目录位于 `$CODEX_HOME/provider-connect/`，默认是 `~/.codex/provider-connect/`。
POSIX 目录权限 `0700`、文件权限 `0600`；Windows 用当前用户 SID 设置私有目录 ACL。密钥通过子进程环境传递，不放进进程参数。
密钥以本机受限明文文件保存，并非系统钥匙串；不要上传该目录。

自动化可用 `CODEX_PROVIDER_API_KEY` 和 `CODEX_PROVIDER_URL`，密钥应来自秘密存储，不要写进 shell 历史、Git 或 CI 日志。
`CODEX_BINARY` 可以指定实际的官方 Codex 可执行文件。

## 卸载

Windows PowerShell：

```powershell
Remove-Item "$env:USERPROFILE\.local\bin\codex-provider.cmd"
Remove-Item "$env:LOCALAPPDATA\codex-provider-connect" -Recurse
$CodexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "$env:USERPROFILE\.codex" }
Remove-Item "$CodexHome\provider-connect" -Recurse
```

Linux / macOS / WSL：

删除两个本工具拥有的位置即可；原有 Codex 配置和会话不受影响：

```bash
rm ~/.local/bin/codex-provider
rm -r "${CODEX_HOME:-$HOME/.codex}/provider-connect"
```

## 发布维护

版本号同时位于 `install.sh`、`install.ps1` 和 `codex_provider.py`。更新时先修改版本并提交，再运行 `just release 0.1.0`。
维护者可用 `CODEX_CONNECT_REF=main` 验收 GitHub 主分支入口；默认用户入口固定在发布标签。
验收应从空白 HOME/CODEX_HOME 出发，用真实 Provider 和原生 `app-server model/list` 检查菜单，而不只检查下载成功。
