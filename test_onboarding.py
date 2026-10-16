"""真实子进程/本地 HTTP 验收安装与恢复协议；模型输出为明确的模拟 fixture。"""
import base64
import contextlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest import mock

import codex_provider as connector


ROOT = Path(__file__).resolve().parent
MODEL = "chatgpt-web/gpt-6-tools-temp"


class OnboardingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.codex = self.home / "native-fixture"
        self.codex.write_text("""#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
a=sys.argv[1:]
if '--version' in a: print('codex-cli 0.162.1');sys.exit(0)
if a[:2]==['debug','models']: print('{"models":[]}');sys.exit(0)
counter=Path(os.environ['HOME'])/'calls'
counter.write_text(str(int(counter.read_text())+1) if counter.exists() else '1')
if os.environ.get('FIXTURE_FAIL'):
 print(json.dumps({'type':'error','message':'ChatGPT web turn is missing network access in trusted Codex environment context'}))
 print(json.dumps({'type':'turn.failed','error':{'message':'fixture failure'}}));sys.exit(1)
if os.environ.get('FIXTURE_SLOW'): time.sleep(3)
workspace=Path(a[a.index('-C')+1]);marker=(workspace/'marker.txt').read_text().strip()
print(json.dumps({'type':'item.completed','item':{'type':'command_execution','command':'read '+str(workspace/'marker.txt'),'exit_code':0,'aggregated_output':marker}}))
Path(a[a.index('-o')+1]).write_text(marker[:-4] if os.environ.get('FIXTURE_TRUNCATE') else marker)
print(json.dumps({'type':'turn.completed'}))
""", encoding="utf-8")
        self.codex.chmod(0o700)
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home / "codex-home"),
                        CODEX_BINARY=str(self.codex), CODEX_PROVIDER_API_KEY="fixture-secret-do-not-print",
                        NO_PROXY="127.0.0.1,localhost", no_proxy="127.0.0.1,localhost")
        self.env.pop("CODEX_PROVIDER_URL", None)
        self.env.pop("CODEX_PROVIDER_NAME", None)
        self.requests = []
        self.status = 200
        case = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                case.requests.append(self.path)
                body = json.dumps({"models": [{"slug": MODEL, "visibility": "list", "supported_in_api": True}]}).encode()
                self.send_response(case.status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = "http://127.0.0.1:%s/v1" % self.server.server_port

    def run_cli(self, *args, **environment):
        return subprocess.run([sys.executable, str(ROOT / "codex_provider.py")] + list(args),
                              env=dict(self.env, **environment), text=True, capture_output=True, timeout=30)

    def calls(self):
        path = self.home / "calls"
        return int(path.read_text()) if path.exists() else 0

    def test_legacy_setup_reuses_terminal_check_without_changing_configuration(self):
        original = self.home / "codex-home"
        original.mkdir()
        (original / "config.toml").write_text('# existing configuration\n')
        (original / "auth.json").write_text('{"existing":"credential"}\n')
        installed = self.run_cli("setup", "--url", self.url)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertIn("[READY]", installed.stdout)
        self.assertNotIn(self.env["CODEX_PROVIDER_API_KEY"], installed.stdout + installed.stderr)
        self.assertEqual((original / "config.toml").read_text(), '# existing configuration\n')
        self.assertEqual((original / "auth.json").read_text(), '{"existing":"credential"}\n')
        repeated = self.run_cli("setup", "--url", self.url)
        self.assertEqual(repeated.returncode, 0, repeated.stderr + repeated.stdout)
        self.assertEqual(self.calls(), 1)
        connection = original / "provider-connect/connection.json"
        self.assertEqual(connection.stat().st_mode & 0o777, 0o600)

    def test_failed_legacy_setup_is_not_success_or_blindly_retried(self):
        installed = self.run_cli("setup", "--url", self.url, FIXTURE_FAIL="1")
        self.assertEqual(installed.returncode, 1)
        self.assertIn("UPSTREAM_COMPAT", installed.stdout)
        self.assertNotIn("[READY]", installed.stdout)
        report = self.run_cli("doctor", "--check", "--json")
        data = json.loads(report.stdout)
        self.assertEqual(data["code"], "UPSTREAM_COMPAT")
        self.assertEqual(self.calls(), 1)
        repaired = self.run_cli("repair")
        self.assertEqual(repaired.returncode, 0, repaired.stderr + repaired.stdout)
        self.assertEqual(self.calls(), 2)

    def test_truncated_final_fails_even_when_command_and_native_turn_pass(self):
        installed = self.run_cli("setup", "--url", self.url, FIXTURE_TRUNCATE="1")
        self.assertEqual(installed.returncode, 1)
        self.assertIn("OUTPUT_MISMATCH", installed.stdout)
        self.assertNotIn("[READY]", installed.stdout)
        root = self.home / "codex-home/provider-connect/checks"
        directory = Path(json.loads((root / "current.json").read_text())["directory"])
        record = json.loads((directory / "state.json").read_text())
        self.assertRegex(record["marker"], r"^CPC-[0-9a-f]{12}-[0-9a-f]{12}-[0-9a-f]{12}-END$")
        self.assertNotIn(record["marker"], record["arguments"][-1])
        report = self.run_cli("doctor", "--check", "--json")
        self.assertEqual(json.loads(report.stdout)["code"], "OUTPUT_MISMATCH")
        self.assertEqual(self.calls(), 1)

    def test_pending_check_is_recovered_without_second_submission(self):
        prepared = self.run_cli("setup", "--url", self.url, "--skip-check")
        self.assertEqual(prepared.returncode, 2)
        self.assertEqual(self.calls(), 0)
        with mock.patch.dict(os.environ, dict(self.env, FIXTURE_SLOW="1"), clear=True):
            connection = connector.read_connection()
            catalog = connector.state_directory() / "models.json"
            pending = connector.model_check([str(self.codex)], connection, catalog, MODEL, wait_seconds=0)
            self.assertEqual(pending["code"], "CHECK_PENDING")
            recovered = connector.model_check([str(self.codex)], connection, catalog, MODEL, retry=True, wait_seconds=10)
        self.assertEqual(recovered["code"], "READY")
        self.assertEqual(self.calls(), 1)

    def test_key_change_cannot_reuse_old_success(self):
        self.assertEqual(self.run_cli("setup", "--url", self.url).returncode, 0)
        changed = self.run_cli("setup", "--url", self.url, CODEX_PROVIDER_API_KEY="another-fixture-key")
        self.assertEqual(changed.returncode, 1)
        self.assertIn("CHECK_CONNECTION_CHANGED", changed.stdout)
        self.assertEqual(self.calls(), 1)

    def test_401_stops_once_preserves_catalog_and_is_redacted(self):
        self.assertEqual(self.run_cli("setup", "--url", self.url, "--skip-check").returncode, 2)
        catalog = self.home / "codex-home/provider-connect/models.json"
        before = catalog.read_bytes()
        self.status = 401
        self.requests.clear()
        result = self.run_cli("doctor", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["code"], "AUTH")
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(catalog.read_bytes(), before)
        self.assertEqual(self.calls(), 0)
        self.assertNotIn(self.env["CODEX_PROVIDER_API_KEY"], result.stdout + result.stderr)

    def test_direct_is_explicit_scoped_and_survives_repair(self):
        prepared = self.run_cli("setup", "--url", self.url, "--direct", "--skip-check")
        self.assertEqual(prepared.returncode, 2, prepared.stderr)
        with mock.patch.dict(os.environ, self.env, clear=True):
            connection = connector.read_connection()
            self.assertTrue(connection["direct"])
            original = os.environ.get("NO_PROXY")
            command, environment = connector.provider_command([str(self.codex)], connection, "models.json", ["-m", "override"])
            self.assertEqual(command[-2:], ["-m", "override"])
            self.assertIn("127.0.0.1", environment["NO_PROXY"])
            self.assertEqual(os.environ.get("NO_PROXY"), original)
        repaired = self.run_cli("repair", "--skip-check")
        self.assertEqual(repaired.returncode, 2)
        self.assertTrue(json.loads((self.home / "codex-home/provider-connect/connection.json").read_text())["direct"])

    def test_all_launches_are_independent_of_existing_shared_server(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            connection = {"url": self.url, "api_key": "fixture-secret-do-not-print"}
            for arguments in ([], ["resume", "--last"], ["app-server"],
                              ["--no-daemon", "exec", "hello"]):
                command, _ = connector.provider_command([str(self.codex)], connection, "models.json", arguments)
                self.assertEqual(command.count("--no-daemon"), 1)
                self.assertIn('model_provider="provider_connect"', command)
                if arguments:
                    self.assertEqual(command[-len(arguments):], arguments)

    def test_native_preflight_checks_key_without_synchronizing_catalog(self):
        with mock.patch.dict(os.environ, self.env, clear=True):
            connection = {"url": self.url, "api_key": self.env["CODEX_PROVIDER_API_KEY"]}
            self.assertEqual(connector.native_preflight(connection, MODEL)["code"], "ENDPOINT_OK")
            self.status = 401
            rejected = connector.native_preflight(connection, MODEL)
        self.assertEqual(rejected["code"], "AUTH")
        self.assertEqual(self.calls(), 0)
        self.assertEqual(self.requests, ["/v1/models", "/v1/models"])
        self.assertNotIn(connection["api_key"], json.dumps(rejected))

    def test_native_preflight_bad_all_proxy_fails_before_any_turn(self):
        with mock.patch.dict(os.environ, {"ALL_PROXY": "http://127.0.0.1:9", "NO_PROXY": ""}, clear=True):
            result = connector.native_preflight({"url": self.url, "api_key": "private-fixture"}, MODEL)
        self.assertEqual(result["code"], "NETWORK")
        self.assertEqual(self.requests, [])
        self.assertEqual(self.calls(), 0)


class OfficialInstallTests(unittest.TestCase):
    def test_verified_official_archive_and_integrity_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = io.BytesIO()
            script = b'#!/bin/sh\necho "codex-cli 0.162.1"\n'
            with tarfile.open(fileobj=archive, mode="w:gz") as package:
                member = tarfile.TarInfo("package/vendor/x86_64-unknown-linux-musl/bin/codex")
                member.size, member.mode = len(script), 0o755
                package.addfile(member, io.BytesIO(script))
            blob = archive.getvalue()
            metadata = {"name": "@openai/codex", "version": "0.162.1-linux-x64", "dist": {
                "tarball": "https://registry.npmjs.org/@openai/codex/-/fixture.tgz",
                "integrity": "sha512-" + base64.b64encode(hashlib.sha512(blob).digest()).decode()}}
            with mock.patch.dict(os.environ, {"CODEX_HOME": str(root)}), \
                    mock.patch.object(connector.platform, "machine", return_value="x86_64"), \
                    mock.patch.object(connector.sys, "platform", "linux"), \
                    mock.patch.object(connector.urllib.request, "urlopen", side_effect=lambda *a, **k: io.BytesIO(json.dumps(metadata).encode())), \
                    mock.patch.object(connector, "_download", side_effect=lambda url, target: target.write_bytes(blob)):
                installed = connector.official_client()
                self.assertEqual(connector.client_version(installed), "0.162.1")
                self.assertFalse(json.loads(connector.client_record_path().read_text())["patched"])
                Path(installed[0]).unlink()
                repaired = connector.setup_client()
                self.assertEqual(connector.client_version(repaired), "0.162.1")
                self.assertEqual(len(list((root / "provider-connect/official").glob("*.unusable-*"))), 1)
                shutil.rmtree(root / "provider-connect/official")
                connector.client_record_path().unlink()
                metadata["dist"]["integrity"] = "sha512-invalid"
                with self.assertRaisesRegex(ValueError, "SHA512"):
                    connector.official_client()
                self.assertFalse(connector.client_record_path().exists())


class NativeIntegrationTests(unittest.TestCase):
    """Model native startup snapshots, rather than assuming batchWrite reloads them."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.environment = mock.patch.dict(os.environ, {"HOME": str(self.home),
            "CODEX_HOME": str(self.home / ".codex"), "CODEX_PROVIDER_API_KEY": "fixture-secret"}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.connection = {"url": "https://fixture.invalid/v1", "api_key": "fixture-secret", "generation": "fixture-generation"}
        self.catalog = connector.native_catalog(self.connection, ["fixture-codex"])
        self.expected = [m["slug"] for m in json.loads(self.catalog.read_text())["models"]
                         if m.get("visibility") == "list" and m.get("supported_in_api", True)]

    def rpc_factory(self, live=False):
        owner = self
        owner.config = {"model_provider": "old", "model": "old-model",
                        "model_providers": {"old": {"base_url": "https://old.invalid/v1"}},
                        "projects": {"/example": {"trust_level": "untrusted"}}}
        owner.requests, owner.instances = [], []
        owner.server_identity = [1, 2, 3]
        connector.config_path().write_text('# original configuration\n')
        auth = connector.config_path().with_name("auth.json")
        auth.write_text('{"untouched":"existing credential"}')

        class RPC:
            def __init__(self, binary):
                self.live = live
                self.identity = owner.server_identity if live else None
                self.menu = ["old-model"] if live or owner.config.get("model_provider") == "old" else owner.expected
                owner.instances.append(self)

            def call(self, method, params):
                owner.requests.append((method, params))
                if method == "config/read":
                    return {"config": json.loads(json.dumps(owner.config)), "layers": [
                        {"name": {"type": "user", "file": str(connector.config_path())}, "version": "native-version"}]}
                if method == "config/batchWrite":
                    for edit in params["edits"]:
                        parts = edit["keyPath"].split(".")
                        target = owner.config
                        for part in parts[:-1]:
                            target = target.setdefault(part, {})
                        target[parts[-1]] = edit["value"]
                    return {"status": "ok"}
                if method == "model/list":
                    return {"data": [{"model": model} for model in self.menu], "nextCursor": None}
                raise AssertionError(method)

            def __enter__(self):
                return self

            def __exit__(self, *unused):
                pass
        return RPC

    def test_fresh_native_configuration_reopens_only_owned_stdio(self):
        with mock.patch.object(connector, "NativeRPC", self.rpc_factory()):
            report = connector.native_configure(["fixture-codex"], self.connection, MODEL)
        self.assertFalse(report["restart_required"])
        self.assertEqual(set(report["visible_models"]), set(self.expected))
        self.assertEqual(len(self.instances), 2)
        write = next(params for method, params in self.requests if method == "config/batchWrite")
        self.assertFalse(write["reloadUserConfig"])
        self.assertEqual(write["expectedVersion"], "native-version")
        self.assertEqual(self.config["model_provider"], "provider_connect")
        self.assertEqual(self.config["model_reasoning_effort"], "xhigh")
        self.assertEqual(self.config["model_providers"]["old"]["base_url"], "https://old.invalid/v1")
        self.assertEqual(self.config["projects"]["/example"]["trust_level"], "untrusted")
        self.assertEqual(connector.config_path().with_name("auth.json").read_text(), '{"untouched":"existing credential"}')
        self.assertEqual(Path(report["config_backup"]).read_text(), '# original configuration\n')

    def test_running_native_server_reports_stale_catalog_without_polling_or_restart(self):
        with mock.patch.object(connector, "NativeRPC", self.rpc_factory(live=True)):
            report = connector.native_configure(["fixture-codex"], self.connection, MODEL)
        self.assertTrue(report["restart_required"])
        self.assertFalse(report["shared_server_updated"])
        self.assertEqual(len(self.instances), 1)
        self.assertEqual(sum(method == "model/list" for method, _ in self.requests), 1)

    def test_restart_required_never_submits_check_or_reports_ready(self):
        output = io.StringIO()
        with mock.patch.object(connector, "native_client", return_value=["fixture-codex"]), \
                mock.patch.object(connector, "client_version", return_value="0.162.1"), \
                mock.patch.object(connector, "native_preflight", return_value={"status": "network_ok"}), \
                mock.patch.object(connector, "native_restart", return_value=(False, "SERVER_RESTART_REQUIRED", "restart required")), \
                mock.patch.object(connector, "NativeRPC", self.rpc_factory(live=True)), \
                mock.patch.object(connector, "model_check", side_effect=AssertionError("unexpected model call")), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = connector.native_setup(["--url", self.connection["url"]])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["code"], "SERVER_RESTART_REQUIRED")
        self.assertNotIn("fixture-secret", output.getvalue())
        self.assertTrue((connector.state_directory() / "connection.json").is_file())

    def test_same_model_ids_still_require_restart_and_survive_repeated_setup(self):
        factory = self.rpc_factory(live=True)
        original = factory.__init__
        def matching_menu(rpc, binary):
            original(rpc, binary)
            rpc.menu = self.expected
        with mock.patch.object(factory, "__init__", matching_menu), mock.patch.object(connector, "NativeRPC", factory):
            first = connector.native_configure(["fixture-codex"], self.connection, MODEL)
            repeated = connector.native_configure(["fixture-codex"], self.connection, MODEL)
            self.assertTrue(first["restart_required"])
            self.assertTrue(repeated["restart_required"])
            self.assertEqual(sum(method == "config/batchWrite" for method, _ in self.requests), 1)
            self.server_identity = [1, 2, 4]
            fresh = connector.native_configure(["fixture-codex"], self.connection, MODEL)
        self.assertFalse(fresh["restart_required"])
        self.assertFalse((connector.state_directory() / "native-reload.json").exists())

    def test_restart_checks_busy_status_even_with_explicit_confirmation(self):
        rpc = mock.MagicMock(live=True, identity=[1, 2, 3])
        rpc.__enter__.return_value = rpc
        rpc.call.side_effect = [{"data": ["busy-thread"]}, {"thread": {"status": {"type": "active"}}}]
        with mock.patch.object(connector, "NativeRPC", return_value=rpc), \
                mock.patch.object(connector.subprocess, "run") as run:
            result = connector.native_restart(["fixture-codex"], {"server_identity": rpc.identity}, confirmed=True)
        self.assertEqual(result[1], "SERVER_BUSY")
        run.assert_not_called()

    def test_restart_checks_again_after_confirmation_before_official_restart(self):
        rpc = mock.MagicMock(live=True, identity=[1, 2, 3])
        rpc.__enter__.return_value = rpc
        with mock.patch.object(connector, "NativeRPC", return_value=rpc), \
                mock.patch.object(connector, "native_server_idle", side_effect=[True, False]), \
                mock.patch.object(connector.subprocess, "run") as run:
            result = connector.native_restart(["fixture-codex"], {"server_identity": rpc.identity}, confirmed=True)
        self.assertEqual(result[1], "SERVER_BUSY")
        run.assert_not_called()

    def test_idle_confirmed_restart_uses_official_command_and_new_server_identity(self):
        old, new = mock.MagicMock(live=True, identity=[1, 2, 3]), mock.MagicMock(live=True, identity=[1, 2, 4])
        old.__enter__.return_value, new.__enter__.return_value = old, new
        old.call.return_value = {"data": [], "nextCursor": None}
        with mock.patch.object(connector, "NativeRPC", side_effect=[old, new]), \
                mock.patch.object(connector.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            result = connector.native_restart(["fixture-codex"], {"server_identity": old.identity}, confirmed=True)
        self.assertTrue(result[0])
        self.assertEqual(run.call_args[0][0], ["fixture-codex", "app-server", "daemon", "restart"])

    def test_restart_terminal_confirmation_uses_separate_read_and_write_handles(self):
        old, new = mock.MagicMock(live=True, identity=[1, 2, 3]), mock.MagicMock(live=True, identity=[1, 2, 4])
        old.__enter__.return_value, new.__enter__.return_value = old, new
        terminal = mock.mock_open(read_data="y\n")
        with mock.patch.object(connector, "NativeRPC", side_effect=[old, new]), \
                mock.patch.object(connector, "native_server_idle", return_value=True), \
                mock.patch.object(connector.subprocess, "run", return_value=mock.Mock(returncode=0)), \
                mock.patch("builtins.open", terminal):
            result = connector.native_restart(["fixture-codex"], {"server_identity": old.identity})
        self.assertTrue(result[0])
        terminal.assert_any_call("/dev/tty", "w")
        terminal.assert_any_call("/dev/tty", "r")

    def test_changed_native_connection_checks_new_generation_without_repair_flag(self):
        output = io.StringIO()
        with mock.patch.object(connector, "native_client", return_value=["fixture-codex"]), \
                mock.patch.object(connector, "client_version", return_value="0.162.1"), \
                mock.patch.object(connector, "native_preflight", return_value={"status": "network_ok"}), \
                mock.patch.object(connector, "NativeRPC", self.rpc_factory()), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(connector.native_setup(["--url", self.connection["url"], "--skip-check"]), 2)
            with mock.patch.dict(os.environ, {"CODEX_PROVIDER_API_KEY": "changed-private-fixture"}), \
                    mock.patch.object(connector, "model_check", return_value={"status": "passed", "code": "READY"}) as check:
                self.assertEqual(connector.native_setup(["--url", self.connection["url"]]), 0)
        self.assertTrue(check.call_args.kwargs["retry"])
        self.assertTrue(check.call_args.kwargs["native"])

    def test_native_rerun_retries_failed_terminal_check_without_flag_but_reuses_success(self):
        with mock.patch.object(connector, "native_client", return_value=["fixture-codex"]), \
                mock.patch.object(connector, "client_version", return_value="0.162.1"), \
                mock.patch.object(connector, "native_preflight", return_value={"status": "network_ok"}), \
                mock.patch.object(connector, "NativeRPC", self.rpc_factory()), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(connector.native_setup(["--url", self.connection["url"], "--skip-check"]), 2)
            connector.private_json(connector.state_directory() / "checks/current.json", {"directory": str(self.home / "old-check")})
            with mock.patch.object(connector, "check_result", return_value={"status": "failed", "code": "UPSTREAM_COMPAT"}), \
                    mock.patch.object(connector, "model_check", return_value={"status": "passed", "code": "READY"}) as check:
                self.assertEqual(connector.native_setup([]), 0)
                self.assertTrue(check.call_args.kwargs["retry"])
            with mock.patch.object(connector, "check_result", return_value={"status": "passed", "code": "READY"}), \
                    mock.patch.object(connector, "model_check", return_value={"status": "passed", "code": "READY"}) as check:
                self.assertEqual(connector.native_setup([]), 0)
                self.assertFalse(check.call_args.kwargs["retry"])
                self.assertEqual(connector.native_setup(["--repair"]), 0)
                self.assertTrue(check.call_args.kwargs["retry"])

    def test_native_rerun_preserves_pending_check_before_changing_client_or_server(self):
        connector.private_json(connector.state_directory() / "checks/current.json", {"directory": str(self.home / "pending-check")})
        with mock.patch.object(connector, "check_result", return_value={"status": "running", "code": "CHECK_PENDING"}), \
                mock.patch.object(connector, "native_client", side_effect=AssertionError("must not replace client")), \
                mock.patch.object(connector, "native_configure", side_effect=AssertionError("must not mutate server")), \
                mock.patch.object(connector, "model_check", side_effect=AssertionError("must not resubmit")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(connector.native_setup(["--repair", "--restart-if-idle"]), 2)

    def test_catalog_updates_use_immutable_paths_and_do_not_fetch_upstream(self):
        old = self.catalog.read_bytes()
        with mock.patch.object(connector.urllib.request, "urlopen", side_effect=AssertionError("no upstream sync")):
            self.assertEqual(connector.native_catalog(self.connection, []), self.catalog)
            source = self.home / "new-catalog.json"
            source.write_text(json.dumps({"models": [{"slug": "new-model", "visibility": "list"}]}))
            self.connection["catalog_source"] = str(source)
            new = connector.native_catalog(self.connection, [])
        self.assertNotEqual(new, self.catalog)
        self.assertEqual(self.catalog.read_bytes(), old)
        self.assertEqual(new.stat().st_mode & 0o777, 0o600)
        source.write_text('{"models": []}')
        self.connection["catalog_source"] = str(source)
        with self.assertRaises(ValueError):
            connector.native_catalog(self.connection, [])
        self.assertEqual(self.connection["catalog_file"], str(new))

    def test_native_entry_is_official_binary_not_a_wrapper(self):
        binary = self.home / "official-codex"
        binary.write_bytes(b"fixture executable")
        binary.chmod(0o700)
        entry = self.home / ".local/bin/codex"
        entry.parent.mkdir(parents=True)
        entry.write_text("old entry")
        with mock.patch.dict(os.environ, {"CODEX_BINARY": str(binary)}), \
                mock.patch.object(connector, "client_version", return_value="0.162.1"), \
                mock.patch.object(connector, "resolve_native_binary", return_value=binary):
            self.assertEqual(connector.native_client(), [str(entry)])
        self.assertTrue(entry.is_symlink())
        self.assertEqual(entry.resolve(), binary)
        backups = list((connector.state_directory() / "backups").glob("codex-entry-*"))
        self.assertEqual(backups[0].read_text(), "old entry")
        self.assertFalse((entry.parent / "codex-provider").exists())

    def test_repair_owned_damaged_catalog_before_starting_native_rpc(self):
        self.catalog.write_text('{broken fixture')
        recovered = connector.native_catalog(self.connection, [])
        self.assertEqual(recovered, self.catalog)
        self.assertTrue(self.connection["catalog_repaired"])
        self.assertEqual(json.loads(recovered.read_text())["models"][0]["slug"],
                         json.loads((ROOT / "model_catalog.json").read_text())["models"][0]["slug"])
        backups = list((connector.state_directory() / "backups").glob("damaged-catalog-*.json"))
        self.assertEqual(backups[0].read_text(), '{broken fixture')
        outside = self.home / "unrelated-models.json"
        outside.write_text('{unrelated broken file')
        self.connection["catalog_file"] = str(outside)
        connector.native_catalog(self.connection, [])
        self.assertEqual(outside.read_text(), '{unrelated broken file')

    def test_shell_installer_uses_private_native_setup_and_bundled_catalog(self):
        source = self.home / "source"
        source.mkdir()
        (source / "model_catalog.json").write_text('{"models":[{"slug":"fixture"}]}')
        (source / "codex_provider.py").write_text('''# codex-provider-connect\nVERSION = "%s"\nimport sys\nassert sys.argv[1] == "_native-setup"\nassert "--url" in sys.argv\nprint("fixture setup passed")\n''' % connector.VERSION)
        env = dict(os.environ, PATH=os.environ.get("PATH", "/usr/bin:/bin"), CODEX_CONNECT_BASE=source.as_uri())
        result = subprocess.run(["bash", str(ROOT / "install.sh"), "--url", self.connection["url"]],
                                env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[READY]", result.stdout)
        self.assertTrue((connector.state_directory() / "codex_provider.py").is_file())
        self.assertTrue((connector.state_directory() / "model_catalog.json").is_file())
        self.assertFalse((self.home / ".local/bin/codex-provider").exists())

    def test_native_path_is_idempotent(self):
        with mock.patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            connector.native_path()
            connector.native_path()
        self.assertEqual((self.home / ".bashrc").read_text().count('export PATH='), 1)


class ReleaseBootstrapTests(unittest.TestCase):
    """Exercise one unchanged latest URL; only release hosting/setup are fixtures."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.root = self.home / ".codex/provider-connect"
        self.env = {"HOME": str(self.home), "CODEX_HOME": str(self.home / ".codex"),
                    "PATH": os.environ.get("PATH", os.defpath), "NO_PROXY": "127.0.0.1", "no_proxy": "127.0.0.1"}
        self.latest = "v" + connector.VERSION
        self.future = "v0.1.9"
        self.requests = []
        self.missing_catalog = False
        self.mismatch = False
        self.flip_during_download = False
        case = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                case.requests.append(self.path)
                if self.path == "/releases/latest/download/install.sh":
                    source = (ROOT / "install.sh").read_text().replace("v" + connector.VERSION, case.latest)
                    body = source.replace("https://github.com/Molaison/codex-provider-connect", case.base).encode()
                else:
                    parts = self.path.split("/")
                    if len(parts) != 5 or parts[1:3] != ["releases", "download"]:
                        self.send_error(404)
                        return
                    tag, filename = parts[3:]
                    if filename == "codex_provider.py":
                        version = "0.0.0" if case.mismatch else tag[1:]
                        body = ('''# codex-provider-connect; fixture setup only, no real model\nVERSION = "%s"\nimport json,sys\nfrom pathlib import Path\nassert sys.argv[1] == "_native-setup"\nroot=Path(__file__).parent\nassert json.loads((root/"model_catalog.json").read_text())["models"][0]["display_name"] == "release-" + VERSION\nprint("fixture setup passed")\n''' % version).encode()
                        if case.flip_during_download:
                            case.latest = case.future
                    elif filename == "model_catalog.json" and not case.missing_catalog:
                        body = json.dumps({"models": [{"slug": MODEL, "display_name": "release-" + tag[1:]}]}).encode()
                    else:
                        self.send_error(404)
                        return
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = "http://127.0.0.1:%s" % self.server.server_port
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def install(self):
        # This command is identical before/after a new release. No ref override.
        return subprocess.run(["bash", "-o", "pipefail", "-c",
            'curl -fsSL "$1/releases/latest/download/install.sh" | bash', "fixture", self.base],
            env=self.env, capture_output=True, text=True, timeout=20)

    def test_same_latest_url_updates_without_mixing_releases_when_latest_changes_mid_download(self):
        self.flip_during_download = True
        installed = self.install()
        self.assertEqual(installed.returncode, 0, installed.stderr)
        self.assertIn('VERSION = "' + connector.VERSION + '"', (self.root / "codex_provider.py").read_text())
        updated = self.install()
        self.assertEqual(updated.returncode, 0, updated.stderr)
        self.assertIn('VERSION = "0.1.9"', (self.root / "codex_provider.py").read_text())
        self.assertEqual(self.requests, ["/releases/latest/download/install.sh",
            "/releases/download/v" + connector.VERSION + "/codex_provider.py",
            "/releases/download/v" + connector.VERSION + "/model_catalog.json",
            "/releases/latest/download/install.sh", "/releases/download/v0.1.9/codex_provider.py",
            "/releases/download/v0.1.9/model_catalog.json"])

    def test_missing_payload_or_version_mismatch_never_replaces_working_installation(self):
        self.assertEqual(self.install().returncode, 0)
        previous = {name: (self.root / name).read_bytes() for name in ("codex_provider.py", "model_catalog.json")}
        for failure in ("missing_catalog", "mismatch"):
            with self.subTest(failure=failure):
                setattr(self, failure, True)
                failed = self.install()
                self.assertNotEqual(failed.returncode, 0)
                self.assertNotIn("[READY]", failed.stdout)
                for name, content in previous.items():
                    self.assertEqual((self.root / name).read_bytes(), content)
                setattr(self, failure, False)

    def test_same_entry_repairs_empty_owned_helper_but_preserves_unrelated_file(self):
        self.root.mkdir(parents=True)
        helper = self.root / "codex_provider.py"
        helper.write_text("unrelated file")
        refused = self.install()
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(helper.read_text(), "unrelated file")
        helper.write_text("")
        (self.root / "connection.json").write_text('{"integration":"native"}')
        repaired = self.install()
        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        backups = list((self.root / "backups").glob("damaged-helper.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), b"")

    def test_failed_latest_download_is_not_success(self):
        result = subprocess.run(["bash", "-o", "pipefail", "-c", 'curl -fsSL "$1/missing" | bash', "fixture", self.base],
                                env=self.env, capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("[READY]", result.stdout)
