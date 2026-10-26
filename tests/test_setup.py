import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup_device", ROOT / "scripts/setup_device.py")
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def assert_tuned_settings(test, config):
    """The five settings verified on 2026-10-26 (README: Since 1.1.0)."""
    model = config["providers"]["chatgpt-subscription"]["models"]["gpt-6-astra"]
    test.assertEqual(model, {"supports_vision": True, "context_length": 872000})
    test.assertIs(model["supports_vision"], True)
    test.assertIs(type(model["context_length"]), int)
    test.assertEqual(config["compression"], {"threshold": 0.6})
    test.assertEqual(config["browser"], {"inactivity_timeout": 900})
    test.assertEqual(set(config["platform_hints"]), {"cli"})
    hint = config["platform_hints"]["cli"]["append"]
    test.assertTrue(hint.startswith("When work splits into independent parts"))
    test.assertTrue(hint.endswith("one-shot runs allow at most 2 children."))
    # Pin the exact verified text; change this digest only with a deliberate guidance change.
    test.assertEqual(hashlib.sha256(hint.encode()).hexdigest(), "b7d216a8071211b213a053012866f9cab41574f089fdf308b0d5f6bf216d37bc")


class DistributionTemplateTest(unittest.TestCase):
    def test_config_matches_template_byte_for_byte(self):
        # setup_device.py refuses an initial bind unless config.yaml == templates/config.json.
        self.assertEqual((ROOT / "config.yaml").read_bytes(), (ROOT / "templates/config.json").read_bytes())

    def test_template_carries_tuned_settings_and_none_kept_off(self):
        config = json.loads((ROOT / "templates/config.json").read_text())
        assert_tuned_settings(self, config)
        for key in ["web", "checkpoints", "tools"]:
            self.assertNotIn(key, config)
        self.assertNotIn("extra_body", config["providers"]["chatgpt-subscription"])


class DeviceSetupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hermes device test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profile = self.root / "profiles/astra-ultra"
        self.profile.mkdir(parents=True)
        for name in ["config.yaml", "distribution.yaml", "setup-lock.json"]:
            shutil.copyfile(ROOT / name, self.profile / name)
        shutil.copytree(ROOT / "templates", self.profile / "templates")
        self.codex = self.root / "codex"
        self.codex.mkdir()
        self.auth = {"auth_mode": "chatgpt", "tokens": {"account_id": "test-account", "access_token": "synthetic-secret-never-share"}}
        (self.codex / "auth.json").write_text(json.dumps(self.auth))
        self.source = self.root / "workbench-source"
        (self.source / "scripts").mkdir(parents=True)
        (self.source / "scripts/hermes-codex-token").write_text('''import json, sys
assert "--check" in sys.argv
print(json.dumps({"status": "ready", "account_bound": True, "refresh_performed": False}))
''')
        (self.source / "scripts/agent-workbench").write_text("print('fixture workbench')\n")
        for args in [["init", "-q"], ["add", "."], ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"]]:
            subprocess.run(["git", "-C", self.source, *args], check=True, capture_output=True)
        self.pin = subprocess.check_output(["git", "-C", self.source, "rev-parse", "HEAD"], text=True).strip()
        self.lock = {"workbench": {"repository": str(self.source), "commit": self.pin}}
        (self.profile / "setup-lock.json").write_text(json.dumps(self.lock))
        self.hermes = self.root / "hermes"
        self.hermes.write_text("#!/bin/sh\nexit 0\n")
        self.hermes.chmod(0o700)

    def configure(self, **kwargs):
        return setup.configure(self.profile, self.codex, self.hermes, **kwargs)

    def test_install_paths_permissions_and_no_token_copy(self):
        self.assertEqual(self.configure()["status"], "ready")
        config = json.loads((self.profile / "config.yaml").read_text())
        self.assertEqual(config["agent"]["reasoning_effort"], "ultra")
        self.assertEqual(config["providers"]["chatgpt-subscription"]["extra_headers"], {"ChatGPT-Account-ID": "test-account"})
        self.assertEqual((self.profile / "local/workbench-subscription.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.profile / "config.yaml").stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.profile / "plugins/agent-workbench").resolve(), self.profile / "local/workbench")
        output = subprocess.check_output([self.profile / "local/bin/agent-workbench"], text=True)
        self.assertEqual(output.strip(), "fixture workbench")
        for p in self.profile.rglob("*"):
            if p.is_file() and ".git" not in p.parts:
                self.assertNotIn(b"synthetic-secret-never-share", p.read_bytes())

    def test_bound_config_carries_tuned_settings(self):
        self.configure()
        bound = json.loads((self.profile / "config.yaml").read_text())
        assert_tuned_settings(self, bound)
        # Binding adds only device-local wiring; every shared setting comes from the template.
        expected = json.loads((ROOT / "templates/config.json").read_text())
        provider = expected["providers"]["chatgpt-subscription"]
        provider["key_cmd"] = bound["providers"]["chatgpt-subscription"]["key_cmd"]
        provider["extra_headers"] = {"ChatGPT-Account-ID": "test-account"}
        expected["terminal"]["shell_init_files"] = bound["terminal"]["shell_init_files"]
        self.assertEqual(bound, expected)

    def test_repeat_preserves_custom_config_and_history(self):
        self.configure()
        (self.profile / "config.yaml").write_text("user: custom-yaml\n")
        (self.profile / "state.db").write_bytes(b"local history")
        self.configure()
        self.assertEqual((self.profile / "config.yaml").read_text(), "user: custom-yaml\n")
        self.assertEqual((self.profile / "state.db").read_bytes(), b"local history")

    def test_account_change_refused_without_rebinding(self):
        self.configure()
        original = (self.profile / "local/workbench-subscription.json").read_bytes()
        self.auth["tokens"]["account_id"] = "other-account"
        (self.codex / "auth.json").write_text(json.dumps(self.auth))
        with self.assertRaisesRegex(setup.SetupError, "Account or Codex home changed"):
            self.configure()
        self.assertEqual((self.profile / "local/workbench-subscription.json").read_bytes(), original)

    def test_missing_login_leaves_config_and_plugin_untouched(self):
        (self.codex / "auth.json").unlink()
        original = (self.profile / "config.yaml").read_bytes()
        with self.assertRaises(setup.SetupError):
            self.configure()
        self.assertEqual((self.profile / "config.yaml").read_bytes(), original)
        self.assertFalse((self.profile / "local").exists())

    def test_edited_initial_profile_refused(self):
        (self.profile / "config.yaml").write_text("custom: true\n")
        with self.assertRaisesRegex(setup.SetupError, "local edits"):
            self.configure()
        self.assertFalse((self.profile / "local").exists())

    def test_symlink_destination_refused(self):
        (self.profile / "local").symlink_to(self.codex, target_is_directory=True)
        with self.assertRaisesRegex(setup.SetupError, "symlinks"):
            self.configure()
        self.assertFalse((self.codex / "workbench-subscription.json").exists())

    def test_dirty_plugin_refused(self):
        self.configure()
        (self.profile / "local/workbench/scripts/agent-workbench").write_text("local edit")
        with self.assertRaisesRegex(setup.SetupError, "local changes"):
            self.configure()

    def test_check_is_read_only(self):
        self.configure()
        tracked = [self.profile / n for n in ["config.yaml", "local/device-setup.json", "local/workbench-subscription.json"]]
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in tracked]
        self.configure(check=True)
        self.assertEqual(before, [(p.read_bytes(), p.stat().st_mtime_ns) for p in tracked])

    def test_plugin_failure_can_resume_without_overwriting_config(self):
        self.hermes.write_text("#!/bin/sh\nexit 1\n")
        with self.assertRaises(setup.SetupError):
            self.configure()
        self.assertFalse(json.loads((self.profile / "local/device-setup.json").read_text())["complete"])
        config = (self.profile / "config.yaml").read_bytes()
        self.hermes.write_text("#!/bin/sh\nexit 0\n")
        self.configure()
        self.assertEqual((self.profile / "config.yaml").read_bytes(), config)
        self.assertTrue(json.loads((self.profile / "local/device-setup.json").read_text())["complete"])


if __name__ == "__main__":
    unittest.main()
