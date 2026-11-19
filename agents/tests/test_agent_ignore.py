"""The search-sweep filter hides every finished-todo directory, and only those.

agent-ignore is glob, applied by a ripgrep build, so neither reading the pattern nor
reasoning about gitignore semantics proves what it does: globset accepts constructs it
then never matches through. This runs the real `rg` against a tree that carries every
naming variation the convention takes, plus the near-misses that must stay visible.
"""
import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import skilltree as ST

IGNORE_FILE = os.path.join(ST.AGENTS, "agent-ignore")
MARKER = "MARKER_HIT"
RG = shutil.which("rg")

# Directories the filter must hide: an ordering prefix or suffix on either segment,
# any casing, at any depth. `todo/done` itself is the case the filter started from.
HIDDEN = [
    "todo/done",
    "todo/01_done",
    "todo/done_01",
    "01_todo/done",
    "todo_old/done",
    "todo.old/done.1",
    "todo2/done2",
    "notes/todo/2_done_2026",
    "sub/deep/01-todo/99-done",
    "archive/2026_todo/03_done",
    "TODO/DONE",
    "ToDo/Done",
]

# Near-misses that must keep answering a sweep. `todo` itself is the live queue: only
# the finished receipts under it go quiet.
#
# The second group pins the contract that makes the affix wildcards safe: the match is
# on the literal substring `todo` and the literal substring `done`, never on their
# letters loosely. A segment that merely comes close (tod, tdo, to_do; godon, dnoe,
# do_ne) is a different directory and keeps answering.
VISIBLE = [
    "todo",
    "todo/active",
    "todo/donations",
    "src/donations",
    "done",
    "doing/dont",
    "notes",
    "tod/done",
    "tdo/done",
    "to_do/done",
    "todo/godon",
    "todo/dnoe",
    "todo/do_ne",
    "dot/enod",
]


def _tree(root):
    for rel in HIDDEN + VISIBLE:
        d = os.path.join(root, *rel.split("/"))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "f.md"), "w", encoding="utf-8") as fh:
            fh.write(MARKER + "\n")


def _sweep(root, *args):
    """One sweep of `root`, with only agent-ignore applied.

    RIPGREP_CONFIG_PATH is neutralised so an installed config cannot supply the very
    filter under test, and `.` is passed explicitly because ripgrep with no path
    argument reads standard input instead of the working directory.
    """
    env = dict(os.environ, RIPGREP_CONFIG_PATH=os.devnull)
    proc = subprocess.run(
        [RG, "--ignore-file", IGNORE_FILE, "--files-with-matches", MARKER, *(args or (".",))],
        cwd=root, env=env, stdin=subprocess.DEVNULL,
        capture_output=True, text=True,
    )
    hits = {p.replace(os.sep, "/").lstrip("./") for p in proc.stdout.split()}
    return hits, proc.stderr


@unittest.skipUnless(RG, "ripgrep not installed")
class Filter(unittest.TestCase):
    def setUp(self):
        # Under the gitignored repo tmp/, never beside the source: the fixture
        # is a tree of todo/done directories, so while it exists next to the
        # tests it shows up as untracked in `git status` and the editor's
        # source-control view. tmp/ also keeps it inspectable after a failure,
        # which a system temp dir removed on cleanup would not.
        self.root = os.path.join(ST.REPO, "tmp", "agent-tests", "__ignore_tree__")
        shutil.rmtree(self.root, ignore_errors=True)
        os.makedirs(os.path.dirname(self.root), exist_ok=True)
        _tree(self.root)
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.hits, self.err = _sweep(self.root)

    def test_no_pattern_fails_to_parse(self):
        # A malformed glob is reported on stderr and then simply never matches, so a
        # typo would disable the filter while every other assertion here still passed
        # for the wrong reason.
        self.assertEqual("", self.err.strip(), f"{IGNORE_FILE}: ripgrep rejected a pattern")

    def test_finished_todo_directories_are_hidden(self):
        for rel in HIDDEN:
            with self.subTest(directory=rel):
                self.assertNotIn(f"{rel}/f.md", self.hits, f"{rel}: still answers a sweep")

    def test_near_misses_stay_visible(self):
        for rel in VISIBLE:
            with self.subTest(directory=rel):
                self.assertIn(f"{rel}/f.md", self.hits, f"{rel}: wrongly hidden by the filter")

    def test_naming_the_directory_still_reads_it(self):
        # The documented escape hatch: ripgrep never ignores a path handed to it
        # explicitly, so a receipt stays readable without disabling anything.
        hits, _ = _sweep(self.root, "todo/done")
        self.assertIn("todo/done/f.md", hits)

    def test_no_ignore_files_lifts_the_filter_and_no_ignore_does_not(self):
        lifted, _ = _sweep(self.root, "--no-ignore-files", ".")
        self.assertIn("todo/done/f.md", lifted)
        still, _ = _sweep(self.root, "--no-ignore", ".")
        self.assertNotIn("todo/done/f.md", still)


if __name__ == "__main__":
    unittest.main()
