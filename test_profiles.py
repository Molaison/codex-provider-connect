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


class CatalogTrimTests(unittest.TestCase):
    """目录里那四段大块文案不下发；其余字段原样保留。"""

    def test_drops_four_optional_blocks_and_keeps_the_rest(self):
        model = {"slug": "gpt-6-astra", "model_messages": {
            "instructions_template": "keep", "permissions": None, "approvals": {"never": None},
            "confirmation_policies": {"browser_use": "x" * 10},
            "persistent_instructions": "y" * 10, "token_budget": {"enabled": False},
            "guardian_v2": {"classifier_instructions": "z" * 10}}}
        catalog = {"models": [model, {"slug": "deepseek/deepseek-v4.1-flash"}]}
        removed = connector.trim_model_messages(catalog)
        self.assertEqual(sorted(removed), ["confirmation_policies", "guardian_v2",
                                           "persistent_instructions", "token_budget"])
        self.assertTrue(all(size > 0 for size in removed.values()))
        self.assertEqual(sorted(model["model_messages"]),
                         ["approvals", "instructions_template", "permissions"])
        self.assertEqual(connector.trim_model_messages(catalog), {})
        self.assertEqual(model["model_messages"]["instructions_template"], "keep")


class CatalogLimitPatchTests(unittest.TestCase):
    """安装时对现成二进制做定点替换，而不是下载预编译客户端。"""

    @staticmethod
    def binary(immediate, sites=1):
        head = connector.CATALOG_LIMIT_SIGNATURE_PRE + connector.CATALOG_LIMIT_SIGNATURE_OPCODE
        tail = connector.CATALOG_LIMIT_SIGNATURE_POST
        return b"\x7fELF" + b"\x00" * 60 + (
            head + immediate.to_bytes(4, "little") + tail + b"\x90" * 20) * sites

    def test_rewrites_one_mebibyte_limit_to_eight(self):
        signed = self.binary(connector.CATALOG_LIMIT_IMMEDIATE)
        patched, note = connector.patch_catalog_limit_bytes(signed)
        self.assertEqual(len(patched), len(signed))
        self.assertIn("1 MiB -> 8 MiB", note)
        self.assertEqual([value for _, value in connector.catalog_limit_sites(patched)],
                         [connector.CATALOG_LIMIT_PATCHED])

    def test_already_patched_stays_unchanged(self):
        signed = self.binary(connector.CATALOG_LIMIT_PATCHED)
        patched, note = connector.patch_catalog_limit_bytes(signed)
        self.assertEqual(patched, signed)
        self.assertIn("已是 8 MiB", note)

    def test_refuses_unknown_and_ambiguous_binaries(self):
        with self.assertRaises(ValueError):
            connector.patch_catalog_limit_bytes(b"\x7fELF" + b"\x00" * 500)
        with self.assertRaises(ValueError):
            connector.patch_catalog_limit_bytes(
                self.binary(connector.CATALOG_LIMIT_IMMEDIATE, sites=2))
        with self.assertRaises(ValueError):
            connector.patch_catalog_limit_bytes(self.binary(4096))


class ProviderReuseTests(unittest.TestCase):
    """直接指定 config.toml 里已有的 provider，且重复安装不再询问。"""

    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="codex-provider-reuse-")
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)
        self.env = mock.patch.dict(os.environ, {"CODEX_HOME": self.home})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(os.environ.pop, "CODEX_PROVIDER_URL", None)
        self.addCleanup(os.environ.pop, "CODEX_PROVIDER_API_KEY", None)
        self.addCleanup(os.environ.pop, "CODEX_PROVIDER_NAME", None)

    def write_config(self, text):
        (Path(self.home) / "config.toml").write_text(text, encoding="utf-8")

    def state(self):
        state = Path(self.home) / "provider-connect"
        state.mkdir(parents=True, exist_ok=True)
        return state

    AUTH_CONFIG = """model_provider = "ywl"
model = "gpt-6-astra"

[model_providers.ywl]
name = 'ywl'
wire_api = "responses"
requires_openai_auth = false      # 命令式 provider 不走 1MiB 目录上限
base_url = "http://192.168.233.231:18082/v1"

[model_providers.ywl.auth]
command = "/bin/cat"
args = ["{token}"]
"""

    def test_reads_base_url_and_auth_command(self):
        token = Path(self.home) / "token"
        token.write_text("sk-from-command\n", encoding="utf-8")
        self.write_config(self.AUTH_CONFIG.format(token=token))
        connection = connector.config_provider("ywl")
        self.assertEqual(connection["url"], "http://192.168.233.231:18082/v1")
        self.assertEqual(connection["provider"], "ywl")
        self.assertEqual(connection["auth_command"], ["/bin/cat", str(token)])
        self.assertEqual(connection["api_key"], "sk-from-command")
        self.assertEqual(connector.resolved_key(connection), "sk-from-command")

    def test_reads_bearer_token_and_env_key(self):
        self.write_config("""[model_providers.tok]
base_url = "https://example.test/v1"
experimental_bearer_token = "sk-bearer"
""")
        self.assertEqual(connector.config_provider("tok")["api_key"], "sk-bearer")
        self.write_config("""[model_providers.env]
base_url = "https://example.test/v1"
env_key = "MY_PROVIDER_KEY"
""")
        with mock.patch.dict(os.environ, {"MY_PROVIDER_KEY": "sk-env"}):
            self.assertEqual(connector.config_provider("env")["api_key"], "sk-env")
        with self.assertRaises(ValueError):
            connector.config_provider("env")

    def test_unknown_provider_and_missing_base_url(self):
        self.write_config("[model_providers.other]\nbase_url = \"https://x.test/v1\"\n")
        with self.assertRaises(ValueError):
            connector.config_provider("nope")
        self.write_config("[model_providers.nourl]\nname = \"nourl\"\n")
        with self.assertRaises(ValueError):
            connector.config_provider("nourl")

    def test_fallback_parser_matches_tomllib(self):
        token = Path(self.home) / "token"
        token.write_text("sk-fallback\n", encoding="utf-8")
        self.write_config(self.AUTH_CONFIG.format(token=token))
        expected = connector.config_provider("ywl")
        with mock.patch.object(connector, "tomllib", None):
            self.assertEqual(connector.config_provider("ywl"), expected)

    def test_configure_reuses_saved_connection_without_prompting(self):
        connector.private_json(self.state() / "connection.json",
                               {"url": "https://example.test/v1", "api_key": "sk-saved"})
        prompts = mock.patch.object(connector, "prompt_url", side_effect=AssertionError("不应询问地址"))
        keys = mock.patch.object(connector, "prompt_key", side_effect=AssertionError("不应询问密钥"))
        catalog = mock.patch.object(connector, "fetch_catalog")
        with prompts, keys, catalog as fetched:
            with mock.patch.object(connector, "codex_binary", return_value=["/bin/true"]):
                connector.configure([])
        self.assertEqual(fetched.call_args[0][0],
                         {"url": "https://example.test/v1", "api_key": "sk-saved"})

    def test_configure_url_keeps_saved_key_when_url_unchanged(self):
        connector.private_json(self.state() / "connection.json",
                               {"url": "https://example.test/v1", "api_key": "sk-saved"})
        with mock.patch.object(connector, "prompt_key", side_effect=AssertionError("不应询问密钥")), \
                mock.patch.object(connector, "fetch_catalog") as fetched, \
                mock.patch.object(connector, "codex_binary", return_value=["/bin/true"]):
            connector.configure(["--url", "https://example.test/v1/"])
        self.assertEqual(fetched.call_args[0][0]["api_key"], "sk-saved")

    def test_configure_provider_writes_connection_without_prompting(self):
        self.write_config("""[model_providers.tok]
base_url = "https://example.test/v1"
experimental_bearer_token = "sk-bearer"
""")
        with mock.patch.object(connector, "prompt_url", side_effect=AssertionError("不应询问地址")), \
                mock.patch.object(connector, "prompt_key", side_effect=AssertionError("不应询问密钥")), \
                mock.patch.object(connector, "fetch_catalog"), \
                mock.patch.object(connector, "codex_binary", return_value=["/bin/true"]):
            connector.configure(["--provider", "tok"])
        stored = json.loads((self.state() / "connection.json").read_text(encoding="utf-8"))
        self.assertEqual(stored, {"url": "https://example.test/v1", "provider": "tok",
                                  "api_key": "sk-bearer"})


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
