import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from engine import Engine
from rangelab import RangeLab, configure
from test_engine import Memory


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure(cls.app)

    def setUp(self):
        self.qt_errors = []
        self.previous_hook = sys.excepthook
        sys.excepthook = lambda kind, value, trace: self.qt_errors.append(str(value))

    def tearDown(self):
        sys.excepthook = self.previous_hook
        self.assertEqual(self.qt_errors, [], 'A Qt signal handler raised an exception')

    def test_disconnected_controls_and_category_search(self):
        window = RangeLab()
        window.timer.stop()
        window.show()
        self.app.processEvents()
        self.assertTrue(all(not c['widget'].isEnabled() for c in window.cards))
        window.navigate('Weapons')
        window.search.setText('reload')
        self.assertEqual([c['key'] for c in window.cards if not c['widget'].isHidden()], ['fast_reload', 'large_mags', 'auto_refill'])
        window.search.setText('nothing-matches')
        self.assertFalse(window.empty.isHidden())
        window.close()

    def test_gui_toggle_and_close_restore_values(self):
        memory = Memory()
        engine = Engine(memory)
        window = RangeLab(engine)
        window.timer.stop()
        window.show()
        self.app.processEvents()
        health = next(c for c in window.cards if c['key'] == 'health')
        health['editor'].setValue(400)
        health['toggle'].click()
        self.assertEqual(engine.telemetry()['health'], 400)
        self.assertFalse(health['editor'].isEnabled())
        window.close()
        self.assertTrue(memory.closed)
        self.assertEqual(int.from_bytes(memory.read(0x2000000+0xEC, 4), 'little'), 100)

    def test_invalid_player_does_not_leave_toggle_enabled(self):
        memory = Memory()
        engine = Engine(memory)
        window = RangeLab(engine)
        window.timer.stop()
        memory.put(0x2000000, 'uint', 0)
        health = next(c for c in window.cards if c['key'] == 'health')
        health['toggle'].click()
        self.assertFalse(health['toggle'].isChecked())
        memory.put(0x2000000, 'uint', memory.base+0x1000)
        window.close()

    def test_overlay_renders_and_hides_with_game_focus(self):
        import test_combat
        from overlay import PracticeOverlay
        fixture=test_combat.CombatTests('test_angle_convention_and_wrap');fixture.setUp()
        engine=fixture.engine
        for key,value in (('wall_esp',250),('radar',75),('crosshair',0),('esp_tracers',0)):
            engine.set_feature(key,True,value)
        class WindowSource:
            focused=True
            def rectangle(self,pid):return (0,0,800,600) if self.focused else None
        source=WindowSource();overlay=PracticeOverlay(engine,source);overlay.timer.stop()
        overlay.refresh();self.app.processEvents()
        self.assertTrue(overlay.isVisible())
        image=overlay.grab().toImage()
        self.assertFalse(image.isNull())
        self.assertEqual(image.pixelColor(0,0).alpha(),0,'Overlay must not cover the game with an opaque background')
        source.focused=False;overlay.refresh()
        self.assertFalse(overlay.isVisible())
        engine.reset();overlay.close()

    def test_multiplayer_marks_offline_controls_and_actions(self):
        memory=Memory();memory.put(memory.base+__import__('engine').PROFILE['connected_rva'],'int',1)
        engine=Engine(memory);engine.enforce_multiplayer()
        window=RangeLab(engine);window.timer.stop()
        health=next(c for c in window.cards if c['key']=='health')
        esp=next(c for c in window.cards if c['key']=='wall_esp')
        self.assertFalse(health['widget'].isEnabled())
        self.assertIn('Offline only',health['description_label'].text())
        self.assertTrue(esp['widget'].isEnabled())
        self.assertFalse(next(b for b in window.actions if b.text()=='Replenish loadout').isEnabled())
        window.close()

    def test_profile_loading_is_inactive_by_default_and_skips_online_stats(self):
        import tempfile
        from profile_store import ProfileStore
        from engine import PROFILE
        memory=Memory();engine=Engine(memory);window=RangeLab(engine);window.timer.stop()
        with tempfile.TemporaryDirectory()as folder:
            panel=window.configuration;panel.store=ProfileStore(folder)
            health=next(c for c in window.cards if c['key']=='health')
            health['editor'].setValue(500);engine.set_feature('health',True,500)
            engine.set_feature('crosshair',True);engine.configure_visuals(crosshair_style='circle',esp_boxes=False)
            panel.save();engine.reset();engine.configure_visuals(crosshair_style='dot')
            panel.load()
            self.assertEqual(engine.enabled,{})
            self.assertEqual(engine.visual_options['crosshair_style'],'circle')
            self.assertFalse(engine.visual_options['esp_boxes'])
            memory.put(memory.base+PROFILE['connected_rva'],'int',1)
            panel.activate.setChecked(True);panel.load()
            self.assertNotIn('health',engine.enabled);self.assertIn('crosshair',engine.enabled)
            self.assertIn('skipped 1',window.status.text())
        window.close()


if __name__ == '__main__':
    unittest.main()
