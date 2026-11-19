"""The local configuration boundary survives extraction into its own repository."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

AI = Path(__file__).resolve().parents[2]


class PrivateConfiguration(unittest.TestCase):
    def test_example_leaves_optional_browser_disabled(self):
        example = json.loads((AI / "config.local.example.json").read_text())
        self.assertIsNone(example["browser"]["cdp_url"])

    def test_local_files_are_excluded_without_parent_ignore_rules(self):
        with tempfile.TemporaryDirectory(prefix="private-config-") as temporary:
            root = Path(temporary)
            for name in (".gitignore", "config.local.example.json"):
                shutil.copyfile(AI / name, root / name)
            for name in ("config.local.json", "config.local.json.bak"):
                (root / name).write_text('{"fixture": "private-local-value"}\n')
            env = dict(os.environ)
            # Only the disposable repository's index may be written.
            for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
                env.pop(key, None)

            def git(*args):
                return subprocess.run(
                    ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.excludesFile=/dev/null", *args],
                    cwd=root, env=env, check=True, capture_output=True,
                ).stdout

            git("init", "-q")
            git("add", ".")
            manifest = git("ls-files", "-z").decode().split("\0")
            self.assertIn("config.local.example.json", manifest)
            self.assertNotIn("config.local.json", manifest)
            self.assertNotIn("config.local.json.bak", manifest)

            # Prove the fixture would expose private files without the owned rule.
            (root / ".gitignore").write_text("")
            git("add", ".")
            self.assertIn("config.local.json", git("ls-files", "-z").decode().split("\0"))

    def test_standalone_checkout_preserves_shell_and_vendored_bytes_with_autocrlf(self):
        with tempfile.TemporaryDirectory(prefix='source-line-endings-') as temporary:
            root=Path(temporary)
            if (AI/'.gitattributes').exists():shutil.copyfile(AI/'.gitattributes',root/'.gitattributes')
            script=b'#!/usr/bin/env bash\nset -euo pipefail\nprintf "ready\\n"\n'
            (root/'tool.sh').write_bytes(script)
            manual=AI/'agents/skills/drive-browser/references/playwright-cli/COMMANDS.md'
            license=AI/'agents/skills/drive-browser/references/playwright-cli/LICENSE'
            for source in (manual,license):
                target=root/source.relative_to(AI);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(source.read_bytes())
            env=dict(os.environ,GIT_ATTR_NOSYSTEM='1')
            for key in ('GIT_DIR','GIT_WORK_TREE','GIT_INDEX_FILE'):env.pop(key,None)
            def git(*args):
                subprocess.run(['git','-c','core.autocrlf=true','-c','core.safecrlf=false','-c','core.attributesFile='+os.devnull,*args],cwd=root,env=env,capture_output=True,check=True)
            git('init','-q');git('add','.')
            for file in (root/'tool.sh',*(root/source.relative_to(AI) for source in (manual,license))):file.unlink()
            git('checkout-index','--force','--all')
            self.assertEqual((root/'tool.sh').read_bytes(),script)
            for source in (manual,license):self.assertEqual((root/source.relative_to(AI)).read_bytes(),source.read_bytes())

    def test_installed_skill_can_locate_local_config_after_canonical_resolution(self):
        with tempfile.TemporaryDirectory(prefix="skill-location-") as temporary:
            root = Path(temporary)
            source = root / "source with spaces" / "agents" / "skills" / "drive-browser"
            source.mkdir(parents=True)
            (source / "SKILL.md").touch()
            installed = root / "installed-skill"
            if os.name == "nt":
                linked = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(installed), str(source)],
                                        capture_output=True)
                self.assertEqual(linked.returncode, 0, "could not create the isolated native junction")
            else:
                installed.symlink_to(source, target_is_directory=True)
            try:
                located = (installed / "SKILL.md").resolve(strict=True).parents[3] / "config.local.json"
                self.assertEqual(located, root / "source with spaces" / "config.local.json")
            finally:
                if os.name == "nt":
                    installed.rmdir()


if __name__ == "__main__":
    unittest.main()
