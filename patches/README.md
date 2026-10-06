# 客户端目录上限：安装时字节替换

官方 Codex 在读取**显式配置的目录**（`model_catalog_url`）时限制 1 MiB，超过就丢弃整份目录、
不报错。上游目录约 1.7 MiB，所以这条路径默认拿不到模型。

`codex-provider client patch`（安装脚本里的 `--patch-catalog-limit`）把现成的官方 `codex`
复制一份，就地把那个 `1 MiB` 立即数改成 `8 MiB`。不重新编译，不下载预编译客户端，原文件不动。

## 定位方式

`MAX_MODEL_CATALOG_BYTES` 在机器码里是一条 `mov ecx, 0x100000` 立即数。它前后各 32 字节的上下文
在三个独立构建里逐字节一致，可以直接当签名用：

| 客户端 | 立即数偏移 | 前后文 |
| --- | --- | --- |
| 官方 0.160.0（stripped，289 MB） | `0x97ed784` | 一致 |
| collab-plaintext 调试版（1.38 GB） | `0x9796754` | 一致 |
| 8 MiB 重编译版（已打过） | `0x9796194` | 一致，值为 `0x800000` |

- 前 32 字节：`6804000048898b480600004c89bb50060000488dabc01a0000c683c01a000000`
- 操作码：`b9`
- 立即数：`00001000`（1 MiB）→ `00008000`（8 MiB）
- 后 32 字节：`488d935806000048899424500100004889835806000048898b600600000f1083`

签名必须**唯一命中**。命中 0 处或多处、或立即数既不是 `0x100000` 也不是已打过补丁的 `0x800000`，
都直接报错退出，不做猜测性改写。0.157.1 这类没有该签名的版本会被拒绝。

## 实测

同一份本地代理载荷，只替换客户端二进制：

| 载荷 | 官方 0.160.0 | `client patch` 产物 |
| --- | --- | --- |
| 0.50 MiB | 1 条 | 1 条 |
| 0.95 MiB | 1 条 | 1 条 |
| 1.50 MiB | 0 条 | 1 条 |
| 7.00 MiB | 0 条 | 1 条 |
| 7.90 MiB | 0 条 | 1 条 |
| 8.50 MiB | 0 条 | 0 条 |
| 9.00 MiB | 0 条 | 0 条 |

上限确实从 1 MiB 变成 8 MiB。

## 复现

```bash
codex-provider client patch --source /path/to/codex   # 复制、替换、--version 自检
codex-provider client status                          # 记录 sha256 / 来源 / 偏移
codex-provider client remove                          # 回到官方 Codex
```

## 源码补丁（备选）

`codex-catalog-limit-8mib.patch` 是同一处上限的源码改法
（`codex-rs/model-provider/src/models_endpoint.rs`，`1024 * 1024` → `8 * 1024 * 1024`），
用于自建客户端或需要完全可审计链路时：

```bash
codex-provider client install <预编译客户端 URL 或本地路径> --sha256 <64 位校验和>
```

两条路互斥：`--client` 装预编译产物，`--patch-catalog-limit` 就地改现成的官方二进制。
