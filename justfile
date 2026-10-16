# 发布前先完成真实空白客户端验收，并提交与参数一致的版本号。
test:
    python3 -m unittest -v test_profiles test_onboarding

release version:
    git push origin HEAD
    gh release create v{{version}} --target "$(git rev-parse HEAD)" --title "v{{version}}" --notes "Native official Codex configuration, maintained model catalog, idle-confirmed server reload, and recoverable tool verification."
