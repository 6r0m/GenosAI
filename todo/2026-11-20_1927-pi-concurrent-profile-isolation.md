# Isolate concurrent Pi connection profiles

**Status:** REVIEW REQUIRED  
**Scope:** Pi managed runtime, lifecycle, permission-path coverage and native acceptance  
**Stable documentation owner:** [Pi runtime](../agents/providers/pi/runtime/README.md)

## Contents

- [Goal](#goal)
- [Authority register](#authority-register)
- [Non-goals](#non-goals)
- [Verified evidence](#verified-evidence)
- [Current architecture and source of truth](#current-architecture-and-source-of-truth)
- [Problem and root cause](#problem-and-root-cause)
- [Decision](#decision)
- [Required invariants](#required-invariants)
- [Implementation tasks](#implementation-tasks)
- [Test-first and verification plan](#test-first-and-verification-plan)
- [Documentation plan](#documentation-plan)
- [Rollout and rollback](#rollout-and-rollback)
- [Completion criteria](#completion-criteria)
- [Review record](#review-record)

## Goal

Launching a second configured Pi profile must leave an existing session able to use its own
provider, model, endpoint and credential. Investigate native Pi behavior and propose a small,
maintainable GenosAI correction under D1–D2.

## Authority register

### Operator decisions

- **D1:** Investigate the Pi profile failure with `investigate-change` and put the implementation
  todo in GenosAI.
  - Effect: investigation and this single todo; no implementation or workstation cutover.
  - Reason: determine whether native Pi or the GenosAI integration causes the failure.
  - Date/source: operator request, 2026-11-20.
- **D2:** Prefer a KISS solution using the best practical industrial approach, if possible.
  - Effect: prefer a supported native boundary over a custom provider/session framework.
  - Reason: not stated.
  - Date/source: operator request, 2026-11-20.

### Operator gates

None open for this proposal. Implementation requires approval of this todo under D1.

### Working assumptions

- **A1 [ACTIVE]:** Preserve the existing schema's ability to name two profiles with the same
  provider and different keys/endpoints; concurrency should cover that case too.
- **A2 [ACTIVE]:** Native mutable preferences and caches may be profile-local. Common GenosAI
  instructions/skills/permission code and existing conversation history remain reusable.
- **A3 [ACTIVE]:** Isolation is between distinct profile IDs. Editing one profile's connection
  while its sessions run requires restarting those sessions; immutable per-invocation snapshots
  are outside this change.

## Non-goals

No Pi fork, runtime upgrade, provider aliases, proxy, daemon, process registry, session watchdog,
retry workaround, live provider request, new secret store or secret copying. No automatic merging
of arbitrary unmanaged native settings. No concurrent editing of the same conversation file.
No implementation of the separate optional-plugin/image-budget plan.

## Verified evidence

### Repository and native facts

| Evidence | Observation |
|---|---|
| [Runtime pin](../agents/lifecycle/providers.conf.sh) | Managed Pi is pinned to `@earendil-works/pi-coding-agent@1.5.2`; both installed managed platform runtimes reported that version. |
| [Launcher](../agents/providers/pi/runtime/launch.sh) | Every managed invocation sets `PI_CODING_AGENT_DIR` to the same registry-owned base and calls the projector before native dispatch. |
| [Projector](../agents/providers/pi/runtime/configure.js), `configure()` | Deletes all previously owned auth/model entries from its candidate, then inserts only the selected profile under its native provider ID. The ownership record tracks one current profile. |
| [Configuration tests](../agents/tests/providers/pi/config.test.js) | Assert removal of previous provider references and exactly one managed provider after competing writers. They prove writer consistency, not continued usability of older sessions. |
| [Compatible acceptance](../agents/tests/providers/pi/compatible.js) | Retains a real native `ModelRuntime`, switches provider through the shared projector, and asserts that the old runtime loses authentication. |
| [Endpoint acceptance](../agents/tests/providers/pi/endpoint.js) | Already exercises two DeepSeek profiles with different endpoint/key references, sequentially. A1 preserves a real supported input class. |
| Installed Pi 1.5.2, `dist/core/auth-storage.js`, `AuthStorage.readLatestData()` / `read()`; `dist/core/model-runtime.js`, `prepareRequest()` | Auth storage observes file revisions. Removing a provider makes later resolution fail; `prepareRequest()` raises `Provider is not configured` before transport. Command-output caching does not pin a removed auth entry. |
| Installed Pi 1.5.2, `dist/config.js`, `getAgentDir()` / `getAuthPath()` / `getModelsPath()` | `PI_CODING_AGENT_DIR` is the supported native boundary for independent configuration roots. |
| Installed Pi 1.5.2, `dist/core/settings-manager.js`, `FileSettingsStorage` | Settings writes lock the lexical settings path with `realpath: false`. Sharing one writable settings file through different profile symlinks would not give a common lock. |
| [Permission gate](../agents/providers/pi/permissions/gate.py), `secret()` | Recognizes `.pi/agent/auth.json`; a synthetic `.pi/agent/profiles/alpha/auth.json` is currently not classified as protected. New paths need coverage before use. |
| [Runtime documentation](../agents/providers/pi/runtime/README.md); [verification documentation](../agents/tests/providers/pi/README.md) | Explicitly document sequential sessions and authentication loss. This is an existing GenosAI limitation, not a native Pi requirement. |

Upstream [model selection](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/models.md)
documents multiple authenticated providers and session-local model selection.
[Native agent-directory configuration](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/configuration.md)
documents the isolation mechanism. These moving upstream pages corroborate the installed-source
inspection; implementation must continue to use the pinned version's behavior.

### Checks actually run

- WSL: `node --test agents/tests/providers/pi/config.test.js` — 18 passed.
- Native Windows Node: the same test file — 18 passed, none skipped.
- Both platforms: `node agents/tests/providers/pi/compatible.js <installed-pi-cli>` — passed;
  16 refusal cases, both thinking modes, `retainedRuntimeAuthRemoved: true`, zero network requests.
- WSL scratch-only diagnostic using the production `configure()` and native 1.5.2 `ModelRuntime`:
  shared directory, alpha/DeepSeek → beta/Anthropic removes alpha auth; alpha → gamma/DeepSeek
  replaces alpha's resolved key while alpha's retained endpoint remains unchanged. Three separate
  native directories retain all three original keys/endpoints. Only synthetic keys were used;
  network access was rejected, and the fixture was removed afterwards.
- Synthetic `secret()` classification: base auth path protected; two nested profile auth paths
  unprotected. No real credential contents were inspected.
- `python3 -m unittest discover -s agents/tests -p test_conformance.py` — 11 passed,
  including repository document-link validation after this todo was added.

### Inferences and limits

The shared projection mechanism explains the reported error, but the exact historical launch
sequence in the screenshot was not captured. The diagnostic proves a possible same-provider
credential/endpoint mismatch, not a real credential leak. Native-directory auth isolation is
demonstrated; the proposed complete managed CLI/resource/session lifecycle is not implemented or
proven yet. Existing green tests encode the old limitation and must change with the contract.

Initial unrelated modifications in `agents/tests/test_release.py`, `docs/preparation.md` and
`tools/release.py` were left untouched. They were no longer dirty at the final pre-write check;
no staging, commits or cleanup were performed by this investigation.

## Current architecture and source of truth

[Local configuration](../agents/configuration.md) owns composition and private references.
[The Pi runtime owner](../agents/providers/pi/runtime/README.md) owns profile validation,
selection and native connection projections; [lifecycle](../agents/providers/pi/lifecycle.sh)
owns installation, package registration and removal. [The package manifest](../agents/package.json)
owns common skills and the permission extension. Pi owns native protocol behavior and session
persistence. [Permission policy](../agents/providers/pi/permissions/README.md) and
[verification](../agents/tests/providers/pi/README.md) retain their existing boundaries.

## Problem and root cause

A process-local profile selection currently causes a global replacement of mutable provider
configuration. A startup writer lock prevents competing projectors from interleaving; it does
not preserve the data needed by already running sessions. Provider IDs key native credentials,
so retaining more provider entries alone cannot isolate different accounts/routes for the same
provider. Retained native model objects and refreshed auth storage can then disagree.

## Decision

**Proposal, subject to review:** use a persistent native agent directory per configured profile,
selected with `PI_CODING_AGENT_DIR`. Extend the existing Pi owner; keep one installed runtime.

1. Derive a profile directory from the registry-owned base and validated profile ID, proposed as
   `<base-agent-dir>/profiles/<profile-id>`. The runtime configuration owner resolves this path
   once with the selected snapshot and returns it to consumers. Do not derive it independently
   in launch, lifecycle and acceptance code.
2. Keep each profile's `auth.json`, `models.json`, ownership record, writer lock and mutable
   native settings/cache in that profile directory. Reuse existing native-provider IDs,
   catalog pinning, command-based credential references and projection checks. Selecting B
   must not delete, rewrite or sweep A's files.
3. Register the same local GenosAI package and canonical instructions in each selected native
   directory through the existing lifecycle/native package boundaries. Bootstrap a newly
   selected profile locally after preflight; require no manual credential duplication or runtime
   reinstall. Reuse platform link mechanics with ownership checks. Do not launch if required
   instruction links, package discovery or guard initialization are unavailable.
4. Keep mutable native preferences independent under A2; never symlink writable `settings.json`
   between profile directories. Base native preferences and foreign packages remain untouched.
   Document the change in preference scope explicitly; do not silently copy foreign settings.
5. Preserve default conversation discovery using a verified directory link from each profile's
   `sessions` to the existing base session directory: POSIX link / native Windows junction.
   This retains Pi's own per-working-directory grouping and resume/list behavior without moving
   history or adding an index. Native explicit session-location overrides retain precedence.
6. Keep retired profile directories until explicit lifecycle cleanup; launching another profile
   is never garbage collection. Removal recognizes owned projections even for profiles no
   longer in current config and preserves native preferences/history/foreign files.

### Premise / KISS gate

The need is independent live connections. Pi already owns per-agent configuration and sessions;
GenosAI already owns profile selection and native provisioning. Add one persistent directory per
used profile and a shared-history link, reusing the existing projector/package/link code. Add zero
services, ports, providers, protocols, timers, key copies or PID lifecycles. Remove cross-profile
replacement from ordinary launch. Retain validation, ownership and writer locking because they
protect against actual drift and competing writes within one directory.

The deliberate tradeoff is that native mutable preferences are profile-local under A2. Automatic
global preference synchronization is not a deferred feature. A3 avoids a separate generation
snapshot lifecycle; changing a live profile's own definition requires restarting its sessions.

### Alternatives considered

| Option | Moving parts and tradeoff |
|---|---|
| Project all configured providers into the shared root | Fewer directories and no new process, but one credential/endpoint slot per provider cannot satisfy A1. Would require new conflict restrictions or further machinery. |
| Derive a custom provider alias per profile | Keeps one root but adds a provider namespace/mapping and can alter provider-specific behavior. Native isolation preserves provider identity. |
| Per-invocation temporary directories or a custom SDK launcher | Adds cleanup/snapshot or CLI compatibility ownership. Persistent native profile directories satisfy A3 without those lifecycles. |
| Single-session lock or retaining the sequential-session warning | Prevents or documents concurrency rather than providing the goal. |

## Required invariants

1. Distinct profile launches preserve each other's auth, endpoint, model and thinking behavior,
   including the same provider/model with distinct credential references/endpoints (A1).
2. Every managed profile loads the canonical instructions, intended skills and healthy permission
   adapter. Protect active and sibling profile auth paths through direct tools and recognized
   shell readers, including native/WSL spellings and path aliases.
3. Credentials stay with the existing secret owner; validation uses metadata and native Pi
   resolves command references. No raw keys in argv, projections, logs or copied native stores.
4. Preserve one-snapshot selection, explicit leading selector rules, native argument forwarding,
   installed-version refusal, selected-model pinning and no mutation of local source input.
5. Inactive keys remain optional. Preserve disabled setup and the existing non-projecting
   validate/help/version/list paths. Invalid selector/capability/key refusals must not create a
   profile or modify protected state; an explicitly selected version probe retains its current
   selected-profile validation/projection semantics.
6. Per-directory collision/drift checks and bounded writer locks remain. Symlink/junction escapes,
   foreign directories and partial provisioning refuse observably before native session dispatch.
   Individual atomic file replacements are not a multi-file transaction.
7. Conversation history remains discoverable and unchanged; do not migrate, duplicate or delete
   it. Preserve explicit native session-directory overrides. A3 bounds live reconfiguration.

## Implementation tasks

- [ ] Add failing tests for the matrix below before production changes. Keep the old shared-root
  auth-loss behavior as an explicit negative control, not the expected managed outcome.
- [ ] Extend `configure.js` to own profile-path resolution and selected native projection using
  one parsed snapshot. Return the resolved directory in its result/CLI contract; update all
  consumers together, including [the acceptance interface](../agents/tests/providers/pi/run.sh).
- [ ] Extend lifecycle provisioning/removal for per-profile canonical instructions, native local
  package registration and shared-session links. Preflight before writes; bootstrap selected
  profiles idempotently, using existing platform machinery without a parallel registry.
- [ ] Update `launch.sh` to dispatch the pinned native CLI with that returned directory. Preserve
  source/config immutability, startup effort, nonlaunch inspection and all forwarding semantics.
- [ ] Extend `gate.py` and its native startup probe/tests for the new owned auth paths before
  enabling those paths. Cover sibling profiles and configurable native base paths.
- [ ] Adapt `config.test.js`, `compatible.js`, `endpoint.js`, `catalog.js`, installed loader checks,
  installer/path fixtures and SDK acceptance consumers to resolved profile directories. Preserve
  compatible serialization, poisoned-catalog controls and existing refusal evidence.
- [ ] Implement the bounded legacy transition/removal described below, then update stable owners.
- [ ] Run both platform matrices sequentially, inspect every changed file/final diff, and verify
  no changes to private input, secret files, unrelated work or Git index.

## Test-first and verification plan

### Red evidence

Use synthetic keys and loopback or injected transport. No real provider or paid account is needed.

| Case / evidence type | Required failure before implementation |
|---|---|
| Retained runtime, different providers — permanent guard in `compatible.js` | Retain A, launch/select B, then request again from A. A cannot authenticate today. Assert A remains usable after the fix. |
| Same provider/model, different keys/endpoints — permanent guard | Record A's synthetic key at A's endpoint, select B, repeat A, then request B. Today A can resolve B's key; assert endpoint/key pairs never cross. Check values in memory, never log auth headers. |
| Two real managed CLI processes — acceptance in `endpoint.js` | Keep A alive behind a fixture barrier, start B, then release A's next generation. Current shared projections break A. Assert both serialized requests and loaded directories, not merely file counts. Bound and verify child cleanup. |
| Refusal/no mutation — permanent guards | Missing/invalid B, foreign target, escaping link and provisioning failure leave A, source input and history byte-identical; no native dispatch or partial success. Existing coverage only observes shared-root files. |
| Native resources and sessions — acceptance | Two profile roots load the package/guard and resume/list pre-existing shared history with working-directory filtering. Current launcher supplies no independent profile roots. Native settings remain separate, explicit session overrides work. |
| Credential-path protection — permanent guard in `test_gate.py` | Nested active/sibling auth paths currently fail secret classification. Require denials through gated tools and recognized shell readers; include ordinary-document allow controls. |
| Install, removal, legacy transition — acceptance/guards | Current installer provisions only the base root; no selected-profile bootstrap, retired-profile removal or owned-link transition contract exists. Prove repeatability and preservation of foreign/user data. |

The current shared-root defect must remain observable in the native negative control. A new
directory-layout assertion alone does not prove retained sessions or correct credential routing.

### Green evidence

From the source root, use each platform's configured native Node and installed pinned CLI:

```bash
node --test agents/tests/providers/pi/config.test.js
python3 -m unittest discover -s agents/tests -p test_pi_paths.py
python3 -m unittest discover -s agents/tests -p test_platform_paths.py
python3 -m unittest discover -s agents/tests/providers/pi -p test_gate.py
node agents/tests/providers/pi/compatible.js <installed-pi-cli>
node agents/tests/providers/pi/endpoint.js <installed-pi-cli>
node agents/tests/providers/pi/endpoint.js <installed-pi-cli> agents/tests/providers/pi/endpoint-profiles.json
node agents/tests/providers/pi/catalog.js <installed-pi-cli>
node agents/tests/providers/pi/catalog.js <installed-pi-cli> unprojected-control
make check
make test
```

Use native Windows Python equivalents there; WSL-only installer skips are documented gaps,
not Windows proof. Run WSL and Windows sequentially because fixtures share scratch names.
Exercise the updated installed-loader route from [native verification](../agents/tests/providers/pi/README.md)
for both profile roots with synthetic homes; do not reuse real auth state. Include fresh disabled
install, adding/selecting another profile without runtime reacquisition, interrupted provisioning,
legacy cleanup and uninstall with sessions/foreign sentinels. No live cutover or paid smoke is
necessary to prove this local-state defect. Check docs/relative links with existing conformance tests.

## Documentation plan

- **Authoritative stable owner:** runtime README above; replace the sequential-session limitation
  with native profile scope, A2–A3 consequences, shared-history behavior and transition procedure.
- **Permission owner:** [Pi permissions](../agents/providers/pi/permissions/README.md), only the
  new protected-path responsibility if explanation is needed; executable shapes stay in code.
- **Verification owner:** [Pi verification](../agents/tests/providers/pi/README.md), replace the
  auth-loss success assertion with positive isolation evidence and the native negative control.
- **Other consumers:** [Pi provider](../agents/providers/pi/README.md) and
  [local configuration](../agents/configuration.md) change only their affected install/removal
  consequences and link to the runtime owner. No new architecture document or router is needed.
- **Duplication avoided:** the two sequential-session explanations above are current duplicate
  statements to remove together. The separate optional-plugin/image-budget todo is independent;
  its future implementation must consume the selected directory/snapshot without a second owner.
  Stable files must never cite this todo or its decision IDs.

## Rollout and rollback

Implement and prove in synthetic homes first. Real workstation reapplication is separate from D1.
Before a real transition, finish legacy managed sessions once: their loaded native runtimes still
refer to the base auth store. New profile launches must leave legacy base auth/model entries intact;
they must not silently perform cleanup while an older session could need them.

An explicit lifecycle reapplication/removal can retire exact unchanged legacy managed entries
after ownership validation. Preserve base foreign auth/models, native preferences and session data;
do not repurpose or recursively delete the base directory. Uninstall discovers owned profile state,
including retired IDs, and removes only verified owned entries/links. It must never traverse a
shared-session link during cleanup. Tampered ownership, partial native provisioning or foreign
links refuse with actionable diagnostics; repair must not discard unknown state.

Rollback uses the prior source/lifecycle after finishing new-profile sessions and validating owned
state. Keep sessions/native user files and original key references; no secret export or copying is
required. Do not promise in-place rollback of running native runtimes.

## Completion criteria

The same real managed route supports two live profiles with correct synthetic endpoint/key
pairs, for both different and identical provider/model IDs, on WSL and native Windows. Native
negative controls still expose the old failure. Guards protect all new auth locations; required
instructions/skills load; existing history, foreign settings and source input survive. Required
checks pass with explicit platform gaps, stable docs agree, and task changes stay within the named
owners. No claim about provider availability, billing or production rollout follows from this proof.

## Review record

### 2026-11-20 — Initial investigation

- **Trigger:** reported `Provider is not configured: deepseek` after an existing Pi session had
  already performed work; operator requested D1–D2.
- **Root cause:** shared provider projection replacement under process-local selection; details
  and evidence are in the sections above.
- **Fix:** proposed native profile directories; no implementation or native configuration changes.
- **Verification:** existing configuration suites and compatible acceptance passed on both platforms;
  the scratch diagnostic distinguished shared-root failures from native-directory auth isolation.
- **Authority:** D1–D2 recorded; A1–A3 are proposals/assumptions, not operator approvals.
