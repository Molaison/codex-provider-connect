# Codex Provider Connect

**一条命令接入 Provider；模型目录自动同步，不手工编辑 catalog。**

适用于原生 Windows、Linux、macOS、WSL。先安装官方 Codex。
Linux/macOS/WSL 还需要 Python 3.8+ 和 curl；Windows 安装器自动准备经过 SHA256 校验的用户私有 Python 3.13.7，不要求管理员或手装 Python。
保留官方 Codex，不修改其二进制，不覆盖现有配置，也不重启现有会话。

## 安装并连接

**原生 Windows：在 PowerShell 中执行一条命令。**

```powershell
irm https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.4/install.ps1 | iex
```

地址已知时，可以仍用一条命令，仅交互输入密钥：

```powershell
& ([scriptblock]::Create((irm 'https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.4/install.ps1'))) -Url 'https://your-provider.example/v1'
```

**Linux / macOS / WSL：**

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.4/install.sh | bash
```

按提示输入 Provider API 地址（通常以 `/v1` 结尾）和 API key；密钥隐藏输入。
也可在同一条命令里提供非敏感地址：

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.4/install.sh | bash -s -- --url https://your-provider.example/v1
```

这是执行远程安装脚本的命令。入口固定到版本标签（`CODEX_CONNECT_REF` 可换版本，`CODEX_CONNECT_BASE` 可换镜像）；需要审阅时，先下载该脚本及同版本的 `codex_provider.py`。

### 可选：解除官方客户端的 1 MiB 目录上限

官方 Codex 读取显式配置的目录（`model_catalog_url`）时限制 1 MiB，上游目录约 1.7 MiB，
超过会静默丢弃整个目录。加一个参数即可在安装时解除，不下载任何大文件：

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.4/install.sh | bash -s -- \
  --url https://your-provider.example/v1 \
  --patch-catalog-limit
```

`--patch-catalog-limit` 做的事只有一步：把现成的官方 `codex` 复制一份，按已验证的机器码
签名定位那个 `1 MiB` 立即数并改成 `8 MiB`，再用 `codex --version` 确认副本可执行。
原文件不动；签名不唯一或对不上的客户端版本会明确失败，不会盲改。

安装后单独管理：

```bash
codex-provider client patch                                    # 就地打补丁并启用
codex-provider client install <URL 或路径> --sha256 <校验和>   # 改用预编译补丁客户端
codex-provider client status                                   # 查看当前使用的客户端
codex-provider client remove                                   # 回到官方 Codex
```

实测的目录上限：补丁前 0.95 MiB 通过、1.5 MiB 起丢弃；补丁后 7.9 MiB 通过、
8.5 MiB 起丢弃（同一个本地代理、同一份载荷，只换客户端）。签名偏移与复现步骤见
`patches/README.md`。

补丁只影响 `model_catalog_url` 这条路径；通过本工具启动时用的是 `model_catalog_json`
本地文件，本来就不受 1 MiB 限制。官方 Codex 安装不被修改，补丁客户端单独存放，
`client remove` 随时回退。

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
- 自动修正 DeepSeek / ChatGPT Web 目录中已知的旧 GPT-5 fallback 提示词，分别使用 DeepSeek 工作指令和简短 Web 问答指令。只匹配两种已确认的旧模板前缀；其他模型及上游已修正的模板保持原样。
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

v0.1.2 起在每次同步时修正已确认的旧模板，不要求用户编辑 catalog：

| 模型 | 自动调整 | 保留与限制 |
| --- | --- | --- |
| DeepSeek | 去掉 GPT-5 身份及写死的工具名，使用精简工作指令 | 保留当前能力字段；reasoning summary 与 effort 独立，不因 effort 不可调就关闭 summary |
| ChatGPT Web | 只保留简短问答指令，不再设定 Codex / coding-agent 身份、工作区或工具操作流程 | 定位为纯问答；不启用本机工具、不引导切换 Full 模式 |

DeepSeek 保留编码代理的授权与验证要求；Web 提示词仅要求直接回答、结合对话/附件并如实说明不确定性。当前部署的 Web 后端另有问答转换层，剔除客户端的 Codex 系统/开发者模板、工具定义与执行记录、运行环境和技能注入，仅保留真实问答及附件。
不会凭模型名称扩大上下文窗口、打开图像、搜索、并行或其他工具能力。目录声明本身不是这些能力的实测证明。
这属于接入工具的客户端修正：不会修改 Provider 原始响应，也不会更新已经打开的会话。
升级时重新运行上方 v0.1.4 安装命令并通过 `codex-provider` 启动。用户显式覆盖基础提示词的配置仍可能优先。

同步时还会丢掉 `model_messages` 里四段用不到的文案：`confirmation_policies`、
`persistent_instructions`、`token_budget`、`guardian_v2`。它们占目录一半体积（实测约 790 KB），
缺失时客户端走内置默认行为。当前上游目录经此精简后为 1,035,777 字节（0.99 MiB），
已在 1 MiB 以下；HTTP 响应本身仍由 Provider 决定，所以 `model_catalog_url` 路径是否还需要补丁，
取决于 Provider 下发的原始体积。

## 发布维护

v0.1.4 增加 `--patch-catalog-limit`：安装时对现成的官方 `codex` 做一次定点字节替换，
把目录上限从 1 MiB 提到 8 MiB，并保留 `client install` 作为预编译客户端的备选。同版本还会在同步时
丢掉四段用不到的 `model_messages` 文案（约 790 KB），实测精简后的目录降到 0.99 MiB。
v0.1.4 同时修复目录只写 Provider 结果导致的模型缺失。`model_catalog_json` 是整体替换而非合并，
此前只写 Provider 目录会让 Codex 内置模型（`gpt-6-astra`、`gpt-6.1-sol`、`gpt-6-sol`、`gpt-6-luna`、
`gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna`、`gpt-daybreak-*-latest`、`gpt-5.5`、`codex-auto-review`）
从选择器和元数据中消失；若 `config.toml` 里指定了这些模型，Codex 会退回 fallback 元数据并告警
`Model metadata ... not found`。现在同步时会用一个不可达 base_url 的临时 CODEX_HOME 读出内置目录，
按 slug 合并（Provider 条目优先），并在日志中分别报告 Provider、内置与可见条目数。
实测：Provider 19 条 + 内置 11 条 = 30 条，17 条 API 可见；空白客户端安装后内置模型与 Provider 模型同时可用。

同一版本新增可选的补丁客户端安装：`install.sh --client <URL|路径> --client-sha256 <校验和>`
或安装后运行 `codex-provider client install`，把 `model_catalog_url` 的 1 MiB 上限提到 8 MiB。
A/B 实测（同一上游 1.70 MiB 目录）：官方 0.160.0 得到 0 条模型，补丁客户端得到 29 条、17 条可见；
9 MiB 目录两者都拒绝，说明新上限真实生效。远程安装强制校验 SHA256，官方 Codex 不被改写，
`codex-provider client remove` 回到官方客户端。

v0.1.3 修复 `curl | bash` 场景的交互提示：此前询问 Provider 地址和密钥时使用
`open("/dev/tty", "r+")`，该缓冲读写对象在终端上会触发
`io.UnsupportedOperation: File or stream is not seekable.`，安装脚本在提示阶段中止。
现在改用独立的读/写句柄；没有可用控制终端（例如非交互环境）时给出明确提示，
让用户改用 `CODEX_PROVIDER_URL` / `CODEX_PROVIDER_API_KEY` 或安装后单独运行
`codex-provider configure`，不再抛底层异常。


v0.1.2 将 Web fallback 收敛为简短纯问答指令。服务端已补齐 Windows 缺失的问答转换，并按原生 `content_item_kinds` 清理 AGENTS/环境/技能注入；不会按关键词删除真实提问。Linux、Windows 各两轮真实问答共 4/4 完成，正确保留前轮标记、计算结果及用户引用的 `Codex` / `AGENTS.md`，无本机工具提示或 Full 引导。DeepSeek 编码代理行为不变。


v0.1.1：DeepSeek 新提示词的真实 function call/result 两轮完成（4.025s + 3.348s）；空白 CODEX_HOME 下通过新版入口自动同步、官方 Codex 执行本机 shell 并返回标记，exit 0（9.934s）。3 个定向回归用例覆盖两处 prompt 来源、别名、重复同步和无关模型/能力保留。

2026-10-01 后续服务恢复：原 Windows Web 后台重新启动，Linux 账号池的卡住页面已恢复。公网原 Web key + 官方 Codex 问答完成（16.61s），账号池同一会话两轮上下文续接完成（17.753s、7.935s）。生产 Provider 现下发 browser-only 提示词并关闭本机 shell/patch 声明，接入工具自动保留这些已修正元数据。

**当前自动 Web 模式明确不支持本机工具，不是提示词可以开启的能力。** 本项目明确只保留纯问答，不计划启用 Full、手动工具确认或本机工具通道。此前 tunnel unavailable/session_account_unreachable 是已恢复服务的历史故障；底层模型版本、图像、搜索及结构化输出未在本次逐项验收。

v0.1.0 的真实空白配置验收（安装器与平台启动机制在 v0.1.1 未改变）：

| 环境 | 官方 Codex | Provider 条目 / 原生菜单可见条目 |
| --- | --- | --- |
| Linux | 0.158.0 | 18 / 16 |
| 原生 Windows PowerShell 5.1 | 全新 npm 安装 0.159.2 | 19 / 17 |

两端都在原生 model/list 中显示了 DeepSeek，Windows 同时显示 gpt-6.1-sol。数量来自各次 Provider 返回值，并非固定名单；隐藏条目保留但不强行展示。已验证启动自动刷新、不覆盖现有 Codex 配置，以及错误密钥不覆盖已保存连接。Windows 从 GitHub 安装并实际使用私有 Python 和原生 npm Codex，非 WSL 模拟。macOS 共用 POSIX 入口，尚未实机验收。

版本号同时位于 `install.sh`、`install.ps1` 和 `codex_provider.py`。更新时先修改版本并提交，再运行 `just release 0.1.3`。
标签会固化入口脚本自带的默认版本；两个安装器在下载 `codex_provider.py` 后校验该文件里的 `VERSION` 与入口版本一致，不一致就中止而不是静默装成旧版本（`CODEX_CONNECT_REF=main` 时跳过该校验）。
维护者可用 `CODEX_CONNECT_REF=main` 验收 GitHub 主分支入口；默认用户入口固定在发布标签。
验收应从空白 HOME/CODEX_HOME 出发，用真实 Provider 和原生 `app-server model/list` 检查菜单，而不只检查下载成功。
