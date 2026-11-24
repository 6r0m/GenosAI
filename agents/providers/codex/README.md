# Codex provider

[user-settings.json](user-settings.json) owns the machine-wide Codex permission defaults.
[settings.py](settings.py) applies or checks those composed fields through the installed Codex
app-server's native config API. [lifecycle.sh](lifecycle.sh) connects that owner to the shared installer and the
existing instruction and skill wiring.

Public defaults require approval on request and limit writes to the workspace. Private operator
choices belong in `config.local.jsonc` under `codex`: the optional `model` and
`model_reasoning_effort` preferences, plus any permission override. The same native writer applies
the composed policy and prints changes to owned fields before writing. Public defaults never select a
model, and only fields present in the composed policy are managed; an omitted optional field keeps its
native value. Removing one stops managing it and leaves the last written value until it is changed
natively.
Shared instructions guide the agent's behavior. The accident guards documented by
[the permission owner](../../permissions/README.md) are integrated separately by Claude Code and Pi;
this provider does not register deletion hooks for Codex. Those guards are not an OS security boundary.

Run from WSL:

```bash
bash agents/scripts/install.sh --provider codex
```

The selected install targets the current Linux/WSL host; add `--platform both` for native Windows too. It requires each platform's Codex
executable or npm command shim on its own PATH. A `bash` launched from Windows starts WSL without reading the login profile, so a Codex
installed under a user npm prefix is not on that PATH. WSL discovery then asks the account login shell once, only when the selected home
is that account home, and accepts a runtime only if the shell stayed in that home; an alternate or disposable home never runs login
initialization. A runtime that neither PATH exposes is reported as a partial failure. Windows discovery selects `.exe`, `.cmd` or `.bat`
entries and skips npm's extensionless Unix launcher. Command shims run through the native command
interpreter, with the selected Windows `CODEX_HOME` propagated across WSL interop.
Missing runtimes and refused settings are reported as partial failures; the independent instruction
and skill wiring is still attempted. It does not acquire or upgrade Codex.

The native writer changes only the composed top-level fields in each user's `config.toml`, preserving
unrelated models, providers, projects, Windows sandbox selection and comments. Editing the checkout
changes nothing by itself; the selected install projects the composed values into each native file.
It uses the native config version to reject a stale write and reads the result back. Matching defaults
produce `already current` without another config write. Config parse failures and managed restrictions
are reported; native error payloads and configuration contents are not printed. Existing
`default_permissions` or `sandbox_workspace_write` configuration refuses before writing because
those settings require an explicit reconciliation with the composed policy. Uninstall removes the
owned instruction and skill links and leaves user configuration in place.

GenosAI validates the optional model preferences only as non-empty strings and does not pin model IDs
or effort levels. A successful configuration write establishes only that the field was written: it
does not prove that the installed Codex or the signed-in account supports the selected model or
effort level.

These are defaults for newly initialized sessions. Project configuration, selected profiles, CLI
flags, an IDE's thread settings and managed requirements can override or constrain them. An active
thread is not reconfigured by installation. Start a fresh session after installation and inspect its
effective model and permissions with `/status`; changing a model or permissions selector in another
interface does not establish this thread's effective policy. Codex's [configuration precedence](https://learn.chatgpt.com/docs/config-file/config-basic)
and [sandbox documentation](https://learn.chatgpt.com/docs/sandboxing) define those native boundaries.

For a local configuration check without inference:

```bash
python3 agents/providers/codex/settings.py check "$HOME/.codex" --codex "$(command -v codex)"
```

[Settings tests](../../tests/test_codex_settings.py) exercise the native writer in a disposable home,
with synthetic configuration and no model requests. They cover repeated installation, preservation,
refusal of malformed TOML, and a native Windows command shim with spaces using an empty or conflicting
selected home. Deterministic tests cover version guarding, optional model selection, interpreter
selection, environment propagation and override handling.

For WSL-to-Windows installed-route acceptance, run from `agents/tests/`:

```bash
python3 -m unittest -v test_codex_settings.NativeCodexSettings.test_windows_command_shim_with_spaces_empty_home_and_conflicting_policy
```

This case must finish with `ok`. A `skipped` result leaves WSL-to-Windows shim execution unverified,
even when the overall suite reports success.

The config client completes the [native initialization handshake](https://developers.openai.com/codex/app-server/)
before config RPCs. Native Windows starts in its temporary directory; config RPCs explicitly select
the target home, so inherited cwd handles cannot pin that home. On exit it closes stdin and allows the native RPC drain before forcing termination.
A forced exit or unclosed response reader reports failure; it cannot be treated as a clean configuration
operation. A shutdown error can follow a completed config write: inspect the config through this owner
before retrying. The writer does not change or stop an unrelated native app-server.
