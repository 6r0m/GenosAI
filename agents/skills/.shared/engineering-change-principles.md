# Shared engineering change principles

Apply these rules in addition to the repository's own instructions. More specific repository evidence and accepted decisions override generic guidance.

## Evidence, authority, and review

Evidence stance, claim verification, challenge behavior, the authority vocabulary, verdicts, and
how a finding is stated are owned by [review-contract.md](review-contract.md).

## Design discipline

- Apply KISS, SOLID, and YAGNI together.
- Prefer the smallest safe local change that fits the existing architecture and preserves accepted invariants.
- Resolve goals and constraints before architecture, and architecture before implementation, for broad or irreversible work. Do not force staged discussion for small reversible work whose direction is already clear.
- Use SOLID to discover real ownership boundaries, not to maximize interfaces, services, factories, repositories, layers, or dependency-injection machinery.
- Reuse existing domain boundaries, extension points, helpers, error types, configuration, fixtures, and test infrastructure before adding anything new.
- Do not create a new abstraction merely to avoid a few lines of local code. Extract or extend a reusable component only when it has one clear responsibility and solves demonstrated reuse, consistency, or invariant-enforcement needs.
- Do not add abstractions, services, timers, queues, fallbacks, compatibility layers, migrations, flags, or configuration knobs without a demonstrated present need. Do not introduce a parallel framework, source of truth, lifecycle, cache, queue, state machine, dependency, or configuration path unless the existing architecture cannot satisfy a concrete requirement.
- Prefer extending the existing owner over creating a parallel owner. Policies, data, invariants, and state transitions each have a single authority; projections and caches derive from it.
- Keep lifecycle interfaces thin. For operations such as install and uninstall with provider variants, use one configuration owner for provider registration, managed paths, availability checks and operation routing. Dispatch the selected operation to the provider through a defined contract; keep provider behaviour in its adapter. Interfaces must not maintain separate provider lists or path rules. Report absent, unsupported and failed operations accurately, with the applicable next step. Extend the registry and adapter to add a provider, preserving existing consumers; use the smallest mechanism that serves the providers actually present.
- Prefer one writer for mutable state or define an explicit coordination contract. Do not add a fallback writer merely to hide projection/runtime failure.
- Prefer an existing reliable event over polling. Use periodic reconciliation only for wall-clock state, missed events, or external drift that events cannot own.
- Eliminate duplicated semantic authority. Small incidental duplication may be safer than a premature shared abstraction.
- File count and line count are diagnostic signals, not gates. Around 1,000 lines in one file or broad propagation across many files warrants an ownership review, but never degrade code/tests merely to hit a number. A cohesive large file may remain; a smaller mixed-responsibility file may need a split. Decompose only along a real separation of concerns.
- Propose deeper refactoring only when evidence shows a concrete maintainability, reliability, operational, or scaling benefit.
- Prefer open-source, self-hosted, Linux-friendly components with transparent architecture and clear data ownership. Use closed/commercial options only when required or materially better; state the trade-off.
- Keep unrelated cleanup and speculative refactoring out of the change.

## Reliability guard

- Identify invariants, ownership boundaries, failure domains, and recovery behavior before changing stateful/distributed flows.
- Do not remove or simplify an existing reliability mechanism merely because another mechanism appears to overlap.
- First reconstruct why it exists: original failure or incident, invariants, regression or chaos tests, retry budgets, failure-domain isolation, observability, recovery, and rollback behavior.
- Preserve the proven mechanism unless the replacement demonstrates equivalent or stronger guarantees through code and tests, including the failure that originally required it.

## Sources of truth and documentation

- Ownership is recursive black-box: each owner documents only its own level — what it is for, its immediate parts as black boxes each linked to that part's own documentation, and what it decides — and never carries a part's internals upward. Each part repeats the same pattern inside itself.
- Give each durable fact one authoritative owner. A fact about one owner belongs to that owner. A relationship between owners in one documented tree belongs to their nearest common owner; across separately documented trees, each directed dependency belongs to its dependent side; a relationship with an external you do not document — a service, a third-party library — belongs to the maintained owner that takes part in it.
- Anything that does not own a fact either references its owner or is generated from it, and adds only the consequences it owns itself. It never copies the fact by hand — whether the fact is a relationship, a contract, or a rationale, and whether the copy is prose, a table, an example, or a view.
- Code owns executable behavior and local implementation details; a document that disagrees with it is stale.
- Tests own executable examples and regressions.
- Schemas and interface definitions own the contract shapes they define. Everything else names or links the contract and never copies its fields, parameters, signatures, or payload members.
- Configuration owns configurable values.
- Stable documentation owns durable architecture, invariants, contract semantics that no schema or interface definition expresses, operational procedures, and rationale that cannot be expressed clearly in code or tests.
- Document shape and navigation — routing, contents, length signals, reference depth — is owned by [documentation-structure.md](documentation-structure.md).
- Update docs when public behavior, architecture, operations, recovery, or user workflow changes. Update an existing stable document when it already owns the concern. Create a new stable document only when the concern has no suitable owner and enough durable content exists to justify one; do not create broad docs for trivial local details.
- What a durable document and a code comment may say, how they divide the work, and the one-way dependency on transient artifacts are owned by [content-rules.md](content-rules.md).
