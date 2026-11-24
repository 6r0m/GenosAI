# Pi runtime

[profiles.json](profiles.json) supplies disabled public defaults. The ignored root `config.local.jsonc`
`pi` object owns private connection choices; [configuration](../../../configuration.md) owns composition. [configure.js](configure.js)
owns its schema, pinned-catalog validation and the owned native authentication/model projection;
[launch.sh](launch.sh) resolves the active profile through `configure.js` and dispatches the pinned native CLI.
The pinned Pi release requires Node 22.19 or newer; the lifecycle configuration selects the interpreter
used on each platform.
On Linux/WSL, a missing preferred interpreter falls back to `node` on `PATH`; acquisition uses
its sibling `npm`, or `npm` on `PATH`, with package engine requirements enforced. Native package
install/remove and managed launch disable Pi telemetry explicitly.

## Contents

- Change a Pi connection
- Native and compatible models
- DeepSeek Flash compaction
- Repository retry policy
- Pinned runtime
- Verify

## Change a Pi connection

Installation can precede connection setup:

```bash
make install PROVIDER=pi PLATFORM=both RUNTIME=1
pi-sot --version
```

Use `PLATFORM=host` for Linux/WSL only. Both-platform installation requires Linux Node/npm and native
Windows Node/Git Bash. Missing prerequisites refuse with guidance; installation never installs system Node.
Windows instruction file links need Developer Mode or the installer's explicitly reported elevated batch.
An unconfigured installation registers the local package without creating managed auth/model
projections. The native CLI may initialize an empty `auth.json`; that empty store contains no credential
reference or provider selection.
An existing managed connection cannot be cleared by replacing its profile with disabled defaults.

Before starting a model session, copy [the connection example](profiles.example.json) into the private root `pi` object,
choose your own provider/model, and supply the referenced key. Public defaults intentionally
configure no connection. Install the selected integration before using its default or an explicit profile:

```bash
pi-sot
pi-sot --profile example
pi-sot --profile example --version
```

The strict JSON example is copy-ready profile data, not a second settings file. Its fields are:

| Field | Meaning |
|---|---|
| `active` | Exact local profile ID selected by default |
| `profiles.example.provider` | Provider ID from the pinned native catalog |
| `profiles.example.model` | Model ID from that same provider/catalog |
| `profiles.example.credential` | File reference under `pi.secret_root`, never the key value |

Optional profile fields are `thinking`, `endpoint`, `api` and `compatibleModel`. For example,
a separately authorized compatible server can use this **synthetic** profile definition:

```json
{
  "provider": "example-service",
  "model": "example-model",
  "credential": "secrets/compatible.key",
  "endpoint": "http://127.0.0.1:8000/v1",
  "api": "openai-completions",
  "compatibleModel": {
    "name": "Example model",
    "reasoning": false,
    "input": ["text"],
    "contextWindow": 8192,
    "maxTokens": 1024
  }
}
```

Place that under another `profiles` ID and select it through `active` or `--profile`.
This example neither starts a server nor proves that any server implements the protocol.
For catalog-backed profiles, omit `compatibleModel`; omit `thinking` to inherit the
native default, or choose a level verified by the pinned model's capability check.
An endpoint override does not authorize contacting it. Credential files for inactive profiles
are not required. Do not paste credentials into endpoints or add authorization headers.

`--profile <id>` (also `--profile=<id>`) must precede native Pi arguments. IDs are exact keys from the composed private profiles; there is no alias table. The selector is consumed by the managed
launcher and never rewrites that file or its `active` default. Remaining native arguments, including
values containing `--profile` and arguments after `--`, are forwarded unchanged. An invalid, missing
or repeated leading selector refuses before configuration mutation or native dispatch.

Managed startup uses one config-owner installation to validate and project one parsed SOT snapshot,
then launches the exact selection returned from that operation. Edits after that read apply to later
launches. Read-only consumers retain the separate `resolve` operation.

To change the persistent default or a route definition, edit `active` and the profile fields (`provider`, `model`, `credential`, optional `thinking`,
optional `endpoint` and `api`) in the ignored local `pi` object. Start a
new session through `pi-sot` (native Windows also exposes `pi-sot.cmd`). The launcher re-reads the profile,
reconciles owned native configuration and passes provider/model, the profile's optional startup
thinking level and the selected profile's native agent directory explicitly to the pinned CLI. An omitted
`thinking` leaves Pi's native default in charge, and an explicit CLI override is session-local.
Each used profile has its own native directory beneath the registry-owned base's `profiles/`:
authentication/model projections, mutable native settings, caches and writer lock are isolated.
Distinct profiles can run concurrently, including the same provider/model with different keys or
endpoints. Changing one profile's own connection requires restarting that profile's sessions.
The runtime is installed once. A first profile launch registers the common local package and links
canonical instructions; later launches verify ownership. File-link permissions must be available on
Windows; an unavailable canonical link refuses before native dispatch.
Native preferences are profile-local; base preferences and foreign packages are not copied.
Set `"hide_thinking_block": true` in the private root `pi` object to collapse thinking blocks in
managed profiles. The wrapper writes this default when a selected profile has no saved display
preference. Pi saves changes made with Ctrl+T per profile. This setting controls transcript display.
Pi also caches downloaded `fd` and `rg` executables in each profile's native `bin/` directory.
Managed launches, reapplication and uninstall/reinstall preserve these caches. A profile or
platform without a cached tool or a matching executable on `PATH` can download its own copy;
Windows and WSL keep separate native executable caches.
After a bootstrap failure, fix the reported local prerequisite and rerun the same profile.
Partial owned provisioning remains recoverable; a failed registration never dispatches the assistant CLI.
Raw `pi` uses Pi's native defaults instead of this managed route.
`pi-sot list` inspects the configured active profile; `pi-sot --profile <id> list` inspects that
profile independently of the default. Inspection does not require its credential file or provision
missing state: an uninitialized profile refuses with guidance to launch it first. With disabled
connection defaults, bare `list` inspects the existing base directory. An absent base also refuses.
The native command stays first. Native temporary read locks leave no persistent artifacts;
explicit native project-trust decisions retain their ordinary mutation semantics. Managed launch refuses
native auth, configuration, MCP and package mutations: change the SOT for connections and use the
shared install/uninstall interfaces for lifecycle operations. Raw `pi` remains the explicitly unmanaged
route; its writes can cause managed ownership drift and a subsequent managed launch refusal.
Supported API-key native providers and compatible endpoints require profile data only; other
authentication or unsupported protocols need an explicit adapter when a real use case requires one. The package manifest owns skill/extension discovery, independently of model connection choice.

To switch between configured routes, pass the desired profile ID or edit `active` for a persistent
default, then start a new managed session. Each route keeps its own native provider/model, credential and
effort together; another profile's projections are independent. Profile IDs have no built-in
meaning; the same schema handles new route entries. Switching does not require an
installation or a code change, and credentials for inactive routes are not required.

All managed profiles link `sessions/` to the existing base session directory, preserving native
working-directory grouping and conversation discovery. Native explicit session-location overrides
retain precedence. History records model selections, not this wrapper's profile identity: resuming
an A conversation through profile B uses B's connection for the selected model. Select A to use
A's endpoint/key. There is no session-to-profile index; do not edit one conversation concurrently.
Pointing `PI_CODING_AGENT_SESSION_DIR` at the parent of the grouped history does not preserve this
discovery layout and is not installed by the launcher.

Before reapplying the Pi lifecycle to a legacy shared projection, finish its sessions once.
Normal profile launches leave legacy base auth/models intact. Explicit lifecycle reapplication
retires only unchanged owned legacy entries after profile provisioning; base foreign state survives.
Removal visits owned profile records, including retired IDs, without sweeping other directories.
Disabled setup checks only valid profile IDs and refuses directory or ownership-file links before
reading their state. Native package/link removal precedes connection projection cleanup; if native
package removal fails, that profile's auth/models and ownership record remain unchanged for a normal retry.
Session links require the exact expected base-history target; cleanup removes the link/junction
alone. Tampered links or ownership refuse. Native preferences, history and original keys survive.

## Native and compatible models

Managed profiles prefer the model's original provider whenever practical. Direct profiles connect
to first-party APIs; there is no automatic broker fallback. Broker routes
belong to explicit discovery/testing or an explicit exception when first-party access is unavailable
or inferior. Additional routes can be defined in the private config when access is approved.
The private profile owns route IDs, selected providers, endpoints and startup efforts.

A profile without `compatibleModel` must name a model in the pinned native catalog. A compatible
profile instead supplies native model metadata in `compatibleModel` and requires explicit `endpoint`
and `api`. [The profile validator](configure.js) owns the accepted metadata surface; provider/model
IDs, endpoint, API and credentials retain their existing profile owners. A compatible definition
cannot replace a built-in provider. Unknown metadata/map/compat keys and embedded
auth or headers refuse. The installed pinned schemas validate native field types, and Pi's capability
function validates the selected thinking level. Before runtime acquisition only structural validation
is available; native validation follows acquisition before wiring. Only the active credential is required.

The projector emits an owned native model definition with Bearer auth for a compatible provider;
the existing `auth.json` command reference remains the credential owner. Pi serializes requests,
thinking, streamed responses and tool history. No provider extension is needed for supported APIs.
Compatible definitions without pricing metadata use Pi's zero cost estimates; those figures do not
establish actual billing. The provider's billing remains authoritative.

Native catalog definitions supply their model limits and pricing. Bounded transport checks do not
establish full-window acceptance or service billing.

## DeepSeek Flash compaction

For a managed `deepseek/deepseek-flash` profile, [configure.js](configure.js) reserves 30% of the
pinned model's context window, rounded up. Pi can start automatic compaction when its estimated
usage exceeds the remaining 70%, using its existing summarization and retention settings.

The wrapper owns only that model's `reserveTokens` field in the profile's native settings. A
conflicting value refuses projection. The profile retains the model-specific reserve and ownership
record through reconfiguration or removal. A project can override the same model field through
Pi's native project settings.

## Repository retry policy

[retry-policy.json](retry-policy.json) owns the agent retry policy shared by managed profiles.
Edit that file to change the policy; [configure.js](configure.js) validates its complete field set,
boolean enablement, retry count from 1 to 10, and delays from 1 to 900,000 milliseconds, with the
delay cap at least the base delay. Native Pi owns retry scheduling and error classification.
Provider retries (`retry.provider.*`), other native preferences and project settings remain native.

Selected-profile installation, lifecycle reapplication and ordinary `pi-sot` launch reconcile the
policy after native package registration. Each profile receives it independently when selected;
inactive and retired profiles are not swept. Source updates alone do not change native settings.
Initialization, validation, package inspection (`list`) and disabled setup do not apply the policy.
Runtime acquisition preserves profile settings and applies the policy after the runtime is ready.

Reconciliation uses the pinned runtime's settings lock and changes only the policy's named fields.
An identical policy leaves `settings.json` byte-identical. The existing ownership record keeps
only the last-applied policy snapshot. Unrelated native edits survive. A native value matching the
desired policy can be adopted, including recovery after settings were written but ownership
recording failed. Missing owned fields or values matching neither the recorded policy nor the
desired policy refuse before dispatch, with the conflicting `retry.<field>` named.

For a conflict, stop editing that profile concurrently, inspect its `settings.json`, the
`retryPolicy` snapshot in `agents-sot-state.json`, and the repository policy. Restore the conflicting
field to its recorded value, or deliberately set it to the repository's desired value, then rerun
the selected launch or install. For an older profile with no snapshot, absent managed fields can
be initialized; differing existing values require the same explicit reconciliation. Do not delete
the ownership record to bypass other ownership checks. Uninstall leaves retry values and unrelated
native preferences in place and retains the snapshot for repeatable reinstallation.

Native project-level `.pi/settings.json` overrides retain Pi's normal precedence and can override
these profile defaults. Existing live sessions keep their loaded settings; start a new managed
session to load an updated policy. Errors outside Pi's terminal-error classifier can consume the
bounded agent retry budget; GenosAI does not add another retry loop.

## Pinned runtime

Runtime acquisition consumes [install-lock](install-lock/package.json): the provider installer copies the
generated `package.json` and `package-lock.json` into the runtime prefix and runs `npm ci`, so neither the
CLI release nor the transitive `@earendil-works/pi-ai` capability source floats inside a caret range.
`PI_PACKAGE` in [the lifecycle configuration](../../../lifecycle/providers.conf.sh) stays the operator
decision; the lock is its derived artifact. After a pin bump, regenerate it — the generator derives
`package.json` from `PI_PACKAGE` and lets npm pin the tree:

```bash
bash agents/providers/pi/runtime/install-lock/generate.sh
```

[The provider tests](../../../tests/test_install.py) fail closed when a bumped pin leaves the lock stale.

Close Windows Pi sessions before an upgrade: loaded native modules can prevent npm from replacing
files. An interrupted acquisition can leave a partial runtime; repeat the selected Pi installation
through [the lifecycle interface](../../../lifecycle/README.md) after releasing the file lock.

A managed launch refuses when the installed coding-agent version differs from `PI_PACKAGE`, prints the
reinstall command and never updates a runtime itself. The Windows runtime prefix is a dedicated directory
(`AppData/Roaming/pi-sot`) rather than npm's shared global prefix, so lock-based installation cannot remove
other globally installed packages; the `pi-sot.cmd` shims stay on the global `PATH`.

Profile validation is fail-closed: unknown keys, malformed references and an undefined `active` refuse
before any write. When the pinned runtime is available, validation also proves the selected model exists
in its catalog, that a declared `api` matches the catalog, and that a declared `thinking` level is
supported by that model through Pi's own `getSupportedThinkingLevels()`. The pinned Pi dependency is
located in the same place the native runtime resolves it from, whether npm nests it under the
coding-agent package or hoists it into the install prefix — the SOT never lets Pi silently
clamp a level and never duplicates provider compatibility rules.

Pi can restore newer cached model catalogs and refresh them independently of its npm version.
Managed configuration projects the selected model's bundled definition into the owned `models.json`
entry, with any SOT endpoint override applied. Pi's native configuration precedence keeps that
definition above catalog overlays, so the selected model's dispatched endpoint and reasoning
metadata match preflight. This is a derived projection, not another model catalog to maintain.
Other catalog entries retain Pi's normal refresh behavior. A foreign provider entry in `models.json`
refuses managed launch even when the profile has no endpoint override; it is never overwritten.

Credential files belong to [the local secret owner](../../../../secrets/README.md). Profiles contain file
references only. Platform-specific auth commands defer key access to Pi; no plaintext key is copied to
tracked config or logs, and no global API-key environment variable is installed. Installation does not require a credential file or create a placeholder. Model-session launch requires a
readable regular credential file; validation uses metadata without reading its contents.
Pi install telemetry is disabled. Provider account budgets remain operator-managed.

Each profile's `auth.json` and optional `models.json` are projections. A SOT ownership record identifies
managed entries and common-resource references. Selecting another profile leaves these files alone.
Reconfiguring the same profile replaces its obsolete owned entries. Foreign entries, edited managed values, malformed
JSON and collisions are never overwritten. A bounded directory lock coordinates concurrent writers;
validated files are promoted individually through atomic replacement. If a write fails between files,
inspect the reported ownership drift before repairing it; this is not a multi-file transaction.
Read-only validation checks the same profile schema/capability and projection ownership/collision rules
without creating files, directories or locks. Writers repeat those checks while holding the directory lock.

## Verify

Run [provider tests](../../../tests/providers/pi/README.md) on both native platforms. Managed
`pi-sot --version` and `/guard-status` check the installed route without generating an assistant response.
The native SDK loader check proves package discovery and permission startup without calling a model.
