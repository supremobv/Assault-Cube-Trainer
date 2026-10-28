import copy
import tempfile
import unittest
from pathlib import Path
from catalog import CONTROLS
from engine import Engine
from profile_store import ProfileStore,validate
from visual_settings import DEFAULTS,validate as visual_validate


def payload():
    return {'version':1,'controls':{key:{'enabled':False,'value':default}for _,key,_,_,default in CONTROLS},
            'combat':dict(Engine().combat_options),'visuals':dict(DEFAULTS)}


class ProfileTests(unittest.TestCase):
    def test_roundtrip_keeps_independent_esp_crosshair_and_aim_settings(self):
        data=payload();data['visuals'].update(esp_boxes=False,esp_armour=True,crosshair_style='circle',crosshair_color='#123456')
        data['combat']['smoothing']=8
        with tempfile.TemporaryDirectory()as folder:
            store=ProfileStore(folder);store.save('Practice',data)
            self.assertEqual(store.load('Practice'),data);self.assertEqual(store.names(),['Practice'])

    def test_invalid_profile_cannot_replace_existing_file(self):
        with tempfile.TemporaryDirectory()as folder:
            store=ProfileStore(folder);path=store.save('Practice',payload());before=path.read_bytes()
            bad=payload();bad['visuals']['crosshair_color']='red;run()'
            with self.assertRaises(ValueError):store.save('Practice',bad)
            self.assertEqual(path.read_bytes(),before)

    def test_rejects_path_escape_and_windows_device_names(self):
        with tempfile.TemporaryDirectory()as folder:
            store=ProfileStore(folder)
            for name in ('../escape','..\\escape','C:\\escape','CON','LPT1',''):
                with self.subTest(name=name),self.assertRaises(ValueError):store.save(name,payload())
            self.assertEqual(list(Path(folder).iterdir()),[])

    def test_rejects_unknown_controls_conflicts_and_bad_numeric_values(self):
        for modify in (lambda d:d['controls'].update(unknown={'enabled':True,'value':None}),
                       lambda d:d['controls']['noclip'].update(enabled=True),
                       lambda d:d['controls']['health'].update(value=100000),
                       lambda d:d['combat'].update(team_filter='yes')):
            data=payload();data['controls']['hover']['enabled']=True;modify(data)
            with self.assertRaises(ValueError):validate(data)

    def test_oversize_and_non_json_profiles_are_not_executed(self):
        with tempfile.TemporaryDirectory()as folder:
            store=ProfileStore(folder);p=Path(folder)/'Bad.json';p.write_text('print("bad")')
            with self.assertRaises(ValueError):store.load('Bad')
            p.write_text(' '*1048577)
            with self.assertRaises(ValueError):store.load('Bad')

    def test_visual_bounds_boolean_types_and_styles(self):
        for value in ({'esp_armour':'yes'},{'crosshair_size':1000},{'crosshair_width':True},
                      {'crosshair_style':'code'},{'enemy_color':'#zzzzzz'}):
            with self.subTest(value=value),self.assertRaises(ValueError):visual_validate(value)
