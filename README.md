# Hermes on my devices

A private [Hermes profile distribution](https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions)
for the Astra Ultra setup, captured on 12 October 2026. Install the same settings
on macOS and Linux; authenticate separately on each device.

It carries `gpt-6-astra`, `ultra` reasoning, a 60-turn limit, native local tools,
concise response guidance, disabled shared telemetry, a portable terminal setup,
and the exact Agent Workbench plugin revision. `ultra` maps to the provider's
`max` effort in the recorded Workbench integration; it is not an extra service
tier. Access to this model still depends on the receiving account.

The runtime reference and enforced Workbench pin are in [setup-lock.json](setup-lock.json).
Hermes itself is a prerequisite: this distribution does not upgrade or downgrade
an installed runtime. The source Mac used Hermes commit
`73162b00eefde3794bed0afb53d84a19c0eed230` from
[cambridgetcg/hermes-agent](https://github.com/cambridgetcg/hermes-agent).

## Set up another Mac or Linux machine

1. Install Git, GitHub CLI, Python 3.11+, [Hermes](https://hermes-agent.nousresearch.com/docs/getting-started/quickstart),
   and Codex CLI. `hermes profile install --help` and `hermes plugins enable --help`
   must work. Use your normal Hermes installer; do not copy this Mac's Python
   environments or launchers. Native Windows is outside this package's support;
   Linux under WSL2 can use the Linux route.
2. Authenticate GitHub with access to both private repos:

   ```sh
   gh auth login
   gh auth setup-git
   ```

3. Sign in to Codex with ChatGPT **on this device**. The existing Workbench bridge
   requires file-backed storage. Set `cli_auth_credentials_store = "file"` in
   your Codex `config.toml`, then run `codex login`. On a headless device use
   `codex login --device-auth` if enabled for your account. See the
   [official authentication and storage guidance](https://learn.chatgpt.com/docs/auth#credential-storage).
   Keep that storage setting for future refreshes. The helper cannot use a
   keyring-only cache and does not switch your storage automatically.
4. Install and bind the profile:

   ```sh
   hermes profile install https://github.com/cambridgetcg/hermes-device-setup.git --yes
   python3 "$HOME/.hermes/profiles/astra-ultra/scripts/setup_device.py"
   hermes --profile astra-ultra
   ```

The setup command checks out the locked private Workbench repository, validates
the local account binding without refreshing, and enables the native plugin.
It makes no model request. It preserves existing profiles; if `astra-ultra`
already exists, install with `--name astra-device` and run the script from that
profile's directory. For a custom Hermes root, use its actual `profiles/<name>`
path. `--codex-home /absolute/path` selects a nondefault local Codex home.

The initial template uses `key_cmd: false` (the shell command `false`) until
device setup succeeds, so it has no embedded credential or guessed account.
Do not start chatting before binding it. During a later chat the existing
Workbench token helper can request a Codex-owned refresh when needed; its
normal output is a private credential pipe and must never be printed.

## What lives where

| Shared source | Device-local state |
| --- | --- |
| Profile settings and response style | Login tokens, account binding and account header |
| Workbench Git pin and setup helper | Workbench checkout in `local/workbench/` |
| Terminal initialization template | Python path, shell initialization and CLI shims |
| Source version metadata | Memories, sessions, databases, logs, caches and project paths |

The profile's `local/bin/` is on PATH inside its native terminal. Workbench can
therefore invoke `hermes-astra-ultra` within that profile. From another terminal,
use `hermes --profile astra-ultra`, or add that profile's `local/bin` to PATH
yourself. Setup does not replace global commands or edit shell startup files.

This captures the harness baseline. Learned/private skills, personal history,
the home directory's instructions, local project integrations, MCP credentials,
scheduled jobs, gateway services and messaging connections are not included.
Built-in skills follow the receiving Hermes installation. Optional web, voice,
browser and external tools may need their own dependencies or logins.

## Update and check

```sh
hermes profile update astra-ultra
python3 "$HOME/.hermes/profiles/astra-ultra/scripts/setup_device.py" --check
```

Native updates preserve `config.yaml` and user data by default. They update the
distributed instructions, templates and setup code. Do not use `--force-config`
on a bound profile: that restores the unbound template and loses its local
provider wiring. Future configuration changes need an explicit migration;
updating the template alone does not change an existing device's settings.

Repeat setup preserves completed configuration. It refuses a changed account,
a dirty Workbench checkout, a conflicting plugin, or edited configuration before
initial binding. A failed plugin activation can be resumed by rerunning setup.
If a future release changes the Workbench pin, install a separate profile name
to test that release; this version does not update an existing pinned checkout.
Keep the old profile and its history until the new one works.

The read-only `--check` reports only local binding/pin metadata. `ready` means
the cached token passes local expiry/account checks, not that the provider has
accepted a request. A real conversation on the receiving device is the final
model and tool check. This release does not claim that another physical device
has already been verified.

## GitHub, AgentTool, and handoffs

GitHub is the source and update channel. Native Hermes distributions already
support private Git authentication and preserve each device's user data.
For installation without a GitHub fetch, clone an exact commit with `gh`, then
run `hermes profile install /path/to/clone --yes`; updates then read that local
checkout after you advance it. A Git bundle can carry the reviewed source by
USB, but Workbench and the runtime still need installation.

AgentTool's current `love-package/v1` is a public, registry-neutral npm-tarball
format. A private Python/Hermes distribution does not fit that contract, so this
repository does not publish an AgentTool package or upload private state there.
AgentTool can later hold an explicitly chosen pointer or encrypted data workflow
if needed. It is not required to install this setup.

For selected work context, use Agent Workbench's `note`, `export`, and `import`
commands, review the exported text, and transfer it separately. That is an
explicit task handoff, not synchronization of native conversations. Avoid a
blanket `hermes profile export` for this purpose: exports can include private
memory and session history, while this distribution is curated source.

## Validation and maintenance

```sh
python3 -m unittest discover -s tests -v
```

Tests use synthetic auth and local Git fixtures. `tests/native_smoke.py` is a
separate explicit integration check, run with an already installed Hermes
Python environment and `--hermes-source` / `--workbench-source` arguments. It
uses a temporary Hermes root, enables the real plugin, checks the real bridge
with synthetic credentials, and verifies that a native update preserves local
configuration and user-data sentinels. It does not call a model.

Only the source paths allowlisted in `.gitignore` belong in commits. Edit this
curated repo, never initialize Git in a live profile. Review and test changes,
commit, push, and tag releases. Do not add `local/`, account headers, auth files,
copied home directories or runtime exports.
