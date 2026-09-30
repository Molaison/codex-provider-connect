# 发布前先完成真实空白客户端验收，并提交与参数一致的版本号。
release version:
    git push origin HEAD
    gh release create v{{version}} --target "$(git rev-parse HEAD)" --title "v{{version}}" --notes "Single-command Provider setup and automatic model-catalog refresh for official Codex."
