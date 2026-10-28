"""Configuration/profile page; loading never activates controls by default."""
from PySide6.QtWidgets import (QFrame,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,
    QLineEdit,QComboBox,QPushButton,QCheckBox,QSpinBox,QScrollArea)
from profile_store import ProfileStore
from visual_settings import DEFAULTS,BOUNDS


class ConfigurationPanel(QFrame):
    def __init__(self,owner,store=None):
        super().__init__();self.owner=owner;self.store=store or ProfileStore();self.editors={}
        self.setObjectName('card');box=QVBoxLayout(self)
        note=QLabel('Save aim settings, control presets and appearance. Loading restores current controls first.\nActivation is opt-in; multiplayer-incompatible controls are skipped.\nAppearance options use the master ESP / crosshair controls.')
        note.setWordWrap(True);box.addWidget(note)
        row=QHBoxLayout();self.profile_list=QComboBox();self.profile_list.setMinimumWidth(150)
        self.profile_name=QLineEdit('Practice');self.profile_name.setPlaceholderText('Profile name')
        row.addWidget(self.profile_list);row.addWidget(self.profile_name,1)
        for label,fn in [('Save current',self.save),('Load profile',self.load)]:
            button=QPushButton(label);button.clicked.connect(fn);row.addWidget(button)
        box.addLayout(row)
        self.activate=QCheckBox('Activate compatible saved controls when loading (requires connection)')
        box.addWidget(self.activate)
        scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();grid=QGridLayout(body)
        labels={'esp_boxes':'ESP boxes','esp_names':'ESP names','esp_health':'ESP health','esp_armour':'ESP armour','esp_distance':'ESP distance',
                'enemy_color':'Enemy color (#RRGGBB)','ally_color':'Ally color (#RRGGBB)','crosshair_color':'Crosshair color (#RRGGBB)',
                'crosshair_style':'Crosshair style','crosshair_size':'Crosshair size','crosshair_gap':'Crosshair gap',
                'crosshair_width':'Crosshair thickness','esp_line_width':'ESP line thickness','esp_text_size':'ESP text size','radar_size':'Radar size'}
        for n,(key,default)in enumerate(DEFAULTS.items()):
            label=QLabel(labels[key]);grid.addWidget(label,n//2,(n%2)*2)
            if type(default)is bool:
                editor=QCheckBox();editor.setChecked(default)
                editor.toggled.connect(lambda value,k=key:self.change(k,value))
            elif key in BOUNDS:
                editor=QSpinBox();editor.setRange(*BOUNDS[key]);editor.setValue(default)
                editor.valueChanged.connect(lambda value,k=key:self.change(k,value))
            elif key=='crosshair_style':
                editor=QComboBox();editor.addItems(['plus','dot','circle']);editor.setCurrentText(default)
                editor.currentTextChanged.connect(lambda value,k=key:self.change(k,value))
            else:
                editor=QLineEdit(default);editor.setMaxLength(7)
                editor.editingFinished.connect(lambda k=key:self.change(k,self.editors[k].text()))
            editor.setAccessibleName(labels[key]);grid.addWidget(editor,n//2,(n%2)*2+1);self.editors[key]=editor
        grid.setColumnStretch(1,1);grid.setColumnStretch(3,1)
        scroll.setWidget(body);box.addWidget(scroll,1)
        path=QLabel('Profiles: '+str(self.store.directory));path.setWordWrap(True);box.addWidget(path)
        self.profile_list.currentTextChanged.connect(self.profile_name.setText)
        self.reload_names();self.sync()

    def reload_names(self):
        self.profile_list.blockSignals(True);self.profile_list.clear();self.profile_list.addItems(self.store.names());self.profile_list.blockSignals(False)

    def sync(self):
        for key,editor in self.editors.items():
            value=self.owner.engine.visual_options[key];editor.blockSignals(True)
            if isinstance(editor,QCheckBox):editor.setChecked(value)
            elif isinstance(editor,QSpinBox):editor.setValue(value)
            elif isinstance(editor,QComboBox):editor.setCurrentText(value)
            else:editor.setText(value)
            editor.blockSignals(False)

    def change(self,key,value):
        try:
            self.owner.engine.configure_visuals(**{key:value})
            self.owner.status.setText('Appearance updated. Save a profile to keep these settings.')
        except Exception as error:self.owner.status.setText(str(error))
        self.sync()

    def capture(self):
        engine=self.owner.engine
        with engine.lock:
            return {'version':1,'controls':{card['key']:{'enabled':card['key']in engine.enabled,'value':card['editor'].value()if card['editor']else None}for card in self.owner.cards},
                    'combat':dict(engine.combat_options),'visuals':dict(engine.visual_options)}

    def save(self):
        try:
            path=self.store.save(self.profile_name.text().strip(),self.capture());self.reload_names()
            self.owner.status.setText('Saved profile: '+str(path))
        except Exception as error:self.owner.status.setText(str(error))

    def load(self):
        try:
            name=self.profile_name.text().strip();data=self.store.load(name);engine=self.owner.engine
            if self.activate.isChecked()and not engine.connected:raise ValueError('Connect before activating profile controls.')
            if engine.connected:engine.reset()
            engine.configure_combat(**data['combat']);engine.configure_visuals(**data['visuals']);self.sync()
            activation=['alt','right_mouse','always'].index(data['combat']['activation'])
            self.owner.activation.blockSignals(True);self.owner.activation.setCurrentIndex(activation);self.owner.activation.blockSignals(False)
            for key,editor in self.owner.aim_editors.items():
                editor.blockSignals(True);editor.setValue(int(data['combat'][key]));editor.blockSignals(False)
            self.owner.skip_allies.blockSignals(True);self.owner.skip_allies.setChecked(data['combat']['team_filter']);self.owner.skip_allies.blockSignals(False)
            for card in self.owner.cards:
                if card['editor']:card['editor'].setValue(data['controls'][card['key']]['value'])
            enabled=0;skipped=[]
            if self.activate.isChecked():
                for key,record in data['controls'].items():
                    if record['enabled']:
                        try:engine.set_feature(key,True,record['value']if record['value']is not None else 0);enabled+=1
                        except Exception as error:skipped.append(key+': '+str(error))
            self.owner.status.setText(f'Loaded {name}. Activated {enabled}; skipped {len(skipped)}. '+('Controls stay off until enabled.'if not self.activate.isChecked()else''))
            self.owner.status.setToolTip('\n'.join(skipped));self.owner.refresh()
        except Exception as error:self.owner.status.setText(str(error))
