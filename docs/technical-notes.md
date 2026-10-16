# 技术边界与版本记录

本页保留 README 精简前的操作细节、限制说明、卸载步骤和历史验收记录。

## v0.1.7：原生 codex 接入（2026-10-16）

当前安装入口配置原生 `codex`，不再安装 `codex-provider` 或 `codex-web` 日常入口。固定下载官方未修改的 0.162.1，核验 npm SHA512 和客户端版本；`~/.local/bin/codex` 直接指向官方二进制。维护助手和恢复状态留在私有目录，不参与每次启动。

目录改为维护者直接管理的 `model_catalog.json`，安装时通过 `model_catalog_json` 写入原生配置，不从上游同步元数据。当前包有 21 条记录，其中原生菜单可见 17 项，包含 8 项 Web。目录保留隐藏项；只读工具实测采用 GPT-6 tools temporary，不代表逐一验收全部模型。

安装器用原生 `config/read`、带版本条件的 `config/batchWrite` 修改默认 provider/model、目录和所需功能设置。修改前备份配置，保留旧 provider、项目、认证和历史。目录与凭据使用不可变的分代路径，旧会话仍可引用旧文件。自有损坏目录先备份并恢复，使官方配置接口能够启动；不覆盖无关目录文件。

已有 server 时，通过其原生控制 socket 检查任务。忙碌或状态未知时不重启；空闲并获确认后执行官方 `codex app-server daemon restart`，再确认新 server 身份、配置和目录。无交互时需显式 `--restart-if-idle`。确认后再次检查任务，但检查与官方 restart 并非原子操作，协调期间仍应避免另起任务。写入配置不能替代此重载；同一模型 ID 的元数据变更也必须重载。新方案不加 `--no-daemon`、不在日常命令中覆盖 provider。

`GET /models` 仅预检网络、key 和所选模型权限，接受标准模型列表，不将响应变成 catalog。不关闭 TLS，不静默改代理或出口。随后通过已保存的原生配置执行随机文件读取，要求命令成功、文件内容完整匹配、原生回合成功和进程 exit 0，才报告 `READY`。`--skip-check` 返回 2 / `NOT_VERIFIED`。

更新或修复重跑 README 的同一安装器并加 `--repair`；换连接加 `--reconfigure`。未完成自检只恢复原 owner，不新投；终态后明确修复可新测。前台最多等待 10 分钟，超时保留运行 owner。脱敏结果为 `provider-connect/native-installation.json`，原始事件与凭据不应上传。旧 Python API 继续保留原合同，以下旧入口说明只适用于历史调用方。

TY 与 h100 的新原生入口已在隔离 HOME 完成真实工具验收；h100 包含入口和目录损坏后的同一 HOME 修复。ty3 的全新 HOME 首次下载、已有 daemon 的忙碌保护、空闲确认重启和普通 TUI 实测均通过；同 ID 元数据成功重载，普通 TUI 连接同一新 daemon 完成真实读取，80.21 秒。新方案证据为项目 rev24 的 runs/49 与 runs/51，不能用下方旧独立入口结果代替。macOS、Windows 未做本轮实机验收，Windows 常驻 server 重载未覆盖。

**三台真实用户 HOME 已全部返回 `READY` / exit 0。** TY 90.92 秒、ty3 87.69 秒、h100 139.25 秒；均加载 17 项可见模型、其中 8 项 Web，并以 GPT-6 tools temporary 完成真实只读工具调用。新登录 shell 的 `codex` 均解析到官方 0.162.1；h100 实际使用的交互 zsh 也通过。正式安装与新终端证据为项目 rev24 的 runs/53、59。

ty3 首次正式安装曾因官方技能/记忆说明位于 developer 权限包之前而返回 `UPSTREAM_COMPAT`，原失败收据继续保留。服务端最小修复经用户授权、96 项定向测试及真实请求离线权限对照后，排空双 Full 并顺序上线完整 r6 CLI/helper。修复只接受已观察到的完整官方前缀，仍要求完整、唯一的权限包，保持 read-only / network restricted；未禁用用户技能或记忆。原安装在失败终态后用同一入口 `--repair` 通过，不重放失败回合。

主机特定的代理修复不属于安装器默认行为：TY 获准仅将 API 域名加入 `NO_PROXY`；h100 将旧入口已有的内网 IP 直连延续到实际加载的代理配置，保留其余代理设置。h100 使用现有未加密 LAN HTTP endpoint，不能将它作为公网接入方案。

## v0.1.6 历史候选：独立入口方案（已被 v0.1.7 替代，未发布）

安装器现在调用 `setup`：无 Codex 时从官方 npm registry 下载固定平台包 0.162.1，核对发布 SHA512 后解包并验证版本，再配置 endpoint/key、同步目录和执行真实只读工具自检。不修改官方二进制，不依赖 npm，不使用可选目录补丁。`CODEX_BINARY` 或用户原有自定义客户端仍优先；本工具下载的官方副本位于私有 `official/` 下。

只有命令执行成功、读取随机文件的内容匹配且原生回合终态成功，才返回 0 和 `READY`。`--skip-check` 返回 2，表示尚未验收。自检 owner、原生事件和终态保存在 `checks/attempt-*/`；前台最多等 10 分钟，超时不杀回合，后续 `doctor --check` 恢复同一 owner。重复 setup 默认复用同连接的终态证据，地址、key、路由、客户端或模型变化不能复用旧成功。

`doctor` 默认只核对客户端、连接和最新目录，不调用模型；JSON 输出只含脱敏诊断。`repair` 会修复本工具的官方副本、同步目录并验证一次真实工具调用；旧回合未结束时只恢复，终止后才新建一次。替换损坏的工具自有官方安装前保留 `.unusable-*` 备份；自定义/显式指定客户端不自动覆盖。`doctor --check --retry-check` 也是显式新测入口。

新入口自动加 `--no-daemon`，并传入本次 provider 和本地目录，防止官方 TUI 发现同一 HOME 中已有的常驻 server 后误用其旧连接；显式传入该选项时不重复添加。不会停止或重配旧 server，也不自动迁移其活跃会话。ty3 实测同一 HOME 中旧官方 server 常驻时，新入口普通 TUI 完成真实只读工具回合（50.46 秒），新菜单包含八项 Web、排除旧 sentinel；回合结束后旧进程仍在，原生 Unix WebSocket 的旧菜单不变。

这次共存验收原收据的字节级配置断言失败：安装器未改文件，但官方 TUI 追加了 `tui.screen_reader_detection_done` 和 `tui.model_availability_nux`。接受补充证据保留这个原始失败，并确认原 provider/model/catalog/endpoint 配置完整保留；没有重投模型回合。验收脚本已将该条件改为只允许原配置之后出现这两类原生首次提示状态。

三机真实验收均使用官方未修改 0.162.1、只读沙箱和禁止审批。TY 全新 HOME 安装通过（76.09 秒，显式复用已验官方二进制）；ty3 全新 HOME、PATH 无 Codex，首次下载官方包并通过（85.74 秒）；h100 对原失败安装运行 `repair` 后通过（48.8 秒）。三机原生菜单均有八项 Web，实际模型回合使用 GPT-6 tools temporary，没有逐一调用全部八项。日常 `codex-web` 已同步最终本地候选，官方二进制未替换。

首次工具回合曾被上游拒绝：`missing network access in trusted Codex environment context`。官方把网络状态放在独立 developer 权限块，上游原先仅解析 user 环境块。用户随后授权修复 ywl 双 Full：保持可信来源和权限绑定，兼容独立块及官方打包 developer wrapper；在 HTTP 和 browser 回合排空后上线，未扩大只读沙箱权限。另修复长提示词折叠后的网页发送绑定：发送时附加独立随机回执，恢复只接管已发送回合，不重发。发布必须同时构建 CLI 和实际执行的 `browser-helper.cjs`；曾遗漏后者的中间包已被完整 r5 bundle 替代。

ty3 的一次后续新安装中，真实命令已读出 36 位随机串，但网页回答只复制了前 32 位；原生结果与网页一致，安装器严格拒绝成功。自检随后保留相同 18 字节随机性，改成 `CPC-12hex-12hex-12hex-END` 并要求完整复制；仍逐字核对全部内容。增加 `OUTPUT_MISMATCH` 诊断和定向测试，不自动重投、不接受部分匹配。上述 ty3 的 85.74 秒通过结果来自这份最终候选。

本轮没有 v0.1.6 的 Windows/macOS 实机证据。此前已发布的 v0.1.5 要求预装 Codex，且没有新的真实工具验收与修复合同。v0.1.6 当时未获 Git 发布授权，未发布；随后用户要求融入原生入口，改由 v0.1.7 交付，不提供 v0.1.6 标签安装链接。

## v0.1.6 及更早版本的工作方式和边界

- 请求 `BASE_URL/models?client_version=已安装的Codex版本`，使用该 Provider 的 Bearer key。
- Provider 必须提供非空的 Codex 格式 `{"models":[...]}`，而不只是 OpenAI 的 `data/id` 列表。
- 完整保留服务器的模型 ID、能力、上下文窗口、可见性和隐藏条目；不新增模型或扩大密钥权限。
- 自动修正 DeepSeek / ChatGPT Web 目录中已知的旧 GPT-5 fallback 提示词，分别使用 DeepSeek 工作指令和简短 Web 问答指令。只匹配两种已确认的旧模板前缀；其他模型及上游已修正的模板保持原样。
- 自动生成本地 catalog，再用命令行覆盖参数交给 Codex；**不是修改原版 Codex 的原生发现机制**。
- 安装器不改写现有 `config.toml`、`auth.json`、`models_cache.json`；官方 TUI 可以记录自身状态或用户设置。用户后置传入的 Codex 参数仍由 Codex 处理。
- 获取失败会明确退出；只对连接错误和临时 HTTP 错误做最多三次尝试，不静默退回旧目录。401/403 不重试。
- Windows 旧入口支持官方原生可执行程序或全局 npm 安装；npm 场景直接调用官方 Node 入口，避免 cmd.exe 改写 TOML 参数。安装器私有 Python 为 x64，ARM 设备需要系统的 x64 兼容能力；新候选会按该运行时架构准备官方平台包。其他 Codex 版本需要兼容 Provider 返回的元数据。

凭据和生成目录位于 `$CODEX_HOME/provider-connect/`，默认是 `~/.codex/provider-connect/`。
POSIX 目录权限 `0700`、文件权限 `0600`；Windows 用当前用户 SID 设置私有目录 ACL。密钥通过子进程环境传递，不放进进程参数。
密钥以本机受限明文文件保存，并非系统钥匙串；不要上传该目录。

自动化可用 `CODEX_PROVIDER_API_KEY` 和 `CODEX_PROVIDER_URL`，密钥应来自秘密存储，不要写进 shell 历史、Git 或 CI 日志。
`CODEX_BINARY` 可以指定实际的官方 Codex 可执行文件。

## 恢复与卸载

### 当前原生接入：先恢复引用，再移走文件

不能直接删除 `provider-connect/`：当前原生配置还引用其中的目录和凭据文件。

1. 等待现有任务结束。使用安装报告 `config_backup` 指向的安装前备份，恢复所需的 provider/model、目录和功能设置；若安装后有其他配置变更，只还原本工具改动的键，不整份覆盖新设置。
2. 需要恢复旧 `codex` 入口时，从私有 `backups/codex-entry-*` 中选取原入口；没有旧入口时才移走本工具的符号链接。
3. 使用官方 restart 让空闲 server 加载已恢复的配置。确认它不再引用本工具的目录或凭据后，将 `provider-connect/` 改名留作恢复备份。
4. 确认日常使用恢复，再删除这份备份，并移除 shell 中 `codex-provider-connect: official codex executable` 标记的 PATH 设置。不要删除其他 Codex 安装、认证或历史。

Windows 另有 `%LOCALAPPDATA%\codex-provider-connect` 下的私有 Python 和助手；同样先解除原生配置引用，再移走本工具拥有的文件。

### 历史独立入口

仅旧版本独立入口、且原生配置未引用私有目录时，可移走 `~/.local/bin/codex-provider` / `codex-web` 及其本工具拥有的状态。先保留恢复副本；不要套用此步骤卸载当前原生接入。

## 模型提示词与能力边界（旧问答部署的历史范围）

v0.1.2 起在每次同步时修正已确认的旧模板，不要求用户编辑 catalog：

| 模型 | 自动调整 | 保留与限制 |
| --- | --- | --- |
| DeepSeek | 去掉 GPT-5 身份及写死的工具名，使用精简工作指令 | 保留当前能力字段；reasoning summary 与 effort 独立，不因 effort 不可调就关闭 summary |
| ChatGPT Web | 只保留简短问答指令，不再设定 Codex / coding-agent 身份、工作区或工具操作流程 | 定位为纯问答；不启用本机工具、不引导切换 Full 模式 |

DeepSeek 保留编码代理的授权与验证要求；Web 旧模板修正仅要求直接回答、结合对话/附件并如实说明不确定性。2026-10-01 的 Web 问答后端另有转换层，剔除客户端的 Codex 系统/开发者模板、工具定义与执行记录、运行环境和技能注入，仅保留真实问答及附件。该历史部署不代表后续 Full/tools 模式的合同；上游已修正的工具模板不会被此规则替换。
不会凭模型名称扩大上下文窗口、打开图像、搜索、并行或其他工具能力。目录声明本身不是这些能力的实测证明。
这属于接入工具的客户端修正：不会修改 Provider 原始响应，也不会更新已经打开的会话。
用户显式覆盖基础提示词的配置仍可能优先。当前原生安装与修复命令见 README；本节的旧动态同步不用于 v0.1.7。

同步时还会丢掉 `model_messages` 里四段用不到的文案：`confirmation_policies`、
`persistent_instructions`、`token_budget`、`guardian_v2`。它们占目录一半体积（实测约 790 KB），
缺失时客户端走内置默认行为。当时的上游目录经此精简后为 1,035,777 字节（0.99 MiB），
已在 1 MiB 以下；HTTP 响应本身仍由 Provider 决定，所以 `model_catalog_url` 路径是否还需要补丁，
取决于 Provider 下发的原始体积。

## 发布维护

v0.1.5 让 `--patch-catalog-limit` 支持 npm 安装的 Codex（自动从 `bin/codex.js` 找到平台包里的原生二进制）以及 arm64（Apple Silicon / Linux arm64）；macOS 上补丁后会做 ad-hoc 重签名，否则系统会拒绝运行改动过的二进制。v0.1.4 增加 `--provider`：直接复用 `config.toml` 里已有的 provider，重复安装不再询问地址与密钥。同版本增加 `--patch-catalog-limit`：安装时对现成的官方 `codex` 做一次定点字节替换，
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

**2026-10-01 当时仅交付纯问答，不支持本机工具。** 后续用户已将范围扩展到 Full/tools；2026-10-16 的官方客户端工具验收见页首，历史问答结果只对应当时的部署。此前 tunnel unavailable/session_account_unreachable 是已恢复服务的历史故障；底层模型版本、图像、搜索及结构化输出未在该次逐项验收。

v0.1.0 的真实空白配置验收（安装器与平台启动机制在 v0.1.1 未改变）：

| 环境 | 官方 Codex | Provider 条目 / 原生菜单可见条目 |
| --- | --- | --- |
| Linux | 0.158.0 | 18 / 16 |
| 原生 Windows PowerShell 5.1 | 全新 npm 安装 0.159.2 | 19 / 17 |

两端都在原生 model/list 中显示了 DeepSeek，Windows 同时显示 gpt-6.1-sol。数量来自各次 Provider 返回值，并非固定名单；隐藏条目保留但不强行展示。已验证启动自动刷新、不覆盖现有 Codex 配置，以及错误密钥不覆盖已保存连接。Windows 从 GitHub 安装并实际使用私有 Python 和原生 npm Codex，非 WSL 模拟。macOS 共用 POSIX 入口，尚未实机验收。

版本号同时位于 `install.sh`、`install.ps1` 和 `codex_provider.py`。发布必须先获授权、完成真实空白客户端验收，再提交对应版本并使用 `just release <版本号>`。v0.1.7 已取得发布授权并完成上述 Linux 验收，使用同一发布入口交付。
标签会固化入口脚本自带的默认版本；两个安装器在下载 `codex_provider.py` 后校验该文件里的 `VERSION` 与入口版本一致，不一致就中止而不是静默装成旧版本（`CODEX_CONNECT_REF=main` 时跳过该校验）。
维护者可用 `CODEX_CONNECT_REF=main` 验收 GitHub 主分支入口；默认用户入口固定在发布标签。
修改维护目录后必须发布新版本，并给用户新版安装链接；旧标签的 `--repair` 只恢复旧目录。已有 server 仍需经过任务检查及确认重启，不能以写入文件代替更新完成。
验收应从空白 HOME/CODEX_HOME 出发，用真实 Provider 和原生 `app-server model/list` 检查菜单，并以一次真实只读工具回合完成验收；目录可见不能替代实际可用。
