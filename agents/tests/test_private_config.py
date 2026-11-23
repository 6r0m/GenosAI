"""The local configuration boundary survives extraction into its own repository."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import sys
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

AI = Path(__file__).resolve().parents[2]


class PrivateConfiguration(unittest.TestCase):
    def test_example_leaves_optional_browser_disabled(self):
        example = config.parse((AI / "config.local.example.jsonc").read_bytes(), commented=True)
        self.assertIsNone(example["browser"]["cdp_url"])

    def test_codex_model_preferences_are_explicit_optional_strings(self):
        base = {'approval_policy': 'on-request', 'sandbox_mode': 'workspace-write'}
        for extra in ({}, {'model': 'fixture-model'}, {'model_reasoning_effort': 'high'},
                      {'model': 'fixture-model', 'model_reasoning_effort': 'high'}):
            with self.subTest(extra=extra):
                raw = json.dumps({'codex': {**base, **extra}}).encode()
                self.assertEqual(config.parse(raw), {'codex': {**base, **extra}})
        for extra in ({'model': ''}, {'model': ' fixture-model'}, {'model': 'fixture-model\n'},
                      {'model': 7}, {'model': None}, {'model_reasoning_effort': ''},
                      {'model_reasoning_effort': 'HIGH '}, {'unmanaged': 'x'},
                      {'sandbox_mode': 'yolo'}):
            with self.subTest(extra=extra), self.assertRaises(config.ConfigError):
                config.parse(json.dumps({'codex': {**base, **extra}}).encode())

    def test_jsonc_preserves_strings_and_rejects_ambiguous_or_malformed_input(self):
        example=b'{/* setup */"browser":{"cdp_url":"http://127.0.0.1:9222/a//b"},"pi":{"active":null,"profiles":{}}}// end'
        self.assertEqual(config.parse(example,True)['browser']['cdp_url'],'http://127.0.0.1:9222/a//b')
        for raw in (b'{"browser":{},"browser":{}}', b'{"browser":{},}', b'{"pi":{/*broken}',
                    b'{"browser":{"cdp_url":"private-marker"} invalid}', b'{"pi":{"active":1/*x*/2}}', b'{"claude":{"autoCompactEnabled":tr/*x*/ue}}'):
            with self.subTest(raw=raw), self.assertRaises(config.ConfigError) as failure:
                config.parse(raw,True)
            self.assertNotIn('private-marker',str(failure.exception))
        with self.assertRaises(config.ConfigError):config.parse(example,False)

    def test_one_local_owner_and_legacy_bytes_survive(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(config,'LOCAL',Path(temporary)/'config.local.json'):
            legacy=config.LOCAL;commented=legacy.with_suffix('.jsonc')
            raw=b'{"browser":{"cdp_url":null}}'
            legacy.write_bytes(raw)
            self.assertEqual(config.load(),(raw,{'browser':{'cdp_url':None}}))
            commented.write_bytes(b'{// private preferences\n}')
            with self.assertRaisesRegex(config.ConfigError,'both local'):config.load()
            self.assertEqual(legacy.read_bytes(),raw)
            legacy.unlink()
            self.assertEqual(config.load()[1],{})

    def test_local_files_are_excluded_without_parent_ignore_rules(self):
        with tempfile.TemporaryDirectory(prefix="private-config-") as temporary:
            root = Path(temporary)
            for name in (".gitignore", "config.local.example.jsonc"):
                shutil.copyfile(AI / name, root / name)
            for name in ("config.local.json", "config.local.json.bak", "config.local.jsonc", "config.local.jsonc.bak"):
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
            self.assertIn("config.local.example.jsonc", manifest)
            self.assertNotIn("config.local.json", manifest)
            self.assertNotIn("config.local.json.bak", manifest)
            self.assertNotIn("config.local.jsonc", manifest)
            self.assertNotIn("config.local.jsonc.bak", manifest)

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
