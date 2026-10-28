import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
from export_ce_table import export
from catalog import CONTROLS
from engine import FEATURE_KEYS


class TableTests(unittest.TestCase):
    def test_export_has_no_startup_lua_and_covers_every_control(self):
        with tempfile.TemporaryDirectory() as folder:
            path = export(Path(folder)/'test.CT')
            tree = ET.parse(path)
            root = tree.getroot()
            self.assertIsNone(root.find('LuaScript'))
            health = next(e for e in root.iter('CheatEntry') if e.findtext('Description') == '"Health"')
            self.assertEqual(health.findtext('Address'), '"ac_client.exe"+18AC00')
            self.assertEqual(health.findtext('Offsets/Offset'), 'EC')
            scripts=[e.findtext('AssemblerScript') for e in root.iter('CheatEntry') if e.find('AssemblerScript') is not None]
            self.assertEqual(len(scripts),len(CONTROLS)+2)
            self.assertEqual({c[1] for c in CONTROLS},FEATURE_KEYS)
            for key in FEATURE_KEYS:
                self.assertEqual(sum('-- RangeLab feature: '+key+'\n' in s for s in scripts),1)
            self.assertTrue(all('[ENABLE]' in s and '[DISABLE]' in s and 'if syntaxcheck then return end' in s for s in scripts))
            self.assertTrue(all(e.find('LastState') is None for e in root.iter('CheatEntry')))
            self.assertGreater(len(list(root.iter('Address'))), 130)
