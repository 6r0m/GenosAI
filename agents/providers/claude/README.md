# Claude Code provider

Owns Claude Code's user settings on both sides of the machine. [user-settings.json](user-settings.json)
holds component defaults. [Shared local configuration](../../configuration.md) composes private
additions; this owner generates platform-correct hook paths. The install interface applies the result
to each side's `~/.claude/settings.json` through a plan the operator confirms.

| file | owns |
|---|---|
| [user-settings.json](user-settings.json) | the owned keys and their values; the one place to change them |
| [settings.py](settings.py) | source `validate`, `check` (the plan), `apply` (confirm, then write), `hook` (the session-start drift check) and `registered-hook` (judging the hook a live file registers) |
| [session-check.sh](session-check.sh) | the session-start adapter that turns the hook result into a warning or silence |
| [lifecycle.sh](lifecycle.sh) | the `claude` lifecycle handler: generic links per platform, then one settings plan for both |

## What is owned

Every top-level key in `user-settings.json` is owned and replaced with its composed value. Any other key in a live file
belongs to Claude Code or to that side, and survives every apply in its position. Compaction tuning
(`autoCompactWindow`, idle compaction, pre-computed summaries) is deliberately not owned, so Claude Code's
model-tuned defaults apply.

These are user-level defaults, not each session's effective settings. Something with higher precedence
still wins for its own sessions:

- orchestra's per-role `--model`, `--effort` and `--permission-mode`. Its `dontAsk` and `plan` modes are
  deliberately stricter than `bypassPermissions`.
- VS Code's `claudeCode.initialPermissionMode`, which sets the mode a VS Code chat starts in. Keep it equal
  to the tracked `permissions.defaultMode` on both sides.
- a repository's own `.claude/settings.json` or `.claude/settings.local.json`.

An owned value always masks the same key in `~/.claude.json`, so the legacy `autoCompactEnabled` there
does not matter.

## Two writers

Claude Code writes the same file, for example on `/model`, `/config`, `/effort`, `/autocompact` and
plugin toggles. A change it makes to an owned key lasts until the next install. Meanwhile each new
session's warning names the key, and the next install shows it in the plan before resetting it.

## Changing a setting

Edit `user-settings.json` for a shared default, or the ignored local input for a personal addition,
then run, from WSL:

```bash
bash agents/scripts/install.sh --provider claude
```

- **One plan for both sides.** Install validates the tracked file and every reachable side before writing
  any of them. It prints one line per changed field, then the plan id, and asks once in a terminal.
- **Without a terminal.** Run `settings.py check` for the plan and its id, then
  `install.sh --provider claude --approve <plan id>`.
- **The id binds the approval.** It covers public/local source inputs, projection code and source location,
  generated hook commands, and each side's name, path and full content.
  If anything changed since that plan, including a Claude Code save while it was being reviewed, install
  writes nothing and asks for a fresh plan.
- **Writes and backups.** Each side's write is atomic. The previous file is kept beside it as
  `settings.json.<timestamp>.bak`, because it holds every `env` value the live file held. An unchanged side
  is not rewritten.
- **Who can read them.** On WSL the backup is created owner-only (`0600`) whatever the umask, and the new file
  keeps the old mode. On Windows, mode bits do not apply: a file written from WSL inherits the ACL of
  `%USERPROFILE%\.claude`, so the backup and the replaced file get the same access list as the live file.
  `icacls` showed the three identical.
- **A failed side.** If one side fails to write, install stops, names the sides applied and not applied,
  and exits non-zero. Nothing is rolled back: run it again once the cause is fixed. A common cause is a
  Windows Claude Code window holding the file open.
- **What the plan never prints.** Values under `env`, values whose field name looks like a credential, and
  free-form command lines all show as `<redacted #hash>`. The hash still shows when one changed.

Before link creation or a settings plan, install refuses invalid local input and a tracked file in either
of two cases. The first is a file that fails the
guard posture in [check-registration.py](../../permissions/check-registration.py). The second is a file whose
session-start warning is not the expected managed-path template: checked by its structure, not by keywords, with a JSON
`systemMessage` fallback and a timeout of at most 5 s. A broken tracked file can therefore never strip the
guards from both sides at once, or put a hook's plain text into every session. Uninstall leaves both
settings files as they are. `@AGENTS_ROOT@` is expanded by this writer into a shell-quoted canonical
path; it is not an environment variable or a native Claude placeholder. Native Windows generation from
WSL uses `wslpath`; a path that cannot be resolved refuses rather than installing a guessed command.

## Session-start warning

The tracked `hooks` registers a `SessionStart` command that runs [session-check.sh](session-check.sh).
That adapter calls `settings.py hook` through the shared interpreter launcher
[run-guard.sh](../../permissions/run-guard.sh).

- **Clean side:** prints nothing. A `SessionStart` hook's plain stdout can reach the model's context.
- **Drift:** prints only a JSON `systemMessage` naming the differing keys, never their values. The model
  does not see a `systemMessage`.
- **Failure:** anything that is not one of those two answers becomes a "could not run" warning. That
  covers a missing interpreter or script, a crash, and the launcher's `{}` fallback. If the adapter itself
  is missing, the command's `|| printf` still warns.
- **Still silent in a session:** the hook not being registered at all, and Claude Code killing it at its
  5 s timeout. `settings.py registered-hook` covers both. [selfcheck.sh](../../permissions/selfcheck.sh)
  runs it on each side: it runs the command that side registers and fails unless it exits 0 with no
  output within its timeout. A run costs about 0.15 s on WSL and 0.55 s on Windows, so a timeout means a
  hang.

## What a session actually runs with

This costs nothing: it calls no model.

```bash
claude -p "/context" --output-format stream-json --verbose --no-session-persistence
```

- The `system/init` event shows `model` and `permissionMode`.
- The context table shows an `Autocompact buffer` row only when auto-compact is on.
- The `SessionStart` `hook_response` shows the warning's output, which is empty on a clean side.
- Run it with `claude.exe` from a Windows directory for the Windows side.
