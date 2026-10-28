"""Local JSON profiles: bounded, validated, atomic writes; never executable content."""
import json
import os
from pathlib import Path
import re
import tempfile
from catalog import CONTROLS
from engine import Engine,LIMITS
from visual_settings import validate as validate_visuals


def validate(payload):
    if not isinstance(payload,dict)or set(payload)!={'version','controls','combat','visuals'}or type(payload['version'])is not int or payload['version']!=1:
        raise ValueError('Unsupported profile format.')
    defaults={key:{'enabled':False,'value':default} for _,key,_,_,default in CONTROLS}
    records=payload['controls']
    if not isinstance(records,dict)or set(records)-set(defaults):raise ValueError('Profile contains unknown controls.')
    for key,record in records.items():
        if not isinstance(record,dict)or set(record)!={'enabled','value'}or type(record['enabled'])is not bool:
            raise ValueError('Invalid profile control.')
        value=record['value']
        if key in LIMITS:
            low,high=LIMITS[key]
            if type(value)is not int or not low<=value<=high:raise ValueError(f'Invalid preset for {key}.')
        elif value is not None:raise ValueError('Unexpected value for a toggle control.')
        defaults[key]=dict(record)
    combat=payload['combat'];validator=Engine()
    if not isinstance(combat,dict)or set(combat)!=set(validator.combat_options):raise ValueError('Invalid aim settings.')
    if any(type(combat[key])is not bool for key in ('team_filter','rendered_only')):raise ValueError('Aim filter settings must be true or false.')
    validator.configure_combat(**combat)
    active={key for key,r in defaults.items()if r['enabled']}
    for group in ({'noclip','hover','bunnyhop','speed_hack'},{'auto_aim','headshot','view_lock'},
                  {'headshot','auto_shoot','triggerbot'},{'fragile_bots','bot_health'}):
        if len(group & active)>1:raise ValueError('Profile enables mutually exclusive controls.')
    if 'auto_refill' in active and active & {'magazines','reserves'}:raise ValueError('Profile enables conflicting ammo controls.')
    return {'version':1,'controls':defaults,'combat':dict(combat),'visuals':validate_visuals(payload['visuals'])}


class ProfileStore:
    def __init__(self,directory=None):
        self.directory=Path(directory)if directory is not None else Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'RangeLab'/'profiles'

    def path(self,name):
        reserved={'CON','PRN','AUX','NUL',*(f'COM{i}'for i in range(1,10)),*(f'LPT{i}'for i in range(1,10))}
        if not isinstance(name,str)or name!=name.strip()or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,47}',name)or name.upper()in reserved:
            raise ValueError('Use 1–48 letters, numbers, spaces, underscores or hyphens for the profile name.')
        return self.directory/(name+'.json')

    def names(self):
        return sorted(p.stem for p in self.directory.glob('*.json')if p.is_file())

    def save(self,name,payload):
        path=self.path(name);data=validate(payload)
        self.directory.mkdir(parents=True,exist_ok=True)
        temporary=None
        try:
            with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=self.directory,prefix='.profile-',suffix='.tmp',delete=False)as f:
                temporary=Path(f.name);json.dump(data,f,indent=2,allow_nan=False);f.write('\n')
            os.replace(temporary,path)
        finally:
            if temporary is not None and temporary.exists():temporary.unlink()
        return path

    def load(self,name):
        path=self.path(name)
        if path.stat().st_size>1024*1024:raise ValueError('Profile is too large.')
        return validate(json.loads(path.read_text(encoding='utf-8')))
