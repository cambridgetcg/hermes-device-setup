#!/usr/bin/env python3
"""Bind an installed distribution to this device; never export its credentials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


class SetupError(Exception):
    pass


def run(argv, *, env=None, capture=False):
    result = subprocess.run([str(x) for x in argv], env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
    if result.returncode:
        # Native errors may quote private configuration. Keep diagnostics bounded.
        raise SetupError(f"{Path(str(argv[0])).name} failed (exit {result.returncode}); no private output displayed")
    return result.stdout.strip() if capture else None


def read_json(path):
    try:
        if path.stat().st_size > 1_048_576:
            raise ValueError()
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError, TypeError):
        raise SetupError("Required local JSON file is missing or invalid; see README setup steps") from None


def private_write(path, content, mode=0o600):
    if path.is_symlink():
        raise SetupError("Refusing to replace a symlink")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(prefix=".setup-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def encoded(data):
    return json.dumps(data, indent=2) + "\n"


def local_account(codex_home):
    auth = read_json(codex_home / "auth.json")
    tokens = auth.get("tokens")
    account = tokens.get("account_id") if isinstance(tokens, dict) else None
    if auth.get("auth_mode") != "chatgpt" or not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}", account):
        raise SetupError("A file-backed Codex ChatGPT login is required on this device; see README")
    return account


def verify_workbench(path, lock):
    if path.is_symlink() or not (path / ".git").exists():
        raise SetupError("Workbench must be an ordinary pinned Git checkout")
    if run(["git", "-C", path, "rev-parse", "HEAD"], capture=True) != lock["commit"]:
        raise SetupError("Workbench commit differs from setup-lock.json; existing checkout preserved")
    if run(["git", "-C", path, "status", "--porcelain"], capture=True):
        raise SetupError("Workbench checkout has local changes; preserved")


def check_binding(profile, python):
    result = run([python, profile / "local/workbench/scripts/hermes-codex-token",
                  "--binding", profile / "local/workbench-subscription.json", "--check"], capture=True)
    status = json.loads(result)
    if status.get("status") not in {"ready", "refresh_needed"}:
        raise SetupError("Local subscription binding is not ready")
    return {k: status[k] for k in ("status", "account_bound", "refresh_performed")}


def shell_exec(python, script):
    return "#!/bin/sh\nexec " + shlex.join([str(python), str(script)]) + ' "$@"\n'


def configure(profile, codex_home, hermes, *, check=False):
    profile = profile.expanduser().absolute()
    if profile.is_symlink() or profile.resolve() != profile:
        raise SetupError("Use the real installed profile path, not a symlink")
    if profile.parent.name != "profiles" or (profile / ".git").exists():
        raise SetupError("Run this on an installed profile under a Hermes profiles directory, never the source repo")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", profile.name):
        raise SetupError("Invalid profile name")
    if not (profile / "distribution.yaml").is_file():
        raise SetupError("Install this distribution with hermes profile install first")
    for relative in ["local", "local/bin", "local/workbench", "plugins", "config.yaml"]:
        if (profile / relative).is_symlink():
            raise SetupError("Device setup paths must not be symlinks")
    lock = read_json(profile / "setup-lock.json")["workbench"]
    if not re.fullmatch(r"[0-9a-f]{40}", lock["commit"]):
        raise SetupError("Invalid Workbench pin")
    python = Path(sys.executable).resolve()
    workbench = profile / "local/workbench"
    receipt = profile / "local/device-setup.json"
    binding = profile / "local/workbench-subscription.json"
    plugin = profile / "plugins/agent-workbench"
    if check:
        verify_workbench(workbench, lock)
        return check_binding(profile, python)

    codex_home = codex_home.expanduser().resolve()
    account = local_account(codex_home)
    expected = {"expected_account_id": account, "codex_home": str(codex_home)}
    if binding.exists() and read_json(binding) != expected:
        raise SetupError("Account or Codex home changed; existing binding preserved. Install a separate profile to rebind")
    template = (profile / "templates/config.json").read_text()
    if not receipt.exists() and (profile / "config.yaml").read_text() != template:
        raise SetupError("Profile config has local edits; preserved. Install a fresh profile name for initial setup")
    if os.path.lexists(plugin) and not (plugin.is_symlink() and plugin.resolve() == workbench.resolve()):
        raise SetupError("Existing Workbench plugin path is different; preserved")
    if not workbench.exists():
        workbench.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        run(["git", "clone", "--quiet", "--no-checkout", lock["repository"], workbench])
        run(["git", "-C", workbench, "checkout", "--quiet", "--detach", lock["commit"]])
    verify_workbench(workbench, lock)
    private_write(binding, encoded(expected))
    status = check_binding(profile, python)
    if receipt.exists():
        existing = read_json(receipt)
        if existing.get("workbench_commit") != lock["commit"]:
            raise SetupError("Setup version changed; review the upgrade instructions before changing the pinned plugin")
        if existing.get("complete"):
            return status
    else:
        config = json.loads(template)
        provider = config["providers"]["chatgpt-subscription"]
        provider["key_cmd"] = shlex.join([str(python), str(workbench / "scripts/hermes-codex-token"),
                                         "--binding", str(binding)])
        provider["extra_headers"] = {"ChatGPT-Account-ID": account}
        init = profile / "local/terminal-init.sh"
        config["terminal"]["shell_init_files"] = ["~/.profile", "~/.bash_profile", "~/.bashrc", str(init)]
        init_text = (profile / "templates/terminal-init.sh").read_text()
        init_text += '\nexport PATH=' + shlex.quote(str(profile / "local/bin") + ':' + str(python.parent)) + ':"$PATH"\n'
        private_write(init, init_text)
        for name in ["agent-workbench", "hermes-codex-token"]:
            private_write(profile / "local/bin" / name, shell_exec(python, workbench / "scripts" / name), 0o700)
        # A stable Python selection for native tools, including Linux machines with python3 only.
        for name in ["python", "python3"]:
            private_write(profile / "local/bin" / name, "#!/bin/sh\nexec " + shlex.quote(str(python)) + ' "$@"\n', 0o700)
        launcher = "#!/bin/sh\nexport HERMES_HOME=" + shlex.quote(str(profile.parent.parent)) + "\nexec "
        launcher += shlex.join([str(hermes), "--profile", profile.name]) + ' "$@"\n'
        private_write(profile / "local/bin/hermes-astra-ultra", launcher, 0o700)
        private_write(profile / "local/original-config.yaml", template)
        private_write(profile / "config.yaml", encoded(config))
        private_write(receipt, encoded({"workbench_commit": lock["commit"], "complete": False}))

    plugin.parent.mkdir(exist_ok=True, mode=0o700)
    if not os.path.lexists(plugin):
        plugin.symlink_to(workbench, target_is_directory=True)
    env = dict(os.environ, HERMES_HOME=str(profile.parent.parent))
    run([hermes, "--profile", profile.name, "plugins", "enable", "agent-workbench", "--no-allow-tool-override"], env=env)
    (profile / "config.yaml").chmod(0o600)
    private_write(receipt, encoded({"workbench_commit": lock["commit"], "complete": True}))
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-dir", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
    parser.add_argument("--check", action="store_true", help="Read-only pin and subscription metadata; no refresh or model call")
    args = parser.parse_args(argv)
    try:
        if os.name != "posix" or sys.version_info < (3, 11):
            raise SetupError("macOS/Linux and Python 3.11+ are required")
        hermes = shutil.which("hermes")
        if not hermes or not shutil.which("git"):
            raise SetupError("Install Hermes and Git first; see README")
        status = configure(args.profile_dir, args.codex_home, Path(hermes), check=args.check)
        print(json.dumps({"device_setup": "checked" if args.check else "ready", **status}))
        return 0
    except (SetupError, OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        message = str(error) if isinstance(error, SetupError) else "Local setup failed; existing private data is not printed"
        print("setup-device: " + message, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
