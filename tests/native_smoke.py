"""Explicit native check using an existing Hermes runtime and synthetic auth only.

Run with Hermes's selected Python environment (not a freshly guessed venv).
"""
import argparse
import base64
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-source", type=Path, required=True)
    parser.add_argument("--workbench-source", type=Path, required=True)
    parser.add_argument("--distribution-source", help="Optional remote source for release verification")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="hermes-distribution-native-") as temporary:
        root = Path(temporary).resolve()
        os.environ["HERMES_HOME"] = str(root)
        sys.path.insert(0, str(args.hermes_source.resolve()))
        from hermes_cli.profile_distribution import install_distribution, update_distribution
        import hermes_yaml as yaml

        plan = install_distribution(args.distribution_source or str(ROOT))
        profile = plan.target_dir
        assert profile == root / "profiles/astra-ultra"
        assert not (profile / "README.md").exists(), "distribution allowlist not applied"
        (profile / "local").mkdir(exist_ok=True)
        workbench = profile / "local/workbench"
        subprocess.run(["git", "clone", "--quiet", str(args.workbench_source.resolve()), str(workbench)], check=True)
        lock = json.loads((profile / "setup-lock.json").read_text())
        subprocess.run(["git", "-C", str(workbench), "checkout", "--quiet", "--detach", lock["workbench"]["commit"]], check=True)
        codex = root / "synthetic-codex"
        codex.mkdir()
        claims = {"exp": int(time.time()) + 7200, "https://api.openai.com/auth": {"chatgpt_account_id": "synthetic-device"}}
        payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
        (codex / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt", "tokens": {
            "account_id": "synthetic-device", "access_token": "synthetic." + payload + ".not-a-signature",
            "refresh_token": "synthetic-never-refresh"}}))
        hermes = root / "hermes-native"
        entry = "import sys; sys.path.insert(0, " + repr(str(args.hermes_source.resolve())) + "); from hermes_cli.main import main; main()"
        hermes.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, "-c", entry]) + ' "$@"\n')
        hermes.chmod(0o700)
        spec = importlib.util.spec_from_file_location("setup_device", ROOT / "scripts/setup_device.py")
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        result = setup.configure(profile, codex, hermes)
        assert result == {"status": "ready", "account_bound": True, "refresh_performed": False}
        config = yaml.safe_load((profile / "config.yaml").read_text())
        assert "agent-workbench" in config["plugins"]["enabled"]
        assert config["agent"]["reasoning_effort"] == "ultra"
        assert config["providers"]["chatgpt-subscription"]["transport"] == "codex_responses"
        assert setup.configure(profile, codex, hermes, check=True) == result

        # Native update must preserve local config, account binding and user data.
        sentinels = {"memories/MEMORY.md": "synthetic memory", "sessions/local.txt": "synthetic session",
                     ".env": "SYNTHETIC=local-only", "state.db": "synthetic state"}
        for name, body in sentinels.items():
            path = profile / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(body)
        private = [profile / name for name in ["config.yaml", "local/workbench-subscription.json", "local/device-setup.json"]]
        before = [p.read_bytes() for p in private]
        update_distribution("astra-ultra")
        assert before == [p.read_bytes() for p in private]
        for name, body in sentinels.items():
            assert (profile / name).read_text() == body
        assert setup.configure(profile, codex, hermes) == result
        print("PASS: native distribution install, native plugin enable, real bridge metadata check, repeat setup, native update preserves local data; synthetic auth, no model request")


if __name__ == "__main__":
    main()
