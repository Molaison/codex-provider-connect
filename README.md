<h1 align="center">Codex Provider Connect</h1>

<p align="center">
  <strong>让 Codex 自动读取你的 Provider 模型目录。</strong><br>
  一次连接，启动时同步模型；保留原版 Codex、现有配置和已打开的会话。
</p>

<p align="center">
  <a href="https://github.com/Molaison/codex-provider-connect/stargazers"><img src="https://img.shields.io/github/stars/Molaison/codex-provider-connect" alt="GitHub stars"></a>
  <a href="https://github.com/Molaison/codex-provider-connect"><img src="https://img.shields.io/badge/platforms-Windows%20%7C%20Linux%20%7C%20macOS%20%7C%20WSL-4C6EF5" alt="Windows Linux macOS WSL"></a>
  <a href="#安装"><img src="https://img.shields.io/badge/install-v0.1.5-green" alt="Installer v0.1.5"></a>
</p>

<p align="center">
  <a href="#安装">安装</a> ·
  <a href="#日常使用">日常使用</a> ·
  <a href="#高级功能">高级功能</a> ·
  <a href="#常见问题">常见问题</a>
</p>

---

## 它能解决什么问题？

不必手工维护 Codex 的模型 catalog。**Codex Provider Connect** 每次启动前读取 Provider 提供的 Codex 模型目录，将其与 Codex 内置模型合并，再启动官方客户端。

| 能力 | 行为 |
| --- | --- |
| **自动同步模型** | 启动时重新获取 Provider 目录；在 Codex 的 `/model` 中选择已公开的模型。 |
| **复用现有 Provider** | 可直接读取 `config.toml` 中已有的 `model_providers.<name>`，沿用其地址和认证方式。 |
| **不侵入现有安装** | 默认只生成本工具的启动器和私有配置；原版 Codex 二进制与现有 `config.toml` 不变。 |
| **保留内置模型** | Provider 模型与 Codex 内置模型按 ID 合并，不因自定义目录而让内置选项消失。 |
| **可选目录限制补丁** | 针对另行使用 `model_catalog_url` 的场景，在单独副本上调整目录大小上限，可撤销。 |

**支持的平台：** 原生 Windows（64 位）、Linux、macOS、WSL。需要先安装[官方 Codex](https://github.com/openai/codex)。Linux/macOS/WSL 另需 Python 3.8+ 和 `curl`；Windows 安装器会在当前用户目录准备经 SHA256 校验的 Python 运行时。macOS 使用同一 POSIX 安装路径，尚无项目记录中的实机验收。

## 安装

安装入口固定在仓库的 **v0.1.5** 标签。按提示输入 Provider API 地址（通常以 `/v1` 结尾）与 API key；密钥通过隐藏输入读取。

**Windows · PowerShell**

```powershell
irm https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.5/install.ps1 | iex
```

**Linux / macOS / WSL · Terminal**

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.5/install.sh | bash
```

> 以上命令会执行下载的安装脚本。希望先审核代码时，请查看 [install.ps1](install.ps1)、[install.sh](install.sh) 与 [codex_provider.py](codex_provider.py)。无需管理员权限；安装不会重启已经运行的 Codex 会话。

已经知道地址时，可跳过地址输入：

```bash
curl -fsSL https://raw.githubusercontent.com/Molaison/codex-provider-connect/v0.1.5/install.sh \
  | bash -s -- --url https://your-provider.example/v1
```

**Linux / macOS / WSL** 的安装器还支持 `--provider <名称>` 复用 Codex 已有 Provider，或使用 `--reconfigure` 重新输入连接。Windows 可在安装完成后通过已安装的 `codex-provider.cmd` 配置；重复安装会优先沿用已保存的连接信息。

## 日常使用

**使用本工具的入口启动 Codex**，才会在每次新会话开始前刷新模型目录；原本的 `codex` 命令照常工作，但不会执行本工具的同步。

Linux / macOS / WSL：

```bash
~/.local/bin/codex-provider
```

Windows PowerShell：

```powershell
& "$env:USERPROFILE\.local\bin\codex-provider.cmd"
```

常用命令（Linux / macOS / WSL；如果 `~/.local/bin` 已在 `PATH` 中可省略前缀）：

```bash
codex-provider sync                              # 只更新目录，不进入会话
codex-provider resume                            # 继续原有会话
codex-provider -m DeepSeek-V4.1-Flash             # Codex 参数正常透传
codex-provider configure --provider my-provider  # 复用已有的 Codex Provider
codex-provider configure --url https://your-provider.example/v1
```

模型目录需要返回 **Codex 格式** `{"models": [...]}`；只有标准 OpenAI `{"data": [...]}` 的 Provider 不满足该接口。同步失败会报告错误，不会静默使用旧目录。后台会保留 Provider 声明的模型 ID 和能力字段，也不会擅自赋予模型未提供的能力。

## 高级功能

### 独立管理目录上限补丁（可选）

官方 Codex 的 `model_catalog_url` 路径存在 1 MiB 目录大小限制。本工具启动时采用本地 `model_catalog_json`，通常无需安装补丁。只有其他流程确实依赖超大 `model_catalog_url` 时，才考虑：

```bash
codex-provider client patch   # 在已验证的 Codex 副本中调整上限
codex-provider client status  # 查看当前使用的客户端
codex-provider client remove  # 恢复使用官方客户端
```

补丁使用版本/架构对应的机器码签名；不匹配会失败，原始官方二进制不受影响。详见 [补丁支持说明](patches/README.md) 和 [技术边界与历史记录](docs/technical-notes.md)。

### 凭据与配置

- 默认存储位置：`$CODEX_HOME/provider-connect/`（通常为 `~/.codex/provider-connect/`）。
- 密钥以**本机受限明文**保存，并非系统钥匙串。POSIX 文件权限为 `0600`、目录为 `0700`；Windows 使用当前用户私有 ACL。不要同步或上传此目录。
- 支持 `CODEX_PROVIDER_URL`、`CODEX_PROVIDER_API_KEY` 和 `CODEX_BINARY`。自动化环境请从秘密存储提供 key，避免写进命令历史或仓库。
- 部分已知旧版 DeepSeek / ChatGPT Web 模板可在同步时被定向修正；不会因为模型名称而开启搜索、图像、本机工具等未经验证的能力。具体规则与限制见 [技术记录](docs/technical-notes.md)。

## 常见问题

| 现象 | 建议检查 |
| --- | --- |
| `/model` 没有 Provider 模型 | 是否通过 `codex-provider` 启动；运行 `codex-provider sync` 并重新打开会话。 |
| 连接失败或 `401/403` | 核对 Provider URL、认证方式与 key；认证拒绝不会被当作临时故障重试。 |
| Provider 返回了列表但不能使用 | 确认响应为 Codex 的 `models` 结构，并与当前 Codex 客户端版本兼容。 |
| 目录大小补丁失败 | 该 Codex 版本/架构可能没有已验证的签名；可直接继续使用默认的本地目录方式。 |

完整卸载路径、版本兼容、目录合并行为与过去的验收记录均保留在 [技术边界与历史记录](docs/technical-notes.md)。反馈问题请使用 [GitHub Issues](https://github.com/Molaison/codex-provider-connect/issues)，附平台、Codex 版本和脱敏报错。
