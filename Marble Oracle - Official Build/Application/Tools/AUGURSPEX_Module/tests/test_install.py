"""Integration patch tests (stdlib only). Run: python3 -m unittest discover -s tests -v"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sys import path as sys_path

sys_path.insert(0, str(Path(__file__).resolve().parents[1]))
from install_into_suite import (edit_chrome, edit_oracle, install, inventory_for,
                                CHROME_RELPATH, ORACLE_RELPATH, INV_RELPATH,
                                MANIFEST_RELPATH, BRIDGE_RELPATH, ADDON_RELPATH,
                                sha)
from uninstall_from_suite import uninstall


class ModuleIntegrationTest(unittest.TestCase):
    def test_patches_are_scoped_and_duplicates_rejected(self):
        chrome = 'def _primary_tabs(self):\n    tabs = (("TOUCH TYPE", "tab_touch_type"))\nlabel = {"EIDOLITH": "EIDO"}.get(label, label)\n'
        result = edit_chrome(chrome)
        self.assertIn('tab_augurspex', result)
        self.assertIn('"AUGURSPEX": "AUGUR"', result)
        with self.assertRaises(ValueError):
            edit_chrome(result)
        oracle = '        if name == "tab_eidolith":\n            return\n'
        changed = edit_oracle(oracle)
        self.assertIn('from oracle_augurspex_bridge import launch', changed)
        with self.assertRaises(ValueError):
            edit_oracle(changed)

    def test_install_and_uninstall_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'Marble Oracle - Official Build'
            for rel in (CHROME_RELPATH, ORACLE_RELPATH, MANIFEST_RELPATH, INV_RELPATH):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / 'START MARBLE ORACLE - LINUX.sh').write_text('#!/bin/sh\n')
            (root / CHROME_RELPATH).write_text('''def _primary_tabs(self):\n    tabs = (("TOUCH TYPE", "tab_touch_type"))\nlabel = {"EIDOLITH": "EIDO"}.get(label, label)\n''')
            (root / ORACLE_RELPATH).write_text('        if name == "tab_eidolith":\n            return\n')
            (root / MANIFEST_RELPATH).write_text(json.dumps({'tabs':['HOME','TOUCH TYPE']}))
            inv=inventory_for(root,{'schema':'sha256-inventory-v1'})
            (root / INV_RELPATH).write_text(json.dumps(inv))
            baseline={str(rel): (root/rel).read_bytes() for rel in (CHROME_RELPATH,ORACLE_RELPATH,MANIFEST_RELPATH,INV_RELPATH)}
            install(root)
            self.assertTrue((root/ADDON_RELPATH/'run.py').is_file())
            self.assertTrue((root/BRIDGE_RELPATH).is_file())
            self.assertIn('AUGURSPEX',json.loads((root/MANIFEST_RELPATH).read_text())['tabs'])
            with self.assertRaises(ValueError):
                install(root)
            uninstall(root)
            for rel in (CHROME_RELPATH, ORACLE_RELPATH, MANIFEST_RELPATH, INV_RELPATH):
                self.assertEqual((root/rel).read_bytes(), baseline[str(rel)])
            self.assertFalse((root / ADDON_RELPATH).exists())
            self.assertFalse((root / BRIDGE_RELPATH).exists())

    def test_refuse_if_source_modified_before_uninstall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for rel in (CHROME_RELPATH, ORACLE_RELPATH,MANIFEST_RELPATH,INV_RELPATH):
                (root / rel).parent.mkdir(parents=True,exist_ok=True)
            (root/'START MARBLE ORACLE - LINUX.sh').write_text('start')
            (root/CHROME_RELPATH).write_text('tabs = (("TOUCH TYPE", "tab_touch_type"))\nlabel = {"EIDOLITH": "EIDO"}.get(label, label)')
            (root/ORACLE_RELPATH).write_text('        if name == "tab_eidolith":\n')
            (root/MANIFEST_RELPATH).write_text('{"tabs":[]}')
            (root/INV_RELPATH).write_text(json.dumps(inventory_for(root, {})))
            install(root)
            (root/ORACLE_RELPATH).write_text((root/ORACLE_RELPATH).read_text() + '\n# user modification\n')
            with self.assertRaises(ValueError):
                uninstall(root)
            self.assertTrue((root/ADDON_RELPATH/'integration_backup').exists())

if __name__ == '__main__':
    unittest.main()
