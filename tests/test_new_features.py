import unittest
from engine import Engine
from aiming import choose_target
import test_combat


class NewFeatureTests(unittest.TestCase):
    def setUp(self):
        fixture=test_combat.CombatTests('test_angle_convention_and_wrap')
        fixture.setUp()
        self.engine,self.memory,self.inputs,self.p=fixture.engine,fixture.memory,fixture.inputs,fixture.p
        for i in range(9):
            w=0x2800000+i*0x100
            self.memory.put(self.p+0x33C+i*4,'uint',w)
            self.memory.put(w+4,'int',i)
            self.memory.put(w+8,'uint',self.p)

    def test_akimbo_flag_and_expiry_restore(self):
        w=self.engine.weapon_object(self.p,8)
        self.engine.set_feature('akimbo',True)
        self.assertEqual(self.engine.read(self.p+0x100,'byte'),1)
        self.assertEqual(self.engine.read(w+0x2C),31000)
        self.engine.set_feature('akimbo',False)
        self.assertEqual(self.engine.read(self.p+0x100,'byte'),0)
        self.assertEqual(self.engine.read(w+0x2C),0)

    def test_speed_changes_movement_input_without_changing_maxspeed(self):
        self.memory.put(self.p+0x44,'float',16.);self.inputs.keys={0x57,0x44}
        self.engine.set_feature('speed_hack',True,3)
        self.assertEqual(self.engine.read(self.p+0x74,'byte'),3)
        self.assertEqual(self.engine.read(self.p+0x75,'byte'),253)
        self.assertEqual(self.engine.read(self.p+0x44,'float'),16.)
        self.inputs.focused=False;self.engine.tick()
        self.assertEqual(self.engine.read(self.p+0x74,'byte'),0)
        self.engine.reset()

    def test_scope_lock_and_settling_apply_only_to_sniper(self):
        self.engine.set_feature('scope_lock',True)
        self.assertFalse(self.engine.scoped())
        self.engine.equip_primary(5)
        self.engine.set_feature('scope_settle',True)
        self.engine.tick()
        self.assertTrue(self.engine.scoped())
        self.assertEqual(self.engine.read(self.engine.weapon_object(self.p,5)+0x2C),819)
        self.engine.reset()
        self.assertFalse(self.engine.scoped())

    def test_refill_consumes_reserve_and_excludes_locks(self):
        self.engine.set_feature('magazines',True,50)
        self.engine.set_feature('auto_refill',True)
        self.assertNotIn('magazines',self.engine.enabled)
        self.memory.put(self.p+0x140,'int',0)
        self.memory.put(self.p+0x11C,'int',35)
        self.engine.tick()
        self.assertEqual(self.engine.read(self.p+0x140),20)
        self.assertEqual(self.engine.read(self.p+0x11C),15)
        self.engine.set_feature('reserves',True,120)
        self.assertNotIn('auto_refill',self.engine.enabled)

    def test_bunnyhop_requires_focus_space_and_ground(self):
        self.memory.put(self.p+0x5D,'byte',1)
        self.inputs.keys={0x20}
        self.engine.set_feature('bunnyhop',True)
        self.assertEqual(self.engine.read(self.p+0x5F,'byte'),1)
        self.inputs.focused=False
        self.engine.tick()
        self.assertEqual(self.engine.read(self.p+0x5F,'byte'),0)

    def test_crouch_request_restores(self):
        self.engine.set_feature('crouch_hold',True)
        self.assertEqual(self.engine.read(self.p+0x63,'byte'),1)
        self.engine.reset()
        self.assertEqual(self.engine.read(self.p+0x63,'byte'),0)

    def test_target_priority_and_lock_keep_eligible_targets(self):
        bots=self.engine.bots()
        for b in bots:b['team']=0
        bots[0]['position']=(30.,20.,8.)
        bots[1]['position']=(18.,22.,8.)
        selected=choose_target(bots,(10.,20.,8.),90.,0.,1,nearest=True)
        self.assertEqual(selected['pointer'],bots[1]['pointer'])
        locked=choose_target(bots,(10.,20.,8.),90.,0.,1,nearest=True,preferred=bots[0]['pointer'])
        self.assertEqual(locked['pointer'],bots[0]['pointer'])
