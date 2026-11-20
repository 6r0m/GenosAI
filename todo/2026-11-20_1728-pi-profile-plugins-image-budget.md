# Pi profile plugins and outbound image budgets

**Status:** REVIEW REQUIRED

**Scope:** Pi configuration, managed extension selection and request-size handling

**Stable documentation owner:** [Pi integration](../agents/providers/pi/README.md), [configuration](../agents/configuration.md) and [provider verification](../agents/tests/providers/pi/README.md)

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

Allow optional Pi extensions to apply to every managed run or only selected run profiles,
using the existing configuration and installation workflow. Provide an opt-in image budget
that reduces outbound image payloads before provider limits prevent further requests,
without compacting text or rewriting saved image originals and conversation records.
Keep the unblocker replaceable behind a narrow adapter boundary, with supported policy changes
driven by configuration rather than edits scattered across the integration.

## Authority register

### Operator decisions

- **D1:** Produce an investigation TODO for review, without implementing the change.
  - Effect: this artifact proposes work; it does not approve installation or implementation.
  - Reason: investigate the appropriate integration first.
  - Date/source: operator request, 2026-11-20.
- **D2:** Repository content must contain only public, portable information.
  - Effect: use public sources and synthetic fixtures; exclude private operational context.
  - Reason: the repository is public.
  - Date/source: operator request, 2026-11-20.
- **D3:** Support both global plugins and plugins selected per run profile; prefer an
  existing idempotent installation route when it suffices and avoid overengineering.
  - Effect: assess native Pi loading and existing lifecycle ownership before adding machinery.
  - Reason: simple extension reuse across differently configured profiles.
  - Date/source: operator request, 2026-11-20.
- **D4:** Unblocker code should be flexible, quickly adjustable through configuration, and
  architecturally treated as an external black box wherever practical.
  - Effect: separate algorithm implementation from GenosAI configuration, lifecycle and
    safety enforcement; keep the adapter contract small and implementations replaceable.
  - Reason: quick changes to unblocker behavior as restrictions change.
  - Date/source: operator follow-up request, 2026-11-20.

### Operator gates

- **Q1 [OPEN - BLOCKING]:** Is this implementation plan approved? Gates implementation,
  not further read-only investigation. No external publication or live cutover is included.

### Working assumptions

- **A1 [ACTIVE]:** Start with reviewed, repository-shipped extension IDs, not arbitrary
  package URLs supplied through private configuration. Broader package acquisition is not
  necessary for the requested global/profile selection contract.
- **A2 [ACTIVE]:** Enablement is fixed for a launched process. Configuration changes take
  effect on its next launch; changing the selected model does not silently enable other plugins.
- **A3 [ACTIVE]:** Reuse upstream image-budget algorithms selectively under their license;
  adoption of the entire upstream extension is conditional on compatibility and ownership proof.

## Non-goals

No second plugin manager, daemon, marketplace, provider fork, separate operator-edited plugin
file, automatic remote uploads, secret copying, network diagnosis, or general retry framework.
No unrelated provider refactor. No promise to isolate existing shared native authentication
projections between concurrent mixed-provider sessions. No inference that a socket reset proves
a request-size failure. Public defaults remain unconfigured and optional plugins disabled.
No provider-wide interception of compaction, branch summaries or independent nested SDK calls.
No live code fetching, arbitrary configuration-supplied imports, persistent image-consumption
ledger without demonstrated need, or promise to police arbitrary third-party payload transformers.

## Verified evidence

### Repository facts

| Evidence | Observed contract |
|---|---|
| [Pi registry](../agents/lifecycle/providers.conf.sh) | Pi is pinned to 1.5.2; platform paths and runtime identity already have an owner. |
| [Package manifest](../agents/package.json) | The managed package declares the permission adapter and shared skills; optional plugins are not currently selected by profile. |
| [Configuration input](../agents/config.py), `validate()` / `pi_input()` | Pi top-level fields are explicitly allowed and one selected platform snapshot is produced. |
| [Profile owner](../agents/providers/pi/runtime/configure.js), `resolveProfiles()` | Unknown profile keys refuse; current allowed keys contain no plugin selection/options. Setup and credential-requiring launch are separate. |
| [Managed launcher](../agents/providers/pi/runtime/launch.sh) | Leading `--profile` selects a run; one validated snapshot supplies native arguments. Lifecycle mutations through `pi-sot` are deliberately refused. |
| [Lifecycle adapter](../agents/providers/pi/lifecycle.sh), `pi_native_package()` | Existing install registers the local package with native Pi. Runtime acquisition is separate; Windows environment transport already has a helper. |
| [Lifecycle contract](../agents/lifecycle/README.md) | Reapplying the selected provider is already supported; no new apply command is needed to express this feature. |

### Native and public evidence

- [Pi 1.5.2 packages](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/docs/packages.md)
  support local packages, per-package resource filters, and invocation-specific `-e` loading.
  Remote `-e` sources can acquire/update dependencies during startup: use already available
  local paths for the managed selection, not a launch-time package download.
- [Pi 1.5.2 CLI](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/docs/cli.md)
  documents repeated `--extension` and `--no-extensions`; the latter disables discovered and
  configured extensions. Selection must not inject it and accidentally remove the managed guard.
- [Pi 1.5.2 extension runner](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/core/extensions/runner.ts),
  `emitBeforeProviderRequest()`, catches handler exceptions and returns the current payload.
  This behavior was also inspected in the installed 1.5.2 distribution. A thrown hook error is
  **not** a demonstrated request veto. Later hooks receive earlier hooks' returned payloads.
- [Pi 1.5.2 resource loader](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/core/resource-loader.ts)
  merges CLI extension paths before normally enabled paths. Thus optional `-e` loading does
  not make an image-budget handler the final handler across arbitrary installed extensions.
  The existing managed permission adapter has session/tool handlers, not a payload transformer.
- [Pi 1.5.2 OpenAI-compatible transport](https://github.com/earendil-works/pi/blob/v1.5.2/packages/ai/src/api/openai-completions.ts)
  invokes `onPayload` before the SDK request and forwards the abort signal to the request and
  retry wrapper. The extension context exposes `ctx.abort()`. These are a plausible cancellation
  path, not proof that invoking it inside this hook prevents every dispatch/retry.
- [Pi issue 9773](https://github.com/earendil-works/pi/issues/9773) reports missing hooks for
  summaries/compaction on 0.85.1. Inspection of 1.5.2's
  [compaction options](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/core/compaction/compaction.ts)
  and branch-summary request options also finds no agent-turn `onPayload` callback in those
  option builders. The extension must not claim universal coverage of native model calls.
- [DeepSeek vision limits](https://api-docs.deepseek.com/guides/vision/#limits)
  distinguish the 48 MiB JSON-body limit from per-image limits; inline base64 contributes to
  that body. Direct requests also have a documented image-count ceiling of 600. A gateway
  may impose different byte/count ceilings. Neither count-only nor byte-only filtering suffices.
- [Pi issue 9579](https://github.com/earendil-works/pi/issues/9579) discusses native per-image
  sizing and temporary image blocking. Those are useful controls, not evidence of automatic
  aggregate-byte recovery. [Issue 10162](https://github.com/earendil-works/pi/issues/10162)
  provides community reports of route-specific limits and outbound filtering, not proof for
  every platform or extension combination.
- [The Pi 1.5.2/Linux workaround report](https://github.com/earendil-works/pi/issues/10162#issuecomment-6806831696)
  describes successful request-only filtering for observed gateway caps of 20 and 8, including
  a 25-image request succeeding with filtering and failing without it. This is author-reported
  evidence, not an independently rerun acceptance result or a stable limit for those model names.
  [A separate 503 report](https://github.com/earendil-works/pi/issues/10162#issuecomment-6719166976)
  demonstrates why an ambiguous server error cannot safely identify an image-count rejection.
- [pi-image-budget source](https://github.com/Aaalice233/pi-image-budget/blob/main/src/index.ts)
  and [package](https://github.com/Aaalice233/pi-image-budget/blob/main/package.json), observed
  version 0.2.0: compression, payload measurement and bounded recovery are useful references.
  The inspected index blob is `8e9c0f09e6f066f3c55e095e83733b7723a369b6`;
  this is a file identity, not an adoption commit pin. Its dev runtime range is `^0.87.1`.
  Record an immutable repository revision before incorporating code.
- [pi-imagefiles routing](https://github.com/adamcjm/pi-imagefiles/blob/main/extensions/pi-imagefiles/src/scan.ts)
  requires a `deepseek*vision*` model ID; `deepseek-flash` does not match.
  Its [credential resolver](https://github.com/adamcjm/pi-imagefiles/blob/main/extensions/pi-imagefiles/src/files-api.ts)
  returns the auth entry's key literally. That does not resolve GenosAI's command-reference
  credentials. Files API uploads also introduce remote storage, expiry and credential handling.

### Corrections and unverified areas

The proposed outbound-only approach is justified; production-grade compatibility is **unverified**.
The upstream image-budget final guard can warn and return an unchanged oversized payload when
no images can be removed. It also reads independent user/project configuration and appends
recovery/custom session entries. Preserving original records is different from keeping the entire
session file byte-identical. Do not describe upstream as an unmodified fit or a proven hard guard.

Zero-dispatch cancellation, the supported managed ordering, Windows native loading,
resumed-session behavior and bounded recovery on pinned Pi remain implementation acceptance
gates. Third-party final-payload ordering is not guaranteed. Do not claim any socket error is
cured by this feature.

## Current architecture and source of truth

[Project architecture](../docs/architecture/structure.md) owns subsystem boundaries.
The ignored local configuration owns operator choices; `config.py` transports one platform
snapshot, and the Pi profile owner validates connection semantics and manages native projections.
The launcher selects the run. The lifecycle adapter owns managed native package registration.
The manifest owns mandatory extension/skill discovery. Native Pi owns extension execution,
provider conversion, session persistence and transport behavior.

Extend these owners. Plugin options must not become independently editable native settings.
Any generated selection is a projection, not another source of truth.

## Problem and root cause

Profiles currently select connections but cannot select extensions or their options. Installing
an optional extension globally would affect unrelated runs unless it gates itself correctly.
Separately, individually acceptable images can accumulate into a request exceeding a provider's
body limit while remaining below a token compaction threshold. Compaction changes conversational
context and does not provide a precise byte budget for that outgoing request.
Small images can independently exceed route image-count limits while remaining far below a
body-size ceiling. These constraints require separate checks against the same effective route.

## Decision

**Recommendation, pending Q1:** reuse ordinary `make install PROVIDER=pi PLATFORM=host|windows|both`
for idempotent installation/reconciliation; retain `RUNTIME=1` only for explicit runtime acquisition.
Do not add an apply command. Starting a new session resolves current plugin choices from the
same profile snapshot already used for the connection.

Add a small, explicit set of reviewed extension IDs under the Pi owner (A1). Public code maps
each ID to its local entrypoint and validates its supported options. The existing private Pi
configuration supplies global enablement/options and per-profile enablement/options. Define
these fields once in the configuration owner; examples link to that contract. Reject unknown
IDs/options and invalid budgets before native projections or execution.

Compute a deterministic union of global and selected-profile plugins, load each once, and let
validated profile options override global options for the same ID. An empty profile selection
does not disable global plugins. Do not invent recursive merge semantics for arbitrary objects.
Pass only the resulting non-secret plugin options and resolved route identity to the process;
never forward the full private configuration or credential references to optional extensions.

Prefer Pi's native repeated `-e <local-entrypoint>` for optional modules, leaving mandatory
package registration intact. Optional entrypoints must not also be auto-loaded by a manifest
or directory glob. Preserve foreign native resources and existing argument/environment contracts.
This is native extension selection, not a second installer. A reviewed extension can be used
globally or per profile without acquiring it again. No launch-time network acquisition.

Loading order is a supported-composition contract, not a universal final-hook guarantee.
Order GenosAI-managed payload transformers deterministically, with budget validation after
the managed payload-growing transformations. Test that actual order, not just argv construction.
Do not disable or reorder foreign resources to manufacture this guarantee: independently loaded
third-party hooks may still run afterward. A combination with an unverified later transformer is
outside the guarded-composition claim and must be reported as such, not silently certified.
If arbitrary-extension coverage is later required, it needs a genuine last-stage transport guard
and separate review; this task does not add that framework.

### Replaceable unblocker boundary

Following D4, treat the algorithm as an external dependency behind a thin Pi-owned adapter,
even if its audited source ships inside the managed package. This is a module boundary, not
a separate process, service or new package manager. GenosAI owns selection, validated route
options, native integration and final refusal; the replaceable algorithm owns image selection,
compression planning and candidate construction. A library's warning or success flag is not
authority to bypass GenosAI's size/count checks.

Use one small explicit contract: receive outbound copies, resolved route limits/options and
the current conversation boundary; return a candidate plus reduction/omission diagnostics or
an explicit cannot-fit result. Keep original messages, credentials, native settings, provider
calls and retry scheduling outside that algorithm's ownership. GenosAI independently measures
the candidate through the supported native route. This is separation of responsibility, not
a sandbox: reviewed in-process extensions still have the host process's permissions.

The same private configuration selects the reviewed implementation ID and its supported
options. Changing route `maxRequestBytes`, `maxImages`, recent-image retention or supported
compression policy takes effect on next launch without source edits, package registration
changes or runtime reinstall. Switching between already shipped compatible implementations
uses that same selection. Adding a new implementation requires an audited pinned source and
its adapter/validator/tests, but must not require changes to generic lifecycle or launcher code.
Do not promise configuration can express a new algorithm or load unreviewed code.
Start with one production implementation; use a synthetic second adapter to prove replaceability
without building an unused framework. Unknown options/IDs refuse rather than falling back.

The first optional extension is an image-budget adapter, using pinned/audited upstream helpers
where useful (A3). It accepts resolved options rather than consulting upstream user/project
config files. Reuse native resizing; retain MIT notices for copied code. Avoid importing all
upstream recovery/configuration machinery merely to access a pure budgeting helper.

Scope every request transformation and learned limit to the resolved provider, model, API and
normalized endpoint. An in-session model/route switch must not inherit another route's budget;
the adapter becomes a no-op for an unmatched route. Unknown route identity must not be guessed.

Apply compression and explicit omission markers to outbound copies only. Prefer retaining
recent images and protect images not yet included in a successfully completed answer. Failed,
aborted or partial generations do not prove an image was processed. If protected content cannot
fit after permitted resizing, refuse clearly rather than silently dropping it. Historical image
omission is visible to the model and user and never means an image's content remains recoverable
from text alone. All original messages, images and tool-result identities remain available.
Derive new/unprocessed images from the active conversation branch and current request boundary
where possible, including images introduced by tools mid-turn. Test retry, abort, fork and resume
boundaries first. Ambiguous processing state remains protected; do not introduce a persistent
consumption ledger unless these tests establish that existing boundaries cannot satisfy the rule.

Measure UTF-8 serialized request bytes, including system/tools/text/base64 overhead, and count
all supported image blocks after provider conversion. Keep `maxRequestBytes` and `maxImages`
as independent validated per-route options and satisfy both. Do not infer gateway caps from
the provider/model name. Use an explicitly configured route ceiling; a conservative 40 MiB target
for a documented 48 MiB direct route is an example, not a global DeepSeek default.

**Coverage:** guarantees apply to supported normal agent-turn requests (including subsequent
tool-loop requests) on the tested API/transport and managed extension composition. They do not
cover compaction, branch summaries, independent nested model calls or arbitrary later third-party
transformers. Document and test this boundary rather than calling the hook provider-wide.

**Technical gate:** first test `ctx.abort()` inside the payload hook against an actual 1.5.2
recording local endpoint. Oversized, over-count and intentionally unmeasurable candidates must
produce zero HTTP requests, including with native retries enabled and after the run settles.
A caught throw may accompany an abort for diagnostics; throwing alone, warning, or returning
invalid payloads is not acceptable. Test managed payload-growing handlers before validation,
and a later foreign handler as a negative control for the documented ordering boundary.
Inspect cancellation and serialization ordering before implementation depends on them. If no
supported mechanism meets this invariant, stop that path and return for review; do not silently
weaken the guard or fork the provider/runtime.

Retry only a confirmed byte/count rejection, only with a measured reduction in the rejected
dimension while satisfying both configured limits, and with at most one plugin recovery per
input coordinated with Pi's native retry/settle behavior. Aborts must not schedule recovery.
Generic connection resets, auth failures, rate limits and ambiguous 503 responses are not
image-limit evidence. Their existing native behavior must not gain plugin image-recovery loops.
If text/tools alone exceed the ceiling, stop with an actionable error; do not compact or retry
unchanged input.

### Premise / KISS gate

Existing owners already cover configuration, launch and installation. Add one bounded selection
contract and an optional image adapter; reuse native extension loading and resizing. Add no
services, ports, credentials, remote image lifecycle or polling. Reuse removes the need for a new
apply interface and an independent plugin configuration file. Deliberately give up arbitrary
marketplace acquisition and hot-changing the plugin set inside an active process (A1–A2).

### Alternatives considered

| Option | Additional moving parts / trade-off | Assessment |
|---|---|---|
| Native Block images / per-image resizing | No new module, but manual/all-image behavior or no aggregate-body guarantee | Emergency control, not the requested selective automatic behavior. |
| Globally install upstream image-budget unchanged | Separate configuration precedence and recovery state; affects non-selected routes by default | Reject unchanged; retain audited algorithms as reference. |
| Rewrite native package filters on each launch | Shared settings writer and concurrency/drift coordination for process-local selection | Prefer local `-e` selection with no new shared settings mutation. |
| Small audited outbound adapter | One selection contract and bounded image logic | Recommended; do not rewrite image codecs or all upstream policy. |
| Files API image offload | Uploads, credentials, remote cache, quota and expiry lifecycle | Excluded from this scope; not a compatible drop-in. |
| Conversation compaction | Alters text context; byte guarantee still separate | Does not meet the history-preservation goal. |

## Required invariants

1. One private input owner; disabled public defaults and credential-free tooling installation remain valid.
2. Global plus selected-profile activation is deterministic, deduplicated and process-local.
3. Mandatory permission integration, shared skills and foreign resources survive installation and selection.
4. No implicit runtime upgrade, global npm change, plugin credential reads or package downloads at launch.
   Native model authentication remains with its existing owner; verification uses no paid calls.
5. Saved originals and text are preserved; omission markers cannot replace unrelated text or tool IDs.
6. Actual serialized bytes and image count govern independent route budgets; unknown measurement cannot produce a success result.
7. For the declared agent-turn transport and managed ordering, oversized/over-count/unmeasurable
   opted-in requests cannot reach transport. No universal final-hook or nested-call coverage is claimed.
8. Unmatched/non-opted-in routes are unchanged. Recovery budgets and learned limits never leak across routes.
9. Reapply is idempotent; uninstall removes owned resources only and preserves unrelated native files.
10. Diagnostics expose counts, bytes, route match, action and retry reason without bodies, images or secrets.
11. D4's adapter boundary keeps algorithm changes local; supported option changes and selection of
    shipped implementations require only configuration and next launch, with safety checks unchanged.

## Implementation tasks

- [ ] After Q1, prove `ctx.abort()` zero-dispatch refusal and managed ordering with installed Pi and a recording local provider before adopting a budgeting implementation. Record unsupported call paths and the later-foreign-hook negative control.
- [ ] Add failing feature/regression cases below using [configuration tests](../agents/tests/providers/pi/config.test.js), [private input tests](../agents/tests/test_private_config.py), [platform tests](../agents/tests/test_platform_paths.py) and [native transport fixtures](../agents/tests/providers/pi/transport.js).
- [ ] Extend `config.py` and `runtime/configure.js` at their existing schema/snapshot boundaries; support global plugins even when no connection profile is configured for setup. Keep normal bare launch refusal intact.
- [ ] Extend `runtime/launch.sh` with deterministic native optional-extension selection and process-local non-secret options. Reuse Windows transport/path helpers when needed; preserve foreign environment entries and opaque prompt arguments.
- [ ] Add the smallest Pi-owned optional entrypoint/ID resolver needed for the selected contract. Keep optional modules out of unconditional manifest discovery; retain the existing mandatory package.
- [ ] Establish D4's thin adapter contract and validate byte/count/policy options at the existing input boundary. Demonstrate two configurations and a synthetic replacement implementation without changing lifecycle/launcher code or reading an independent plugin config file.
- [ ] Select an immutable upstream revision, audit helper dependencies/license, and integrate only needed budgeting/resizing logic. Add provenance/notices and exact source admission for incorporated files; no floating source reference in shipped code.
- [ ] Implement independent scoped byte/count budgets, boundary-derived protected-image policy, confirmed bounded recovery and observable refusal; verify supported OpenAI-compatible payload handling and explicit coverage/no-op behavior for unsupported routes.
- [ ] Exercise existing install/uninstall, source-move ownership, credential-free setup and second-apply checks. Change lifecycle code only where an acceptance case demonstrates a missing responsibility.
- [ ] Update stable owners below and register new source/test files through [source disposition](../tools/source-manifest.json). Resolve this TODO's own disposition explicitly before release checks; it is currently not an admitted export file.
- [ ] Run the full declared matrix, inspect the complete diff, and request renewed review if the technical gate requires a different design.

## Test-first and verification plan

### Red evidence

Permanent guards must be observed failing against the unchanged implementation before production edits.
Use generated public images, synthetic keys and local recording endpoints only.

| Case / evidence type | Wrong or missing behavior to demonstrate before implementation |
|---|---|
| Global/profile selection — permanent guard | New plugin fields are refused today; no global/profile union, deduplication or override contract exists. |
| Configurability/replaceability — permanent guard + acceptance | Change limits/policy and select a synthetic alternate adapter using only configuration and next launch; verify different outbound results, unchanged source/native registration and identical independent safety enforcement. |
| Validation/no mutation — permanent guard | Establish unsupported ID/options/budget and inherited-environment controls; verify refusals leave native files unchanged. |
| Native lifecycle — acceptance | Installed route cannot yet enable one optional extension only for a selected profile while preserving guard/foreign extensions. |
| Aggregate bytes — permanent guard + native acceptance | Multiple individually valid synthetic images exceed a local body ceiling and the current route sends an oversized request. Test reduction from above 40 MiB, a smaller gateway ceiling and the 48 MiB boundary. |
| Image count — permanent guard + native acceptance | Tiny images pass byte checks but exceed a local 20/30-image cap; cover an 8-image option, exact-cap boundaries, and both constraints simultaneously. No model-name-derived global cap. |
| Request veto — permanent guard + native acceptance | A throwing hook currently does not prove zero dispatch. Test `ctx.abort()` for oversize, over-count and measurement failure with native retries enabled; record zero HTTP requests through settlement. |
| Ordering/coverage — permanent guard + native acceptance | Show a later foreign hook can invalidate an earlier check; prove managed growth precedes the guard and do not claim the foreign case is protected. Inspect/test normal turns versus compaction/branch/nested paths to delimit hook coverage. |
| Protected images/history — permanent guard | Define current/unprocessed and successful-answer history, then demonstrate missing outbound reduction; assert original records/text/images remain intact after reduction, retry and resume. |
| Route switching — permanent guard | Cover matched opt-in, non-opt-in, differing endpoint/API/model, native model switch and two process-local selections without shared plugin-setting mutation. |
| Recovery — permanent guard + native acceptance | Local 413 then success must show smaller bytes and at most one plugin recovery; explicit count rejection must reduce count. Repeated rejection, text-only overflow, ambiguous 503, reset/401/429, abort and native retry interaction must not produce an uncontrolled continuation. |
| Platform/reapply/removal — acceptance | Real Windows and WSL native launchers must load the selected local entrypoints with Unicode/spaced paths; second install and owned removal preserve sentinels. |
| KISS/source/privacy — reviewer judgment | Check sole ownership, dependency/provenance scope, no extra operator config, and no private operational material. Do not replace this judgment with text-presence tests. |

Instrument the provider's received UTF-8 body and dispatch count, not only the plugin's estimate.
For a veto case, prove a known-bad control reaches the endpoint when the guard is absent.
For serialization, include non-ASCII text, system instructions, tools and base64 expansion.
For image processing, decode resized outputs and exercise corrupt/unsupported inputs and failure paths.
Original session records must remain unchanged; explicitly account for any append-only native metadata.
Do not demand byte-identical whole session files while a normal session is appending new messages.

### Green evidence

Run the same named cases, then the existing boundary suites and repository checks:

```bash
node --test agents/tests/providers/pi/adapter.test.js agents/tests/providers/pi/config.test.js agents/tests/providers/pi/probe.test.js
python3 -m unittest discover -s agents/tests -p 'test_private_config.py'
python3 -m unittest discover -s agents/tests -p 'test_platform_paths.py'
make check
make test
make public-check
```

Wire any new JavaScript suite into [the existing Node boundary runner](../agents/tests/providers/pi/test_adapter.py)
so `make test` actually executes it. Use registry-selected native Node; satisfy the pinned scanner prerequisite.
Check source admission before expecting `make check`/`public-check` to succeed with this new artifact.

Use [fresh export and installed-route acceptance](../agents/tests/providers/pi/README.md) in disposable
homes from an independent export with the source unavailable. Run `make install PROVIDER=pi PLATFORM=host RUNTIME=1`,
version/help and unconfigured refusal, configure synthetic profile/plugin cases, reapply with no runtime
flag, then remove and inspect unrelated sentinels. Repeat `PLATFORM=both` with actual native Windows
tools sequentially, including NT links and launchers. Missing native platform execution is UNVERIFIED,
not a mocked PASS. Paid provider calls are unnecessary for this acceptance.

## Documentation plan

- **Authoritative stable owners:** configuration schema/selection semantics in `agents/configuration.md`;
  launch/extension behavior in `agents/providers/pi/README.md`; lifecycle operations in
  `agents/lifecycle/README.md`; acceptance in `agents/tests/providers/pi/README.md`.
- **Router / TOC update:** update an existing owner only if it gains a child owner; do not introduce
  a documentation subtree just for this bounded change.
- **Content:** options ownership, global/profile precedence, reapply/next-launch behavior, route scope,
  replaceable adapter boundary, configurable byte/count policies, managed ordering and excluded call
  paths, omission/refusal semantics, diagnostics and supported native acceptance.
- **Duplication avoided:** examples reference the executable schema; package pins/provenance have one
  owner. Stable docs, code, comments and tests must not reference this transient TODO.

## Rollout and rollback

After approval, prepare and verify in disposable environments first. No live cutover is authorized
by this document. Optional plugins remain disabled by default. Reverting a private enablement choice
and starting a new process disables the optional behavior without altering saved sessions; this is
not a claim to roll back an already submitted provider request. Use existing owned uninstall for
lifecycle removal, preserving foreign resources. Do not add a separate rollback framework.

## Completion criteria

Q1 must be resolved before implementation. Completion requires recorded red/green evidence for the
matrix, proven zero-dispatch refusal and actual serialized byte/count bounds for the declared
agent-turn transport/composition, preserved originals/text, configuration-only policy/adapter
selection changes, global/profile isolation, idempotent lifecycle/removal, and real Windows/WSL
installed-route proof. Unsupported third-party ordering and summary/nested calls are explicit exclusions.
All existing required checks must pass with explicit source disposition. License/provenance and
public-information review must be complete. No unverified community reliability claim, private
session replay, runtime fork, extra configuration authority or unrelated diff may substitute for proof.

Keep this TODO open if native cancellation/ordering or a required platform remains unverified.

## Review record

### 2026-11-20 — Investigation and reviewer assessment

- **Trigger:** D1–D3.
- **Root cause:** profiles lack optional-extension selection; token-oriented history management
  does not bound aggregate provider request bytes.
- **Recommendation:** existing idempotent installation plus native per-run optional loading,
  with a scoped outbound adapter and a transport-veto feasibility gate.
- **Corrections:** upstream is a reference, not a verified drop-in hard guard; native hook errors
  are caught; preserving original records is distinct from freezing the session file.
- **Verification:** read-only owner/source inspection and public upstream review. No implementation,
  lifecycle change, provider request or installed-route acceptance performed for this investigation.
- **Authority:** D1–D3 recorded; Q1 remains open; A1–A3 are proposals, not operator approval.

### 2026-11-20 — Configurable boundary and source-audit follow-up

- **Trigger:** D4 and reviewer F1–F5.
- **Assessment:** F1 accepted as an experiment, not a proven veto; F2 accepted because CLI-first
  loading invalidates an arbitrary-extension final-hook promise; F3 accepted as a separate route
  count budget; F4 accepted with the issue's older version distinguished from inspected 1.5.2;
  F5 retained as a reference/adaptation constraint. No reviewed finding establishes runtime PASS.
- **Changes:** added the replaceable module contract and configuration-only acceptance; narrowed
  ordering/call-path claims; added abort/count/503/boundary tests and avoided a speculative ledger.
- **Qualification:** reported gateway caps are observations, not permanent provider defaults.
  `ctx.abort()` is an exposed helper, but hook-level zero-dispatch semantics remain unverified.
  A black-box module boundary does not imply sandboxing of an in-process extension.
- **Verification:** read-only pinned runtime inspection and public primary-source review; document
  links, diff, privacy and secret checks. No implementation or provider request performed.
- **Authority:** D4 added; Q1 remains open.
