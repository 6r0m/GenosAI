# Local browser setup

The browser skill consumes optional connection metadata from the AI checkout's
`config.local.jsonc`. This file is ignored by Git and must contain references only,
never cookies, tokens, passwords, or exported browser state. Authentication material
stays with its existing secret-store owner.

Run `make init` at the GenosAI checkout root to create `config.local.jsonc`.
Existing `config.local.json` remains supported; keep one file only.
The example leaves the browser disabled. No shared repository catalogue or user-name
variables are needed: installation owns skill links, and the browser owner supplies
only the connection details required here.

## Locate the configuration

Resolve the installed skill file to its canonical source before walking its parents.
Do not use lexical `../../` through a Windows skill junction. With Python on the
same platform as the installed skill path:

```bash
python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve(strict=True).parents[3])' "<installed-drive-browser>/SKILL.md"
```

On native Windows, use `python` and a native path. Native junction behavior requires
native acceptance; a WSL symlink test does not establish it. A project-owned browser
runbook may instead supply the connection and authentication procedures directly.

## Local connection fields

From that checkout, load through `agents/config.py` (its `load()` function returns
the parsed object alongside the raw bytes; never print either). This owner supports
JSONC comments and legacy strict JSON and refuses ambiguous dual files. Missing configuration, a missing `browser` object,
or a null/missing `browser.cdp_url` means browser automation is unconfigured. Report
the missing setup; do not guess a port, scan endpoints, launch, or attach. Invalid
JSON/JSONC or invalid field types must be corrected before use, without guessing defaults.

The optional `browser` object holds:

| Field | Meaning |
|---|---|
| `cdp_url` | Explicit loopback CDP endpoint, or null to disable browser automation |
| `agent_profile` | Dedicated automation profile paths keyed by platform, such as `win`, `wsl`, or `linux`; verify the selected endpoint belongs to this profile |
| `launcher` | Optional command owned by the local browser integration; inspect its instructions/effects before running it, and attach rather than relaunching an existing owner |
| `auth.cookies_dir` | Optional reference to the existing cookie-vault owner; not permission to read/export its contents |
| `auth.importer` | Optional existing session importer; use its own documented interface and success condition |
| `auth.staging_dir` | Optional platform-specific staging location required by that importer |

These are integration references, not executable setup defaults. Paths must be
absolute native paths for the platform consuming them; cross-platform variants use
an object keyed by platform. Local commands remain subject to current task authority.
Do not print the file or copy its values into tracked documentation or diagnostics.

## Connection and session ownership

Use Chrome with a dedicated agent profile. Never use the operator's daily profile or
attach to an endpoint owned by an unrelated integration, even if it is reachable.
Keep CDP on loopback; do not expose it through LAN listeners or port forwarding.
On WSL, determine which platform owns Chrome: Windows loopback may require Windows
interop rather than a Linux client. Do not assume a particular WSL gateway address.

Session recovery is optional. If an existing importer is configured and the task
authorizes access to the exact secret store, follow that owner's runbook. Where it
requires staging, delete staged plaintext immediately after success or failure. If
no importer is configured, report the missing integration instead of assuming another
checkout or copying its auth code. CAPTCHA/MFA and account login/recovery stay human
steps. Browser snapshots, traces, and CLI output may contain authenticated data;
keep `.playwright-cli/` and `.playwright/` ignored in every working repository.
