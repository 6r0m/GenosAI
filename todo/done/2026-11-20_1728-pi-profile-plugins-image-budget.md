# Pi profile plugins and outbound image budgets

**Status:** IMPLEMENTED — pinned acquisition and native Pi scope verified

**Scope:** Pi configuration, managed extension selection and request-size handling

**Stable documentation owner:** [Pi integration](../../agents/providers/pi/README.md), [configuration](../../agents/configuration.md) and [provider verification](../../agents/tests/providers/pi/README.md)

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
- **D5 [SUPERSEDED IN PART by D6 — implementation paused for candidate investigation]:**
  Implement the reviewed plan, starting with its local feasibility gate.
  - Supersedes: D1 for the reviewed implementation phase.
  - Effect: authorizes the reviewed scope. D6 pauses production edits pending the candidate review.
  - Reason: not stated.
  - Source: operator invocation of `implement-approved-change` for this TODO.
- **D6:** Investigate existing community packages and check their evidence before proceeding with implementation.
  - Supersedes in part: D5, by pausing implementation for this investigation.
  - Effect: compare existing candidates and verify the strongest one against the pinned runtime.
  - Reason: establish whether reuse is better than building another image-budget engine.
  - Source: operator follow-up request.
- **D7:** Implement the revised upstream-first plan.
  - Effect: closes Q2 and resumes implementation with the reviewed overflow coordination.
  - Reason: not stated.
  - Source: operator request to implement the approved change.
- **D8:** Evaluate fixed-ref native acquisition and apply valid findings.
  - Effect: the managed installer acquires the audited upstream revision and the adapter loads its local helpers.
  - Reason: remove copied upstream source and keep the dependency replaceable.
  - Source: operator request to evaluate and apply the package acquisition review.

### No longer binding

- **D1 [SUPERSEDED by D5]:** Produce an investigation TODO for review, without implementing the change.
  - Effect: this artifact proposes work; it does not approve installation or implementation.
  - Reason: investigate the appropriate integration first.
  - Date/source: operator request, 2026-11-20.

### Operator gates

- **Q1 [CLOSED by D5]:** Is this implementation plan approved? Gates implementation,
  not further read-only investigation. No external publication or live cutover is included.
- **Q2 [CLOSED by D7]:** Approve the upstream-first revision before resuming implementation.
  This gates production changes under the revised approach.

### Working assumptions

- **A1 [ACTIVE]:** Start with reviewed, repository-shipped extension IDs, not arbitrary
  package URLs supplied through private configuration. Broader package acquisition is not
  necessary for the requested global/profile selection contract.
- **A2 [ACTIVE]:** Enablement is fixed for a launched process. Configuration changes take
  effect on its next launch; changing the selected model does not silently enable other plugins.
- **A3 [SUPERSEDED by A4]:** Reuse upstream image-budget algorithms selectively under their license;
  adoption of the entire upstream extension is conditional on compatibility and ownership proof.
  The intact package is now the starting point for compatibility testing. Selective reuse remains
  technically feasible if the whole-package integration proves unsuitable.
- **A4 [ACTIVE]:** Start from the pinned `pi-image-budget` implementation and retain its tested
  algorithms. Prefer a small upstream integration seam and fix if the acceptance cases support it.

## Non-goals

No second plugin manager, daemon, marketplace, provider fork, separate operator-edited plugin
file, automatic remote uploads, secret copying, network diagnosis, or general retry framework.
No unrelated provider refactor. Preserve the existing isolation between different native profile
directories and the shared session-history contract. No inference that a socket reset proves
a request-size failure. Public defaults remain unconfigured and optional plugins disabled.
No provider-wide interception of compaction, branch summaries or independent nested SDK calls.
No launch-time managed acquisition, arbitrary configuration-supplied imports, persistent image-consumption
ledger without demonstrated need, or promise to police arbitrary third-party payload transformers.

## Verified evidence

### Repository facts

| Evidence | Observed contract |
|---|---|
| [Pi registry](../../agents/lifecycle/providers.conf.sh) | Pi is pinned to 1.5.2; platform paths and runtime identity already have an owner. |
| [Package manifest](../../agents/package.json) | The managed package declares the permission adapter and shared skills; optional plugins are not currently selected by profile. |
| [Configuration input](../../agents/config.py), `validate()` / `pi_input()` | Pi top-level fields are explicitly allowed and one selected platform snapshot is produced. |
| [Profile owner](../../agents/providers/pi/runtime/configure.js), `resolveProfiles()` | Unknown profile keys refuse; current allowed keys contain no plugin selection/options. Setup and credential-requiring launch are separate. |
| [Managed launcher](../../agents/providers/pi/runtime/launch.sh) | Leading `--profile` selects a run; one validated snapshot supplies native arguments and the profile's native directory. Lifecycle mutations through `pi-sot` are deliberately refused. |
| [Lifecycle adapter](../../agents/providers/pi/lifecycle.sh), `pi_native_package()` | Existing install registers the local package with native Pi. Runtime acquisition is separate; Windows environment transport already has a helper. |
| [Lifecycle contract](../../agents/lifecycle/README.md) | Reapplying the selected provider is already supported; no new apply command is needed to express this feature. |

### Native and public evidence

- [Pi 1.5.2 packages](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/docs/packages.md)
  support local packages, per-package resource filters, and invocation-specific `-e` loading.
  Remote `-e` sources can acquire/update dependencies during startup: use already available
  local paths for the managed selection, not a launch-time package download.
- [Pi 1.5.2 CLI](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/docs/cli.md)
  documents repeated `--extension` and `--no-extensions`; the latter disables discovered and
  configured extensions. Selection must not inject it and accidentally remove the managed guard.
  The current launcher also forwards operator-supplied native arguments unchanged, including
  `-ne` / `--no-extensions` and `-e` / `--extension` sources. Explicit extensions can remain
  active while the normally discovered mandatory adapter is disabled.
- [Pi 1.5.2 tool-image normalization](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/utils/tool-result-images.ts)
  keeps the original image when `processImage()` returns failure. Native resizing defaults in
  [the resize core](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/utils/image-resize-core.ts)
  are 2000 pixels per side and 4.5 MiB of base64 payload, but are not a hard outbound guarantee
  for all inputs, failures or configured overrides.
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
  Per-image constraints also apply: 32 MiB for inline images, 8192 pixels per side below
  15 images, and 4096 per side for 15 or more. These are direct-route documentation, not
  universal gateway defaults. Payload bytes, individual image size and dimensions are distinct.
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
- `pi-image-budget` identifies itself as 0.2.0 at audited commit
  `742e9f0afd1e303117fa28c41c9ef50b9b7e3d66`. It loads through a Git or local package.
  The Git repository advertises no tags or GitHub releases and the exact npm package name
  returned 404. Use the commit for reproducibility. Its dev runtime range is `^0.87.1`.
  [Pinned manifest](https://github.com/Aaalice233/pi-image-budget/blob/742e9f0afd1e303117fa28c41c9ef50b9b7e3d66/package.json).
- Its unmodified `node --test test/*.test.ts` passed **57/57** with GenosAI's Pi 1.5.2 runtime.
  The unmodified `node scripts/e2e.mjs --turns=10` exited **1** on a local 8 MiB gateway.
  Turns 1–7 succeeded. Turn 8 sent about 8.1 MiB, received 413 and logged a lowered limit,
  with no second request in that turn. Turns 9–10 succeeded around 6 MiB. The four-turn
  `--without-extension` control reproduced 413 at about 9 and 12 MiB on turns 3–4.
  Native Windows Pi 1.5.2 on Node 24 independently reproduced the same first seven successes
  and the same unretried turn-8 413 (`--turns=8`, exit **1**). These runs demonstrate package
  loadability and useful reduction in both CLIs, plus a concrete same-turn recovery gap.
  [Upstream harness](https://github.com/Aaalice233/pi-image-budget/blob/742e9f0afd1e303117fa28c41c9ef50b9b7e3d66/scripts/e2e.mjs).
- A diagnostic rerun kept the candidate source intact and added a read-only settle observer.
  With native auto-compaction enabled, upstream proposed only a learned-limit entry and no
  continuation after the 413. With auto-compaction disabled in the fixture, the same turn
  retried once at about 6.0 MiB and completed. Pi classifies 413 as overflow and can omit the
  failed attempt from projected messages before `agent_before_settle`. Upstream searches those
  projected messages for the failed attempt before it offers recovery. This makes native overflow
  coordination a compatibility requirement. [Pi session loop](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/core/agent-session.ts).
- Pi can append the failed-attempt omission before preparing automatic compaction. The
  `session_before_compact` hook runs only after a valid cut point has been found. It receives
  the compaction reason and raw branch entries. Returning `{cancel: true}` at that point
  prevents the summary request and new compaction entry. An earlier omission can still be
  present, including in short branches where Pi could not prepare compaction at all.
  [Overflow classifier](https://github.com/earendil-works/pi/blob/v1.5.2/packages/ai/src/utils/overflow.ts)
  and [compaction preparation](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/core/compaction/compaction.ts).
- A WSL diagnostic retained the pinned candidate and set the fixture's recent-token budget to
  256 so Pi could find a valid cut point. After turn 8's 8.1 MiB HTTP 413, the endpoint recorded
  two summary requests and one native continuation with zero images. Pi emitted `session_compact`
  for `overflow`, and the CLI exited zero. The upstream exit status alone therefore cannot
  distinguish native text compaction from the desired image-only recovery.
- The earlier local CLI cancellation probe against Pi 1.5.2 observed zero loopback HTTP
  requests for each of the byte, count, individual-image and measurement-failure abort cases.
  The throw-only control reached the endpoint and a transient-error control retried. A later
  discovered transform could still grow an accepted request. This is feasibility evidence for
  the tested JSON CLI mode and hook ordering. Native Windows and interactive acceptance remain open.
- [pi-imagefiles routing](https://github.com/adamcjm/pi-imagefiles/blob/main/extensions/pi-imagefiles/src/scan.ts)
  requires a `deepseek*vision*` model ID; `deepseek-flash` does not match.
  Its [credential resolver](https://github.com/adamcjm/pi-imagefiles/blob/main/extensions/pi-imagefiles/src/files-api.ts)
  returns the auth entry's key literally. That does not resolve GenosAI's command-reference
  credentials. Files API uploads also introduce remote storage, expiry and credential handling.

### Corrections and unverified areas

The proposed outbound-only approach is justified; production-grade compatibility is **unverified**.
The upstream image-budget final guard can warn and return an unchanged oversized payload when
no images can be removed. It also reads independent user/project configuration, matches learned
state by provider/model, and appends recovery/custom entries. The factory's injected option is
limited to resizing, so the configuration and exact-route options need an explicit upstream seam
or a narrowly patched entrypoint. Its own tests accept hard per-request caps outranking recent-image
protection and dropping a protected invalid image. Verify the stricter current-image contract through
the integration. [Pinned implementation](https://github.com/Aaalice233/pi-image-budget/blob/742e9f0afd1e303117fa28c41c9ef50b9b7e3d66/src/index.ts).

Zero-dispatch cancellation, the supported managed ordering, Windows native loading,
resumed-session behavior and bounded recovery on pinned Pi remain implementation acceptance
gates. Third-party final-payload ordering is not guaranteed. Do not claim any socket error is
cured by this feature.

## Current architecture and source of truth

[Project architecture](../../docs/architecture/structure.md) owns subsystem boundaries.
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

**Approved by D7:** reuse ordinary `make install PROVIDER=pi PLATFORM=host|windows|both`
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
globally or per profile without acquiring it again. Managed selection introduces no launch-time
network acquisition.

Before connection projection, native initialization or extension loading, the managed launcher
must refuse operator-supplied `-ne` / `--no-extensions`. No operator decision accepts disabling
the mandatory permission adapter through this route. Refuse native CLI extension sources that
can trigger acquisition, including npm, git and remote URL forms; direct users to reviewed
configuration and the existing lifecycle route. Preserve any permitted existing local extension
behavior within the declared foreign-ordering exclusion. Validate using pinned Pi's option
semantics, including repeated options, consumed option values and `--`: do not substring-scan
prompts or mistake an option's literal value for an active disabling flag. Raw Pi remains the
explicit unmanaged route. Do not claim this makes in-process extensions a security sandbox.
This CLI policy does not prove native foreign package declarations never fetch; document that
existing native behavior as outside the managed acquisition guarantee, rather than silently
rewriting foreign settings or adding a second package policy system.

Loading order is a supported-composition contract, not a universal final-hook guarantee.
Order GenosAI-managed payload transformers deterministically, with budget validation after
the managed payload-growing transformations. Test that actual order, not just argv construction.
Do not disable or reorder foreign resources to manufacture this guarantee: independently loaded
third-party hooks may still run afterward. A combination with an unverified later transformer is
outside the guarded-composition claim and must be reported as such, not silently certified.
If arbitrary-extension coverage is later required, it needs a genuine last-stage transport guard
and separate review; this task does not add that framework.

### Replaceable unblocker boundary

The Pi-owned adapter consumes an external dependency under D4 and D8. GenosAI owns selection,
validated route options, native integration and final refusal. The replaceable algorithm owns
image selection, compression planning and candidate construction. GenosAI verifies the candidate
with its own size and count checks.

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

Use Pi's SDK package manager during an explicit managed install to acquire the pinned
`pi-image-budget` Git revision. The dependency owner verifies imported helper files and publishes
one owned checkout per platform. Every managed profile shares that checkout. The launcher loads
the GenosAI adapter, which imports upstream selection, resizing, sizing and error classification
helpers from the verified local checkout. The adapter owns protected-image policy, route matching,
request refusal and Pi 1.5.2 recovery. Direct registration of the upstream entrypoint would add
its independent options and retry hooks. The public source contains the pin and adapter, and the
external checkout retains its MIT license.

### Native overflow coordination

Keep native auto-compaction enabled during acceptance. The compatibility layer owns a
single pending attempt in process, using the existing upstream recovery state where practical.
Coordinate the following Pi lifecycle hooks for the same branch, input and effective route.

1. At `message_end`, bind the confirmed rejection to the failed assistant and to the measured
   request that elicited it. Record the image count or bytes and which reduction is possible.
   A generic HTTP 413 identifies a body-size problem. Treat it as recoverable by this plugin
   only when the measured attempt contained eligible images and the same history admits a
   demonstrably smaller candidate within the route limits. Keep explicit token overflows,
   text-only failures and ambiguous errors out of the plugin recovery path.
2. At `session_before_compact`, cancel only `reason: "overflow"` with `willRetry: true` when
   the raw branch identifies that same current failed attempt and its smaller candidate is
   ready within the remaining recovery allowance. If attribution or reduction is uncertain,
   leave Pi's decision in force. Manual and threshold compaction keep their normal behavior.
3. At `agent_before_settle`, match the pending failure to the raw attempt and current projection.
   Recover even if Pi already hid the failed assistant. Reuse its existing omission and add a
   context edit only when the identified failed assistant still contributes to the projection.
   Check `canContinue` against the context after any necessary omission. Consume the allowance
   before requesting continuation and recheck the exact reduced body at the request boundary.
   The same continuation path must work on short branches where the compaction hook never ran.

Invalidate stale recovery state on success, abort, settlement, input or route/branch change.
Preserve session originals, relevant tool pairs and ordinary Pi compaction. Keep the
compaction-disabled run as a diagnostic control. It does not satisfy the production gate.

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

For an opted-in route, validate applicable individual-image byte and dimension limits on the
final candidate as well. Keep these restrictions configurable through the same adapter/options
boundary; no separate image-processing framework or global provider-name constants. Specify
the byte basis explicitly: native base64-payload targets, serialized request bytes and the
provider's single-image size restriction are not interchangeable measurements. Reuse Pi's
native processor for resizing and inspect the resulting image, not just its success flag.
Evaluate count-dependent dimension limits using the final image count and recheck after
reduction; test the 14/15-image boundary. Failed normalization can leave an original image in
history, so validate that original if it remains in the outbound candidate. Unknown image
measurements fail closed. Resize a protected image when permitted; if it still violates an
applicable hard limit, refuse with zero dispatch instead of silently omitting or forwarding it.
Older omissions remain subject to the established history/protection policy. This adds no
claim of complete provider-input validation: other unsupported image forms or restrictions
must be explicitly outside the supported adapter contract, not marked compliant without proof.

**Coverage:** guarantees apply to supported normal agent-turn requests (including subsequent
tool-loop requests) on the tested API/transport and managed extension composition. They do not
cover compaction, branch summaries, independent nested model calls or arbitrary later third-party
transformers. Document and test this boundary rather than calling the hook provider-wide.

**Technical gate:** first test `ctx.abort()` inside the payload hook against an actual 1.5.2
recording local endpoint. Oversized, over-count, per-image-invalid and unmeasurable candidates must
produce zero HTTP requests, including with native retries enabled and after the run settles.
A caught throw may accompany an abort for diagnostics; throwing alone, warning, or returning
invalid payloads is not acceptable. Test managed payload-growing handlers before validation,
and a later foreign handler as a negative control for the documented ordering boundary.
Inspect cancellation and serialization ordering before implementation depends on them. If no
supported mechanism meets this invariant, stop that path and return for review; do not silently
weaken the guard or fork the provider/runtime.

Retry only a confirmed byte/count rejection, only with a measured reduction in the rejected
dimension while satisfying all applicable configured limits, and with at most one plugin recovery per
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
| `pi-image-budget` at the audited Git commit | Measures final JSON and supports independent image budgets. GenosAI supplies profile integration, protected-image enforcement, request veto and same-turn recovery. | Selected external dependency. |
| [pi-image-slim 0.2.2](https://github.com/wiidede/pi-image-slim/blob/15c290dc4c358eb9a2feed312dd61541fec56ac7/index.ts) | Default `tool_result` compression changes saved tool image bytes. `compress: false`, `caption: false`, `strip: true` keeps the image pixels, but stripping still adds path or batch notes to persisted tool results. `maxKeptImages` counts image-bearing messages, and there is no serialized body cap | Useful for bandwidth or history-window policy. Strict outbound-only use would require isolating its strip hook. |
| [pi-image-compact budget component](https://github.com/Don-Yin/pi-image-compact/blob/db69dbaaccbc247f591c7305fe992c6b76abfdd6/src/budget.ts) | Budget-only hook omits older images from a request copy using fixed base64-image totals. The package manifest also enables compression and pruning by default. Pruning rewrites session files after compaction | Budget-only can preserve originals. It lacks final body, count and refusal checks. |
| Rewrite native package filters on each launch | Shared settings writer and concurrency/drift coordination for process-local selection | Prefer local `-e` selection with no new shared settings mutation. |
| New image-budget engine | GenosAI would own image policies, sizing, codecs integration and recovery regressions | Unjustified while the upstream implementation can be tested and adapted. |
| Files API image offload | Uploads, credentials, remote cache, quota and expiry lifecycle | Excluded from this scope; not a compatible drop-in. |
| Conversation compaction | Alters text context; byte guarantee still separate | Does not meet the history-preservation goal. |

## Required invariants

1. One private input owner; disabled public defaults and credential-free tooling installation remain valid.
2. Global plus selected-profile activation is deterministic, deduplicated and process-local.
3. Mandatory permission integration, shared skills and foreign resources survive installation and selection.
   Managed CLI overrides cannot disable the adapter or introduce remote extension acquisition;
   refusal occurs before projection/loading and respects native option/value/`--` boundaries.
4. No implicit runtime upgrade, global npm change, plugin credential reads or managed/CLI-triggered
   package acquisition at launch. Foreign native package declarations retain the documented exclusion.
   Native model authentication remains with its existing owner; verification uses no paid calls.
5. Saved originals and text are preserved; omission markers cannot replace unrelated text or tool IDs.
6. Actual serialized bytes, image count and applicable per-image byte/dimension limits are
   independently checked on the final candidate; failed native resizing is not evidence of
   compliance. Unknown measurement cannot produce a success result.
7. For the declared agent-turn transport and managed ordering, oversized/over-count/unmeasurable
   opted-in requests, including those violating individual-image limits, cannot reach transport.
   No universal final-hook or nested-call coverage is claimed.
8. Unmatched/non-opted-in routes are unchanged. Recovery budgets and learned limits never leak across routes.
9. Reapply is idempotent; uninstall removes owned resources only and preserves unrelated native files.
10. Diagnostics expose counts, bytes, route match, action and retry reason without bodies, images or secrets.
11. D4's adapter boundary keeps algorithm changes local; supported option changes and selection of
    shipped implementations require only configuration and next launch, with safety checks unchanged.

## Implementation tasks

- [x] Verify `ctx.abort()` against a recording endpoint on WSL and native Windows. Keep installed refusal regressions and record the later-foreign-hook negative control.
- [x] Record the failing configuration and native 413 controls and retain regression coverage in the [configuration tests](../../agents/tests/providers/pi/config.test.js) and [native Pi fixtures](../../agents/tests/providers/pi/README.md).
- [x] Extend `config.py` and `runtime/configure.js` at their existing schema/snapshot boundaries; support global plugins even when no connection profile is configured for setup. Keep normal bare launch refusal intact.
- [x] Extend `runtime/launch.sh` with deterministic native optional-extension selection and process-local non-secret options. Reuse Windows transport/path helpers when needed; preserve foreign environment entries and opaque prompt arguments.
- [x] Add pre-projection managed CLI refusal for extension-disabling flags and acquisition-capable remote extension sources. Verify pinned argument semantics and literal prompt/value handling; do not mutate foreign native package settings.
- [x] Add the smallest Pi-owned optional entrypoint/ID resolver needed for the selected contract. Keep optional modules out of unconditional manifest discovery; retain the existing mandatory package.
- [x] Establish D4's thin adapter contract and validate byte/count/policy options at the existing input boundary. Demonstrate two configurations and a synthetic replacement implementation without changing lifecycle/launcher code or reading an independent plugin config file.
- [x] Turn the reproduced same-turn 413 gap into a managed regression. Pin the audited Git revision, use Pi for managed acquisition, and verify the imported helpers. Record the dependency provenance and license.
- [x] Implement the three-hook overflow coordination at the upstream integration boundary. Prove that short histories recover after native omission and that a long, eligible history avoids the summary request only for the matched, recoverable image-limit failure.
- [x] Implement independent scoped byte/count budgets, boundary-derived protected-image policy, confirmed bounded recovery and observable refusal; verify supported OpenAI-compatible payload handling and explicit coverage/no-op behavior for unsupported routes.
- [x] Validate applicable per-image byte/dimension restrictions on final outbound candidates, reusing native processing. Cover originals retained in session history when a resize fails and the count-dependent dimension boundary.
- [x] Exercise install, uninstall, ownership, credential-free setup and second apply with separate public export fixtures. Keep acquisition and removal in the existing lifecycle.
- [x] Update stable owners below and register new source/test files through [source disposition](../../tools/source-manifest.json). The existing `todo/` scope covers this public plan.
- [x] Verify the supported native and public export paths, review the source disposition and inspect the final diff.

## Test-first and verification plan

### Red evidence

Permanent guards must be observed failing against the unchanged implementation before production edits.
Use generated public images, synthetic keys and local recording endpoints only.

| Case / evidence type | Wrong or missing behavior to demonstrate before implementation |
|---|---|
| Global/profile selection — permanent guard | New plugin fields are refused today; no global/profile union, deduplication or override contract exists. |
| Configurability/replaceability — permanent guard + acceptance | Change limits/policy and select a synthetic alternate adapter using only configuration and next launch; verify different outbound results, unchanged source/native registration and identical independent safety enforcement. |
| Validation/no mutation — permanent guard | Establish unsupported ID/options/budget and inherited-environment controls; verify refusals leave native files unchanged. |
| Managed CLI overrides — permanent guard + native acceptance | Current launcher forwards `--no-extensions` and `-ne`; prove each refuses before projection, native initialization, extension execution or requests. Cover remote npm/git/URL sources through `-e` and `--extension`, repetitions and supported native forms; acquisition counters stay zero. Preserve prompt text after `--`, literal flag-like option values, spaced paths and supported local-extension behavior. |
| Native lifecycle — acceptance | Installed route cannot yet enable one optional extension only for a selected profile while preserving guard/foreign extensions. |
| Aggregate bytes — permanent guard + native acceptance | Multiple individually valid synthetic images exceed a local body ceiling and the current route sends an oversized request. Test reduction from above 40 MiB, a smaller gateway ceiling and the 48 MiB boundary. |
| Image count — permanent guard + native acceptance | Tiny images pass byte checks but exceed a local 20/30-image cap; cover an 8-image option, exact-cap boundaries, and both constraints simultaneously. No model-name-derived global cap. |
| Individual-image constraints — permanent guard + native acceptance | Under aggregate byte/count ceilings, test excessive single-image size, excessive dimensions and native processing failure that retains the original. Cover configured smaller limits, the direct-route 32 MiB restriction, 8192/8193 and 4096/4097 dimensions at 14/15 images, and a reduction from 15 to 14. Permitted resizing must yield independently valid output; an invalid/unmeasurable protected image must produce zero dispatch with originals/text unchanged. |
| Request veto — permanent guard + native acceptance | A throwing hook currently does not prove zero dispatch. Test `ctx.abort()` for oversize, over-count and measurement failure with native retries enabled; record zero HTTP requests through settlement. |
| Ordering/coverage — permanent guard + native acceptance | Show a later foreign hook can invalidate an earlier check; prove managed growth precedes the guard and do not claim the foreign case is protected. Inspect/test normal turns versus compaction/branch/nested paths to delimit hook coverage. |
| Protected images/history — permanent guard | Define current/unprocessed and successful-answer history, then demonstrate missing outbound reduction; assert original records/text/images remain intact after reduction, retry and resume. |
| Route switching — permanent guard | Cover matched opt-in, non-opt-in, differing endpoint/API/model, native model switch and two process-local selections without shared plugin-setting mutation. |
| Short-history recovery — permanent guard + native acceptance | Under native auto-compaction, reproduce a 413 where Pi omits the failed attempt but cannot prepare a summary. It must settle after exactly one smaller retry in the same turn. Assert one omission or reuse of the existing omission, with original records and tool pairs intact. |
| Long-history image 413 — permanent guard + native acceptance | Seed enough real session entries for Pi to prepare overflow compaction. The known-bad control must receive a summary request and append a native compaction entry. With the fix, observe the matching `session_before_compact` decision, zero summary requests, zero new compaction entries and one smaller successful retry in the same turn. Require actual recorded wire bytes and no duplicate omission. |
| Genuine token overflow — permanent guard + native acceptance | On the same route and long fixture, return a recognized token-context overflow with images still present. Observe the native summary request, new compaction entry and native continuation. Also preserve manual and threshold compaction in targeted reason cases. |
| Recovery bounds and attribution — permanent guard | Explicit image-count rejection must reduce count. Repeated rejection after recovery, text-only 413, a protected image that cannot fit, stale route/attempt evidence, ambiguous 503, reset/401/429 and abort must not schedule plugin recovery or suppress unrelated compaction. Check interaction with native retries through settlement. |
| Platform/reapply/removal — acceptance | Real Windows and WSL native launchers must load the selected local entrypoints with Unicode/spaced paths; second install and owned removal preserve sentinels. |
| KISS/source/privacy — reviewer judgment | Check sole ownership, dependency/provenance scope, no extra operator config, and no private operational material. Do not replace this judgment with text-presence tests. |

Instrument the provider's received UTF-8 body and dispatch count, not only the plugin's estimate.
For the compaction fixture, distinguish summary and normal requests at the recording endpoint and
check raw session entries as well as hook events. An `overflow` start event can precede cancellation
  and is not evidence that the provider received a summary request. Use the same prepared history
  in all long-fixture arms so a missing cut point cannot make the suppression test pass vacuously.
For a veto case, prove a known-bad control reaches the endpoint when the guard is absent.
For serialization, include non-ASCII text, system instructions, tools and base64 expansion.
For image processing, decode resized outputs and exercise corrupt/unsupported inputs and failure paths.
Use valid generated images for dimension/size violations and a controlled native processing failure
to exercise retained-original behavior; malformed headers alone are not a production-shaped size test.
For CLI refusal, capture native-file hashes, extension/acquisition execution and endpoint counts.
No-mutation proof must cover existing owned projections as well as a fresh home, on both platforms.
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

Run deterministic JavaScript tests through [the existing Node boundary runner](../../agents/tests/providers/pi/test_adapter.py)
as part of `make test`. Run the installed image and launcher checks separately since their dependency
acquisition contacts public Git. Use registry-selected native Node and the pinned scanner.
Check source admission for newly incorporated implementation files before running release verification.

Use [fresh export and installed-route acceptance](../../agents/tests/providers/pi/README.md) in disposable
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
  paths, per-image byte/dimension checks, managed CLI override refusals, omission/refusal semantics,
  diagnostics and supported native acceptance. State the boundary for foreign native package acquisition.
- **Duplication avoided:** examples reference the executable schema; package pins/provenance have one
  owner. Stable docs, code, comments and tests must not reference this transient TODO.

## Rollout and rollback

After approval, prepare and verify in disposable environments first. No live cutover is authorized
by this document. Optional plugins remain disabled by default. Reverting a private enablement choice
and starting a new process disables the optional behavior without altering saved sessions; this is
not a claim to roll back an already submitted provider request. Use existing owned uninstall for
lifecycle removal, preserving foreign resources. Do not add a separate rollback framework.

## Completion criteria

Completion requires recorded red/green evidence for the
matrix, proven zero-dispatch refusal and actual serialized byte/count/per-image bounds for the declared
agent-turn transport/composition, preserved originals/text, configuration-only policy/adapter
selection changes, global/profile isolation, idempotent lifecycle/removal, and real Windows/WSL
installed-route proof. Unsupported third-party ordering and summary/nested calls are explicit exclusions.
Managed extension-disabling and remote-acquisition CLI attempts must refuse without mutation or
acquisition, while literal prompts and supported native argument values remain unchanged.
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

### 2026-11-20 — Per-image restrictions and managed CLI overrides

- **Assessment:** F6 accepted: native resizing defaults do not establish outbound compliance,
  because failed tool-image normalization preserves originals. F7 accepted: forwarded native
  flags can disable discovered permissions while explicit optional extensions remain enabled.
- **Changes:** added configurable final per-image checks, native-failure and 14/15-image boundary
  tests, pre-projection CLI refusal, remote-source no-acquisition controls and literal-argument tests.
  Kept the existing adapter/lifecycle architecture and cancellation experiment first.
- **Qualification:** defaults are not unconditional native guarantees; CLI acquisition refusal
  does not establish a no-network guarantee for arbitrary foreign native package declarations.
- **Verification:** inspected pinned normalizer, resize defaults, CLI parser and current launcher;
  checked public provider limits and the amended document. Runtime behavior remains unverified.
- **Authority:** no new operator decision or implementation approval; Q1 remains open.

### Community candidate audit

- D5 authorized the first local experiment. D6 paused production edits for candidate evaluation.
- The standalone cancellation probe passed its four abort cases and the dispatch and ordering
  controls. This does not cover a managed plugin running on native Windows.
- The pinned upstream CLI test missed same-turn 413 recovery on WSL and native Windows despite
  a passing unit suite. A WSL diagnostic with native auto-compaction disabled isolated the
  overflow interaction. The managed acceptance test keeps native auto-compaction enabled.
- Public downloads indicate distribution. The community report exercised its author's separate
  filter on Pi 1.5.2/Linux and does not establish package adoption or Windows reliability.
- A4 replaces the earlier selective-first approach. Q2 remains open for the revised approach.

### Native overflow review

- The pinned source confirms that native Pi handles overflow before settlement. Its omission
  can predate `session_before_compact`, and compaction preparation can fail before that hook.
- The proposed coordination now covers both paths. It requires a matched, reducible request
  before cancellation and a continuation that reuses any native omission.
- The long-history control recorded `413`, two summary requests and a successful image-free
  continuation. This establishes the failure mode before adding the managed regression.
- Corrected A3's label. Candidate loadability supports the upstream-first choice and does not
  invalidate selective reuse as a technical option.
- Q2 remains open for the revised plan.

### Implementation and install-time pin check

- D7 approved local implementation. The managed launcher selects optional local plugins from the
  validated connection snapshot. The adapter uses the upstream planner, scrubber, image processor
  and classifier. It excludes protected images from the upstream removal passes and measures the
  resulting provider payload.
- The native local gateway regression confirmed both paths. Without the budget, Pi dispatched
  two summaries after HTTP 413. With the budget, WSL and native Windows each recovered in one
  smaller request with no summary, retained saved originals and used the learned limit on resume.
  Genuine token overflow still dispatched native summaries. Oversized text and protected images
  that could not fit produced zero requests.
- A disposable `pi install` resolved the exact Git revision and persisted an entry in package settings.
  D8 switched acquisition to the pinned [Pi SDK package manager](https://github.com/earendil-works/pi/blob/v1.5.2/packages/coding-agent/src/core/package-manager.ts).
  The managed installer calls its acquisition method and publishes a verified ownership record.
  Matching reapply reads the checkout locally. Launch verifies and loads the helper modules without
  activating the upstream extension. This allows GenosAI to retain its tested compatibility behavior
  with the upstream modules intact.

### External dependency acceptance

- `make check` and `make public-check` passed. From an independent public export, `make test`
  ran 293 tests with 11 skips. Native Pi acceptance ran separately on real WSL and Windows Pi 1.5.2.
- An exported `PLATFORM=both` install acquired the pin once per OS, reapplied from the local
  checkouts, verified both native launcher versions and removed the owned checkouts. Both unrelated
  cache sentinels survived. The Windows fixture used a Unicode path with spaces. Git's long-path
  support was set only for the acquisition process. An unusually deep fixture still exceeded the
  Git for Windows HTTPS helper's path limit.
- With a 48 MiB loopback gateway, the guarded request dropped from about 54.1 MB to 29.5 MB.
  Each native runtime made one smaller retry after a 413, with zero summary requests for that
  rejection. An explicit 20-image cap rejection recovered from 25 to 15 images. The ambiguous
  503 control retained the original images during Pi's native retries. Saved history prefixes
  stayed byte-identical. Oversized text and protected per-image size violations reached no endpoint.
  A gateway that kept returning 413 triggered exactly one plugin retry and no learned limit.
- Both platforms preserved manual, threshold and genuine token-overflow compaction. The inline
  image just below 32 MiB was sent unchanged. An image above that limit was resized below it while
  keeping the saved original. Valid 8192/8193 and 4096/4097 dimension fixtures exercised the ceilings.
  A protected image with a valid header and unreadable raster failed resizing and produced zero
  requests. Two unanswered screenshots reached the gateway under an image cap of two, and three
  unanswered screenshots under the same cap produced zero dispatch.
- An in-session switch sent one request on the alternate route. Switching back reactivated the
  guard and refused before dispatch. Pi's native tool-image normalizer retained a corrupt fixture
  image. The guard then refused the request carrying the saved tool result and preserved its tool ID.
- Both managed launchers refused extension-disabling flags and remote extension sources before
  dispatch. The existing settings, authorization projection and model projection stayed byte-identical.
- The feasibility probe recorded zero dispatches after `ctx.abort()` with retries enabled. The
  throw-only control sent a request. A later independently loaded hook enlarged a payload after the
  guard, confirming the foreign-ordering exclusion.
- A separate fresh public export acquired the pinned runtime with `PLATFORM=both RUNTIME=1`,
  with no provider credentials. Both launchers showed version and help and refused unconfigured
  sessions. Removal preserved unrelated native files on both platforms.

### Image identity review

- The unchanged adapter refused a request with three identical historical screenshots under a
  two-image cap. With occurrence tracking, the newest screenshot reached the loopback gateway.
  On both pinned runtimes, a 413 with four identical screenshots recovered with two images and
  retained the newest occurrence. A fixture that inserted an unmatched wire image produced zero
  dispatches under the same count cap.
- The path-keyed adapter repeated a 413 after reacquiring the same upstream revision at a new
  checkout path. The corrected adapter resumed with one successful request on WSL and Windows,
  even with the budget option keys reordered. Each fixture verified byte-identical saved history
  prefixes. Previously recorded path-keyed limits can be learned again as needed.
  The loopback evidence above covers the pinned dependency acquisition and its managed integration.
