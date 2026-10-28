"""Data-only trainer for the locally verified AssaultCube 1.3.0.2 executable.

Every player address is resolved again from the module-relative root.
Two opt-in local-practice native controls use reversible executable patches.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import threading
import time
from aiming import angle_delta, choose_target
from modes import describe,allied
from compatibility import OFFLINE_ONLY
from visual_settings import DEFAULTS as VISUAL_DEFAULTS,validate as validate_visuals
from native_features import NativeFeatures,KEYS as NATIVE

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
PROFILE = json.loads((ROOT / 'profile.json').read_text(encoding='utf-8-sig'))
FIREARMS = (1, 2, 3, 4, 5, 6, 8)


class TrainerError(RuntimeError):
    pass


class ProcessMemory:
    def __init__(self):
        import pymem
        import pymem.process
        self.pm = pymem.Pymem(PROFILE['process'], exact_match=True, ignore_case=True)
        try:
            module = pymem.process.module_from_name(self.pm.process_handle, PROFILE['process'])
            path = module.filename
            digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            if digest != PROFILE['sha256']:
                raise TrainerError('Unsupported executable. This profile requires the verified 1.3.0.2 SHA-256.')
            self.base = module.lpBaseOfDll
            self.size = module.SizeOfImage
            self.pid = self.pm.process_id
            if self.size != PROFILE['module_size']:
                raise TrainerError('Unexpected module layout.')
        except Exception:
            self.pm.close_process()
            raise

    def read(self, address, size):
        return self.pm.read_bytes(address, size)

    def write(self, address, data):
        self.pm.write_bytes(address, data, len(data))

    def close(self):
        self.pm.close_process()

    def alive(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.GetExitCodeProcess.restype = wintypes.BOOL
        code = wintypes.DWORD()
        return bool(kernel.GetExitCodeProcess(self.pm.process_handle, ctypes.byref(code)) and code.value == 259)


FORMATS = {'int': '<i', 'uint': '<I', 'float': '<f', 'short': '<h', 'byte': '<B'}
LIMITS = {'speed_hack': (1, 5), 'visual_ping': (0, 999), 'noclip': (1, 50), 'bot_health': (1, 1000), 'bot_armour': (0, 1000), 'wall_esp': (10, 500), 'radar': (10, 250), 'health': (1, 1000), 'armour': (0, 1000), 'magazines': (1, 999),
          'reserves': (0, 9999), 'grenades': (0, 50), 'rapid_fire': (1, 250),
          'fast_reload': (1, 1000), 'large_mags': (1, 999), 'damage': (1, 2000),
          'fov': (75, 120), 'scope_fov': (5, 60)}
COMBAT = {'auto_aim', 'headshot', 'auto_shoot', 'triggerbot'}
BOT_CONTROLS = {'freeze_bots', 'fragile_bots', 'bot_health', 'bot_armour'}
VISUALS = {'wall_esp', 'radar', 'esp_allies', 'esp_tracers', 'crosshair', 'aim_circle', 'offscreen_arrows','visual_ping'}
FEATURE_KEYS = set(LIMITS) | {'noclip', 'hover', 'no_recoil', 'no_spread', 'automatic', 'slow_fall', 'view_lock', 'no_cooldown', 'stable_camera', 'akimbo', 'scope_settle', 'scope_lock', 'auto_refill', 'bunnyhop', 'crouch_hold', 'target_lock', 'nearest_target'} | COMBAT | BOT_CONTROLS | VISUALS
FEATURE_KEYS |= NATIVE


class DesktopInput:
    """Read activation keys and the foreground process; never synthesize mouse input."""
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wintypes = ctypes, wintypes
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.user.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.user.GetAsyncKeyState.restype = ctypes.c_short
        self.user.GetForegroundWindow.restype = wintypes.HWND
        self.user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

    def foreground(self, pid):
        value = self.wintypes.DWORD()
        self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(), self.ctypes.byref(value))
        return value.value == pid

    def down(self, key):
        return bool(self.user.GetAsyncKeyState(key) & 0x8000)


class Engine:
    def __init__(self, memory=None, inputs=None):
        self.memory = memory
        self.lock = threading.RLock()
        self.enabled = {}
        self.originals = {}
        self.last_error = ''
        self.marker = None
        self.stop_event = threading.Event()
        self.thread = None
        self.connected = memory is not None
        self.inputs = inputs
        self.combat_options = {'activation': 'alt', 'cone': 35., 'smoothing': 4., 'max_distance': 250., 'tolerance': .6, 'team_filter': True, 'rendered_only': True}
        self.combat_status = 'Aim and firing controls off.'
        self.attack_owner = None
        self.jump_owner = None
        self.locked_target = None
        self.noclip_entry = None
        self.flight_position = None
        self.flight_time = None
        self.last_online = None
        self.compatibility_status = ''
        self.visual_options=dict(VISUAL_DEFAULTS)
        self.speed_owner=None
        self.native=None

    def read(self, address, kind='int'):
        fmt = FORMATS[kind]
        return struct.unpack(fmt, self.memory.read(address, struct.calcsize(fmt)))[0]

    def write(self, address, kind, value):
        self.memory.write(address, struct.pack(FORMATS[kind], value))

    def player(self):
        if not self.connected:
            raise TrainerError('Connect to the game first.')
        base = self.memory.base
        pointer = self.read(base + PROFILE['player_root_rva'], 'uint')
        if not 0x10000 < pointer < 0x7FFF0000:
            raise TrainerError('Player pointer is not ready.')
        vtable = self.read(pointer, 'uint')
        if not base <= vtable < base + self.memory.size:
            raise TrainerError('Player structure failed validation.')
        health = self.read(pointer + 0xEC)
        weapon = self.read(pointer + 0xFC)
        if not -10000 <= health <= 10000 or not 0 <= weapon < 9:
            raise TrainerError('Player layout no longer matches the verified profile.')
        return pointer

    def connect(self, start_worker=True):
        with self.lock:
            if self.connected:
                return
            self.memory = ProcessMemory()
            self.connected = True
            try:
                self.player()
                # Verify table names and each player's weapon references.
                player = self.player()
                expected = ('knife', 'pistol', 'carbine', 'shotgun', 'subgun', 'sniper', 'assault', 'grenade', 'pistol')
                for index, model in enumerate(expected):
                    address = self.memory.base + PROFILE['weapon_table_rva'] + index * PROFILE['weapon_stride']
                    name = self.memory.read(address, 23).split(b'\0')[0].decode('ascii')
                    weapon = self.read(player + 0x33C + index * 4, 'uint')
                    if name != model or self.read(weapon + 8, 'uint') != player or self.read(weapon + 12, 'uint') != address:
                        raise TrainerError('Weapon table failed validation.')
                self.enforce_multiplayer()
            except Exception:
                self.memory.close()
                self.memory = None
                self.connected = False
                raise
            self.stop_event.clear()
            self.last_error = ''
            if start_worker:
                self.thread = threading.Thread(target=self._worker, daemon=True)
                self.thread.start()

    def _worker(self):
        while not self.stop_event.wait(.012):
            if self.last_error:
                continue
            try:
                self.tick()
            except Exception as error:
                with self.lock:
                    self.last_error = f'Writes stopped: {error}'
                    self._release_attack()
                    self._release_jump()
                    self._release_speed()
                    if self.native:
                        try:self.native.reset()
                        except Exception as restore_error:self.last_error+='; native restoration pending: '+str(restore_error)
                    self.enabled.clear()
                # Leave snapshots available for an explicit reset/recovery attempt.
                continue

    def edits(self, name, value, player):
        """Return field edits as (address, scalar type, value, owning player)."""
        base = self.memory.base
        p = lambda off, kind, val: (player + off, kind, val, player)
        if name == 'health': return [p(0xEC, 'int', int(value))]
        if name == 'armour': return [p(0xF0, 'int', int(value))]
        if name == 'magazines': return [p(0x128 + i*4, 'int', int(value)) for i in FIREARMS]
        if name == 'reserves': return [p(0x104 + i*4, 'int', int(value)) for i in FIREARMS]
        if name == 'grenades': return [p(0x144, 'int', int(value))]
        if name == 'slow_fall': return [p(0x48, 'int', 0)]
        if name in {'noclip','speed_hack'} | NATIVE: return []
        if name == 'hover': return [p(12,'float',value), p(0x30,'float',value-self.read(player+0x50,'float')), p(0x18,'float',0.), p(0x24,'float',0.), p(0x48,'int',0)]
        if name in VISUALS: return []
        if name == 'view_lock': return [p(0x34, 'float', value[0]), p(0x38, 'float', value[1])]
        if name == 'no_cooldown':
            gun = self.read(player+0xFC)
            return [p(0x14C+gun*4, 'int', 0)] if gun in FIREARMS else []
        if name == 'stable_camera': return [p(off, 'float', 0.) for off in (0x3C, 0x40, 0x32C, 0x330)]
        if name == 'crouch_hold': return [p(0x63, 'byte', 1)]
        if name == 'akimbo':
            weapon = self.weapon_object(player,8)
            return [p(0x100,'byte',1),(weapon+0x2C,'int',self.read(base+0x17F10C)+30000,player)]
        if name in {'scope_settle','scope_lock'}:
            weapon = self.weapon_object(player,5)
            if self.read(player+0xFC) != 5:return []
            if name == 'scope_settle':return [(weapon+0x2C,'int',self.read(base+0x17F10C)-181,player)]
            return [(weapon+0x28,'byte',1,player),p(0x66,'byte',1)]
        if name in {'auto_refill','bunnyhop','target_lock','nearest_target'}:return []
        if name in COMBAT | BOT_CONTROLS: return []
        if name == 'fov': return [(base + PROFILE['fov_rva'], 'float', float(value), None)]
        if name == 'scope_fov': return [(base + PROFILE['scope_fov_rva'], 'int', int(value), None)]
        fields = {
            'no_recoil': {0x54: ('short', 0), 0x58: ('short', 0), 0x5A: ('short', 0), 0x5E: ('short', 0), 0x60: ('short', 0)},
            'no_spread': {0x52: ('short', 0)},
            'rapid_fire': {0x48: ('short', int(value))},
            'fast_reload': {0x46: ('short', int(value))},
            'automatic': {0x66: ('byte', 1)},
            'large_mags': {0x56: ('short', int(value))},
            'damage': {0x4A: ('short', int(value))},
        }
        if name not in fields:
            raise TrainerError('Unknown control.')
        # Shotgun damage uses a special calculation; do not promise a multiplier.
        indices = [i for i in FIREARMS if name != 'damage' or i != 3]
        return [(base + PROFILE['weapon_table_rva'] + i*PROFILE['weapon_stride'] + off, kind, val, None)
                for i in indices for off, (kind, val) in fields[name].items()]

    def set_feature(self, name, enabled, value=0):
        with self.lock:
            if enabled:
                if name not in FEATURE_KEYS:
                    raise TrainerError('Unknown control.')
                self.enforce_multiplayer()
                if self.multiplayer() and name in OFFLINE_ONLY:
                    raise TrainerError('Offline only: '+OFFLINE_ONLY[name])
                if name in LIMITS:
                    low, high = LIMITS[name]
                    if not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                        raise TrainerError(f'Value must be between {low} and {high}.')
                if self.last_error:
                    raise TrainerError('Reset or reconnect after the previous worker error.')
                if self.originals.get(name) and name not in self.enabled:
                    raise TrainerError('Restoration is pending. Retry Reset all before enabling this control.')
                player = self.player()
                if name in {'noclip','hover','bunnyhop','speed_hack'}:
                    for other in {'noclip','hover','bunnyhop','speed_hack'}-{name}:
                        if other in self.enabled:self.set_feature(other,False)
                if name in {'noclip','hover'}:
                    if self.read(player+0x76,'byte') != 0 or self.read(player+0xEC)<=0:
                        raise TrainerError('Start from a living player in a practice level.')
                if name == 'noclip':
                    self.noclip_entry=(player,tuple(self.read(player+off,'float')for off in (4,8,12)))
                    self.flight_position=self.noclip_entry[1]
                    self.flight_time=time.monotonic()
                if name == 'hover':value=self.read(player+12,'float')
                if name in COMBAT | {'automatic','bunnyhop','noclip','speed_hack'} and self.inputs is None:
                    self.inputs = DesktopInput()
                if name in {'fragile_bots','bot_health'}:
                    other='bot_health' if name=='fragile_bots' else 'fragile_bots'
                    if other in self.enabled:self.set_feature(other,False)
                if name == 'auto_refill':
                    for other in ('magazines','reserves'):
                        if other in self.enabled:self.set_feature(other,False)
                if name in {'magazines','reserves'} and 'auto_refill' in self.enabled:
                    self.set_feature('auto_refill',False)
                if name in {'auto_aim', 'headshot'}:
                    for other in {'auto_aim', 'headshot', 'view_lock'} - {name}:
                        if other in self.enabled:
                            self.set_feature(other, False)
                if name in {'headshot', 'auto_shoot', 'triggerbot'}:
                    for other in {'headshot', 'auto_shoot', 'triggerbot'} - {name}:
                        if other in self.enabled:
                            self.set_feature(other, False)
                if name == 'view_lock':
                    for other in ('auto_aim', 'headshot'):
                        if other in self.enabled:
                            self.set_feature(other, False)
                if name == 'view_lock':
                    value = (self.read(player+0x34, 'float'), self.read(player+0x38, 'float'))
                if name in self.enabled:
                    raise TrainerError('Disable the control before changing its value.')
                self.originals[name] = {}
                try:
                    if name in NATIVE:
                        if self.native is None:self.native=NativeFeatures(self.memory)
                        self.native.enable(name)
                    self.enabled[name] = value
                    self.tick()
                except Exception:
                    self.enabled.pop(name, None)
                    if name == 'noclip':self._finish_noclip()
                    if name in NATIVE and self.native:self.native.disable(name)
                    self._restore(name)
                    raise
            else:
                if name in NATIVE and self.native:self.native.disable(name)
                self.enabled.pop(name, None)
                if name == 'noclip':self._finish_noclip()
                if name == 'akimbo' and self.connected and not self.multiplayer() and self.read(self.player()+0xFC)==8:
                    primary=self.read(self.player()+0xF4)
                    self.equip_primary(primary if primary in (2,3,4,5,6) else 6)
                self._restore(name)
                if name in COMBAT | {'automatic'}:
                    self._release_attack()
                if name == 'bunnyhop':self._release_jump()
                if name == 'speed_hack':self._release_speed()
                if name in {'target_lock','auto_aim','headshot'}:self.locked_target=None

    def tick(self):
        with self.lock:
            self.enforce_multiplayer()
            player = self.player()
            if self.noclip_entry and self.noclip_entry[0]!=player:
                self.set_feature('noclip',False)
            state = self.read(player+0x76, 'byte')
            alive = state == 0 and self.read(player+0xEC) > 0
            for name, value in list(self.enabled.items()):
                for address, kind, newvalue, owner in self.edits(name, value, player):
                    if owner is not None and not alive:
                        continue
                    key = (address, kind)
                    saved = self.originals[name]
                    if key not in saved:
                        size = struct.calcsize(FORMATS[kind])
                        saved[key] = (self.memory.read(address, size), owner)
                    self.write(address, kind, newvalue)
            if self.enabled.keys() & BOT_CONTROLS:
                for bot in self.bots():
                    if bot['state'] != 0 or bot['health'] <= 0 or (self.combat_options['team_filter'] and allied(self.read(player+0x30C),bot['team'],self.mode()['teams'])):
                        continue
                    for name in self.enabled.keys() & BOT_CONTROLS:
                        fields = {'freeze_bots':[(0x44,'float',0.)], 'fragile_bots':[(0xEC,'int',1)],
                                  'bot_health':[(0xEC,'int',self.enabled[name])], 'bot_armour':[(0xF0,'int',self.enabled[name])]}[name]
                        for off, kind, newvalue in fields:
                            address = bot['pointer']+off
                            key = (address, kind)
                            if key not in self.originals[name]:
                                self.originals[name][key] = (self.memory.read(address, struct.calcsize(FORMATS[kind])), ('bot', bot['pointer']))
                            self.write(address, kind, newvalue)
            if 'noclip' in self.enabled:self._flight_tick(player,alive)
            if 'speed_hack' in self.enabled and alive and self.inputs.foreground(self.memory.pid):
                self.write(player+0x74,'byte',((int(self.inputs.down(0x57))-int(self.inputs.down(0x53)))*int(self.enabled['speed_hack']))&255)
                self.write(player+0x75,'byte',((int(self.inputs.down(0x41))-int(self.inputs.down(0x44)))*int(self.enabled['speed_hack']))&255)
                self.speed_owner=player
            else:self._release_speed()
            self._combat_tick(player, alive)
            if alive and 'auto_refill' in self.enabled:self._auto_refill(player)
            if 'bunnyhop' in self.enabled and alive and self.inputs.foreground(self.memory.pid) and self.inputs.down(0x20):
                if self.read(player+0x5D,'byte'):
                    self.write(player+0x5F,'byte',1)
                    self.jump_owner=player
            else:self._release_jump()

    def _restore(self, name):
        saved = self.originals.get(name, {})
        if not saved:
            self.originals.pop(name, None)
            return
        player = self.player()
        failed = []
        for (address, kind), (data, owner) in list(saved.items()):
            # Do not write old heap addresses after the root changes.
            if isinstance(owner, tuple) and owner[0] == 'bot':
                live_bots = {bot['pointer'] for bot in self.bots()}
                if owner[1] not in live_bots:
                    del saved[(address, kind)]
                    continue
            elif owner is not None and owner != player:
                del saved[(address, kind)]
                continue
            try:
                self.memory.write(address, data)
                del saved[(address, kind)]
            except Exception as error:
                failed.append(str(error))
        if not saved:
            self.originals.pop(name, None)
        if failed:
            raise TrainerError('Some values could not be restored: ' + failed[0])

    def reset(self):
        with self.lock:
            if self.native:self.native.reset()
            if self.noclip_entry:self._finish_noclip()
            if 'akimbo' in self.originals and not self.multiplayer() and self.read(self.player()+0xFC)==8:
                primary=self.read(self.player()+0xF4)
                self.equip_primary(primary if primary in (2,3,4,5,6) else 6)
            self.enabled.clear()
            self._release_attack()
            self._release_jump()
            self._release_speed()
            self.locked_target=None
            errors = []
            for name in list(self.originals):
                try:
                    self._restore(name)
                except Exception as error:
                    errors.append(str(error))
            if errors:
                raise TrainerError(errors[0])
            self.last_error = ''

    def _finish_noclip(self):
        if self.noclip_entry:
            owner,position=self.noclip_entry
            if not self.multiplayer() and self.player()==owner and self.read(owner+0x76,'byte')==0 and self.read(owner+0xEC)>0:
                self.teleport(position)
                for off in (0x74,0x75,0x5F):self.write(owner+off,'byte',0)
            self.noclip_entry=None
            self.flight_position=self.flight_time=None

    def _flight_tick(self,p,alive):
        now=time.monotonic();dt=min(.05,max(0.,now-(self.flight_time or now)));self.flight_time=now
        if not alive:
            self.set_feature('noclip',False)
            return
        position=self.flight_position
        if self.inputs.foreground(self.memory.pid):
            yaw=math.radians(self.read(p+0x34,'float'));pitch=math.radians(self.read(p+0x38,'float'))
            f=int(self.inputs.down(0x57))-int(self.inputs.down(0x53))
            r=int(self.inputs.down(0x44))-int(self.inputs.down(0x41))
            u=int(self.inputs.down(0x20))-int(self.inputs.down(0x11))
            delta=(f*math.sin(yaw)*math.cos(pitch)+r*math.cos(yaw),-f*math.cos(yaw)*math.cos(pitch)+r*math.sin(yaw),f*math.sin(pitch)+u)
            length=math.sqrt(sum(v*v for v in delta))
            if length:
                speed=self.enabled['noclip']*(2 if self.inputs.down(0x10) else 1)
                candidate=tuple(v+d/length*speed*dt for v,d in zip(position,delta))
                if all(math.isfinite(v) and -4096<=v<=4096 for v in candidate):position=candidate
        self.flight_position=position
        self.teleport(position)
        # Suppress native movement/gravity input; gun state and attack input stay untouched.
        for off in (0x74,0x75,0x5F):self.write(p+off,'byte',0)

    def visual_snapshot(self):
        """Read-only scene data. Occlusion is deliberately ignored for ESP/radar."""
        with self.lock:
            p=self.player()
            scene={'position':tuple(self.read(p+o,'float')for o in (4,8,12)),
                   'yaw':self.read(p+0x34,'float'),'pitch':self.read(p+0x38,'float'),
                   'roll':self.read(p+0x3C,'float'),'fov':self.read(self.memory.base+PROFILE['fov_rva'],'float'),
                   'team':self.read(p+0x30C),'bots':[], 'enabled':dict(self.enabled),'aim_cone':self.combat_options['cone'],'mode':self.mode(),'visuals':dict(self.visual_options)}
            if self.scoped(p):scene['fov']=self.read(self.memory.base+PROFILE['scope_fov_rva'])
            for b in self.actors(include_players=True) if self.enabled.keys() & {'wall_esp','radar','offscreen_arrows'} else []:
                b['allied']=allied(scene['team'],b['team'],scene['mode']['teams'])
                if b['state']==0 and b['health']>0 and b['team'] in (0,1) and ('esp_allies' in self.enabled or not b['allied']):
                    scene['bots'].append(b)
            return scene

    def mode(self):
        return describe(self.read(self.memory.base+PROFILE['gamemode_rva']))

    def configure_visuals(self,**options):
        with self.lock:self.visual_options=validate_visuals(dict(self.visual_options,**options))

    def _release_speed(self):
        if self.speed_owner is not None:
            try:
                if self.memory and self.player()==self.speed_owner:
                    for off in (0x74,0x75):self.write(self.speed_owner+off,'byte',0)
            except Exception:pass
            self.speed_owner=None

    def multiplayer(self):
        value=self.read(self.memory.base+PROFILE['connected_rva'])
        if value not in (0,1):raise TrainerError('Connection state failed validation. Reconnect to the supported game build.')
        return bool(value)

    def enforce_multiplayer(self):
        online=self.multiplayer()
        if online:
            removed=[]
            for name in list(self.enabled):
                if name in OFFLINE_ONLY:
                    self.set_feature(name,False);removed.append(name)
            if self.last_online is not True:
                # Repair only shared weapon data from this fingerprint's original file.
                # Player health/ammo cannot be reconstructed from client memory; respawn instead.
                for i,fields in enumerate(PROFILE['stock_weapon_data']):
                    for offset,value in fields.items():
                        self.write(self.memory.base+PROFILE['weapon_table_rva']+i*104+int(offset),'short',value)
                self.compatibility_status='Multiplayer: stock weapon sizes/timings/damage restored. Respawn once to resync health and ammo.'
            elif removed:
                self.compatibility_status='Multiplayer: offline-only controls stopped. Respawn to resync health and ammo.'
        else:
            self.compatibility_status='Local game: all practice controls available.'
        self.last_online=online

    def visibility_report(self):
        actors=self.actors(include_players=True);mode=self.mode();local=self.read(self.player()+0x30C)
        living=[b for b in actors if b['state']==0 and b['health']>0 and b['team'] in (0,1)]
        eligible=[b for b in living if 'esp_allies' in self.enabled or not allied(local,b['team'],mode['teams'])]
        active=', '.join(name for key,name in [('wall_esp','ESP'),('radar','radar'),('offscreen_arrows','bearings')]if key in self.enabled)or'ESP / radar off'
        suffix=' · Server may override stat edits' if not mode['bots'] else ''
        if self.read(self.player()+0x76,'byte')!=0:suffix+=' · Respawn for first-person ESP alignment'
        return f'{mode["name"]} · {sum(b["type"]==0 for b in actors)} players / {sum(b["type"]==1 for b in actors)} bots · {len(eligible)} eligible · {active}'+suffix

    def disconnect(self, restore=True):
        self.stop_event.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=2)
        with self.lock:
            if restore and self.connected and getattr(self.memory, 'alive', lambda: True)():
                self.reset()
            if self.memory:
                self.memory.close()
            self.memory = None
            self.native=None
            self.connected = False
            self.marker = None
            self.enabled.clear()
            self.originals.clear()
            self.attack_owner=self.jump_owner=self.locked_target=None
            self.speed_owner=None
            self.noclip_entry=None
            self.flight_position=self.flight_time=None
            self.speed_owner=None
            self.last_online=None

    def telemetry(self):
        with self.lock:
            p = self.player()
            gun = self.read(p+0xFC)
            return {
                'pid': self.memory.pid, 'player': p,
                'health': self.read(p+0xEC), 'armour': self.read(p+0xF0), 'gun': PROFILE['weapon_names'][gun],
                'clip': self.read(p+0x128+gun*4), 'reserve': self.read(p+0x104+gun*4),
                'grenades': self.read(p+0x144), 'fov': self.read(self.memory.base+PROFILE['fov_rva'], 'float'),
                'position': tuple(self.read(p+off, 'float') for off in (4, 8, 12)),
                'active': len(self.enabled), 'error': self.last_error,
                'scoped': self.scoped(p), 'scope_fov': self.read(self.memory.base+PROFILE['scope_fov_rva']),
                'combat_status': self.combat_status,
                'visibility_status':self.visibility_report(),
                'multiplayer':self.multiplayer(),'compatibility_status':self.compatibility_status,
            }

    def scoped(self, player=None):
        p = self.player() if player is None else player
        if self.read(p+0xFC) != 5:
            return False
        weapon = self.read(p+0x350, 'uint')
        return bool(self.read(weapon+0x28, 'byte'))

    def weapon_object(self,player,gun):
        weapon=self.read(player+0x33C+gun*4,'uint')
        if not 0x10000<weapon<0x7FFF0000 or self.read(weapon+4)!=gun or self.read(weapon+8,'uint')!=player:
            raise TrainerError('Weapon object failed validation.')
        return weapon

    def _auto_refill(self,p):
        gun=self.read(p+0xFC)
        if gun not in FIREARMS:return
        magazine=self.read(p+0x128+gun*4)
        reserve=self.read(p+0x104+gun*4)
        if magazine>0 or reserve<=0:return
        capacity=self.read(self.memory.base+PROFILE['weapon_table_rva']+gun*104+0x56,'short')
        amount=min(capacity,reserve)
        self.write(p+0x128+gun*4,'int',amount)
        self.write(p+0x104+gun*4,'int',reserve-amount)
        self.write(p+0x14C+gun*4,'int',0)
        self.write(self.weapon_object(p,gun)+0x20,'int',0)

    def _release_jump(self):
        if self.jump_owner is not None and self.memory:
            try:
                if self.player()==self.jump_owner:self.write(self.jump_owner+0x5F,'byte',0)
            except Exception:pass
        self.jump_owner=None

    def bots(self):
        return self.actors(include_players=False)

    def actors(self,include_players=False):
        base = self.memory.base
        array = self.read(base+0x18AC04, 'uint')
        capacity = self.read(base+0x18AC08)
        count = self.read(base+0x18AC0C)
        if not 0 <= count <= capacity <= 128 or (count and not 0x10000 < array < 0x7FFF0000):
            raise TrainerError('Bot vector failed validation.')
        millis = self.read(base+0x17F10C)
        result = []
        local=self.player()
        for index in range(count):
            pointer = self.read(array+index*4, 'uint')
            if pointer==local or not 0x10000 < pointer < 0x7FFF0000:
                continue
            try:
                data = self.memory.read(pointer, 0x404)
                if not base <= struct.unpack_from('<I', data)[0] < base+self.memory.size or data[0x77] not in ((0,1) if include_players else (1,)):
                    continue
                pos = struct.unpack_from('<fff', data, 4)
                head = struct.unpack_from('<fff', data, 0x3F8)
                if not all(math.isfinite(v) and abs(v) <= 4096 for v in pos):
                    continue
                valid_head = all(math.isfinite(v) for v in head) and head[0] >= 0 and math.dist(head, pos) < 4.
                rendered = valid_head and 0 <= millis-struct.unpack_from('<i', data, 0xE4)[0] <= 150
                result.append({'pointer': pointer, 'position': pos, 'head': head, 'head_valid': valid_head, 'rendered': rendered,
                    'name': data[0x205:0x215].split(b'\0')[0].decode('utf-8', errors='replace'), 'eye_height': struct.unpack_from('<f', data, 0x50)[0],
                    'health': struct.unpack_from('<i', data, 0xEC)[0], 'armour':struct.unpack_from('<i',data,0xF0)[0], 'team': struct.unpack_from('<i', data, 0x30C)[0], 'type': data[0x77], 'state': data[0x76]})
            except Exception:
                continue
        return result

    def configure_combat(self, **options):
        with self.lock:
            for key, value in options.items():
                if key == 'activation' and value not in ('alt', 'right_mouse', 'always'):
                    raise TrainerError('Invalid activation mode.')
                if key not in self.combat_options:
                    raise TrainerError('Unknown aim option.')
                ranges = {'cone': (1, 180), 'smoothing': (1, 20), 'max_distance': (1, 500), 'tolerance': (.1, 5)}
                if key in ranges and (not isinstance(value, (int, float)) or not math.isfinite(value) or not ranges[key][0] <= value <= ranges[key][1]):
                    raise TrainerError('Aim option is out of range.')
                self.combat_options[key] = value

    def _release_attack(self):
        if self.attack_owner is not None and self.memory:
            try:
                if self.player() == self.attack_owner:
                    self.write(self.attack_owner+0x204, 'byte', 0)
            except Exception:
                pass
        self.attack_owner = None

    def _combat_tick(self, p, alive):
        active = self.enabled.keys() & (COMBAT | {'automatic'})
        if not active:
            self.combat_status = 'Aim and firing controls off.'
            self._release_attack()
            return
        if not alive or not self.inputs.foreground(self.memory.pid) or self.read(p+0x310) != 0:
            self.combat_status = 'Paused: game unfocused, player inactive, or switching weapons.'
            self._release_attack()
            return
        gun = self.read(p+0xFC)
        if gun not in FIREARMS:
            self.combat_status = 'Select a firearm for aim and auto-shoot.'
            self._release_attack()
            return
        options = self.combat_options
        engaged = options['activation'] == 'always' or self.inputs.down(0x12 if options['activation'] == 'alt' else 0x02)
        fire = 'automatic' in active and self.inputs.down(0x01)
        target = None
        if engaged and active & COMBAT:
            if 'auto_shoot' in active:
                fire = True
            if active & {'auto_aim', 'headshot', 'triggerbot'}:
                source = tuple(self.read(p+off, 'float') for off in (4, 8, 12))
                yaw, pitch = self.read(p+0x34, 'float'), self.read(p+0x38, 'float')
                target = choose_target(self.actors(include_players=True), source, yaw, pitch, self.read(p+0x30C),
                    head='headshot' in active, cone=options['cone'], max_distance=options['max_distance'],
                    team_filter=options['team_filter'] and self.mode()['teams'], rendered_only=options['rendered_only'],
                    preferred=self.locked_target if 'target_lock' in self.enabled else None,nearest='nearest_target' in self.enabled)
                self.locked_target=target['pointer'] if target else None
                if target and active & {'auto_aim', 'headshot'}:
                    desired_yaw, desired_pitch = target['aim_angles']
                    factor = options['smoothing']
                    yaw = (yaw+angle_delta(desired_yaw, yaw)/factor) % 360.
                    pitch = max(-89., min(89., pitch+(desired_pitch-pitch)/factor))
                    self.write(p+0x34, 'float', yaw)
                    self.write(p+0x38, 'float', pitch)
                    error = math.hypot(angle_delta(desired_yaw, yaw), desired_pitch-pitch)
                    if 'headshot' in active and error <= options['tolerance']:
                        fire = True
                if target and 'triggerbot' in active and target['error'] <= options['tolerance']:
                    fire = True
        self.combat_status = ('Target: '+target['name']) if target else ('Hold activation key to engage.' if not engaged else 'No eligible target in aim cone.')
        if 'auto_shoot' in active and engaged:
            self.combat_status = 'Auto shoot active. Release activation key to stop.'
        if fire and self.read(p+0x128+gun*4) > 0:
            self.write(p+0x204, 'byte', 1)
            self.attack_owner = p
        else:
            self._release_attack()

    def equip_primary(self, gun):
        if gun not in (2, 3, 4, 5, 6):
            raise TrainerError('Choose a valid primary firearm.')
        with self.lock:
            if self.multiplayer():raise TrainerError('Offline only: use normal weapon selection in multiplayer.')
            p = self.player()
            if self.read(p+0x76, 'byte') != 0:
                raise TrainerError('Open a live offline practice level first.')
            weapon = self.read(p+0x33C+gun*4, 'uint')
            if self.read(weapon+4) != gun or self.read(weapon+8, 'uint') != p:
                raise TrainerError('Weapon object failed validation.')
            self._release_attack()
            sniper = self.read(p+0x350, 'uint')
            self.write(sniper+0x28, 'byte', 0)
            self.write(p+0x66, 'byte', 0)
            old = self.read(p+0x364, 'uint')
            self.write(p+0x360, 'uint', old)
            for off in (0xF4, 0xF8, 0xFC, 0x314): self.write(p+off, 'int', gun)
            for off in (0x364, 0x368, 0x36C, 0x370): self.write(p+off, 'uint', weapon)
            self.write(p+0x310, 'int', 0)
            self.write(weapon+0x20, 'int', 0)
            cap = self.read(self.memory.base+PROFILE['weapon_table_rva']+gun*104+0x56, 'short')
            self.write(p+0x128+gun*4, 'int', cap)
            self.write(p+0x104+gun*4, 'int', 120)

    def toggle_scope(self):
        with self.lock:
            p = self.player()
            if self.read(p+0xFC) != 5:
                raise TrainerError('Equip the sniper rifle before toggling the scope.')
            weapon = self.read(p+0x350, 'uint')
            value = int(not self.read(weapon+0x28, 'byte'))
            self.write(weapon+0x28, 'byte', value)
            self.write(weapon+0x2C, 'int', 0)
            self.write(p+0x66, 'byte', value)
            return bool(value)

    def face_nearest_bot(self):
        from aiming import angles_to
        with self.lock:
            p = self.player()
            source = tuple(self.read(p+off, 'float') for off in (4, 8, 12))
            team = self.read(p+0x30C)
            candidates = [bot for bot in self.actors(include_players=True) if bot['state'] == 0 and bot['health'] > 0 and (not self.combat_options['team_filter'] or not allied(team,bot['team'],self.mode()['teams']))]
            if not candidates:
                raise TrainerError('No eligible live bots found.')
            bot = min(candidates, key=lambda item: math.dist(source, item['position']))
            yaw, pitch = angles_to(source, bot['position'])
            self.write(p+0x34, 'float', yaw)
            self.write(p+0x38, 'float', pitch)
            return bot['name']

    def level_view(self):
        with self.lock:
            p=self.player()
            self.write(p+0x38,'float',0.)
            self.write(p+0x3C,'float',0.)

    def save_position(self):
        with self.lock:
            p = self.player()
            self.marker = (p, tuple(self.read(p+off, 'float') for off in (4, 8, 12)))
            return self.marker[1]

    def teleport(self, position):
        with self.lock:
            if self.multiplayer():raise TrainerError('Offline only: the server controls permitted movement.')
            p = self.player()
            if self.read(p+0x76, 'byte') != 0 and not (self.noclip_entry and self.noclip_entry[0]==p and self.read(p+0x76,'byte')==4):
                raise TrainerError('Open a live practice level before teleporting.')
            if len(position) != 3 or not all(math.isfinite(v) and -4096 <= v <= 4096 for v in position):
                raise TrainerError('Coordinates must be finite and between -4096 and 4096.')
            x, y, z = map(float, position)
            # Match resetinterp(): newpos is the foot position, o is the eye position.
            eye = self.read(p+0x50, 'float')
            for off, value in zip((4, 8, 12, 0x28, 0x2C, 0x30), (x, y, z, x, y, z-eye)):
                self.write(p+off, 'float', value)
            for off in (0x10, 0x14, 0x18, 0x1C, 0x20, 0x24, 0x78):
                self.write(p+off, 'float', 0.)

    def return_to_marker(self):
        if self.marker is None or self.marker[0] != self.player():
            raise TrainerError('Save a position in this session first.')
        self.teleport(self.marker[1])

    def replenish(self):
        with self.lock:
            if self.multiplayer():raise TrainerError('Offline only: the server owns health and ammunition.')
            p = self.player()
            if self.read(p+0x76, 'byte') != 0:
                raise TrainerError('Open a live practice level first.')
            self.write(p+0xEC, 'int', 100)
            self.write(p+0xF0, 'int', 100)
            for i in FIREARMS:
                cap = self.read(self.memory.base+PROFILE['weapon_table_rva']+i*PROFILE['weapon_stride']+0x56, 'short')
                self.write(p+0x128+i*4, 'int', cap)
                self.write(p+0x104+i*4, 'int', 120)
            self.write(p+0x144, 'int', 3)
