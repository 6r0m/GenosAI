"""The same ignored Pi path references must resolve in native Windows and WSL."""
import sys
from pathlib import Path, PurePosixPath
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import config

class PiPaths(unittest.TestCase):
    def test_native_windows_projects_shared_wsl_drive_references(self):
        with patch.object(config,'LOCAL',PurePosixPath('/mnt/e/source/config.local.json')),patch.object(config,'load',return_value=(None,{'pi':{'secret_root':'/mnt/g/private keys'}})),patch.object(config.sys,'platform','win32'):
            resolved=config.pi_input('windows')
        self.assertEqual(resolved['root'].replace('\\','/'),'E:/source')
        self.assertEqual(resolved['secretRoot'].replace('\\','/'),'G:/private keys')

    def test_wsl_converts_native_drive_reference_before_native_projection(self):
        with patch.object(config,'LOCAL',PurePosixPath('/mnt/e/source/config.local.json')),patch.object(config,'load',return_value=(None,{'pi':{'secret_root':r'G:\private keys'}})),patch.object(config.sys,'platform','linux'),patch.object(config,'Path',side_effect=lambda value: PurePosixPath(value) if str(value) in ('/mnt/e/source','/mnt/g/private keys') else Path(value)),patch.object(config.subprocess,'check_output',side_effect=['E:\\source\n','/mnt/g/private keys\n','G:\\private keys\n']) as mapper:
            resolved=config.pi_input('windows')
        self.assertEqual(resolved['secretRoot'],r'G:\private keys')
        self.assertEqual(mapper.call_args_list[1].args[0],['wslpath','-u',r'G:\private keys'])

    def test_removal_with_broken_local_input_uses_only_the_canonical_owner(self):
        with patch.object(config,'load',side_effect=config.ConfigError('synthetic invalid input')):
            result=config.pi_input(removing=True)
        self.assertEqual(result['root'],str(config.LOCAL.parent))
        self.assertFalse(result['configured'])

if __name__=='__main__':unittest.main()
