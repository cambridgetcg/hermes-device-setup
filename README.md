# Hermes on my devices

A public [Hermes profile distribution](https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions)
for the Astra Ultra setup, captured on 12 October 2026. Release 1.1.0 adds
settings verified on 26 October 2026. Install the same settings on macOS and
Linux; authenticate separately on each device.

It carries `gpt-6-astra`, `ultra` reasoning, a 60-turn limit, native local tools,
concise response guidance, disabled shared telemetry, a portable terminal setup,
and the exact Agent Workbench plugin revision. `ultra` maps to the provider's
`max` effort in the recorded Workbench integration; it is not an extra service
tier. Access to this model still depends on the receiving account.

Since 1.1.0 it also carries five tuned settings:

| Setting | Value | Why |
| --- | --- | --- |
| `providers.chatgpt-subscription.models.gpt-6-astra.supports_vision` | `true` | Images, including browser screenshots, reach the model directly instead of through an auxiliary describer, which misreported a colour in testing. |
| `providers.chatgpt-subscription.models.gpt-6-astra.context_length` | `872000` | The Codex model catalog's context window. Without it Hermes resolved 1,050,000 tokens from models.dev. |
| `compression.threshold` | `0.6` | Compaction starts near 523K tokens (0.6 × 872,000), about where it started before the window was corrected (0.5 × 1,050,000). |
| `browser.inactivity_timeout` | `900` | The 120-second default closed the browser while a long compaction was running. |
| `platform_hints.cli.append` | delegation guidance | Asks the model to hand bounded, independent work to `delegate_task` by judgement, not as a quota. The full text is in [config.yaml](config.yaml). |

Scope: these values were verified on one Mac with Hermes `73162b00`, the runtime
in setup-lock.json. Testing was about 30 probe calls at low reasoning effort in
isolated Hermes homes, plus one smoke run on a real profile. The smoke run showed
that the 872,000-token window and the delegation guidance load. It did not
measure how much the guidance changes delegation. Other devices, Linux, other
runtime revisions and long `ultra` sessions are not yet verified. The two model
keys apply only to `gpt-6-astra` on this provider. The compression, browser and
CLI keys apply to the whole profile.

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
2. This distribution is public, but setup clones the private Agent Workbench
   repository (`cambridgetcg/agent-workbench`) at its locked revision.
   Authenticate GitHub with access to that repository:

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
provider wiring. Configuration changes need an explicit migration; updating
the template alone does not change an existing device's settings (see
[Existing devices](#existing-devices)).

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

### Existing devices

A profile bound before 1.1.0 keeps its `config.yaml` through
`hermes profile update`, so it does not receive the new settings. Never use
`--force-config` on a bound profile: it restores the unbound template and loses
the account binding. Apply the five settings to the bound profile explicitly:

```sh
hermes profile update astra-ultra &&
hermes --profile astra-ultra config set providers.chatgpt-subscription.models.gpt-6-astra.supports_vision true &&
hermes --profile astra-ultra config set providers.chatgpt-subscription.models.gpt-6-astra.context_length 872000 &&
hermes --profile astra-ultra config set compression.threshold 0.6 &&
hermes --profile astra-ultra config set browser.inactivity_timeout 900 &&
hint=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["platform_hints"]["cli"]["append"])' \
  "$HOME/.hermes/profiles/astra-ultra/templates/config.json") &&
  hermes --profile astra-ultra config set platform_hints.cli.append "$hint"
```

The update refreshes the profile's `templates/config.json`, which holds the
exact delegation text; the last command reads it from there and writes nothing
if it is missing. Check each key with
`hermes --profile astra-ultra config get <key>`. For another profile name or a
custom Hermes root, change the name and path, or use the profile's
`hermes-astra-ultra` launcher in place of `hermes --profile astra-ultra`.
The commands stop at the first failure, including a declined update; rerun the
block once the update succeeds. Restart open sessions afterwards. Hermes reads
the browser timeout once when it starts, so only sessions started after the
change use it, and a resumed conversation keeps its stored system prompt, without
the delegation guidance, until its next compaction.

To move this migration between your own devices as reviewable work, an Agent
Workbench handoff can run the same commands with a check before and a verify
step after. The receiver runs `agent-workbench import FILE --project DIR`,
reviews `plan`, then starts `run` explicitly.

A profile installed with 1.0.0 but never set up (no `local/device-setup.json`)
has no binding to lose. After `hermes profile update`, its `config.yaml` no
longer matches the new template and setup refuses it as edited. Run
`hermes profile update astra-ultra --force-config` once, then setup.

### Settings kept off

These were tried or reviewed on runtime `73162b00` and left out on purpose:

- `web.search_backend: openai-native`: Hermes drops `web_search_call` items when
  it replays history, so after a search and a tool call the model loses its
  results and searches again until it runs out of turns.
- `checkpoints.enabled: true` for the whole profile: a checkpoint runs `git add -A`
  on the write target's directory before the write denylist is checked, so a
  refused write into a directory such as `~/.ssh` could still copy its files
  into the profile's checkpoint store. Use `--checkpoints` per launch inside a
  repository instead.
- Edits to `tools.tool_search.defer`: resumed sessions keep their stored
  `tool_search` description, which then disagrees with what the runtime allows,
  and the model spends whole rounds on calls that are refused.
- `compression.proactive_prune_tokens`: it fires once per compaction cycle
  rather than acting as a ceiling, and adds an extra cold cache refill.
- `providers.<provider>.extra_body.service_tier: priority`: this route still
  served the `default` tier, so the setting changes nothing here.

## GitHub, AgentTool, and handoffs

GitHub is the source and update channel. Installing this public repository
needs no GitHub login; setup still needs access to the private Workbench
repository. Native updates preserve each device's user data. For installation
without a GitHub fetch, clone an exact commit with `gh`, then run
`hermes profile install /path/to/clone --yes`; updates then read that local
checkout after you advance it. A Git bundle can carry the reviewed source by
USB, but Workbench and the runtime still need installation.

AgentTool's current `love-package/v1` is a public, registry-neutral npm-tarball
format. A Git-installed Python/Hermes profile distribution does not fit that
contract, so this repository does not publish an AgentTool package or upload
private state there. AgentTool can hold an explicitly chosen pointer to this
repository and a release tag, or an encrypted data workflow if needed. It is not
required to install this setup. A pointer only helps others find the
distribution: settings reach a device by installing it, or by the explicit
migration in [Existing devices](#existing-devices).

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

`config.yaml` and `templates/config.json` must stay byte-identical: setup
refuses an initial bind when the installed config differs from its template.
A test enforces this, and also that the template carries the tuned settings and
none of the settings kept off.

Only the source paths allowlisted in `.gitignore` belong in commits. Edit this
curated repo, never initialize Git in a live profile. Review and test changes,
commit, push, and tag releases. Do not add `local/`, account headers, auth files,
copied home directories or runtime exports.
