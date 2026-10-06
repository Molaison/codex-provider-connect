# 客户端目录上限：安装时字节替换

官方 Codex 在读取**显式配置的目录**（`model_catalog_url`）时限制 1 MiB，超过就丢弃整份目录、
不报错。上游目录约 1.7 MiB，所以这条路径默认拿不到模型。

`codex-provider client patch`（安装脚本里的 `--patch-catalog-limit`）把现成的客户端复制一份，
就地把那个 `1 MiB` 立即数改成 `8 MiB`。不重新编译，不下载预编译产物，原文件不动。

## 定位方式

那段初始化代码在机器码里留下的形状，跨架构、跨打包方式都一致。锚点是源码里结构体布局产生的
固定偏移（`0x1ac0` 与 `0x648/0x650/0x658/0x660`）：

| 架构 | 形状 | 立即数 |
| --- | --- | --- |
| x86_64 | `movb [rbx+0x1ac0], 0` 之后紧跟 `(41) b8-bf imm32` | 32 位立即数 |
| aarch64 | 同一窗口里 `str [xN,#0x648/#0x650/#0x658/#0x660]` 夹着 `movz w?/x?, #imm16, lsl #16` | `imm16 << 16` |

官方 0.160.0 的四个构建都只有唯一命中：

| 客户端 | 架构 | 立即数偏移 | npm 路径 |
| --- | --- | --- | --- |
| standalone linux-x64 / `@openai/codex-linux-x64` | x86_64 ELF | `0x97ed784` | `vendor/x86_64-unknown-linux-musl/bin/codex` |
| `@openai/codex-darwin-x64` | x86_64 Mach-O | `0x8661d5f` | `vendor/x86_64-apple-darwin/bin/codex` |
| `@openai/codex-linux-arm64` | aarch64 ELF | `0x7bedef0` | `vendor/aarch64-unknown-linux-musl/bin/codex` |
| `@openai/codex-darwin-arm64` | aarch64 Mach-O | `0x72aad20` | `vendor/aarch64-apple-darwin/bin/codex` |

签名必须**唯一命中**。命中 0 处或多处、或立即数既不是 1 MiB 也不是已打过补丁的 8 MiB，
都直接报错退出，不做猜测性改写。0.157.1 这类没有该签名的版本会被拒绝。

## npm / Homebrew 安装

npm 装出来的 `codex` 是 JS 包装（`bin/codex.js`），真正的二进制在平台包里：

```
<node_modules>/@openai/codex-<平台>-<架构>/vendor/<目标三元组>/bin/codex
```

工具会按包装脚本的同一套规则（`POLICIES` 里的目标三元组映射）自动找到它，`codex-provider client status`
里同时记录包装路径（`entry`）和实际打补丁的二进制（`source`）。

macOS 的二进制带 `LC_CODE_SIGNATURE`，改完字节签名即失效、系统会拒绝运行，所以补丁后会自动执行
`codesign --force --sign - <文件>` 重新 ad-hoc 签名，再用 `--version` 确认副本能启动；任一步失败都会
放弃并保留原状。

## 实测

同一份本地代理载荷，只替换客户端二进制（x86_64，运行时验证）：

| 载荷 | 官方 0.160.0 | 补丁产物 |
| --- | --- | --- |
| 0.95 MiB | 1 条 | 1 条 |
| 1.50 MiB | 0 条 | 1 条 |
| 7.90 MiB | 0 条 | 1 条 |
| 8.50 MiB | 0 条 | 0 条 |

npm 打包的 linux-x64 二进制重跑同一张表，结果一致。arm64 与 macOS 目前是静态验证
（补丁后立即数确认为 8 MiB、指令流其余部分不变）；运行时验证需要在对应机器上跑一次。

## 复现

```bash
codex-provider client patch                                  # 自动解析 PATH 里的 codex
codex-provider client patch --source /opt/homebrew/lib/node_modules/@openai/codex/bin/codex.js
codex-provider client status                                 # 记录 entry / source / sha256 / 偏移
codex-provider client remove                                 # 回到官方 Codex
```

## 源码补丁（备选）

`codex-catalog-limit-8mib.patch` 是同一处上限的源码改法
（`codex-rs/model-provider/src/models_endpoint.rs`，`1024 * 1024` → `8 * 1024 * 1024`），
用于自建客户端或需要完全可审计链路时：

```bash
codex-provider client install <预编译客户端 URL 或本地路径> --sha256 <64 位校验和>
```

两条路互斥：`--client` 装预编译产物，`--patch-catalog-limit` 就地改现成的客户端二进制。
