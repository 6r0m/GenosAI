<!-- Template for <owner>/README.md. Copy the file, delete this comment.

This file is one node in a chain, not a standalone page. Its parent's README routes to it, it
routes to each of its own children, and every child does the same, so every routed owner is
reachable by a deterministic path from the repository root, without needing search to find it.
Search stays a valid way to discover things; the router is the predictable path, not a
prohibition on grep. A node that explains instead of routing, or omits a child, is where a branch
of that tree goes dark. `documentation-structure.md` owns the rule and the failure modes.

A router, like every README here — see the rule in documentation-structure.md. This one carries
the single exception it allows: the first minute, below the table. -->

# <owner name>

What this is, and who or what uses it — one or two sentences.

| concern | owner |
|---|---|
| current architecture | [docs/architecture/README.md](docs/architecture/README.md) |
| <usage, build, operations — only those that exist> | <path> |

How to run it, and where the entry point is — the first minute, a line or two. When that needs
more than a line or two it has its own owner: add a row above and link to it.
