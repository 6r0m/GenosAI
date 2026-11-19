"""The standalone project README chain has one route per owner and no orphans."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skilltree as ST

AI = os.path.abspath(os.path.join(ST.AGENTS, os.pardir))


class RouterChain(unittest.TestCase):
    def setUp(self):
        self.owners = ST.router_nodes(AI)
        self.routes = ST.routes(self.owners)

    def test_there_is_something_to_check(self):
        # Guards the guard: a broken discovery helper would make every test below vacuous.
        self.assertGreater(len(self.owners), 1, "no owners discovered under ai/")

    def test_each_owner_is_routed_at_most_once(self):
        for target, routers in self.routes.items():
            with self.subTest(owner=os.path.relpath(target, ST.REPO)):
                unique = sorted(set(routers))
                self.assertEqual(
                    len(unique), 1,
                    f"routed from {[os.path.relpath(r, ST.REPO) for r in unique]}; "
                    "a child is routed by its parent and nobody else",
                )

    def test_every_owner_is_reachable_from_its_parent(self):
        root = os.path.normpath(AI)
        for owner in sorted(self.owners):
            if owner == root:
                continue
            with self.subTest(owner=os.path.relpath(owner, ST.REPO)):
                self.assertIn(
                    owner, self.routes,
                    "nothing routes to it; add one line to its parent's README",
                )

    def test_a_route_points_at_the_owner_not_past_it(self):
        for target, routers in self.routes.items():
            parent = os.path.dirname(target)
            for router in set(routers):
                with self.subTest(owner=os.path.relpath(target, ST.REPO)):
                    self.assertEqual(
                        router, parent,
                        f"routed from {os.path.relpath(router, ST.REPO)}, skipping "
                        f"{os.path.relpath(parent, ST.REPO)}",
                    )


if __name__ == "__main__":
    unittest.main()


class LinkText(unittest.TestCase):
    """The mechanically checkable half of the link rule, over ai/agents/.

    Whether a link says what is on the other side is semantic and stays a review job.
    These three shapes are not: text that promises a directory and delivers one file,
    one phrase pointing at two different targets in the same document, and the
    placeholder phrases that describe nothing.
    """

    VAGUE = re.compile(r"^(here|this|this (?:doc|document|file|page)|click here|link|see)$", re.I)

    def markdown(self):
        for path in ST.markdown_files(ST.AGENTS):
            yield path, ST.strip_code(ST.read(path))

    def links(self, text):
        return re.findall(r"\[([^\]]+)\]\(([^)]+)\)", text)

    def test_link_text_does_not_promise_a_directory_and_deliver_a_file(self):
        for path, text in self.markdown():
            for label, target in self.links(text):
                if label.endswith("/") and not target.endswith("/"):
                    self.fail(f"{os.path.relpath(path, ST.REPO)}: "
                              f"text {label!r} names a directory but points at {target!r}")

    def test_no_link_text_is_a_placeholder(self):
        for path, text in self.markdown():
            for label, target in self.links(text):
                self.assertNotRegex(
                    label, self.VAGUE,
                    f"{os.path.relpath(path, ST.REPO)}: {label!r} describes nothing")

    def test_one_phrase_does_not_point_at_two_targets(self):
        for path, text in self.markdown():
            seen = {}
            for label, target in self.links(text):
                key = label.strip().lower()
                if key in seen and seen[key] != target:
                    self.fail(f"{os.path.relpath(path, ST.REPO)}: {label!r} points at both "
                              f"{seen[key]!r} and {target!r}")
                seen[key] = target
