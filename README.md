# Codex Provider Connect

**一条命令接入 Provider；模型目录自动同步，不手工编辑 catalog。**

适用于原生 Windows、Linux、macOS、WSL。先安装官方 Codex。
Linux/macOS/WSL 还需要 Python 3.8+ 和 curl；Windows 安装器自动准备经过 SHA256 校验的用户私有 Python 3.13.7，不要求管理员或手装 Python。
保留官方 Codex，不修改其二进制，不覆盖现有配置，也不重启现有会话。

## 安装并连接

**原生 Windows：在 PowerShell 中执行一条命令。**

```powershell
irm https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.1/install.ps1 | iex
```

地址已知时，可以仍用一条命令，仅交互输入密钥：

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.1/install.ps1'))) -Url 'https://your-provider.example/v1'
```

**Linux / macOS / WSL：**

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.1/install.sh | bash
```

按提示输入 Provider API 地址（通常以 `/v1` 结尾）和 API key；密钥隐藏输入。
也可在同一条命令里提供非敏感地址：

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.1/install.sh | bash -s -- --url https://your-provider.example/v1
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
- 完整保留服务器的模型 ID、能力、上下文窗口、可见性和隐藏条目；不新增模型或扩大密钥权限。
- 自动修正 DeepSeek / ChatGPT Web 目录中已知的旧 GPT-5 fallback 提示词，分别说明模型身份和 Web 桥接边界。只匹配两种已确认的旧模板前缀；其他模型及上游已修正的模板保持原样。
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

## 模型提示词与能力边界

v0.1.1 在每次同步时修正已确认的旧模板，不要求用户编辑 catalog：

| 模型 | 自动调整 | 保留与限制 |
| --- | --- | --- |
| DeepSeek | 去掉 GPT-5 身份及写死的工具名，使用精简工作指令 | 保留当前能力字段；reasoning summary 与 effort 独立，不因 effort 不可调就关闭 summary |
| ChatGPT Web | 不按 alias 推断底层版本；区分 Codex 本机工具与 Web 内置工具 | reasoning、verbosity、schema 可能由桥接转换，不承诺是原生 API 控件或严格 schema 保证 |

两类提示词均保留授权、沙箱、真实工具结果、无关修改保护及结果验证要求；不替代当前系统/开发者指令或项目指导。
不会凭模型名称扩大上下文窗口、打开图像、搜索、并行或其他工具能力。目录声明本身不是这些能力的实测证明。
这属于接入工具的客户端修正：不会修改 Provider 原始响应，也不会更新已经打开的会话。
升级时重新运行上方 v0.1.1 安装命令并通过 `codex-provider` 启动。用户显式覆盖基础提示词的配置仍可能优先。

## 发布维护

v0.1.1：DeepSeek 新提示词的真实 function call/result 两轮完成（4.025s + 3.348s）；空白 CODEX_HOME 下通过新版入口自动同步、官方 Codex 执行本机 shell 并返回标记，exit 0（9.934s）。3 个定向回归用例覆盖两处 prompt 来源、别名、重复同步和无关模型/能力保留。

本次 Web 验证保留两个运行障碍：旧 Windows 路由返回 tunnel unavailable；既有账号池先成功回答但未返回工具调用，随后指定 function 的请求返回 session_account_unreachable。**本版不宣称 Web 本机工具执行已通过**，不自动切账号、扩大权限或改变路由。底层模型版本、图像、搜索、并行及结构化输出未在本次逐项验收。

v0.1.0 的真实空白配置验收（安装器与平台启动机制在 v0.1.1 未改变）：

| 环境 | 官方 Codex | Provider 条目 / 原生菜单可见条目 |
| --- | --- | --- |
| Linux | 0.158.0 | 18 / 16 |
| 原生 Windows PowerShell 5.1 | 全新 npm 安装 0.159.2 | 19 / 17 |

两端都在原生 model/list 中显示了 DeepSeek，Windows 同时显示 gpt-6.1-sol。数量来自各次 Provider 返回值，并非固定名单；隐藏条目保留但不强行展示。已验证启动自动刷新、不覆盖现有 Codex 配置，以及错误密钥不覆盖已保存连接。Windows 从 GitHub 安装并实际使用私有 Python 和原生 npm Codex，非 WSL 模拟。macOS 共用 POSIX 入口，尚未实机验收。

版本号同时位于 `install.sh`、`install.ps1` 和 `codex_provider.py`。更新时先修改版本并提交，再运行 `just release 0.1.1`。
维护者可用 `CODEX_CONNECT_REF=main` 验收 GitHub 主分支入口；默认用户入口固定在发布标签。
验收应从空白 HOME/CODEX_HOME 出发，用真实 Provider 和原生 `app-server model/list` 检查菜单，而不只检查下载成功。
