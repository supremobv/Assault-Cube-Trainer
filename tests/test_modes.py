import unittest
import test_combat
from engine import PROFILE
from modes import allied,describe


class ModeTests(unittest.TestCase):
    def setUp(self):
        f=test_combat.CombatTests('test_angle_convention_and_wrap');f.setUp()
        self.engine,self.memory,self.p,self.enemy,self.ally=f.engine,f.memory,f.p,f.bot,0x2200000

    def mode(self,n):self.memory.put(self.memory.base+PROFILE['gamemode_rva'],'int',n)

    def test_multiplayer_entities_are_visible_but_not_bot_edit_targets(self):
        self.mode(5)
        self.memory.put(self.enemy+0x77,'byte',0);self.memory.put(self.ally+0x77,'byte',0)
        self.engine.set_feature('wall_esp',True,250)
        scene=self.engine.visual_snapshot()
        self.assertEqual([b['pointer']for b in scene['bots']],[self.enemy])
        self.assertEqual(self.engine.bots(),[])
        self.engine.set_feature('bot_health',True,500)
        self.assertEqual(self.engine.read(self.enemy+0xEC),100)
        self.assertIn('2 players / 0 bots',self.engine.visibility_report())

    def test_ffa_keeps_opponents_with_the_same_team_number(self):
        self.mode(2);self.engine.set_feature('wall_esp',True,250)
        scene=self.engine.visual_snapshot()
        self.assertEqual(len(scene['bots']),2)
        self.assertFalse(any(b['allied'] for b in scene['bots']))

    def test_aim_accepts_network_players_and_uses_mode_team_rules(self):
        self.mode(5);self.memory.put(self.enemy+0x77,'byte',0)
        self.engine.set_feature('auto_aim',True)
        self.assertAlmostEqual(self.engine.read(self.p+0x34,'float'),90.)
        self.engine.reset()

    def test_mode_change_reapplies_team_filter_without_reconnecting(self):
        self.mode(5);self.engine.set_feature('wall_esp',True,250)
        self.assertEqual(len(self.engine.visual_snapshot()['bots']),1)
        self.mode(2)
        self.assertEqual(len(self.engine.visual_snapshot()['bots']),2)
        self.mode(5);self.engine.set_feature('esp_allies',True)
        self.assertEqual(len(self.engine.visual_snapshot()['bots']),2)

    def test_local_player_and_camera_entities_are_not_targets(self):
        self.memory.put(self.enemy+0x77,'byte',2)
        self.memory.put(self.memory.base+0x18AC04,'uint',0x2500000)
        self.memory.put(0x2500000+4,'uint',self.p)
        self.assertEqual(self.engine.actors(True),[])

    def test_ffa_bot_edits_do_not_skip_same_team_numbers(self):
        self.mode(8);self.engine.set_feature('bot_health',True,300)
        self.assertEqual(self.engine.read(self.enemy+0xEC),300)
        self.assertEqual(self.engine.read(self.ally+0xEC),300)
        self.engine.reset()

    def test_team_mode_semantics(self):
        self.assertTrue(describe(5)['teams']);self.assertFalse(describe(2)['teams'])
        self.assertFalse(allied(0,0,False));self.assertTrue(allied(0,0,True))
        self.assertFalse(allied(4,4,True));self.assertFalse(describe(100)['teams'])
