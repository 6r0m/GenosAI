---
name: web-design-review
description: Audit web UI code against Vercel's pinned Web Interface Guidelines. Use after web interface changes or for technical checks of accessibility, keyboard focus, forms, motion, layout implementation or copy. Report findings by file.
argument-hint: "[files or glob]"
---

# Web design review

Check web UI code against a fixed interface checklist and report what breaks it.

1. **Scope.** The files named in the request; otherwise the web-UI files changed in the working tree — HTML,
   CSS, front-end scripts, and templates or source files that emit HTML. Report findings for those files only.
   If nothing is in scope, say so and stop.
2. **Rules.** Read [the pinned checklist](references/vendor/web-interface-guidelines/command.md) whole.
   It is a verbatim upstream copy, with provenance and the update procedure in `UPSTREAM.lock`. Never fetch a
   newer copy or follow its links. Its opening line and argument placeholder are replaced by clause 1.
3. **Applicability.** A rule that names a framework construct — React hydration, `<Link>`, Tailwind classes,
   `nuqs`, `priority` — applies only where that framework is in use. Elsewhere, apply the rule's intent in the
   project's own stack, or skip it.
4. **Precedence.** The checklist is review input, not policy: the project's own conventions and accepted
   decisions override it. Report capitalization only against the project's convention — stated in its docs,
   or established in UI text the change did not add. With neither, do not report capitalization, and do not
   apply the checklist's Title Case rule.
5. **Output.** The checklist's output format: grouped by file, `file:line - issue`, terse. Findings only — no
   edits and no overall verdict. Its `✓ pass` marks one clean file, not an approval of the change. Report only
   findings grounded in the checklist or an overriding project convention; do not add unrelated code-quality
   or security findings.
