"""Every template is copyable, and its headings match the sections it declares.

A template drifts quietly: someone adds a section to the body and not to the guidance
comment, or renames one. The next author then follows a list that no longer describes
the file they are looking at.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skilltree as ST

TEMPLATE_DIRS = [ST.TEMPLATES, os.path.join(ST.SKILLS, "investigate-change", "references")]

# router template -> the children the layout requires it to reach. Every separation-of-concern
# directory carries a README that links to what is inside it, so a mandatory README that no
# router links is unreachable by traversal — and the layout was shipped that way once:
# diagrams/ existed with its own README and nothing routed to it.
REQUIRED_ROUTES = {
    "owner-readme.md": ["docs/architecture/README.md"],
    "architecture-readme.md": ["structure.md", "diagrams/README.md"],
    "diagrams-readme.md": ["main.md"],
}

# The structure template applies the relationship rule without restating it. Guard only the
# regressions that happened: guidance that had every participant state the same edge, and prose
# that restated the graph the main view already draws.
RELATIONSHIP_GUIDANCE_REQUIRED = ["drawn once, in [the main view](diagrams/main.md)", "cite its canonical owner"]
RELATIONSHIP_GUIDANCE_SUPERSEDED = ["parents, siblings, and dependencies", "state the participants, direction"]


def templates():
    for base in TEMPLATE_DIRS:
        if not os.path.isdir(base):
            continue
        for f in sorted(os.listdir(base)):
            if f.endswith(".md"):
                yield os.path.join(base, f)


def declared_sections(comment):
    """The section list from a guidance comment, or None when it declares none.

    The list runs to the first full stop; items may wrap across lines, and a
    parenthetical note about subsections is not part of the heading.
    """
    m = re.search(r"Sections in order:([^.]*)", comment, re.S)
    if not m:
        return None
    raw = re.sub(r"\s+", " ", m.group(1))
    items = [re.sub(r"\s*\(.*?\)", "", s).strip() for s in raw.split("/")]
    return [s for s in items if s]


class Templates(unittest.TestCase):
    def test_at_least_one_template_is_discovered(self):
        self.assertTrue(list(templates()), "no templates found; the discovery paths are wrong")

    def test_each_template_opens_with_guidance_that_is_not_copied(self):
        for path in templates():
            with self.subTest(template=os.path.relpath(path, ST.REPO)):
                text = ST.read(path)
                self.assertTrue(text.startswith("<!--"), "must open with a guidance comment")
                self.assertIn("-->", text, "unterminated guidance comment")
                head = text.split("-->")[0].lower()
                self.assertRegex(head, r"copy|do not copy", "the comment must say it is not part of the document")

    def test_declared_sections_match_the_actual_headings(self):
        checked = 0
        for path in templates():
            text = ST.read(path)
            declared = declared_sections(text.split("-->")[0])
            if declared is None:
                continue                       # short templates declare no section list
            # A fenced block shows an example of what to write, not this template's own
            # structure — the same reason links inside fences are not routes.
            body = ST.strip_code(text.split("-->", 1)[1])
            actual = [h.strip() for h in re.findall(r"(?m)^## (.+)$", body)]
            checked += 1
            with self.subTest(template=os.path.relpath(path, ST.REPO)):
                self.assertEqual(
                    declared, actual,
                    "the guidance comment and the headings disagree",
                )
        self.assertGreater(checked, 0, "no template declared a section list; the parser is broken")

    def test_each_router_template_reaches_its_required_children(self):
        for name, children in REQUIRED_ROUTES.items():
            path = os.path.join(ST.TEMPLATES, name)
            with self.subTest(template=name):
                self.assertTrue(os.path.isfile(path), "router template is missing")
            text = ST.read(path)
            for child in children:
                with self.subTest(template=name, child=child):
                    self.assertIn(
                        f"({child})", text,
                        "the layout requires this router to route to that child",
                    )

    def test_structure_template_limits_relationships_to_their_owner(self):
        text = ST.strip_code(ST.read(os.path.join(ST.TEMPLATES, "architecture-structure.md")))
        m = re.search(r"(?ms)^## Relationships$(.*?)(?=^## )", text)
        self.assertIsNotNone(m, "the relationships section is missing")
        section = re.sub(r"\s+", " ", m.group(1).lower())
        for phrase in RELATIONSHIP_GUIDANCE_REQUIRED:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section, "the template no longer limits relationships to their owner")
        for phrase in RELATIONSHIP_GUIDANCE_SUPERSEDED:
            with self.subTest(superseded=phrase):
                self.assertNotIn(phrase, section, "the duplicating guidance is back")

    def test_every_required_layout_file_has_a_template(self):
        # documentation-structure.md claims each required file in the layout has one.
        for name in ("owner-readme.md", "architecture-readme.md", "architecture-structure.md",
                     "diagrams-readme.md", "diagrams-main.md", "pitfalls.md"):
            with self.subTest(template=name):
                self.assertTrue(
                    os.path.isfile(os.path.join(ST.TEMPLATES, name)),
                    "the layout names this file as required but no template exists",
                )



if __name__ == "__main__":
    unittest.main()
