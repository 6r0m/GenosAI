"""Standalone preparation contracts, with synthetic state and no provider traffic."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import unittest
import skilltree as ST

AI = Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('preparation_release',AI/'tools/release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)


@unittest.skipUnless(shutil.which('bash'), 'source checks require Bash')
class SetupChecks(unittest.TestCase):
    def setUp(self):
        scratch=AI/'tmp';scratch.mkdir(exist_ok=True)
        temporary=tempfile.TemporaryDirectory(prefix='setup-check-',dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.base=Path(temporary.name);self.root=self.base/'source with spaces';self.root.mkdir()
        for source in release.source_files(AI):
            target=self.root/source.relative_to(AI);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy(source,target)
        self.home=self.base/'home';self.home.mkdir();(self.home/'sentinel').write_text('native state survives')
        self.env=dict(os.environ,HOME=str(self.home),USERPROFILE=str(self.home),PYTHONDONTWRITEBYTECODE='1')
        self.policy=self.root/'agents/providers/pi/runtime/retry-policy.json'

    def check(self, no_node=False, make=False):
        script=self.root/'tools/setup.py'
        command=[sys.executable,str(script),'check']
        if make: command=['make','check','PYTHON="'+Path(sys.executable).as_posix()+'"']
        if no_node:
            bootstrap=self.base/'no-node.py'
            bootstrap.write_text('''import pathlib,runpy,shutil,subprocess,sys
from unittest.mock import patch
which,run=shutil.which,subprocess.run
def without_node(args,*positional,**keywords):
    if pathlib.Path(args[0]).name in ('node','node.exe'): raise FileNotFoundError('Node unavailable in fixture')
    return run(args,*positional,**keywords)
sys.argv=sys.argv[1:]
sys.path.insert(0,str(pathlib.Path(sys.argv[0]).parent))
with patch('shutil.which',side_effect=lambda name,*args,**kwargs: None if name=='node' else which(name,*args,**kwargs)), patch('subprocess.run',side_effect=without_node):
    runpy.run_path(sys.argv[0],run_name='__main__')
''')
            command=[sys.executable,str(bootstrap),str(script),'check']
        def snapshot(root):
            return {p.relative_to(root).as_posix():None if p.is_dir() else p.read_bytes() for p in root.rglob('*')}
        before=snapshot(self.root),snapshot(self.home)
        result=subprocess.run(command,cwd=self.root,env=self.env,capture_output=True,text=True,timeout=60)
        self.assertEqual((snapshot(self.root),snapshot(self.home)),before,'checks must not mutate source, local input or native state')
        return result

    @unittest.skipUnless(shutil.which('node') and shutil.which('make'), 'Node and Make required')
    def test_make_check_validates_retry_policy_with_disabled_pi(self):
        valid=json.loads(self.policy.read_text())
        result=self.check(make=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        for text in ('{broken',json.dumps({**valid,'enabled':'yes'})):
            with self.subTest(text=text):
                self.policy.write_text(text)
                result=self.check(make=True)
                self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('pi-config:',result.stderr)

    def test_disabled_pi_without_node_checks_json_syntax_and_reports_schema_gap(self):
        valid=json.loads(self.policy.read_text())
        for value in (valid,{**valid,'enabled':'yes'}):
            self.policy.write_text(json.dumps(value))
            result=self.check(no_node=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('JSON syntax only',result.stdout)
        self.policy.write_text('{broken')
        result=self.check(no_node=True)
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)

    def test_configured_pi_or_plugins_still_require_node_for_schema_checks(self):
        for pi in ({'active':'first','profiles':{'first':{'provider':'deepseek','model':'deepseek-flash','credential':'secrets/fixture.key'}}},
                   {'plugins':{'image-budget':{'maxImages':8}}}):
            with self.subTest(pi=pi):
                (self.root/'config.local.json').write_text(json.dumps({'pi':pi}))
                result=self.check(no_node=True)
                self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('Node unavailable in fixture',result.stderr)


class Preparation(unittest.TestCase):
    def test_public_defaults_require_explicit_privilege_and_connection_choices(self):
        claude = json.loads((AI/'agents/providers/claude/user-settings.json').read_text())
        codex = json.loads((AI/'agents/providers/codex/user-settings.json').read_text())
        pi = json.loads((AI/'agents/providers/pi/runtime/profiles.json').read_text())
        self.assertEqual(claude['permissions']['defaultMode'], 'default')
        self.assertNotIn('Bash', claude['permissions']['allow'])
        self.assertEqual(codex, {'approval_policy':'on-request', 'sandbox_mode':'workspace-write'})
        self.assertIsNone(pi['active'])
        self.assertEqual(pi['profiles'], {})

    @unittest.skipUnless(shutil.which('node'), 'requires Node')
    def test_pi_uses_external_credentials_without_changing_their_bytes(self):
        with tempfile.TemporaryDirectory(prefix='external-credential-') as temporary:
            base=Path(temporary)
            owner=base/'unrelated checkout'; owner.mkdir()
            external=base/'private credentials'; external.mkdir()
            key=external/'provider.key'; key.write_text('synthetic-fixture-key')
            script=base/'probe.mjs'
            script.write_text('''import {configure} from %s;
const [dir,root,secretRoot]=process.argv.slice(2);
await configure({op:'install',dir,root,secretRoot,profiles:{active:'example',profiles:{example:{provider:'deepseek',model:'deepseek-flash',credential:'secrets/provider.key'}}}});
''' % json.dumps((AI/'agents/providers/pi/runtime/configure.js').as_uri()))
            result=subprocess.run(['node',str(script),str(base/'native'),str(owner),str(external)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            auth=json.loads((base/'native/auth.json').read_text())
            self.assertIn(str(external),auth['deepseek']['key'])
            self.assertEqual(key.read_text(),'synthetic-fixture-key')

    @unittest.skipUnless(sys.platform.startswith('linux'),'model helpers execute on Linux/WSL')
    def test_model_url_keeps_revision_and_extra_argument_boundaries(self):
        with tempfile.TemporaryDirectory(prefix='model-argv-') as temporary:
            root=Path(temporary); capture=root/'capture.py'; log=root/'args.json'
            capture.write_text('import json,sys;open(sys.argv[1],"w").write(json.dumps(sys.argv[2:]))')
            driver=root/'driver.sh'
            driver.write_text('hf() { python3 "$CAPTURE" "$CAPTURE_LOG" "$@"; }; export -f hf\n'
                              'bash "$MODEL_HELPER" "https://huggingface.co/example/models/resolve/release-branch/vae/model.safetensors" -- --include "name with spaces"\n')
            env=dict(os.environ,CAPTURE=str(capture),CAPTURE_LOG=str(log),MODEL_BASE_DIR=str(root/'models with spaces'),MODEL_HELPER=str(AI/'integrations/comfyui/model-downloads/download_models.sh'))
            result=subprocess.run(['bash',str(driver)],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            argv=json.loads(log.read_text())
            self.assertNotIn('--local-dir-use-symlinks',argv)
            self.assertEqual(argv[argv.index('--revision')+1],'release-branch')
            self.assertEqual(argv[-2:],['--include','name with spaces'])

    @unittest.skipUnless(sys.platform.startswith('linux'),'model helpers execute on Linux/WSL')
    def test_model_dry_run_recipe_and_refusals_have_no_download_side_effect(self):
        with tempfile.TemporaryDirectory(prefix='model-refusal-') as temporary:
            root=Path(temporary);target=root/'models'
            helper=AI/'integrations/comfyui/model-downloads/download_models.sh'
            env=dict(os.environ,MODEL_BASE_DIR=str(target),PATH=ST.POSIX_TEST_PATH)
            url='https://huggingface.co/example/model/resolve/main/vae/model.safetensors'
            for args in ([str(helper),'--dry-run',url],
                         [str(helper.parent/'download_wan22_i2v.sh'),'--dry-run'],
                         [str(helper.parent/'download_hunyuan_video_1.5.sh'),'--dry-run']):
                result=subprocess.run(['bash',*args],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertNotIn('models downloaded!',result.stdout)
                self.assertFalse(target.exists())
            for args in ([url], [url,'https://huggingface.co/invalid'],
                         ['https://huggingface.co/example/model/resolve/main/../escape']):
                result=subprocess.run(['bash',str(helper),*args],env=env,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse(target.exists())
            driver=root/'failure.sh'
            driver.write_text('hf() { return 17; }; export -f hf\nbash "$MODEL_HELPER" "$MODEL_URL"\n')
            result=subprocess.run(['bash',str(driver)],env=dict(env,MODEL_HELPER=str(helper),MODEL_URL=url),capture_output=True,text=True)
            self.assertEqual(result.returncode,17)

if __name__=='__main__': unittest.main()
