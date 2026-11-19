"""Run JavaScript boundary tests on the native Node, without provider calls."""
from pathlib import Path
import shutil
import subprocess
import unittest

class PiAdapter(unittest.TestCase):
    def test_node_boundaries(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node required; adapter verification must not skip')
        here = Path(__file__).resolve().parent
        result = subprocess.run([node, '--test', str(here/'adapter.test.js'),
                                 str(here/'config.test.js'), str(here/'probe.test.js')], text=True, capture_output=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
