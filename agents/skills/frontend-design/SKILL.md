---
name: frontend-design
description: Design and critique user interfaces. Use for material changes to navigation, task flows, layouts, forms, settings, dashboards, windows or dialogs, and for visual direction and cross-screen consistency.
---

# Frontend design

Work within the current task's authority. Use the method to ground a plan, critique an interface, or implement a UI change as authorized. Record decisions and evidence in the project's existing workflow.

## Establish the product context

Identify the primary task, who performs it, and how they enter, complete, cancel, and recover from it. For an existing product, inspect the affected surface and comparable neighboring views. Find the owners of navigation, layout, shared controls and design tokens. Use those conventions as the starting point. Where a convention causes the reported defect, address the narrowest owner that can fix it consistently.

## Design the flow and layout

- Decide which view owns each action and piece of information. Keep navigation and surrounding controls relevant to the current task.
- Group fields by the decisions users make and their dependencies. Make the primary action and the information needed to take it easy to find. Give repeated facts a clear home and use comparable controls, terminology and status cues for equivalent actions.
- Resolve applicable loading, empty, error, permission and long-content states. For windows and dialogs, decide where content scrolls, where actions remain reachable, how keyboard focus enters and returns, and how dismissal preserves task state.
- Reuse the product's component families, typography, spacing, density and alignment. Preserve its visual identity unless the task calls for changing it. Use a compact layout sketch when it helps resolve a material choice.

When composition, typography, color, motion or visual polish materially affects the result, consult the [pinned Anthropic visual-direction guide](references/vendor/anthropic/frontend-design.md). Apply its relevant guidance within the brief and established product conventions.

## Inspect the result

For material changes to appearance, layout or interaction, exercise the primary task in the normal browser or native runtime when available and authorized. Inspect representative supported sizes, including constrained dimensions and relevant themes, and compare with nearby views where they exist. Check that critical actions remain reachable with long content, focus follows the intended order, and controls and visual hierarchy stay consistent.

Inspect screenshots you use as evidence. Pair them with interaction or layout assertions for objective checks such as action reachability and overflow. Record what you observed and any required visual acceptance that remains unverified. Address concrete problems within the authorized scope.
