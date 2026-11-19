# Fresh-agent evaluation

The deterministic suite one directory up checks the system's **shape**. This checks whether an
agent that has never seen it **reaches the right answer, and what that costs**. Different
failure, and only this one is what the skills exist to prevent.

S1–S4 have no runner: each is a prompt given to a fresh read-only agent against this repository,
and the reply is scored against the stated criterion. The prompts end with a fixed reporting block
so two runs are comparable. S5 writes documentation, so it runs through its own script — see S5
below.

## Metrics

| metric | why it is the one to watch |
|---|---|
| `SEARCHES` | grep calls. **Not a defect signal on its own** — search is a normal discovery mechanism. Watch for thrash: many searches *together with* a wrong answer or an answer from a copy rather than the authoritative owner. Never drive it to zero. Two separate properties are at work here and neither is "fewer greps": the router chain gives a deterministic path from the root, and single ownership is what makes a search land on the authoritative file |
| `READS` | files opened before answering — the direct cost of routing that is too deep or too vague |
| `tokens` | reported per agent run; the behavioural half of the cost table in `../report_cost.py` |
| `duration` | wall time to a correct answer |
| pass/fail | against the scenario's stated criterion, scored by a human or by the parent agent |

## Scenarios

| # | angle | request | passes when |
|---|---|---|---|
| S1 | discovery | "where is the verdict alphabet defined?" | names `.shared/review-contract.md`. Renamed from "traversal": it passes on any route to the right owner, and does not require the README chain, so it never tested traversal |
| S2 | duplication resistance | "explain the verdicts in `agents/providers/README.md`" | links to the owner instead of restating the definitions |
| S3 | placement + template | "where would a new `integrations/sample/` owner put its architecture doc, and what sections?" | `docs/architecture/structure.md`, sections in template order |
| S4 | cold comprehension | "what rules does this system impose?" | rules match the shared contracts, none invented |
| S5 | single ownership in practice | "write the architecture docs" for a mock `shop` and separate `ledger` | every fact is written once, by its owner: **C1** the same-tree relationship, **C2** the cross-repository one and **C3** the external one each appear only in their owner's main view; **C4** no contract field, parameter, signature or payload appears outside its schema or interface; **C5** no view draws another level's relationships or a part's internals |

Each scenario prompt ends with:

```
READS: <n>
FILES: <paths in order>
SEARCHES: <n>
<scenario-specific answer line>
```

## The subject must not move

Use a dedicated detached evaluation worktree, never the live tree. Choose its location
outside the source checkout and create it at the revision being measured:

```bash
git worktree add --detach <evaluation-worktree> <commit>
```

Every run must see the same subject files. Re-point the detached worktree deliberately
when measuring a new state:

```bash
git -C <evaluation-worktree> checkout --detach <commit>
```

Recording the commit beside the results is what makes two runs comparable.

## Running one

**Exclude `agents/tests/evaluation/` in the prompt.** This directory records each scenario's
answer, so an agent that greps into it is reading the answer key rather than finding the file the
scenario is about — observed in run 3, where the S3 agent reported reaching the convention only
because private evaluation receipts surfaced in a search.

Give the prompt verbatim to a fresh read-only agent scoped to the etalon, then record the reply
in private evaluation receipts alongside the existing rows. Change one thing at a time; a run that changes both
the subject and the prompt tells you nothing.

## S5

The one scenario that writes. A cold headless agent documents a small mock of two repositories —
`shop/services/` with `checkout` and `payments`, and a separate `ledger` — whose code holds one
relationship of each kind: within one tree, across repositories, and to an external. The
[S5 script, which builds the mock and both instruction arms and runs one sample per call](s5-relationship-ownership.sh):

```bash
s5=agents/tests/evaluation/s5-relationship-ownership.sh
bash $s5 setup "$TMPDIR/s5" <subject-agents> <control-agents>  # explicit source snapshots
bash $s5 run "$TMPDIR/s5" p1     # then p2, r1, r2
bash $s5 signals "$TMPDIR/s5"    # grep hints per sample
```

Isolation is enforced by the harness, never by the prompt: `--safe-mode` loads no `CLAUDE.md` and
no skills, and reads of this repository and `$HOME` are denied, so a sample reaches only the arm
copy it is pointed at. `setup` writes content identities for both explicit arms to
`inputs.json`; record those content identities with the results.

A sample passes only when C1–C5 all hold. The grep hints find candidates and miss rewordings, so
every written file is still read. The control arm has to fail somewhere: if both arms pass, the
scenario did not discriminate and the result is UNVERIFIED.

Results live in private evaluation receipts.

## Portable input contract

S5 setup takes explicit subject and control agent-source directories, each containing `AGENTS.md`
and `skills/`. It uses no historical commit or enclosing repository. Setup records their content
hashes in `inputs.json`, refuses existing output and excludes runtime skill caches. For example:

```bash
bash s5-relationship-ownership.sh setup <fresh-output> <subject-agents> <control-agents>
```

Actual model evaluations remain separate, paid operations. Set `S5_MODEL` explicitly and obtain
authorization before `run`; ordinary tests never invoke it. Historical receipts are private evidence,
not an acceptance baseline shipped with this source.
