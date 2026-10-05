# 客户端目录上限补丁

官方 Codex 0.160.0 在读取 **显式配置的目录**（`model_catalog_url`）时限制 1 MiB，
超过就丢弃整个目录、不报错。上游目录约 1.7 MiB，因此这条路径必然拿不到模型。

`codex-catalog-limit-8mib.patch` 把上限从 `1024 * 1024` 提到 `8 * 1024 * 1024`
（源码位置 `codex-rs/model-provider/src/models_endpoint.rs`）。实测：

| 场景 | 官方 0.160.0 | 8 MiB 补丁版 |
| --- | --- | --- |
| `model_catalog_url` 直连上游 1.70 MiB | 0 条 | 29 条 / 17 可见 |
| 本地代理 4 MiB | 0 条 | 29 条 |
| 本地代理 9 MiB | 0 条 | 0 条（仍受 8 MiB 限制） |

注意两点：

1. 通过本工具启动时用的是 `model_catalog_json` 本地文件，那条路径没有 1 MiB 上限，
   所以补丁只影响用 `model_catalog_url` 的场景（例如直接把官方 Codex 指向 Provider）。
2. 补丁需要重新编译 Codex。Linux x86_64 可直接用预编译的静态 musl 客户端：

```bash
codex-provider client install <url 或本地路径> --sha256 <64位校验和>
```

安装后 `codex-provider` 固定使用该客户端（官方 Codex 原样保留）；`codex-provider client remove`
可随时回到官方客户端。
