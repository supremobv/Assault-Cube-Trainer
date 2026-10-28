import math
import unittest
from aiming import angles_to, angle_delta, choose_target
from engine import Engine
from test_engine import Memory


class Inputs:
    def __init__(self):
        self.focused = True
        self.keys = {0x12}

    def foreground(self, pid): return self.focused
    def down(self, key): return key in self.keys


class CombatTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory()
        self.inputs = Inputs()
        self.engine = Engine(self.memory, self.inputs)
        self.p = self.engine.player()
        self.memory.put(self.p+0x30C, 'int', 1)
        self.memory.put(self.p+0x128+6*4, 'int', 30)
        self.memory.put(self.p+0x34, 'float', 80.)
        self.memory.put(self.memory.base+0x17F10C, 'int', 1000)
        self.array = 0x2500000
        self.memory.put(self.memory.base+0x18AC04, 'uint', self.array)
        self.memory.put(self.memory.base+0x18AC08, 'int', 2)
        self.memory.put(self.memory.base+0x18AC0C, 'int', 2)
        self.bot = 0x2100000
        self.add_bot(self.bot, 0, 0)
        self.add_bot(0x2200000, 1, 1)
        self.engine.configure_combat(smoothing=1)

    def add_bot(self, pointer, index, team):
        self.memory.initialize_player(pointer)
        self.memory.put(self.array+index*4, 'uint', pointer)
        self.memory.put(pointer+0x77, 'byte', 1)
        self.memory.put(pointer+0x30C, 'int', team)
        self.memory.put(pointer+0xE4, 'int', 995)
        self.memory.put(pointer+0x44, 'float', 16.)
        self.memory.write(pointer+0x205, b'PracticeBot\0')
        for off, value in zip((4,8,12,0x3F8,0x3FC,0x400), (20.,20.,8.,20.,20.,8.3)):
            self.memory.put(pointer+off, 'float', value)

    def test_angle_convention_and_wrap(self):
        self.assertEqual(angles_to((0,0,0), (10,0,0)), (90., 0.))
        self.assertEqual(angles_to((0,0,0), (0,-10,0)), (0., 0.))
        self.assertEqual(angle_delta(1.,359.), 2.)

    def test_target_filter_skips_allies_and_stale_render(self):
        bots = self.engine.bots()
        target = choose_target(bots, (10.,20.,8.), 90., 0., 1, head=True)
        self.assertEqual(target['pointer'], self.bot)
        self.memory.put(self.bot+0xE4, 'int', 10)
        self.assertIsNone(choose_target(self.engine.bots(), (10.,20.,8.), 90., 0., 1, head=True))

    def test_auto_aim_updates_angles_without_firing(self):
        self.engine.set_feature('auto_aim', True)
        self.assertAlmostEqual(self.engine.read(self.p+0x34,'float'), 90.)
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 0)

    def test_head_aim_fires_only_after_alignment(self):
        self.engine.configure_combat(smoothing=20)
        self.engine.set_feature('headshot', True)
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 0)
        self.engine.configure_combat(smoothing=1)
        self.engine.tick()
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 1)

    def test_auto_shoot_releases_when_focus_is_lost(self):
        self.engine.set_feature('auto_shoot', True)
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 1)
        self.inputs.focused = False
        self.engine.tick()
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 0)

    def test_activation_release_and_reset_stop_shooting(self):
        self.engine.set_feature('auto_shoot', True)
        self.inputs.keys.clear()
        self.engine.tick()
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 0)
        self.inputs.keys.add(0x12)
        self.engine.tick()
        self.engine.reset()
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 0)

    def test_hold_to_fire_requires_left_mouse(self):
        self.engine.set_feature('automatic', True)
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 0)
        self.inputs.keys.add(0x01)
        self.engine.tick()
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 1)
        self.inputs.keys.remove(0x01)
        self.engine.tick()
        self.assertEqual(self.engine.read(self.p+0x204,'byte'), 0)

    def test_view_lock_and_aim_modes_do_not_fight(self):
        self.engine.set_feature('view_lock', True)
        self.engine.set_feature('auto_aim', True)
        self.assertNotIn('view_lock', self.engine.enabled)
        self.engine.set_feature('headshot', True)
        self.assertNotIn('auto_aim', self.engine.enabled)
        self.engine.set_feature('auto_shoot', True)
        self.assertNotIn('headshot', self.engine.enabled)

    def test_bot_practice_values_restore_and_skip_allies(self):
        self.engine.set_feature('freeze_bots', True)
        self.engine.set_feature('fragile_bots', True)
        self.assertEqual(self.engine.read(self.bot+0x44,'float'), 0.)
        self.assertEqual(self.engine.read(self.bot+0xEC), 1)
        self.assertEqual(self.engine.read(0x2200000+0xEC), 100)
        self.engine.reset()
        self.assertEqual(self.engine.read(self.bot+0x44,'float'), 16.)
        self.assertEqual(self.engine.read(self.bot+0xEC), 100)

    def test_trigger_requires_crosshair_alignment(self):
        yaw,pitch = angles_to((10.,20.,8.), (20.,20.,8.-4.5*.45))
        self.memory.put(self.p+0x34,'float',yaw)
        self.memory.put(self.p+0x38,'float',pitch)
        self.engine.set_feature('triggerbot',True)
        self.assertEqual(self.engine.read(self.p+0x204,'byte'),1)
        self.memory.put(self.p+0x34,'float',0.)
        self.engine.tick()
        self.assertEqual(self.engine.read(self.p+0x204,'byte'),0)

    def test_scope_helper_and_live_zoom_status(self):
        weapon=0x2600000
        self.memory.put(self.p+0x350,'uint',weapon)
        self.memory.put(weapon+4,'int',5)
        self.memory.put(weapon+8,'uint',self.p)
        self.engine.equip_primary(5)
        self.assertEqual(self.engine.read(self.p+0xFC),5)
        self.assertEqual(self.engine.read(self.p+0x364,'uint'),weapon)
        self.engine.set_feature('scope_fov',True,20)
        self.engine.toggle_scope()
        self.assertTrue(self.engine.telemetry()['scoped'])
        self.assertEqual(self.engine.telemetry()['scope_fov'],20)
        self.engine.toggle_scope()
        self.assertFalse(self.engine.telemetry()['scoped'])
