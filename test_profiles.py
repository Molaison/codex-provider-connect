import copy
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock


import codex_provider as connector


class LegacyPromptTests(unittest.TestCase):
    def test_repairs_both_prompt_sources_and_preserves_capabilities(self):
        legacy = "You are Codex, an agent based on GPT-5. Old instructions."
        model = {
            "slug": "chatgpt-web/light",
            "base_instructions": legacy,
            "model_messages": {"instructions_template": legacy, "permissions": "keep"},
            "context_window": 111193,
            "supports_search_tool": True,
            "supported_reasoning_levels": [{"effort": "low"}],
            "visibility": "hide",
        }
        catalog = {"models": [model], "extra": "keep"}
        expected = copy.deepcopy(catalog)
        expected["models"][0]["base_instructions"] = connector.CHATGPT_WEB_INSTRUCTIONS
        expected["models"][0]["model_messages"]["instructions_template"] = connector.CHATGPT_WEB_INSTRUCTIONS
        self.assertEqual(connector.repair_legacy_prompts(catalog), ["chatgpt-web/light"])
        self.assertEqual(catalog, expected)
        self.assertEqual(connector.repair_legacy_prompts(catalog), [])

    def test_deepseek_aliases_and_both_legacy_prefixes(self):
        for slug in ("DeepSeek-V4.1-Flash", "deepseek/deepseek-v4-pro"):
            for prefix in ("a coding agent", "an agent"):
                with self.subTest(slug=slug, prefix=prefix):
                    model = {"slug": slug, "base_instructions": "", "model_messages": {
                        "instructions_template": "You are Codex, %s based on GPT-5. Old." % prefix}}
                    connector.repair_legacy_prompts({"models": [model]})
                    self.assertEqual(model["model_messages"]["instructions_template"],
                                     connector.DEEPSEEK_INSTRUCTIONS)
                    self.assertEqual(model["base_instructions"], "")

    def test_other_models_and_corrected_upstream_prompts_win(self):
        catalog = {"models": [
            {"slug": "gpt-6-astra", "base_instructions": "You are Codex, an agent based on GPT-5."},
            {"slug": "DeepSeek-V4.1-Flash", "base_instructions": "Upstream DeepSeek instructions",
             "model_messages": None},
            {"slug": "chatgpt-web/pro", "model_messages": {"instructions_template": "New Web prompt"}},
        ]}
        before = copy.deepcopy(catalog)
        self.assertEqual(connector.repair_legacy_prompts(catalog), [])
        self.assertEqual(catalog, before)




class BuiltinMergeTests(unittest.TestCase):
    """model_catalog_json 是整体替换: 只写 Provider 目录会让内置模型(如 gpt-6-astra)丢失元数据。"""

    def test_appends_builtins_missing_from_provider(self):
        catalog = {"models": [{"slug": "deepseek/deepseek-v4.1-flash"}]}
        added = connector.merge_builtin(catalog, [{"slug": "gpt-6-astra"}, {"slug": "gpt-6.1-sol"}])
        self.assertEqual(added, ["gpt-6-astra", "gpt-6.1-sol"])
        self.assertEqual([m["slug"] for m in catalog["models"]],
                         ["deepseek/deepseek-v4.1-flash", "gpt-6-astra", "gpt-6.1-sol"])

    def test_provider_entry_wins_on_conflict(self):
        provider_entry = {"slug": "gpt-6-astra", "provider": "upstream"}
        catalog = {"models": [provider_entry]}
        self.assertEqual(connector.merge_builtin(catalog, [{"slug": "gpt-6-astra", "provider": "builtin"}]), [])
        self.assertEqual(catalog["models"], [provider_entry])
        self.assertEqual(len(catalog["models"]), 1)


if __name__ == "__main__":
    unittest.main()


class ClientOverrideTests(unittest.TestCase):
    """client install 记录的客户端应优先于 PATH 中的官方 Codex。"""

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="codex-provider-test-")
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.env = mock.patch.dict(os.environ, {"CODEX_HOME": self.home})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(os.environ.pop, "CODEX_BINARY", None)

    def install_record(self, path):
        state = Path(self.home) / "provider-connect"
        state.mkdir(parents=True, exist_ok=True)
        (state / "client.json").write_text(json.dumps({"path": str(path)}), encoding="utf-8")

    def test_recorded_client_wins_over_path(self):
        fake = Path(self.home) / "patched-codex"
        fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake.chmod(0o755)
        self.install_record(fake)
        self.assertEqual(connector.codex_binary(), [str(fake)])

    def test_missing_client_falls_back_to_path(self):
        self.install_record(Path(self.home) / "gone")
        self.assertIsNone(connector.installed_client())

    def test_codx_binary_env_still_wins(self):
        fake = Path(self.home) / "patched-codex"
        fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake.chmod(0o755)
        self.install_record(fake)
        os.environ["CODEX_BINARY"] = str(fake)
        self.assertEqual(connector.codex_binary(), [str(fake)])


if __name__ == "__main__":
    unittest.main()
