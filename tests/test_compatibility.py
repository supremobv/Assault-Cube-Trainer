import unittest
from engine import Engine,PROFILE,TrainerError
from compatibility import OFFLINE_ONLY
from test_engine import Memory
from test_combat import Inputs


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.memory=Memory();self.engine=Engine(self.memory,Inputs());self.p=self.engine.player()

    def online(self,value=1):self.memory.put(self.memory.base+PROFILE['connected_rva'],'int',value)

    def test_all_server_dependent_controls_are_blocked_without_player_edits(self):
        self.online();self.engine.enforce_multiplayer();before=dict(self.memory.data)
        for key in OFFLINE_ONLY:
            with self.subTest(key=key):
                with self.assertRaisesRegex(TrainerError,'Offline only'):self.engine.set_feature(key,True,100)
        self.assertEqual(self.memory.data,before)

    def test_repairs_weapon_protocol_fields_using_exact_build_baseline(self):
        base=self.memory.base+PROFILE['weapon_table_rva']+5*104
        self.memory.put(base+0x48,'short',25);self.memory.put(base+0x56,'short',100)
        health=self.engine.read(self.p+0xEC);ammo=self.engine.read(self.p+0x140)
        self.online();self.engine.enforce_multiplayer()
        self.assertEqual(self.engine.read(base+0x48,'short'),1500)
        self.assertEqual(self.engine.read(base+0x56,'short'),5)
        self.assertEqual(self.engine.read(self.p+0xEC),health)
        self.assertEqual(self.engine.read(self.p+0x140),ammo)
        self.assertIn('Respawn',self.engine.compatibility_status)

    def test_connection_transition_restores_owned_edits_but_preserves_visuals(self):
        self.engine.set_feature('health',True,999);self.engine.set_feature('rapid_fire',True,25)
        self.engine.set_feature('crosshair',True)
        self.online();self.engine.tick()
        self.assertNotIn('health',self.engine.enabled);self.assertNotIn('rapid_fire',self.engine.enabled)
        self.assertIn('crosshair',self.engine.enabled)
        self.assertEqual(self.engine.read(self.p+0xEC),100)

    def test_connection_transition_does_not_teleport_to_old_flight_marker(self):
        self.engine.set_feature('noclip',True,16)
        self.memory.put(self.p+4,'float',200.)
        self.online();self.engine.tick()
        self.assertNotIn('noclip',self.engine.enabled)
        self.assertEqual(self.engine.read(self.p+4,'float'),200.)

    def test_actual_connection_overrides_mode_classification(self):
        self.memory.put(self.memory.base+PROFILE['gamemode_rva'],'int',8)
        self.online()
        with self.assertRaises(TrainerError):self.engine.set_feature('health',True,999)
        self.online(0);self.memory.put(self.memory.base+PROFILE['gamemode_rva'],'int',5)
        self.engine.set_feature('health',True,999)
        self.assertEqual(self.engine.read(self.p+0xEC),999)
        self.engine.reset()

    def test_unsafe_one_time_actions_cannot_bypass_compatibility(self):
        self.online();before=dict(self.memory.data)
        for action in (lambda:self.engine.teleport((1.,2.,3.)),self.engine.replenish,lambda:self.engine.equip_primary(5)):
            with self.assertRaisesRegex(TrainerError,'Offline only'):action()
        self.assertEqual(self.memory.data,before)

    def test_invalid_connection_flag_does_not_silently_enable_offline_edits(self):
        self.online(7);before=dict(self.memory.data)
        with self.assertRaisesRegex(TrainerError,'Connection state'):self.engine.set_feature('health',True,999)
        self.assertEqual(self.memory.data,before)
