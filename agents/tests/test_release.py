"""Distribution boundaries with disposable source, homes, Git and synthetic secrets."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
import unittest
from unittest import mock
import skilltree as ST

AI=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ai_release',AI/'tools/release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class Distribution(unittest.TestCase):
    def setUp(self):
        scratch=AI/'tmp';scratch.mkdir(exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='distribution-',dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.base=Path(self.temporary.name)

    def admit(self,source,*names):
        manifest=source/'tools/source-manifest.json'
        manifest.parent.mkdir(parents=True,exist_ok=True)
        manifest.write_text(json.dumps({'version':1,'files':sorted(['tools/source-manifest.json',*names])})+'\n')

    @unittest.skipUnless(os.name=='posix','Unix executable permissions')
    def test_export_preserves_executable_hooks_without_setup_repair(self):
        source=self.base/'source';source.mkdir()
        names=['.githooks/pre-commit','.githooks/pre-push']
        self.admit(source,*names)
        for name in names:
            file=source/name;file.parent.mkdir(exist_ok=True)
            file.write_text('#!/bin/sh\nexit 0\n');file.chmod(0o755)
        destination=self.base/'export'
        release.export(source,destination)
        for name in names:
            self.assertEqual((destination/name).read_bytes(),(source/name).read_bytes())
            self.assertTrue(os.access(destination/name,os.X_OK),'export discarded executable hook mode')
        with mock.patch.object(release.shutil,'copy',side_effect=shutil.copyfile):
            with self.assertRaisesRegex(ValueError,'executable permissions'):
                release.export(source,self.base/'mode-losing-filesystem')

    def test_unreviewed_nested_file_refuses_export_without_creating_destination(self):
        for directory in ('agents','integrations'):
            with self.subTest(directory=directory):
                source=self.base/directory;source.mkdir()
                (source/'README.md').write_text('public')
                self.admit(source,'README.md')
                internal=source/directory/'internal.md';internal.parent.mkdir()
                internal.write_text('Synthetic internal checkout: /srv/private-workspaces/fixture; LAN: 192.168.40.7\n')
                self.assertEqual(release.personal_candidates(source,[internal]),[])
                destination=self.base/(directory+'-export')
                before=internal.read_bytes()
                with self.assertRaisesRegex(ValueError,'unclassified'):
                    release.export(source,destination)
                self.assertFalse(destination.exists())
                self.assertEqual(internal.read_bytes(),before)
                internal.write_text('Reviewed reusable fixture\n')
                self.admit(source,'README.md',internal.relative_to(source).as_posix())
                result=release.export(source,destination)
                self.assertIn(internal.relative_to(source).as_posix(),result)
                self.assertEqual((destination/directory/'internal.md').read_bytes(),internal.read_bytes())

    def test_export_excludes_private_files_and_refuses_unknown_or_linked_source(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public')
        self.admit(source,'README.md')
        for name in ('config.local.json','config.local.jsonc','config.local.jsonc.bak','secrets/provider.key','agents/skills/synced/x.md','tmp/receipt.json','agents/data.log','.env.local'):
            file=source/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('private synthetic marker')
        result=release.export(source,self.base/'export')
        self.assertEqual(set(result),{'README.md','tools/source-manifest.json'})
        (source/'unclassified').write_text('unknown')
        with self.assertRaisesRegex(ValueError,'unclassified'):list(release.source_files(source))
        (source/'unclassified').unlink()
        if os.name!='nt':
            (source/'agents/link.md').symlink_to(source/'README.md')
            with self.assertRaisesRegex(ValueError,'link requires'):list(release.source_files(source))

    def test_artifact_rejects_forbidden_file_before_scanning(self):
        artifact=self.base/'artifact';artifact.mkdir()
        self.admit(artifact)
        (artifact/'config.local.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'forbidden distribution artifact'):release.check(artifact,True)

    def test_artifact_rejects_unreviewed_nested_file_before_scanning(self):
        artifact=self.base/'artifact';artifact.mkdir()
        self.admit(artifact,'agents/README.md')
        (artifact/'agents').mkdir();(artifact/'agents/README.md').write_text('public')
        (artifact/'agents/internal.md').write_text('synthetic private notes')
        with self.assertRaisesRegex(ValueError,'unclassified source file'):release.check(artifact,True)

    def test_manifest_refusals_leave_destination_absent(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public')
        manifest=source/'tools/source-manifest.json'
        self.admit(source,'README.md')
        valid=json.loads(manifest.read_text())
        for extra in ('../outside.md','agents/../outside.md','secrets/provider.key','README.md','readme.md','missing.md'):
            with self.subTest(extra=extra):
                manifest.write_text(json.dumps({**valid,'files':[*valid['files'],extra]}))
                with self.assertRaises(ValueError):release.export(source,self.base/'export')
                self.assertFalse((self.base/'export').exists())
        manifest.unlink()
        with self.assertRaises(FileNotFoundError):release.export(source,self.base/'export')
        self.assertFalse((self.base/'export').exists())

    def test_declared_directory_scope_admits_descendants_without_per_file_entries(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public')
        self.admit(source,'README.md','todo/')
        for name in ('todo/README.md','todo/2026-01-01_0000-plan.md','todo/done/2026-01-02_0000-closed.md'):
            file=source/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('plan')
        result=release.export(source,self.base/'export')
        self.assertIn('todo/done/2026-01-02_0000-closed.md',result)
        self.assertIn('todo/done/2026-01-02_0000-closed.md',[f.relative_to(source).as_posix() for f in release.source_files(source,artifact=True)])
        self.assertEqual(release.personal_candidates(source,list(release.source_files(source))),[])

    def test_directory_scope_refuses_a_sibling_prefix(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public');self.admit(source,'README.md','todo/')
        (source/'todo').mkdir();(source/'todo/plan.md').write_text('plan')
        (source/'todo2').mkdir();(source/'todo2/notes.md').write_text('outside the declared scope')
        with self.assertRaisesRegex(ValueError,'unclassified source file: todo2/notes.md'):
            list(release.source_files(source))

    def test_directory_scope_still_refuses_private_names_inside_it(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public');self.admit(source,'README.md','todo/')
        (source/'todo/done').mkdir(parents=True)
        (source/'todo/done/plan.md').write_text('plan')
        (source/'todo/config.local.json').write_text('{}')
        (source/'todo/done/notes.log').write_text('synthetic private marker')
        self.assertEqual(set(release.export(source,self.base/'export')),{'README.md','todo/done/plan.md','tools/source-manifest.json'})
        with self.assertRaisesRegex(ValueError,r'forbidden distribution artifact: todo[\\/]config\.local\.json'):
            release.check(source,True)

    def test_missing_declared_scope_refuses_instead_of_admitting_nothing(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public');self.admit(source,'README.md','plans/')
        with self.assertRaisesRegex(ValueError,'missing admitted source scope: plans'):
            list(release.source_files(source))
        self.assertFalse((self.base/'export').exists())
        with self.assertRaises(ValueError):release.export(source,self.base/'export')
        self.assertFalse((self.base/'export').exists())

    def test_scope_entries_refuse_traversal_absolute_private_and_collisions(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public')
        for extra in ('../outside/','agents/../outside/','/absolute/','tmp/','todo','todo/'):
            with self.subTest(extra=extra):
                entries=['README.md',extra]
                if extra=='todo/': entries.append('todo')
                self.admit(source,*entries)
                with self.assertRaises(ValueError):release.export(source,self.base/('export-'+str(abs(hash(extra)))))

    @unittest.skipUnless(shutil.which('git') and shutil.which('gitleaks'),'requires Git and pinned scanner')
    def test_independent_index_accepts_scope_descendant(self):
        source=self.base/'git-source';source.mkdir();(source/'README.md').write_text('public')
        self.admit(source,'README.md','todo/')
        subprocess.run(['git','init','-q',str(source)],check=True,capture_output=True)
        (source/'todo/done').mkdir(parents=True);(source/'todo/done/plan.md').write_text('plan')
        subprocess.run(['git','-C',str(source),'add','README.md','tools/source-manifest.json','todo/done/plan.md'],check=True)
        (self.base/'index-ok').mkdir();release.check_index(source,self.base/'index-ok')

    @unittest.skipUnless(shutil.which('git') and shutil.which('gitleaks'),'requires Git and pinned scanner')
    def test_independent_index_refuses_scope_that_does_not_exist(self):
        source=self.base/'git-source';source.mkdir();(source/'README.md').write_text('public')
        self.admit(source,'README.md','plans/')
        subprocess.run(['git','init','-q',str(source)],check=True,capture_output=True)
        subprocess.run(['git','-C',str(source),'add','README.md','tools/source-manifest.json'],check=True)
        (self.base/'index-typo').mkdir()
        with self.assertRaisesRegex(ValueError,'missing admitted source scope: plans'):
            release.check_index(source,self.base/'index-typo')

    def test_portable_paths_refuse_unrepresentable_target_names(self):
        for name in ('todo/a.md','agents/x/y.md','todo/a b.md'):
            self.assertTrue(release.portable(name),name)
        for name in ('','todo/a:b.md','todo/a'+chr(92)+'b.md','todo/nul'+chr(0)+'x.md','../x','todo/./x','/abs/x','a//b',
                     'todo/CON.md','todo/nul','todo/com1.txt','todo/LPT9','todo/a?.md','todo/a<1>.md','todo/a|b.md',
                     'todo/a*b.md','todo/a"b.md','todo/plan.','todo/trail ','todo/dir./x.md','todo/'+chr(7)+'bell.md'):
            self.assertFalse(release.portable(name),repr(name))

    def test_uppercase_private_names_stay_excluded_inside_a_scope(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public');self.admit(source,'README.md','todo/')
        (source/'todo/done').mkdir(parents=True)
        (source/'todo/done/plan.md').write_text('plan')
        private=('todo/provider.KEY','todo/.ENV','todo/CONFIG.LOCAL.JSON','todo/TMP/notes.md','todo/done/OUTPUT.LOG')
        for name in private:
            file=source/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('synthetic private marker')
        self.assertEqual(set(release.export(source,self.base/'export')),{'README.md','todo/done/plan.md','tools/source-manifest.json'})
        for name in private:
            with self.subTest(name=name):
                artifact=self.base/('artifact-'+name.replace('/','-'))
                artifact.mkdir();(artifact/'tools').mkdir()
                (artifact/'tools/source-manifest.json').write_text((source/'tools/source-manifest.json').read_text())
                file=artifact/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('synthetic private marker')
                with self.assertRaisesRegex(ValueError,'forbidden distribution artifact'):release.check(artifact,True)

    @unittest.skipUnless(os.name=='posix','requires POSIX filename semantics')
    def test_unportable_descendants_refuse_on_a_posix_host(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public');self.admit(source,'README.md','todo/')
        (source/'todo').mkdir()
        for name in ('dupe:a.md','nested'+chr(92)+'x.md','CON.md'):
            with self.subTest(name=repr(name)):
                (source/'todo'/name).write_text('plan')
                with self.assertRaisesRegex(ValueError,'nonportable source path'):list(release.source_files(source))
                with self.assertRaises(ValueError):release.export(source,self.base/'export')
                self.assertFalse((self.base/'export').exists())
                (source/'todo'/name).unlink()

    @unittest.skipUnless(os.name=='posix','requires case-sensitive filenames')
    def test_case_colliding_descendants_refuse_on_a_posix_host(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public');self.admit(source,'README.md','todo/')
        (source/'todo/done').mkdir(parents=True)
        (source/'todo/Plan.md').write_text('one');(source/'todo/plan.md').write_text('two')
        (source/'todo/done').mkdir(exist_ok=True)
        with self.assertRaisesRegex(ValueError,'case-insensitive path collision: todo/Plan.md vs todo/plan.md'):
            list(release.source_files(source))
        with self.assertRaises(ValueError):release.export(source,self.base/'export')
        self.assertFalse((self.base/'export').exists())

    def test_index_case_collision_refuses_before_writing_staged_snapshot(self):
        source=self.base/'source';source.mkdir()
        (source/'tools').mkdir();(source/'tools/source-manifest.json').write_text(json.dumps({'version':1,'files':['tools/source-manifest.json','todo/']}))
        (source/'todo/done').mkdir(parents=True)
        for name in ('todo/Plan.md','todo/plan.md'):
            (source/name).write_text('plan')
        entries=[('tools/source-manifest.json',(source/'tools/source-manifest.json').read_bytes()),('todo/Plan.md',b'plan'),('todo/plan.md',b'plan')]
        def fake(cmd,*args,**kwargs):
            if cmd[3]=='ls-files':
                return b''.join(b'100644 '+b'0'*40+b' 0\t'+name.encode()+b'\0' for name,_ in entries)
            if cmd[3]=='show':
                return dict(entries)[cmd[4][1:]]
            raise AssertionError(cmd)
        scratch=self.base/'scratch'
        with mock.patch.object(release.subprocess,'check_output',side_effect=fake):
            with self.assertRaisesRegex(ValueError,'case-insensitive path collision: todo/Plan.md vs todo/plan.md'):
                release.check_index(source,scratch)
        self.assertFalse(scratch.exists(),'staged snapshot must not be written before portability refusal')

    def test_index_refuses_unportable_descendant_under_a_scope(self):
        source=self.base/'source';source.mkdir()
        (source/'tools').mkdir();(source/'tools/source-manifest.json').write_text(json.dumps({'version':1,'files':['tools/source-manifest.json','todo/']}))
        entries=[('tools/source-manifest.json',(source/'tools/source-manifest.json').read_bytes()),('todo/a:b.md',b'plan')]
        def fake(cmd,*args,**kwargs):
            if cmd[3]=='ls-files':
                return b''.join(b'100644 '+b'0'*40+b' 0\t'+name.encode()+b'\0' for name,_ in entries)
            if cmd[3]=='show':
                return dict(entries)[cmd[4][1:]]
            raise AssertionError(cmd)
        with mock.patch.object(release.subprocess,'check_output',side_effect=fake):
            with self.assertRaisesRegex(ValueError,'nonportable indexed source path: todo/a:b.md'):
                release.check_index(source,self.base/'scratch')
        self.assertFalse((self.base/'scratch').exists())

    def test_scope_plus_explicit_router_file_refuses_its_deletion(self):
        source=self.base/'source';source.mkdir()
        (source/'README.md').write_text('public');self.admit(source,'README.md','todo/','todo/README.md')
        (source/'todo/done').mkdir(parents=True)
        (source/'todo/README.md').write_text('router');(source/'todo/done/plan.md').write_text('plan')
        self.assertIn('todo/done/plan.md',release.export(source,self.base/'export'))
        (source/'todo/README.md').unlink()
        with self.assertRaisesRegex(ValueError,'missing admitted source file: todo/README.md'):
            list(release.source_files(source))

    def test_personal_path_controls_and_neutral_examples(self):
        source=self.base/'paths.md'
        source.write_text('/'+'home/'+ 'private-person/project\n'+ 'C:'+r'\Users\private-person\project'+'\n')
        self.assertEqual(len(release.personal_candidates(self.base,[source])),2)
        source.write_text('/'+'home/'+ 'user/project\n'+ 'C:'+r'\Users\sample-user\project'+'\n')
        self.assertEqual(release.personal_candidates(self.base,[source]),[])

    @unittest.skipUnless(shutil.which('gitleaks'),'public-check requires Gitleaks 8.30.1')
    def test_scanner_distinguishes_clean_finding_and_configuration_error(self):
        source=self.base/'source';source.mkdir();(source/'README.md').write_text('public')
        release.scanner(source,self.base/'scanner')
        (source/'data.txt').write_text('token = "'+'ghp_'+'a1b2c3d4e5a1b2c3d4e5a1b2c3d4e5abcdef'+'"')
        with self.assertRaisesRegex(ValueError,'scanner failed or detected'):release.scanner(source,self.base/'scanner-negative')

    @unittest.skipUnless(shutil.which('git') and shutil.which('gitleaks'),'requires Git and pinned scanner')
    def test_independent_index_rejects_force_added_private_file(self):
        source=self.base/'git-source';source.mkdir();(source/'README.md').write_text('public')
        self.admit(source,'README.md')
        subprocess.run(['git','init','-q',str(source)],check=True,capture_output=True)
        # This index is disposable fixture state, never the operator's index.
        (source/'config.local.json').write_text('{}')
        subprocess.run(['git','-C',str(source),'add','-f','config.local.json'],check=True)
        with self.assertRaisesRegex(ValueError,'private file tracked'):release.check(source)

    @unittest.skipUnless(shutil.which('git') and shutil.which('gitleaks'),'requires Git and pinned scanner')
    def test_independent_index_rejects_unadmitted_staged_file(self):
        source=self.base/'git-source';source.mkdir();(source/'README.md').write_text('public')
        self.admit(source,'README.md')
        subprocess.run(['git','init','-q',str(source)],check=True,capture_output=True)
        internal=source/'tools/internal.md';internal.write_text('synthetic private notes')
        subprocess.run(['git','-C',str(source),'add','tools/internal.md'],check=True)
        internal.unlink()
        before=subprocess.check_output(['git','-C',str(source),'ls-files','--stage'])
        with self.assertRaisesRegex(ValueError,'unclassified indexed source file'):release.check(source)
        self.assertEqual(subprocess.check_output(['git','-C',str(source),'ls-files','--stage']),before)

    @unittest.skipUnless(shutil.which('git') and shutil.which('gitleaks'),'requires Git and pinned scanner')
    def test_removed_secret_in_distributed_history_still_refuses(self):
        source=self.base/'history';source.mkdir();file=source/'README.md'
        self.admit(source,'README.md')
        file.write_text('token = "'+'ghp_'+'a1b2c3d4e5a1b2c3d4e5a1b2c3d4e5abcdef'+'"')
        def git(*args):subprocess.run(['git','-C',str(source),*args],check=True,capture_output=True)
        git('init','-q');git('add','README.md','tools/source-manifest.json')
        git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','-c','commit.gpgsign=false','commit','-qm','Synthetic scanner fixture')
        file.write_text('clean current source');git('add','README.md')
        with self.assertRaisesRegex(ValueError,'distributed Git history'):release.check(source)

    @unittest.skipUnless(sys.platform.startswith('linux'),'host lifecycle is Linux/WSL')
    def test_shared_install_refuses_foreign_search_file_and_symlink_without_mutation(self):
        source=self.base/'source';source.mkdir()
        for file in release.source_files(AI):
            target=source/file.relative_to(AI);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
        for linked in (False,True):
            with self.subTest(linked=linked):
                home=self.base/('linked-home' if linked else 'file-home');(home/'.agents').mkdir(parents=True)
                target=home/'.agents/ripgreprc';outside=self.base/('outside-'+str(linked))
                outside.write_text('synthetic foreign configuration\n')
                if linked:target.symlink_to(outside)
                else:target.write_bytes(outside.read_bytes())
                (home/'.bashrc').write_text('# foreign shell settings\n')
                result=subprocess.run(['bash',str(source/'agents/scripts/install.sh')],env=dict(os.environ,HOME=str(home),PATH=ST.POSIX_TEST_PATH,TMPDIR=str(self.base)),capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('foreign search configuration',result.stderr)
                self.assertEqual(target.read_bytes(),b'synthetic foreign configuration\n')
                self.assertEqual(outside.read_bytes(),b'synthetic foreign configuration\n')
                self.assertEqual(target.is_symlink(),linked)
                self.assertEqual((home/'.bashrc').read_text(),'# foreign shell settings\n')
                self.assertFalse((home/'.agents/AGENTS.md').exists())

    @unittest.skipUnless(sys.platform.startswith('linux'),'WSL-to-Windows dispatch fixture')
    def test_windows_foreign_search_environment_refuses_before_file_or_link_creation(self):
        source=self.base/'source';source.mkdir()
        for file in release.source_files(AI):
            target=source/file.relative_to(AI);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
        home=self.base/'windows-home';home.mkdir();binary=self.base/'bin';binary.mkdir()
        scripts={'cmd.exe':'exit 99',
                 'wslpath':'if [ "$1" = -u ] && [ "$2" = "C:/Fixture" ]; then printf "%s\\n" "$FIXTURE_HOME"; elif [ "$1" = -w ]; then printf "%s\\n" "$2"; else exit 98; fi',
                 'powershell.exe':r'''case "$*" in
                   *GetFolderPath*) printf '%s\n' 'C:/Fixture' ;;
                   *GetEnvironmentVariable*) printf '%s\n' 'C:/foreign/ripgreprc' ;;
                   *) exit 97 ;;
                 esac'''}
        for name,body in scripts.items():
            file=binary/name;file.write_text('#!/bin/bash\n'+body+'\n');file.chmod(0o700)
        result=subprocess.run(['bash',str(source/'agents/scripts/install.sh'),'--platform','windows'],env=dict(os.environ,HOME=str(home),FIXTURE_HOME=str(home),PATH=str(binary)+os.pathsep+ST.POSIX_TEST_PATH,TMPDIR=str(self.base)),capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('foreign RIPGREP_CONFIG_PATH',result.stderr)
        self.assertEqual(list(home.iterdir()),[])

    @unittest.skipUnless(sys.platform.startswith('linux'),'host lifecycle is Linux/WSL')
    def test_default_shared_install_is_host_only_repeatable_and_removable(self):
        original=self.base/'source';original.mkdir()
        for file in release.source_files(AI):
            target=original/file.relative_to(AI);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
        source=self.base/'checkout';release.export(original,source)
        home=self.base/'home with spaces';home.mkdir()
        (home/'.bashrc').write_text('# foreign setting\n')
        environment=dict(os.environ,HOME=str(home),PATH=ST.POSIX_TEST_PATH,TMPDIR=str(self.base),PYTHONDONTWRITEBYTECODE='1',PLATFORM='linux/amd64',PROVIDER='pi',RUNTIME='1',APPROVE='000000000000')
        for command in (['make','init'],['make','init'],['make','check'],['make','install'],['make','install']):
            result=subprocess.run(command,cwd=source,env=environment,capture_output=True,text=True,timeout=35)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue((home/'.agents/AGENTS.md').is_symlink())
        self.assertFalse((home/'.pi').exists());self.assertFalse((home/'.codex').exists())
        before=(home/'.bashrc').read_text()
        result=subprocess.run(['make','install','PROVIDER=pi'],cwd=source,env=environment,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('runtime absent',result.stdout)
        self.assertEqual((home/'.bashrc').read_text(),before)
        self.assertTrue((home/'.pi/agent/AGENTS.md').is_symlink())
        self.assertFalse((home/'.local/bin/pi-sot').exists())
        result=subprocess.run(['make','uninstall'],cwd=source,env=environment,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((home/'.bashrc').read_text(),'# foreign setting\n')
        self.assertFalse((home/'.agents/AGENTS.md').exists())
        (source/'config.local.jsonc').unlink()
        (source/'config.local.json').write_text(json.dumps({'pi':{'active':''}}))
        result=subprocess.run(['make','check'],cwd=source,env=environment,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0,'an explicitly invalid selection must reach its schema owner')

if __name__=='__main__':unittest.main()
