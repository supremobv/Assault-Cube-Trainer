"""RangeLab: AssaultCube offline-practice trainer and live memory inspector."""
from pathlib import Path
import os
import sys
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox,
    QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea, QMessageBox)
from engine import Engine, PROFILE, LIMITS, ROOT

from catalog import CONTROLS
from overlay import PracticeOverlay
from compatibility import OFFLINE_ONLY
from configuration_ui import ConfigurationPanel

STYLE = '''
QWidget { background:#0e1720; color:#e4ecec; font-family:'Segoe UI'; font-size:13px; }
QLabel { background:transparent; }
QFrame#sidebar { background:#14222c; border-right:1px solid #2a3a45; }
QLabel#muted { color:#95aab6; }
QLabel#eyebrow { color:#74c8bd; font-size:10px; font-weight:700; letter-spacing:2px; }
QLabel#title { font-size:27px; font-weight:700; }
QFrame#card { background:#172732; border:1px solid #30444f; border-radius:12px; }
QFrame#telemetry { background:#1b323c; border:1px solid #3d5b61; border-radius:12px; }
QPushButton { background:#213945; border:1px solid #45606b; border-radius:7px; padding:9px 13px; font-weight:600; }
QPushButton:hover { background:#2b4b57; border-color:#6cccb8; }
QPushButton:disabled { color:#6c818b; background:#192c36; border-color:#30444f; }
QPushButton#primary { background:#6ad2bc; color:#10272b; border:none; }
QPushButton#nav { text-align:left; border:none; background:transparent; color:#a9b9bf; padding:13px; }
QPushButton#nav:checked { background:#25414a; color:#b2eee0; }
QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox { background:#0f1e28; border:1px solid #3b535f; border-radius:6px; padding:7px; min-height:18px; }
QLineEdit:focus,QSpinBox:focus,QDoubleSpinBox:focus { border-color:#6ad2bc; }
QCheckBox { background:transparent; spacing:10px; }
QCheckBox::indicator { width:36px; height:20px; border-radius:10px; background:#415965; border:1px solid #526d77; }
QCheckBox::indicator:checked { background:#69d1b9; border-color:#9be9d5; }
QCheckBox::indicator:disabled { background:#2e434e; border-color:#3c535e; }
QScrollArea { border:none; }
QScrollBar:vertical { width:8px; background:#0e1720; }
QScrollBar::handle:vertical { background:#375362; min-height:35px; border-radius:4px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
'''


def text(value, name=''):
    label = QLabel(value)
    label.setObjectName(name)
    return label


class RangeLab(QMainWindow):
    def __init__(self, engine=None):
        super().__init__()
        self.engine = engine or Engine()
        self.category = 'All controls'
        self.cards = []
        self.actions = []
        self.setWindowTitle('RangeLab — AssaultCube Trainer')
        self.setWindowIcon(QIcon(str(ROOT/'assets/rangelab.svg')))
        self.resize(1130, 850)
        self.setMinimumSize(980, 720)
        self.build()
        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(350)
        self.overlay=PracticeOverlay(self.engine,parent=self)

    def build(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(205)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 25, 18, 20)
        logo = QLabel()
        logo.setPixmap(QIcon(str(ROOT/'assets/rangelab.svg')).pixmap(62, 62))
        side.addWidget(logo)
        side.addWidget(text('RangeLab', 'title'))
        side.addWidget(text('ASSAULTCUBE TOOLKIT', 'eyebrow'))
        side.addSpacing(25)
        self.nav = {}
        for category in ('All controls', 'Player', 'Weapons', 'Aim & firing', 'Bot practice', 'Visibility', 'Camera & movement', 'Waypoints', 'Configuration', 'Address map'):
            button = QPushButton(category.replace('&', '&&'))
            button.setObjectName('nav')
            button.setCheckable(True)
            button.setChecked(category == self.category)
            button.clicked.connect(lambda checked=False, cat=category: self.navigate(cat))
            side.addWidget(button)
            self.nav[category] = button
        side.addStretch()
        side.addWidget(text('PRACTICE TOOLKIT', 'eyebrow'))
        note = text('Verified build: 1.3.0.2\nDeveloped by Primo\n@supremobv', 'muted')
        side.addWidget(note)
        outer.addWidget(sidebar)
        panel = QWidget()
        main = QVBoxLayout(panel)
        main.setContentsMargins(28, 24, 28, 20)
        main.setSpacing(16)
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(text('YOUR OWN TESTING GROUND', 'eyebrow'))
        titles.addWidget(text('Practice. Inspect. Experiment.', 'title'))
        top.addLayout(titles, 1)
        self.connect_button = QPushButton('Connect to game  ↗')
        self.connect_button.setObjectName('primary')
        self.connect_button.clicked.connect(self.connect_game)
        top.addWidget(self.connect_button)
        main.addLayout(top)
        strip = QFrame()
        strip.setObjectName('telemetry')
        stats = QGridLayout(strip)
        stats.setContentsMargins(18, 15, 18, 15)
        self.stats = {}
        for column, (key, title) in enumerate((('health', 'CLIENT HEALTH'), ('armour', 'CLIENT ARMOUR'), ('ammo', 'CLIENT AMMO'), ('position', 'POSITION'))):
            stats.addWidget(text(title, 'eyebrow'), 0, column)
            self.stats[key] = text('—')
            self.stats[key].setStyleSheet('font-size:20px; font-weight:600;')
            stats.addWidget(self.stats[key], 1, column)
        main.addWidget(strip)
        self.context = text('Weapon / scope / targeting status will appear after connection.', 'muted')
        self.context.setWordWrap(True)
        main.addWidget(self.context)
        self.visibility_context=text('Visibility supports local bots and multiplayer player entities.','muted')
        self.visibility_context.setWordWrap(True)
        main.addWidget(self.visibility_context)
        heading = QHBoxLayout()
        self.page_title = text('All controls', 'title')
        heading.addWidget(self.page_title, 1)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search the toolkit…')
        self.search.setFixedWidth(240)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_cards)
        heading.addWidget(self.search)
        main.addLayout(heading)
        self.combat_panel = self.build_combat_options()
        main.addWidget(self.combat_panel)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.grid = QGridLayout(self.content)
        self.grid.setContentsMargins(0, 0, 8, 0)
        self.grid.setSpacing(12)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        for category, key, title, description, default in CONTROLS:
            card = QFrame(self.content)
            card.setObjectName('card')
            card.setMinimumHeight(145)
            box = QVBoxLayout(card)
            box.setContentsMargins(17, 15, 17, 15)
            line = QHBoxLayout()
            name = text(title)
            name.setStyleSheet('font-size:15px; font-weight:600;')
            line.addWidget(name, 1)
            toggle = QCheckBox()
            toggle.setAccessibleName(title)
            line.addWidget(toggle)
            box.addLayout(line)
            desc = text(description, 'muted')
            desc.setWordWrap(True)
            box.addWidget(desc)
            editor = None
            if default is not None:
                editor = QSpinBox()
                editor.setRange(*LIMITS[key])
                editor.setValue(default)
                editor.setAccessibleName(title + ' value')
                box.addWidget(editor)
            record = {'widget': card, 'key': key, 'category': category, 'title': title, 'description': description, 'description_label':desc,'toggle': toggle, 'editor': editor}
            toggle.toggled.connect(lambda checked, item=record: self.toggle(item, checked))
            self.cards.append(record)
        self.empty = text('No matching controls. Try another search.', 'muted')
        self.empty.setParent(self.content)
        self.scroll.setWidget(self.content)
        main.addWidget(self.scroll, 1)
        self.waypoints = self.build_waypoints()
        self.address_map = self.build_address_map()
        main.addWidget(self.waypoints)
        main.addWidget(self.address_map)
        self.configuration=ConfigurationPanel(self)
        main.addWidget(self.configuration,1)
        footer = QHBoxLayout()
        self.status = text('Open AssaultCube, then connect.', 'muted')
        self.status.setWordWrap(True)
        footer.addWidget(self.status, 1)
        self.reset_button = QPushButton('Reset all')
        self.reset_button.clicked.connect(self.reset)
        footer.addWidget(self.reset_button)
        main.addLayout(footer)
        outer.addWidget(panel, 1)
        for button in self.actions:
            button.setProperty('offlineOnly',button.text() in {'Return to marker','Replenish loadout','Equip primary','Equip sniper','Apply coordinates','Lift two units'})
        self.filter_cards()

    def build_waypoints(self):
        frame = QFrame()
        frame.setObjectName('card')
        box = QVBoxLayout(frame)
        box.setContentsMargins(22, 22, 22, 22)
        info = text('Save a marker, return to it, or set the eye position directly.\nClear and resave your marker when changing maps.', 'muted')
        info.setWordWrap(True)
        box.addWidget(info)
        self.marker_label = text('No position saved.')
        box.addWidget(self.marker_label)
        row = QHBoxLayout()
        for title, fn in [('Save marker', self.save_marker), ('Return to marker', self.engine.return_to_marker), ('Replenish loadout', self.engine.replenish)]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, operation=fn: self.action(operation))
            row.addWidget(button)
            self.actions.append(button)
        box.addLayout(row)
        primary_row = QHBoxLayout()
        self.primary_selector = QComboBox()
        self.primary_selector.addItems(['Carbine', 'Shotgun', 'SMG', 'Sniper rifle', 'Assault rifle'])
        self.primary_selector.setCurrentIndex(4)
        primary_row.addWidget(self.primary_selector)
        for title, fn in [('Equip primary', lambda: self.engine.equip_primary(self.primary_selector.currentIndex()+2)), ('Equip sniper', lambda: self.engine.equip_primary(5)), ('Toggle sniper scope', self.engine.toggle_scope), ('Face nearest player', self.engine.face_nearest_bot)]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, operation=fn: self.action(operation))
            primary_row.addWidget(button)
            self.actions.append(button)
        box.addLayout(primary_row)
        coordinates = QHBoxLayout()
        self.coords = []
        for axis in 'XYZ':
            coordinates.addWidget(text(axis, 'eyebrow'))
            spin = QDoubleSpinBox()
            spin.setRange(-4096, 4096)
            spin.setDecimals(3)
            spin.setAccessibleName(axis + ' coordinate')
            self.coords.append(spin)
            coordinates.addWidget(spin)
        box.addLayout(coordinates)
        row = QHBoxLayout()
        for title, fn in [('Read current position', self.read_position), ('Apply coordinates', lambda: self.engine.teleport(tuple(w.value() for w in self.coords))), ('Lift two units', self.lift), ('Clear marker', self.clear_marker), ('Level view',self.engine.level_view)]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, operation=fn: self.action(operation))
            row.addWidget(button)
            self.actions.append(button)
        box.addLayout(row)
        box.addStretch()
        return frame

    def build_combat_options(self):
        frame = QFrame()
        frame.setObjectName('card')
        box = QGridLayout(frame)
        box.setContentsMargins(14, 10, 14, 10)
        self.activation = QComboBox()
        self.activation.addItems(['Hold Alt', 'Hold right mouse', 'Always while game focused'])
        self.activation.currentIndexChanged.connect(lambda index: self.engine.configure_combat(activation=['alt', 'right_mouse', 'always'][index]))
        box.addWidget(text('Activation', 'muted'), 0, 0)
        box.addWidget(self.activation, 1, 0)
        self.aim_editors = {}
        for column, (key, title, low, high, default) in enumerate([
            ('cone', 'Aim cone (degrees)', 1, 180, 35), ('smoothing', 'Smoothing', 1, 20, 4), ('max_distance', 'Range (units)', 1, 500, 250)], 1):
            spin = QSpinBox()
            spin.setRange(low, high)
            spin.setValue(default)
            spin.valueChanged.connect(lambda value, name=key: self.engine.configure_combat(**{name: value}))
            box.addWidget(text(title, 'muted'), 0, column)
            box.addWidget(spin, 1, column)
            self.aim_editors[key] = spin
        self.skip_allies = QCheckBox('Skip teammates in team modes (free-for-all handled automatically)')
        self.skip_allies.setChecked(True)
        self.skip_allies.toggled.connect(lambda value: self.engine.configure_combat(team_filter=value))
        box.addWidget(self.skip_allies, 2, 0, 1, 4)
        help_text = text('Aim uses recent rendered targets, not a full map raycast. Auto aim and view lock are mutually exclusive.\nHead aim uses the rendered head position; the sniper is the weapon with a headshot damage bonus.', 'muted')
        help_text.setWordWrap(True)
        box.addWidget(help_text, 3, 0, 1, 4)
        shortcuts = QHBoxLayout()
        for title, fn in [('Face nearest player', self.engine.face_nearest_bot), ('Equip sniper', lambda: self.engine.equip_primary(5)), ('Toggle scope', self.engine.toggle_scope)]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, operation=fn: self.action(operation))
            shortcuts.addWidget(button)
            self.actions.append(button)
        box.addLayout(shortcuts, 4, 0, 1, 4)
        return frame

    def build_address_map(self):
        frame = QFrame()
        frame.setObjectName('card')
        box = QVBoxLayout(frame)
        box.setContentsMargins(22, 22, 22, 22)
        title = text('Restart-verified pointer profile')
        title.setStyleSheet('font-size:18px; font-weight:600;')
        box.addWidget(title)
        details = text('Player root       ac_client.exe + 0x18AC00\nHealth            [root] + 0xEC\nArmour            [root] + 0xF0\nReserve ammo      [root] + 0x104 + weapon × 4\nMagazine          [root] + 0x128 + weapon × 4\nPosition          [root] + 0x04 / 0x08 / 0x0C\nWeapon table      ac_client.exe + 0x16BCC0\nWeapon stride     0x68\nCamera FOV        ac_client.exe + 0x18A7CC\nScope FOV         ac_client.exe + 0x18A834')
        details.setStyleSheet('font-family:Consolas; font-size:14px; line-height:1.7;')
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(details)
        note = text('The player moved from 0x0066D448 to 0x009179F0 after restart.\nThe module-relative root stayed valid. Exact executable SHA-256 is checked on connection.\nHealth/ammo had HUD confirmation. Bot aim and repeated firing were exercised live; see the address map for verification limits.', 'muted')
        note.setWordWrap(True)
        box.addWidget(note)
        box.addStretch()
        return frame

    def navigate(self, category):
        self.category = category
        self.page_title.setText(category)
        for name, button in self.nav.items():
            button.setChecked(name == category)
        self.filter_cards()

    def filter_cards(self):
        while self.grid.count():
            self.grid.takeAt(0)
        special = self.category in ('Waypoints', 'Address map','Configuration')
        self.combat_panel.setVisible(self.category == 'Aim & firing')
        self.scroll.setVisible(not special)
        if hasattr(self, 'waypoints'):
            self.waypoints.setVisible(self.category == 'Waypoints')
            self.address_map.setVisible(self.category == 'Address map')
            self.configuration.setVisible(self.category == 'Configuration')
        query = self.search.text().casefold().strip()
        visible = []
        for card in self.cards:
            show = not special and (self.category == 'All controls' or self.category == card['category']) and query in (card['title']+' '+card['description']).casefold()
            card['widget'].setVisible(show)
            if show:
                visible.append(card)
        for n, card in enumerate(visible):
            self.grid.addWidget(card['widget'], n//2, n%2)
        if not visible and not special:
            self.grid.addWidget(self.empty, 0, 0, 1, 2)
        self.empty.setVisible(not visible and not special)

    def connect_game(self):
        try:
            if self.engine.connected:
                self.engine.disconnect()
                self.status.setText('Disconnected. Original captured values restored.')
            else:
                self.engine.connect()
                self.status.setText('Connected to the verified build. No controls are enabled automatically.')
        except Exception as error:
            self.status.setText(str(error))
        self.refresh()

    def toggle(self, card, enabled):
        try:
            value = card['editor'].value() if card['editor'] else 0
            self.engine.set_feature(card['key'], enabled, value)
            self.status.setText(f'{card["title"]} {"enabled" if enabled else "disabled"}.')
        except Exception as error:
            self.status.setText(str(error))
        self.refresh()

    def action(self, fn):
        try:
            fn()
            self.status.setText('Action complete. Position and loadout actions are not undone by Reset all.')
        except Exception as error:
            self.status.setText(str(error))
        self.refresh()

    def save_marker(self):
        pos = self.engine.save_position()
        self.marker_label.setText('Saved: ' + '  /  '.join(f'{v:.3f}' for v in pos))

    def clear_marker(self):
        self.engine.marker = None
        self.marker_label.setText('No position saved.')

    def read_position(self):
        for widget, value in zip(self.coords, self.engine.telemetry()['position']):
            widget.setValue(value)

    def lift(self):
        x, y, z = self.engine.telemetry()['position']
        self.engine.teleport((x, y, z+2))

    def reset(self):
        try:
            self.engine.reset()
            self.status.setText('Captured values restored. One-time actions remain unchanged.')
        except Exception as error:
            self.status.setText(str(error))
        self.refresh()

    def refresh(self):
        connected = self.engine.connected
        try:online=connected and self.engine.multiplayer()
        except Exception:online=True
        self.connect_button.setText('Disconnect' if connected else 'Connect to game  ↗')
        self.reset_button.setEnabled(connected)
        for button in getattr(self, 'actions', []):
            button.setEnabled(connected and not(online and button.property('offlineOnly')))
            button.setToolTip('Offline only: this changes server-controlled state.' if online and button.property('offlineOnly') else '')
        for card in self.cards:
            active = card['key'] in self.engine.enabled
            reason=OFFLINE_ONLY.get(card['key']) if online else None
            card['widget'].setEnabled(connected and not reason)
            card['description_label'].setText(('Offline only: '+reason) if reason else card['description'])
            card['widget'].setToolTip(reason or '')
            card['toggle'].blockSignals(True)
            card['toggle'].setChecked(active)
            card['toggle'].blockSignals(False)
            if card['editor']:
                card['editor'].setEnabled(not active)
        if connected:
            try:
                data = self.engine.telemetry()
                self.stats['health'].setText(str(data['health']))
                self.stats['armour'].setText(str(data['armour']))
                self.stats['ammo'].setText(f'{data["clip"]} / {data["reserve"]}')
                self.stats['position'].setText(' / '.join(f'{v:.1f}' for v in data['position']))
                self.stats['position'].setStyleSheet('font-size:16px; font-weight:600;')
                zoom = f'SCOPED · {data["scope_fov"]}°' if data['scoped'] else f'Unscoped · {data["fov"]:.0f}°'
                self.context.setText(f'{data["gun"]}  |  {zoom}  |  {data["combat_status"]}')
                self.visibility_context.setText(data['visibility_status']+'\n'+data['compatibility_status']+(f' · Overlay error: {self.overlay.last_error}' if hasattr(self,'overlay')and self.overlay.last_error else ''))
                if data['error']:
                    self.status.setText(data['error']+' Reset or reconnect to continue.')
            except Exception as error:
                if self.engine.memory and not self.engine.memory.alive():
                    self.engine.disconnect(restore=False)
                    self.status.setText('The game closed. Connect again after restarting it.')
                else:
                    self.status.setText('Player data unavailable: '+str(error))
        else:
            self.visibility_context.setText('Connect to inspect the mode, player counts and visibility controls.')
            self.context.setText('Connect to inspect the mode, then enable the controls you want.')
            for label in self.stats.values():
                label.setText('—')

    def closeEvent(self, event):
        try:
            self.engine.disconnect()
            self.overlay.timer.stop()
            self.overlay.close()
            event.accept()
        except Exception as error:
            event.ignore()
            QMessageBox.warning(self, 'Reset incomplete', str(error)+'\nKeep the game open and retry Reset all.')


def configure(app):
    font_dir = Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts'
    for name in ('segoeui.ttf', 'segoeuib.ttf', 'seguisb.ttf', 'seguisym.ttf', 'consola.ttf'):
        if (font_dir/name).exists():
            QFontDatabase.addApplicationFont(str(font_dir/name))
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setFont(QFont('Segoe UI', 10))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    configure(app)
    window = RangeLab()
    window.show()
    sys.exit(app.exec())
