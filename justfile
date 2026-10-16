# 发布前先完成验收并提交。四份附件全部上传后才发布，latest 不暴露半包。
test:
    python3 -m unittest -v test_profiles test_onboarding

release version:
    python3 -c 'import re,sys; from pathlib import Path; v=sys.argv[1]; assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+",v); assert ("VERSION = \""+v+"\"") in Path("codex_provider.py").read_text(); assert ("CODEX_CONNECT_REF:-v"+v+"}") in Path("install.sh").read_text(); assert ("else { " + chr(39)+"v"+v+chr(39)+" }") in Path("install.ps1").read_text()' '{{version}}'
    test -z "$(git status --porcelain)"
    git push origin HEAD
    gh release create v{{version}} install.sh install.ps1 codex_provider.py model_catalog.json --draft --target "$(git rev-parse HEAD)" --title "v{{version}}" --notes "One fixed latest entry for install, update, and repair. Official Codex, maintained catalog, busy-server protection, idle-confirmed restart, and recoverable tool verification."
    gh release edit v{{version}} --draft=false --latest
