"""Deterministic sentinels for selected critical shared rules.

Each entry below pins one rule to the file that owns it, by a phrase that rule uses.
The guard is that a listed rule does not silently vanish and does not appear in a
second policy file - which is the failure that has actually happened here: two files
state the same rule, one gets edited, and the system now says two things.

What this CANNOT do is prove that arbitrary prose contains exactly one owner. A
duplicate worded differently passes, and a concept nobody listed is unguarded. It is a
regression sentinel over a hand-maintained set, not static analysis of English;
semantic duplication stays a job for architect review.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skilltree as ST

# The policy files. Templates are deliberately absent: a template's job is to carry
# the rule it implements to the point of use, and component-driven.md cannot be linked
# from .shared/ because `../../` breaks the Windows junction.
POLICY = {
    "universal-agents": os.path.join(ST.AGENTS, "AGENTS.md"),
    "engineering-change-principles": os.path.join(ST.SHARED, "engineering-change-principles.md"),
    "review-contract": os.path.join(ST.SHARED, "review-contract.md"),
    "documentation-structure": os.path.join(ST.SHARED, "documentation-structure.md"),
    "content-rules": os.path.join(ST.SHARED, "content-rules.md"),
    "component-driven": os.path.join(ST.SKILLS, "architect", "references", "component-driven.md"),
}

# concept -> phrases that only its owner should contain.
CONCEPTS = {
    "verdict definitions": [r"ready within the reviewed scope"],
    "finding format": [r"evidence → consequence"],
    "decision vocabulary": [r"\*\*decision\*\* —"],
    "accepted = intent + verification": [r"authority alone makes it a decision"],
    "durable architecture gate": [r"\*\*current architecture\*\* \(implemented, verified"],
    "counter-evidence loop": [r"refutes a finding"],
    "separate facts from inferences": [r"separate verified facts"],
    "repository is authoritative": [r"repository is authoritative", r"repository as authoritative"],
    "one authoritative owner": [r"one authoritative owner", r"two owners of one fact"],
    "README is the front door": [r"front door"],
    "same-tree relationship owner": [r"nearest common (owner|parent)"],
    "cross-tree dependency owner": [r"dependent side"],
    "contract shape vs contract semantics": [r"contract shapes they define", r"contract semantics that no schema"],
    "black box components": [r"is a \*\*black box\*\*"],
    "ADR forest policy": [r"adr, spec, or rule forest"],
    "version control owns history": [r"general repository evolution", r"git already owns history"],
    "recursive black-box ownership": [r"recursive black-box"],
    "reference or generate, never copy": [r"never copies the fact by hand"],
    "main view states the level's graph": [r"one statement of this owner's relationships"],
    "multi-level views are generated": [r"never drawn by hand"],
    "contents threshold": [r"## contents` near the top"],
    "route vs citation": [r"is a \*\*citation\*\*"],
    "traversal index": [r"that chain is the index"],
    "reference depth": [r"one level deep"],
    # Match the rule, not the path: `docs/architecture/` is shared vocabulary that
    # both the shape file and the ownership table legitimately name.
    "architecture address is fixed": [r"the directory exists from the first day"],
    "current truth only": [r"no change chronology"],
    "one-way transient dependency": [r"must never point back"],
    "comment complements the document": [r"complements\*\* the document"],
    "pitfalls pruning": [r"prune it"],
}


class SentinelsForSelectedRules(unittest.TestCase):
    def setUp(self):
        # Collapse whitespace: a phrase wrapped across two lines is still the same rule.
        self.text = {name: re.sub(r"\s+", " ", ST.read(path).lower()) for name, path in POLICY.items()}

    def test_no_listed_rule_appears_in_a_second_policy_file(self):
        for concept, patterns in CONCEPTS.items():
            found = [n for n, t in self.text.items() if any(re.search(p, t) for p in patterns)]
            with self.subTest(concept=concept):
                self.assertLessEqual(
                    len(found), 1,
                    f"'{concept}' is stated in {found}; keep one owner and link to it",
                )

    def test_every_listed_rule_is_still_present(self):
        # Catches the opposite drift: a rule deleted or reworded until nothing states it.
        for concept, patterns in CONCEPTS.items():
            found = [n for n, t in self.text.items() if any(re.search(p, t) for p in patterns)]
            with self.subTest(concept=concept):
                self.assertEqual(
                    len(found), 1,
                    f"'{concept}' needs exactly one policy owner, found {found}",
                )


if __name__ == "__main__":
    unittest.main()
