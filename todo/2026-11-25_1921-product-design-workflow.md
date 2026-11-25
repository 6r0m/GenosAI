# Product design and rendered acceptance

**Status:** REVIEW REQUIRED

**Scope:** GenosAI design-skill guidance and remaining fresh-agent verification

**Stable documentation owner:** [Frontend design skill](../agents/skills/frontend-design/SKILL.md)

## Contents

- [Goal and authority](#goal)
- [Evidence and architecture](#verified-evidence)
- [Decision and invariants](#decision)
- [Implementation and verification](#implementation-tasks)
- [Review record](#review-record)

## Goal

An agent handling a material UI change should understand the user's task, produce a layout and interaction flow that fit the product, and verify the result in the running interface. The workflow should catch misplaced navigation, poor grouping, inconsistent windows and dialogs, and visual drift before it reports completion.

## Authority register

### Operator decisions

- **D1** Investigate GenosAI's design skills and whether Codex can use them. Explain the recurring problems in layout logic, window consistency, and overall style.
  - Effect — Assess both the methodology and its delivery.
  - Reason — Significant design problems recur.
  - Date/source — 2026-11-25, operator request.
- **D2** Use `investigate-change` for this request.
  - Effect — Deliver one reviewable implementation todo. Implementation requires subsequent approval.
  - Reason — Not stated.
  - Date/source — 2026-11-25, explicit skill invocation.
- **D3** Evaluate both reviews against the actual system and apply valid code and documentation fixes for current functionality or future scalability.
  - Effect — Authorizes the in-scope review fixes in this round.
  - Reason — Not stated.
  - Date/source — 2026-11-25, operator review-and-fix request.
- **D4** Evaluate the follow-up review against the repository, project goals and prior decisions, and apply valid code and documentation fixes.
  - Effect — Authorizes the in-scope follow-up fixes.
  - Reason — Not stated.
  - Date/source — 2026-11-25, operator follow-up review-and-fix request.

### Operator gates

Live model evaluation requires separate authorization under the [evaluation contract](../agents/tests/evaluation/README.md#frontend-design). Offline work under D3 is independent of that gate.

### Working assumptions

- **A1 [ACTIVE]** Treat windows as product surfaces, including web dialogs and native windows. Use an established operational workbench as the first evaluation subject.
- **A2 [ACTIVE]** Treat the attached report as a source of hypotheses and example defects. Use sanitized reproductions where a failing-session trace or current product fixture is unavailable.

## Non-goals

Product-specific changes and live cutover are outside this work. Product repositories own their design systems and may define their own acceptance checks.

## Verified evidence

- The baseline frontend entry at `f035778` provided visual direction, copy, responsive design, and optional screenshot critique. It had no specific process for identifying incumbent view ownership, task-order grouping, reusable control families or constrained-window acceptance. The exact baseline body is now the [pinned conditional reference](../agents/skills/frontend-design/references/vendor/anthropic/frontend-design.md).
- The [technical web audit](../agents/skills/web-design-review/SKILL.md) reports pinned checklist findings for named or changed web files. Its former description also invited general UX review, broader than the implementation. Its discovery description now names the technical scope.
- Native Windows Codex `0.172.0` and Ubuntu WSL Codex `0.171.0` discovered the baseline canonical design skills with zero errors in `skills/list`. The debug prompt exposed skill metadata. These checks establish discovery and prompt visibility for the tested checkout. Actual selection in failing sessions and the live Orchestra launch context remain unverified. [App-server skills protocol](https://learn.chatgpt.com/docs/app-server#skills).
- At published Orchestra revision `6609361`, the shared stage map is empty and explicit bindings lead their role prompts. The picker inserts a file-read request. Workbench owns its shared tokens, controls and responsive layout in `style.css`. [Stage settings](https://raw.githubusercontent.com/6r0m/orchestra/6609361/.orchestra/settings.json), [prompt assembly](https://github.com/6r0m/orchestra/blob/6609361/app/agents/nodes.py#L237-L270), [picker](https://raw.githubusercontent.com/6r0m/orchestra/6609361/app/interfaces/workbench/static/skills.js), [Workbench owners](https://raw.githubusercontent.com/6r0m/orchestra/6609361/app/interfaces/workbench/static/README.md).

## Current architecture and source of truth

[Universal instructions](../agents/AGENTS.md#policy-context) own conditional cross-cutting policies and authority. [Skills](../agents/README.md#skills) are selected by description or invoked explicitly. [Lifecycle](../agents/lifecycle/README.md#shared-resource-contracts) projects canonical skill paths, [Pi's package](../agents/package.json) exposes direct skill entries, and the [source manifest](../tools/source-manifest.json) owns artifact admission. The frontend skill owns UX/UI method. The evaluation owner specifies evidence for selection and quality.

## Problem and root cause

The baseline made it possible to produce a polished local screen and satisfy a technical checklist while missing navigation ownership, workflow order, shared control patterns or usable action placement. The old technical description also competed for holistic review requests. These are concrete gaps in skill content and scope. Native discovery succeeded locally. A missed implicit selection can also come from what reaches the model, including shortened or omitted catalog metadata. [Codex skill discovery and metadata budget](https://learn.chatgpt.com/docs/build-skills).

## Decision

Keep the existing `frontend-design` entrypoint and make it own task flow, layout logic, cross-screen consistency and rendered judgment. Make the upstream visual guidance a conditional reference with the same pinned bytes, path provenance and license. Scope technical review metadata to that skill's existing file-level audit. The skills are independently useful and may be selected together as a task requires.

### Premise / KISS gate

The existing frontend entry already owns UI design and has a portable invocation and projection. Extending it reuses that entry and adds only one conditional reference location. The trade-off is that product UX and visual direction share one invocation name. This preserves one selection surface and lets an agent load the deeper visual guidance when the brief calls for it.

### Alternatives considered

| Option | Assessment |
|---|---|
| Separate `product-design` entrypoint | Useful if evidence establishes distinct selection needs or a material discoverability gain. The current capability gap fits the existing frontend design owner. |
| Universal UI routing | Would add a global requirement for a specialist method. Existing native selection, explicit invocation and applicable project-owned instructions cover the available routes. |
| Upstream toolkit | Impeccable's operational UX and rendered critique inform the criteria. Its critique workflow adds machinery. UI/UX Pro Max primarily adds search and design-system generation, and Stitch includes service-oriented design-system workflows. [Impeccable](https://github.com/pbakaus/impeccable/blob/9e460a87ef338ee9d12c7beed8fedc597a5af5f7/.agents/skills/impeccable/SKILL.md), [UI/UX Pro Max](https://raw.githubusercontent.com/nextlevelbuilder/ui-ux-pro-max-skill/8db36338810d0942567b97ce439affd1619fcf31/README.md), [Stitch](https://raw.githubusercontent.com/google-labs-code/stitch-skills/75f4696f162000fb69fca6a31489b5b21d47a506/README.md). |

## Required invariants

1. Each skill keeps one discoverable entrypoint and its existing invocation name. Detailed guidance loads conditionally. Specialist knowledge respects the task's authority.
2. Product sources own navigation, interaction and styles. The technical audit keeps its read-only output and scope.
3. The distribution includes the pinned reference and license. The third-party notice links to the distributed files. Provider projections retain their existing settings, link and foreign-state protections.
4. Discovery, selection, application and rendered quality each require direct evidence at their own layer.

## Implementation tasks

1. [x] Reuse the existing design entrypoint, retain pinned content and license, and update the source manifest and catalog.
2. [x] Distinguish technical code-audit metadata and document the paired evaluation in the existing evaluation owner.
3. [x] Record candidate offline and native route verification in the review record.
4. [ ] Run the paired evaluation once authorized. Record which layer needs correction and revise only that layer.

## Test-first and verification plan

### Red evidence

The baseline skill body establishes the missing workflow steps. The [evaluation protocol](../agents/tests/evaluation/README.md#frontend-design) requires fixtures to show seeded navigation, settings and dialog problems before scoring either arm. Keep actual baseline responses as observed. Use ordinary UI prompts, explicit invocation, planning-skill composition and a backend-only negative control.

### Green evidence

Check the candidate's skill structure, reference and license bytes, public file admission, and skill discovery through the normal Codex routes. Use `make check`, `make test` and `make public-check` for the offline contracts and compare the baseline and candidate with `python3 agents/tests/report_cost.py`. Use the same [evaluation protocol](../agents/tests/evaluation/README.md#frontend-design) to determine whether selection and rendered outcomes improve.

## Documentation plan

The frontend skill owns the method, the agents README routes to it, the upstream lock owns provenance, and the [third-party notice](../THIRD_PARTY.md) identifies the bundled terms. The evaluation README owns the reusable quality and selection rubric.

## Completion criteria

The offline contract passes and the paired evaluation demonstrates applicable selection and a rendered quality gain under the predefined criteria. Report the behavioral outcome as unverified if model evaluation is unavailable or the observed outcomes do not discriminate.

## Review record

### 2026-11-25 — Investigation

- D1 and D2 recorded. Native Windows and WSL discovery and initial context were verified locally. The design proposal and evaluation are awaiting review.

### 2026-11-25 — Review corrections

- D3 recorded. The earlier global route and new skill were proposals. The local implementation follows the existing specialist entrypoint. Comparative model evidence is pending.
- `make check` and `make public-check` passed. An independent archive extraction passed the artifact privacy and configuration checks. The packaged guide and license match the baseline bytes. The skill authoring validator passed the frontend entrypoint. The web audit retains the documented Claude `argument-hint` extension.
- Native Codex on Windows and WSL each exposed one enabled canonical entry per design skill and both revised descriptions in `debug prompt-input`, with zero discovery errors. The estimated frontend body fell from 2,269 to 615 tokens before any conditional read.
- Extracted `make test` reported 302 passes, 9 skips and one failure. `test_windows_command_shim_with_spaces_empty_home_and_conflicting_policy` reported a nonzero Codex server shutdown. The same test failed on unchanged `f035778` when extracted to the WSL filesystem and passed when run natively on Windows.

### 2026-11-25 — Follow-up review

- D4 recorded. The third-party notice now identifies the Anthropic visual-direction reference and links to its shipped license. The release regression failed against the former license path before the notice was corrected.
- The frontend skill now consults the visual-direction reference when visual decisions materially affect the result, including refinement within the incumbent visual identity. Comparative model evidence remains pending.
- The notice regression passed after correction. An independently extracted distribution passed its artifact check, all 11 conformance tests and all 30 release tests. The vendored guide and license still match `f035778` byte-for-byte.
