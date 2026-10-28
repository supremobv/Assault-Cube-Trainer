import unittest
import math
from engine import Engine
from test_engine import Memory
import test_combat
from vision import project,radar_point,bot_box,bearing_marker,cone_radius
from unittest.mock import patch


class VisibilityTests(unittest.TestCase):
    def setUp(self):
        self.memory=Memory();self.inputs=test_combat.Inputs();self.engine=Engine(self.memory,self.inputs);self.p=self.engine.player()

    def test_noclip_returns_to_entry_and_keeps_health_controls_alive(self):
        self.engine.set_feature('noclip',True,16)
        self.assertEqual(self.engine.read(self.p+0x76,'byte'),0)
        self.engine.set_feature('health',True,500)
        self.assertEqual(self.engine.read(self.p+0xEC),500)
        self.memory.put(self.p+4,'float',200.)
        self.engine.tick();self.engine.set_feature('noclip',False)
        self.assertEqual(self.engine.read(self.p+0x76,'byte'),0)
        self.assertEqual(self.engine.read(self.p+4,'float'),10.)
        self.engine.reset()

    def test_root_change_drops_flight_without_teleporting_new_player(self):
        self.engine.set_feature('noclip',True,16)
        new=0x3000000;self.memory.initialize_player(new)
        self.memory.put(self.memory.base+0x18AC00,'uint',new)
        self.engine.tick()
        self.assertNotIn('noclip',self.engine.enabled)
        self.assertEqual(self.engine.read(new+0x76,'byte'),0)

    def test_hover_excludes_flight_and_holds_height(self):
        self.engine.set_feature('noclip',True,16)
        self.engine.set_feature('hover',True)
        self.assertNotIn('noclip',self.engine.enabled)
        self.memory.put(self.p+12,'float',20.)
        self.engine.tick()
        self.assertEqual(self.engine.read(self.p+12,'float'),8.)
        self.assertEqual(self.engine.read(self.p+0x30,'float'),3.5)
        self.engine.reset()

    def test_flight_supports_firing_and_weapon_selection(self):
        f=test_combat.CombatTests('test_angle_convention_and_wrap');f.setUp()
        for i in range(9):
            w=0x2800000+i*0x100;f.memory.put(f.p+0x33C+i*4,'uint',w)
            f.memory.put(w+4,'int',i);f.memory.put(w+8,'uint',f.p)
        f.engine.set_feature('noclip',True,16)
        f.engine.set_feature('auto_shoot',True)
        self.assertEqual(f.engine.read(f.p+0x204,'byte'),1)
        f.engine.equip_primary(5)
        self.assertEqual(f.engine.read(f.p+0xFC),5)
        self.assertEqual(f.engine.read(f.p+0x76,'byte'),0)
        f.engine.reset()

    def test_flight_moves_with_keys_and_stops_on_focus_loss(self):
        with patch('engine.time.monotonic',return_value=1.):self.engine.set_feature('noclip',True,16)
        self.inputs.keys={0x57,0x20}
        with patch('engine.time.monotonic',return_value=1.05):self.engine.tick()
        position=self.engine.telemetry()['position']
        self.assertLess(position[1],20.);self.assertGreater(position[2],8.)
        self.inputs.focused=False
        with patch('engine.time.monotonic',return_value=1.1):self.engine.tick()
        self.assertEqual(position,self.engine.telemetry()['position'])
        self.engine.reset()

    def test_offscreen_bearing_and_cone_geometry(self):
        scene={'position':(0,0,0),'yaw':0,'pitch':0,'roll':0,'fov':90}
        b={'position':(0,20,0),'eye_height':4.5}
        marker=bearing_marker(b,scene,800,600)
        self.assertEqual(marker[:2],(400.,576.))
        self.assertAlmostEqual(cone_radius(45,90,800),400.)

    def test_bot_health_armour_and_conflict_restore(self):
        f=test_combat.CombatTests('test_angle_convention_and_wrap');f.setUp()
        f.memory.put(f.bot+0xF0,'int',75)
        f.engine.set_feature('bot_health',True,500);f.engine.set_feature('bot_armour',True,0)
        self.assertEqual(f.engine.read(f.bot+0xEC),500);self.assertEqual(f.engine.read(f.bot+0xF0),0)
        f.engine.set_feature('fragile_bots',True)
        self.assertNotIn('bot_health',f.engine.enabled)
        self.assertEqual(f.engine.read(f.bot+0xEC),1)
        f.engine.reset()
        self.assertEqual(f.engine.read(f.bot+0xEC),100);self.assertEqual(f.engine.read(f.bot+0xF0),75)

    def test_perspective_and_radar_orientation(self):
        self.assertEqual(project((0,-10,0),(0,0,0),0,0,0,90,800,600),(400.,300.))
        self.assertAlmostEqual(project((10,-10,0),(0,0,0),0,0,0,90,800,600)[0],800.)
        self.assertIsNone(project((0,10,0),(0,0,0),0,0,0,90,800,600))
        self.assertIsNone(project((math.nan,0,0),(0,0,0),0,0,0,90,800,600))
        self.assertEqual(radar_point((10,0,0),(0,0,0),90,10),(90.,8.))

    def test_esp_uses_stale_bots_but_excludes_allies_and_dead(self):
        f=test_combat.CombatTests('test_angle_convention_and_wrap');f.setUp()
        f.memory.put(f.bot+0xE4,'int',0)
        f.engine.set_feature('wall_esp',True,250)
        before=dict(f.memory.data)
        scene=f.engine.visual_snapshot()
        self.assertEqual(len(scene['bots']),1)
        self.assertFalse(scene['bots'][0]['rendered'])
        self.assertIsNotNone(bot_box(scene['bots'][0],scene,800,600))
        self.assertEqual(before,f.memory.data)
        f.engine.set_feature('esp_allies',True)
        self.assertEqual(len(f.engine.visual_snapshot()['bots']),2)
        f.memory.put(f.bot+0x76,'byte',1)
        self.assertEqual(len(f.engine.visual_snapshot()['bots']),1)
