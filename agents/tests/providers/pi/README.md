# Pi verification

## Contents

- Verification entrypoints
- Transport acceptance
- Direct-provider acceptance

## Verification entrypoints

| file | proves |
|---|---|
| [test_gate.py](test_gate.py) | Pi rule families, shared failure propagation and context ownership |
| [test_adapter.py](test_adapter.py) | runs the native Node adapter/config/probe suites; Node is required |
| [adapter.test.js](adapter.test.js) | fail-closed dispatch and real sleeping-interpreter tree termination with PID generation checks |
| [config.test.js](config.test.js) | single-snapshot projection and session-local selection, source preservation, native argument forwarding, installed-version refusal, read-only preflight, ownership, writer locking and mutation refusal |
| [probe.test.js](probe.test.js) | single-use probe, request limits and bounded helper cleanup |
| [probe.js](probe.js) | acceptance-only extension fixture, excluded from the production package |
| [live.js](live.js) | bounded launcher, Git preservation and native evidence validation |
| [session.js](session.js) | installed SDK execution, explicit generation end and single-dispatch transport guard |
| [run.sh](run.sh) | paid acceptance interface reading the active SOT profile |
| [process.js](process.js) | authoritative process-generation identity and termination checks |
| [endpoint.js](endpoint.js) | managed native launch against two local endpoints after SOT-only profile changes |
| [endpoint-profiles.json](endpoint-profiles.json) | synthetic configuration with arbitrary profile/provider IDs, both compatible APIs and a different active selection |
| [Native catalog fixture](profiles.json) | synthetic primary/secondary selections and generic credential references |
| [catalog.js](catalog.js) | selected native endpoint/effort survive newer cached and refreshed catalogs; unprojected control demonstrates native clamping and route drift |
| [compatible.js](compatible.js) | native custom-model schemas, transport/replay, owned cleanup and retained-runtime credential loss after shared profile switching |
| [native.js](native.js) | installed SDK loading, exactly seven SOT skills, instruction sources and healthy permission refusal; no model call |
| [transport.js](transport.js) | installed Pi against a recording local provider with synthetic credentials |

[The shared offline entrypoint](../../README.md) runs discovered Python and nested Node tests.
Run on WSL and native Windows. Windows skips WSL installer fixtures explicitly, while gate/adapter tests
must run, including real process cleanup. Deterministic tests do not prove direct authentication.

For the installed loader, use each platform's configured native Node:

```bash
node agents/tests/providers/pi/native.js <installed-package-dist/index.js> <repo-root> <native-agent-directory>
```

## Transport acceptance

```bash
node agents/tests/providers/pi/transport.js <native-node> <installed-pi-cli> <ignored-fixture-directory>
```

The harness records outgoing payloads, native nested tool events and probe results. The accepted SDK
runner preserves Pi's native boundary dispatch/persistence, then returns `action: end` after the first
assistant generation, so acceptance cannot continue past the accepted generation regardless of how a
runtime treats an extension's `continue: false` on post-tool continuation. The production CLI and
permission adapter use their ordinary routes.

A fetch guard permits one dispatch to the selected model's endpoint, checks the actual output-token
field and refuses unknown payloads, redirects or further dispatches. For native OpenRouter models,
acceptance sets Pi's routing option to disable provider fallbacks and verifies the serialized flag
before dispatch. The acceptance settings disable session and
provider retries, compaction and cache warming. The probe is single-use; truncation, unexpected tools,
missing results, extra generations and unknown cleanup fail acceptance. Captures exclude authentication
headers. Native usage/cost fields are retained; catalog-derived prices are estimates, not billing receipts.
The summary distinguishes a provider-reported total from a catalog estimate; neither is a billing receipt.
Response-stream observation records HTTP status and checks the returned model identity without an
additional request. Credential-shaped strings are redacted before event and session-message storage.

Run `normal` first. Then pass a fifth argument for each known-bad control: `thinking-control`, `cap-control`, `stop-control`,
`retry-control`, `provider-failure`, `truncated`, `fixture-error`, `missing-probe`, `timeout`, `redirect`. A control
must reach the local transport and demonstrate its specific fault before rejection counts as proof.
The cleanup unit control separately observes a real surviving process generation and rejects it.

The managed-launch profile check consumes the installed CLI against synthetic local endpoints:

```bash
node agents/tests/providers/pi/endpoint.js <installed-pi-cli>
node agents/tests/providers/pi/endpoint.js <installed-pi-cli> agents/tests/providers/pi/endpoint-profiles.json
```

It copies the configuration/runtime owners into ignored scratch, prepares synthetic endpoints/keys, and proves
model/endpoint/key/thinking-level selection, the native outbound thinking fields and invalid-profile
refusal without modifying the operator profile.
It enumerates the supplied profiles and selects them through the managed `--profile` argument,
then returns to the configured default with no selector. The copied SOT stays byte-identical across
override launches. There is no fixed production profile list or default in the test.
Each model's outgoing thinking fields are compared with native SDK serialization; profile names,
providers and reasoning formats do not select special test branches. The optional second argument
supplies a different profile file; the synthetic fixture proves config-only changes across both
compatible APIs, arbitrary names and an omitted effort. The test verifies credential/model ownership
cleanup and invalid-selection/effort refusal without modifying protected projections. Hy4-specific
mode/capability checks belong to `compatible.js`.

Verify the selected native model against a newer synthetic cached catalog:

```bash
node agents/tests/providers/pi/catalog.js <installed-pi-cli>
node agents/tests/providers/pi/catalog.js <installed-pi-cli> unprojected-control
```

The SDK restores the planted catalog through ordinary startup with catalog networking disabled,
then consumes a synthetic fresh response through its native catalog refresh path.
The test checks native request URLs and reasoning fields with and without a profile endpoint
override. Synthetic credentials and an injected transport prevent external requests. The control
removes only the fixture's generated model definition and must observe the capability change and
outbound clamped effort; a test that bypasses cache restoration cannot satisfy this check.

Exercise compatible-model semantics through the installed native SDK:

```bash
node agents/tests/providers/pi/compatible.js <installed-pi-cli>
```

The test uses synthetic credentials and transport, validates native schemas and unsupported levels,
and inspects serialized images, tool results and preserved reasoning. It does not contact Tencent.
It also retains an already loaded native runtime while the shared projector selects another provider:
the earlier runtime loses access to its removed synthetic credential. This proves why profile
switching requires sequential sessions rather than promising concurrent isolation.

## Direct-provider acceptance

After native offline enforcement passes, the authorized paid interface reads the active Pi connection
profile through [profiles.json](../../../providers/pi/runtime/profiles.json) (validated by its
`configure.js`):

```bash
bash agents/tests/providers/pi/run.sh <fresh-directory-under-repository-tmp>
```

Run from WSL or native Git Bash. This generates one paid response through the configured provider,
with a 2,048-output-token cap and 180-second deadline. No automatic retry occurs. The native credential
owner consumes configured command references opaquely; no plaintext key is copied into fixtures.
The fixture has one committed README and no remote. Only the probe's scratch write may change its
working tree; HEAD, logical staging, stash and nonexistent protected targets must survive unchanged.
The runner carries the selected startup thinking level into the SDK session. The probe changes only
the output cap; it preserves Pi's native thinking fields. Acceptance compares configured, loaded,
probe-context and actual outgoing thinking evidence, and rejects a deliberately altered effort.
An omitted profile effort retains Pi's native default.

Results, session files, loaded-resource evidence, transport ledger and preservation snapshots stay in
the ignored fixture directory. Per-generation enforcement belongs to this acceptance route; ordinary
[supervised provider use](../../../providers/pi/README.md) retains its normal behavior.
