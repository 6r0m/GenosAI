# Skill improvement history

This record captures changes to the shared skills, the effects observed in evaluation, and the limits of that evidence. The [evaluation guide](tests/evaluation/README.md) owns the test method. Each skill entrypoint owns its current instructions.

## Frontend design

### 2026-11-25 — Product design and rendered verification

The original pinned visual guidance emphasized distinct identity, composition, typography and copy. Commits `4ed5885` and `0afe2ff` kept the `frontend-design` entrypoint and added product-level guidance on task flow, component reuse, dialog behavior and rendered checks. The pinned visual guide became a conditional reference for material visual work, including refinement of existing interfaces.

In one text-only comparison, fresh agents given the original and revised skill proposed the same core layout fixes for a compact repository cleanup dialog. The revised skill produced a more specific plan for comparison against a neighboring dialog and for focus during error recovery. The exercise measured planning with the skill supplied directly.

### 2026-11-25 — Composition and a rendered refinement pass

The next revision asked agents to decide visual reading order before building, apply different composition choices to operational and expressive surfaces, and correct the largest issue seen in the rendered interface before recapturing it. The trial compared the prior entrypoint at `0afe2ff` with the candidate identified by SHA-256 `c2d9b00a3a02d07d70308b8ec08e5556258693eff6d0335446a00c1640fb1394`. One fresh agent per version built both fixtures with the same briefs, assets and tools.

| Fixture | Observed effect |
|---|---|
| Night Field photography workshop | The candidate gave the photograph and type a more cohesive hero and carried the editorial layout through the itinerary and reservation form. The prior version supplied a punchier headline and a stronger button accent. The candidate was preferred in this pair. |
| Latch repository cleanup dialog | Both followed the neighboring Notifications dialog, removed unrelated run controls, and kept Save visible at 720 × 480 with all 40 exceptions. The candidate used a clearer branch count, and the prior version made the long list easier to scan with row dividers. No material visual winner. |

Each implementation passed 15 dialog-flow and five reservation-flow checks in Chrome. The visual comparison used desktop and narrow screenshots, including dark mode and a failed save for the dialog. The landing composition win supported promoting the tested [frontend-design entrypoint](skills/frontend-design/SKILL.md). The result was one paired observation with subjective visual judgment and direct skill supply.

### 2026-11-25 — Native selection and preserving status during layout changes

Fresh Windows Codex sessions selected the design skill on ordinary requests for two held-out Relay workbench surfaces. A native explicit invocation also exercised the skill. A planning turn combined the planning and design methods, wrote one implementation todo and preserved its fixture sources. A backend-only retry-range change passed three tests without reading the design skill body.

The first Delivery implementation improved the compact layout and reused the shared controls, but dropped the existing last-delivery value. The preservation step was made explicit in the skill. Fresh retests read the revision on ordinary requests and passed 63 Chrome assertions. Repositories reused the shared search and kept the Runs route intact. Delivery kept one last-delivery value in its owning view, reused the Notifications button treatment, and kept Save reachable at 700 × 440 in both themes with all 24 destinations and after a rejected save. Save retry, draft preservation and focus return passed. The peer screenshots matched their baselines pixel for pixel.

These results close the recorded layout, reuse and selection criteria for the tested client and fixtures. The sample covers two operational surfaces and the prior expressive-page comparison.
