import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Engine, PROFILE, TrainerError, FORMATS


class Memory:
    base = 0x400000
    size = PROFILE['module_size']
    pid = 123

    def __init__(self):
        self.data = {}
        self.fail = set()
        self.closed = False
        self.initialize_player(0x2000000)
        self.put(self.base+PROFILE['player_root_rva'], 'uint', 0x2000000)
        self.put(self.base+PROFILE['fov_rva'], 'float', 90.)
        self.put(self.base+PROFILE['scope_fov_rva'], 'int', 50)
        for i in range(9):
            b = self.base+PROFILE['weapon_table_rva']+i*PROFILE['weapon_stride']
            for off, value in [(0x46, 2000), (0x48, 120), (0x4A, 22), (0x52, 18), (0x54, 30), (0x56, 20), (0x58, 3), (0x5A, 3), (0x5E, 25), (0x60, 50)]:
                self.put(b+off, 'short', value)

    def initialize_player(self, p):
        self.put(p, 'uint', self.base+0x1000)
        self.put(p+0xEC, 'int', 100)
        self.put(p+0xF0, 'int', 25)
        self.put(p+0xFC, 'int', 6)
        self.put(p+0x50, 'float', 4.5)
        for off, value in zip((4, 8, 12), (10., 20., 8.)):
            self.put(p+off, 'float', value)

    def read(self, address, size):
        return bytes(self.data.get(address+i, 0) for i in range(size))

    def write(self, address, data):
        if address in self.fail:
            raise OSError('simulated write failure')
        for i, value in enumerate(data):
            self.data[address+i] = value

    def put(self, address, kind, value):
        self.write(address, struct.pack(FORMATS[kind], value))

    def close(self):
        self.closed = True

    def alive(self):
        return not self.closed


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory()
        self.engine = Engine(self.memory)
        self.player = self.engine.player()

    def test_health_toggle_restores_captured_value(self):
        self.engine.set_feature('health', True, 700)
        self.assertEqual(self.engine.read(self.player+0xEC), 700)
        self.engine.set_feature('health', False)
        self.assertEqual(self.engine.read(self.player+0xEC), 100)

    def test_root_is_resolved_again_and_stale_heap_is_not_restored(self):
        self.engine.set_feature('health', True, 700)
        new = 0x3000000
        self.memory.initialize_player(new)
        self.memory.put(self.memory.base+PROFILE['player_root_rva'], 'uint', new)
        self.engine.tick()
        self.assertEqual(self.engine.read(new+0xEC), 700)
        self.engine.reset()
        self.assertEqual(self.engine.read(new+0xEC), 100)
        self.assertEqual(self.engine.read(self.player+0xEC), 700)

    def test_validation_rejects_wrong_structure_before_writing(self):
        self.memory.put(self.player, 'uint', 0)
        with self.assertRaises(TrainerError):
            self.engine.set_feature('health', True, 700)
        self.assertEqual(self.engine.read(self.player+0xEC), 100)

    def test_failed_restore_keeps_snapshot_for_retry(self):
        self.engine.set_feature('health', True, 700)
        self.memory.fail.add(self.player+0xEC)
        with self.assertRaises(TrainerError):
            self.engine.set_feature('health', False)
        self.assertIn('health', self.engine.originals)
        with self.assertRaises(TrainerError):
            self.engine.set_feature('health', True, 700)
        self.memory.fail.clear()
        self.engine.reset()
        self.assertEqual(self.engine.read(self.player+0xEC), 100)

    def test_two_shared_controls_restore_independently(self):
        b = self.memory.base+PROFILE['weapon_table_rva']+6*PROFILE['weapon_stride']
        self.engine.set_feature('no_spread', True)
        self.engine.set_feature('rapid_fire', True, 25)
        self.engine.set_feature('no_spread', False)
        self.assertEqual(self.engine.read(b+0x52, 'short'), 18)
        self.assertEqual(self.engine.read(b+0x48, 'short'), 25)
        self.engine.reset()
        self.assertEqual(self.engine.read(b+0x48, 'short'), 120)

    def test_dead_player_is_not_given_health(self):
        self.memory.put(self.player+0x76, 'byte', 1)
        self.memory.put(self.player+0xEC, 'int', 0)
        self.engine.set_feature('health', True, 700)
        self.assertEqual(self.engine.read(self.player+0xEC), 0)

    def test_teleport_updates_interpolation_and_validates_coordinates(self):
        self.engine.save_position()
        self.engine.teleport((30., 40., 10.))
        self.assertAlmostEqual(self.engine.read(self.player+0x30, 'float'), 5.5)
        self.engine.return_to_marker()
        self.assertEqual(self.engine.telemetry()['position'], (10., 20., 8.))
        with self.assertRaises(TrainerError):
            self.engine.teleport((float('nan'), 0., 0.))

    def test_value_bounds_prevent_invalid_writes(self):
        with self.assertRaises(TrainerError):
            self.engine.set_feature('fov', True, 300)
        self.assertEqual(self.engine.read(self.memory.base+PROFILE['fov_rva'], 'float'), 90.)


if __name__ == '__main__':
    unittest.main()
