"""Every skill obeys the Agent Skills authoring limits, and every link works."""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skilltree as ST

NAME = re.compile(r"[a-z0-9-]{1,64}$")
RESERVED = re.compile(r"anthropic|claude")
DESC_MAX = 1024          # Agent Skills spec: description max length
BODY_MAX = 500           # authoring guidance: keep the SKILL.md body under 500 lines
CONTENTS_AT = 100        # a reference over ~100 lines exposes its contents near the top


class Frontmatter(unittest.TestCase):
    def test_every_skill_parses(self):
        for name, path, fm, _ in ST.skills():
            with self.subTest(skill=name):
                self.assertIsNotNone(fm, f"{path}: no frontmatter; '---' must be line 1")

    def test_name_is_valid_and_matches_its_directory(self):
        for name, path, fm, _ in ST.skills():
            with self.subTest(skill=name):
                declared = fm.get("name", name)
                self.assertRegex(declared, NAME, f"{path}: name must be lowercase/digits/hyphens, <=64")
                self.assertEqual(declared, name, f"{path}: frontmatter name must match its directory")
                self.assertIsNone(RESERVED.search(declared), f"{path}: reserved word in name")

    def test_description_is_present_and_within_cap(self):
        for name, path, fm, _ in ST.skills():
            with self.subTest(skill=name):
                desc = fm.get("description", "")
                self.assertTrue(desc, f"{path}: description is required for discovery")
                self.assertLessEqual(len(desc), DESC_MAX, f"{path}: description over {DESC_MAX} chars")
                self.assertNotRegex(desc, r"[<>]", f"{path}: description must not contain XML tags")

    def test_body_within_budget(self):
        for name, path, _, body in ST.skills():
            with self.subTest(skill=name):
                lines = len(body.splitlines())
                self.assertLess(lines, BODY_MAX, f"{path}: body {lines} lines; split above {BODY_MAX}")


class Links(unittest.TestCase):
    def test_project_links_resolve_inside_the_distribution_root(self):
        root=Path(ST.REPO).resolve()
        for path in ST.markdown_files(ST.REPO,include_templates=False):
            for target in ST.links(path):
                resolved=(Path(path).parent/target).resolve()
                with self.subTest(doc=os.path.relpath(path,ST.REPO),target=target):
                    self.assertTrue(resolved.is_relative_to(root),'relative link escapes the distribution root')
                    self.assertTrue(resolved.is_file(),'relative document target is absent')

    def test_global_instructions_reference_the_shared_policies(self):
        path = os.path.join(ST.AGENTS, "AGENTS.md")
        declared = set(ST.links(path))
        for name in ("engineering-change-principles.md", "review-contract.md"):
            target = "skills/.shared/" + name
            with self.subTest(policy=name):
                self.assertIn(target, declared, "global instructions must reference the canonical policy")
                self.assertTrue(os.path.isfile(os.path.join(ST.AGENTS, target)))

    def test_every_relative_link_resolves(self):
        for path in ST.markdown_files(ST.AGENTS, include_templates=False):
            for target in ST.links(path):
                with self.subTest(doc=os.path.relpath(path, ST.REPO), link=target):
                    resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
                    self.assertTrue(os.path.exists(resolved), f"broken link -> {target}")

    def test_no_path_escapes_the_windows_junction(self):
        # `~/.claude/skills` is a junction onto skills/; a lexical `../../` resolves
        # outside it on Windows and the reference breaks silently.
        for path in ST.markdown_files(ST.SKILLS):
            for target in ST.links(path):
                with self.subTest(doc=os.path.relpath(path, ST.REPO), link=target):
                    self.assertNotIn("../../", target, "escapes the junction; keep .shared/ one level up")


class LongDocuments(unittest.TestCase):
    def test_reference_over_threshold_exposes_contents(self):
        # A partial read of a long reference hides the sections it never reached.
        for path in ST.markdown_files(ST.SKILLS):
            base = os.path.basename(path)
            if base == "SKILL.md" or ST._is_template(path):
                continue          # a SKILL.md and a template are read whole
            text = ST.read(path)
            n = len(text.splitlines())
            if n <= CONTENTS_AT:
                continue
            # A template names its sections in the leading guidance comment instead: a
            # "## Contents" heading would be copied into every document produced from it.
            listed = re.search(r"(?m)^## Contents$", text) or (
                text.startswith("<!--") and "Sections in order:" in text.split("-->")[0]
            )
            with self.subTest(doc=os.path.relpath(path, ST.REPO), lines=n):
                self.assertTrue(listed, f"{n} lines: needs '## Contents', or a guidance comment listing its sections")


class GeneratedTrees(unittest.TestCase):
    def test_discovery_is_relative_to_a_checkout_below_a_tmp_directory(self):
        with tempfile.TemporaryDirectory(prefix='source-discovery-') as temporary:
            source=Path(temporary)/'checkout'
            (source/'component').mkdir(parents=True)
            (source/'README.md').write_text('# Root\n')
            (source/'component/README.md').write_text('# Component\n')
            self.assertEqual(ST.router_nodes(str(source)),{str(source),str(source/'component')})
            self.assertEqual(len(list(ST.markdown_files(str(source)))),2)

    def test_trash_is_excluded_while_maintained_documents_are_audited(self):
        with tempfile.TemporaryDirectory(prefix='skill-audit-', dir=os.path.join(ST.REPO, 'tmp')) as root:
            before = os.getcwd()
            try:
                os.chdir(root)
                for name in ('skills/native', 'skills/.trash/discarded', 'skills/synced/cached'):
                    directory = Path(name)
                    directory.mkdir(parents=True)
                    (directory / 'README.md').write_text('# Fixture\n', encoding='utf-8')
                    (directory / 'reference.md').write_text('uncatalogued section\n' * 111, encoding='utf-8')
                self.assertEqual(sorted(ST.markdown_files('skills')),
                                 [os.path.join('skills', 'native', 'README.md'),
                                  os.path.join('skills', 'native', 'reference.md')])
                self.assertEqual(ST.router_nodes('skills'), {os.path.join('skills', 'native')})
            finally:
                os.chdir(before)


if __name__ == "__main__":
    unittest.main()
