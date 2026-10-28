"""Run the embedded Lua against mocked CE APIs, with byte-accurate fake memory."""
import unittest
from lupa.lua53 import LuaRuntime
from engine import PROFILE,FEATURE_KEYS
from export_ce_table import runtime_source,trainer_script,visual_preferences_script
from catalog import CONTROLS
from test_engine import Memory


class CERuntimeTests(unittest.TestCase):
    def setUp(self):
        self.memory=Memory();self.p=0x2000000;self.keys={0x12};self.focused=True
        for i,name in enumerate(('knife','pistol','carbine','shotgun','subgun','sniper','assault','grenade','pistol')):
            w=0x2800000+i*0x100;info=self.memory.base+PROFILE['weapon_table_rva']+i*104
            self.memory.write(info,name.encode()+b'\0')
            self.memory.put(self.p+0x33C+i*4,'uint',w)
            self.memory.put(w+4,'int',i);self.memory.put(w+8,'uint',self.p);self.memory.put(w+12,'uint',info)
        self.memory.put(self.p+0x140,'int',20)
        self.lua=LuaRuntime(unpack_returned_tuples=True)
        g=self.lua.globals()
        import struct
        def read(a,kind):
            fmt={'float':'<f','int':'<i','uint':'<I','short':'<h'}[kind]
            return struct.unpack(fmt,self.memory.read(int(a),struct.calcsize(fmt)))[0]
        def write(a,kind,value):self.memory.put(int(a),kind,value);return True
        def write_bytes(a,*args):
            values=[args[0][i] for i in range(1,len(args[0])+1)] if len(args)==1 and not isinstance(args[0],(int,float)) else list(args)
            self.memory.write(int(a),bytes(values));return True
        g.readInteger=lambda a,signed=False:read(a,'int' if signed else 'uint')
        g.readFloat=lambda a:read(a,'float')
        g.readSmallInteger=lambda a,signed=False:read(a,'short')
        g.readBytes=lambda a,n,as_table=True:self.lua.table_from(list(self.memory.read(int(a),int(n))))
        g.readString=lambda a,n:self.memory.read(int(a),int(n)).split(b'\0')[0].decode()
        g.writeInteger=lambda a,v:write(a,'int',v)
        g.writeFloat=lambda a,v:write(a,'float',v)
        g.writeSmallInteger=lambda a,v:write(a,'short',v)
        g.writeBytes=write_bytes
        g.getOpenedProcessID=lambda:self.memory.pid
        g.getAddressSafe=lambda name,local_lookup=False:self.memory.base if name=='ac_client.exe' else name if local_lookup else None
        g.getModuleSize=lambda name:self.memory.size
        g.enumModules=lambda:self.lua.table_from([self.lua.table_from({'Name':'ac_client.exe','PathToFile':'test.exe'})])
        g.md5file=lambda path:PROFILE['md5']
        g.getForegroundProcess=lambda:self.memory.pid if self.focused else 999
        g.isKeyPressed=lambda key:key in self.keys
        self.clock=1000
        g.getTickCount=lambda:self.clock
        g.getWindowProcessID=lambda hwnd:self.memory.pid
        g.readIntegerLocal=lambda a:read(a,'int')
        g.writeIntegerLocal=lambda a,v:write(a,'int',v)
        def local_api(name,*args):
            if name.endswith('GetForegroundWindow'):return 300
            if name.endswith('GetClientRect'):
                write(args[1]+8,'int',800);write(args[1]+12,'int',600)
            if name.endswith('ClientToScreen'):
                write(args[1],'int',100);write(args[1]+4,'int',100)
            return 1
        g.executeCodeLocalEx=local_api
        self.lua.execute('''
          painted=0
          function createForm(visible)
            local f={Handle=1001,Visible=false}
            f.hide=function()f.Visible=false end
            f.show=function()f.Visible=true end
            f.setLayeredAttributes=function(...)end
            return f
          end
          function createPaintBox(form)
            local function draw(...)painted=painted+1 end
            local c={Pen={},Brush={},Font={},line=draw,fillRect=draw,textOut=draw,ellipse=draw}
            local p={Canvas=c,Width=800,Height=600}
            p.repaint=function()if p.OnPaint then p.OnPaint()end end
            return p
          end
          function createMemoryStream()return {Memory=0x6000000,Size=0}end
        ''')
        self.lua.execute('function createTimer(owner,enabled) return {Enabled=false,Interval=0} end')
        self.lua.execute(runtime_source());self.runtime=g.RangeLabCE
        from native_features import plan
        for name in ('model_wallhack','wall_shots'):
            for a,original,_ in plan(name,self.memory.base,0x30000000,0x70001000,0x70002000)[1]:self.memory.write(a,original)
        previous_address=g.getAddressSafe
        g.getAddressSafe=lambda name,local_lookup=False:{'opengl32.glPushAttrib':0x70001000,'opengl32.glPopAttrib':0x70002000}.get(name)or previous_address(name,local_lookup)
        g.allocateMemory=lambda *args:0x30000000 if not self.runtime.nativeAllocations['model_wallhack']else 0x30010000
        g.pause=lambda:None;g.unpause=lambda:None
        def assemble(text):
            address,values=text.split(':\ndb ')
            self.memory.write(int(address,16),bytes.fromhex(values));return True
        g.autoAssemble=assemble

    def test_every_feature_preset_enables_and_disables(self):
        for category,key,title,description,default in CONTROLS:
            with self.subTest(key=key):
                self.memory.put(self.p+0xFC,'int',5 if key in ('scope_lock','scope_settle') else 6)
                self.runtime.enable(key,default if default is not None else 0)
                self.runtime.disable(key)
        self.assertFalse(self.runtime.timer.Enabled)

    def test_health_snapshot_restore_and_reset(self):
        self.runtime.enable('health',700)
        self.assertEqual(int.from_bytes(self.memory.read(self.p+0xEC,4),'little'),700)
        self.runtime.stopAll()
        self.assertEqual(int.from_bytes(self.memory.read(self.p+0xEC,4),'little'),100)

    def test_noclip_returns_to_entry_and_restores_state(self):
        self.runtime.enable('noclip',16)
        self.assertEqual(self.memory.read(self.p+0x76,1),b'\0')
        self.memory.put(self.p+4,'float',50.)
        self.runtime.tick()
        self.runtime.stopAll()
        self.assertEqual(self.memory.read(self.p+0x76,1),b'\0')
        self.assertEqual(self.lua.globals().readFloat(self.p+4),10.)

    def test_flight_moves_without_disabling_auto_shoot(self):
        self.runtime.enable('noclip',16);self.keys={0x57,0x12,0x20};self.clock+=50
        self.runtime.enable('auto_shoot',0)
        self.assertLess(self.lua.globals().readFloat(self.p+8),20.)
        self.assertGreater(self.lua.globals().readFloat(self.p+12),8.)
        self.assertEqual(self.memory.read(self.p+0x76,1),b'\0')
        self.assertEqual(self.memory.read(self.p+0x204,1),b'\1')
        before=self.lua.globals().readFloat(self.p+8)
        self.focused=False;self.clock+=50;self.runtime.tick()
        self.assertEqual(self.lua.globals().readFloat(self.p+8),before)
        self.assertEqual(self.memory.read(self.p+0x204,1),b'\0')
        self.runtime.stopAll()

    def test_visuals_draw_and_hide_on_focus_loss(self):
        self.runtime.enable('radar',75)
        self.assertGreater(self.lua.globals().painted,0)
        self.assertIsNotNone(self.runtime.visual.scene)
        self.focused=False;self.runtime.tick()
        self.assertIsNone(self.runtime.visual.scene)
        self.runtime.stopAll()

    def test_multiplayer_visibility_and_mode_switch(self):
        bot,arr=0x2100000,0x2500000
        self.memory.initialize_player(bot);self.memory.put(bot+0x77,'byte',0)
        self.memory.put(self.p+0x30C,'int',0);self.memory.put(bot+0x30C,'int',0)
        self.memory.put(self.memory.base+0x18AC04,'uint',arr)
        self.memory.put(self.memory.base+0x18AC08,'int',1);self.memory.put(self.memory.base+0x18AC0C,'int',1)
        self.memory.put(arr,'uint',bot)
        self.memory.put(self.memory.base+PROFILE['gamemode_rva'],'int',5)
        self.runtime.enable('wall_esp',250)
        self.assertEqual(len(self.runtime.visual.scene.bots),0)
        self.memory.put(self.memory.base+PROFILE['gamemode_rva'],'int',2);self.runtime.tick()
        self.assertEqual(len(self.runtime.visual.scene.bots),1)
        self.assertFalse(self.runtime.visual.scene.bots[1].allied)
        self.assertEqual(len(self.runtime.bots()),0)
        self.runtime.enable('bot_health',500)
        self.assertEqual(self.lua.globals().readInteger(bot+0xEC),100)
        self.runtime.stopAll()

    def test_multiplayer_blocks_fake_stats_and_restores_weapon_baseline(self):
        self.memory.put(self.memory.base+PROFILE['connected_rva'],'int',1)
        with self.assertRaisesRegex(Exception,'Offline only'):self.runtime.enable('health',999)
        sniper=self.memory.base+PROFILE['weapon_table_rva']+5*104
        self.assertEqual(self.lua.globals().readSmallInteger(sniper+0x48),1500)
        self.assertEqual(self.lua.globals().readSmallInteger(sniper+0x56),5)
        self.assertEqual(self.lua.globals().readInteger(self.p+0xEC),100)
        self.runtime.enable('wall_esp',250);self.runtime.stopAll()

    def test_multiplayer_transition_stops_incompatible_ce_controls(self):
        self.runtime.enable('health',999);self.runtime.enable('rapid_fire',25)
        self.runtime.enable('crosshair',0)
        self.memory.put(self.memory.base+PROFILE['connected_rva'],'int',1)
        self.runtime.tick()
        self.assertIsNone(self.runtime.enabled.health);self.assertIsNone(self.runtime.enabled.rapid_fire)
        self.assertIsNotNone(self.runtime.enabled.crosshair)
        self.assertEqual(self.lua.globals().readInteger(self.p+0xEC),100)
        self.runtime.stopAll()

    def test_visual_customization_is_validated_before_mutation(self):
        settings=self.lua.table_from({'esp_names':False,'crosshair_style':'circle','crosshair_color':'#FF0000'})
        self.runtime.configureVisuals(settings)
        self.assertFalse(self.runtime.visualOptions.esp_names)
        with self.assertRaises(Exception):self.runtime.configureVisuals(self.lua.table_from({'crosshair_width':99,'esp_names':True}))
        self.assertFalse(self.runtime.visualOptions.esp_names)
        self.runtime.enable('crosshair',0);self.assertGreater(self.lua.globals().painted,0)
        self.runtime.stopAll()

    def test_ce_speed_releases_movement_on_focus_loss(self):
        self.keys={0x57,0x44};self.runtime.enable('speed_hack',3)
        self.assertEqual(self.memory.read(self.p+0x74,1),b'\3')
        self.assertEqual(self.memory.read(self.p+0x75,1),b'\xfd')
        self.focused=False;self.runtime.tick()
        self.assertEqual(self.memory.read(self.p+0x74,1),b'\0')
        self.runtime.stopAll()

    def test_visual_preferences_aa_action_has_no_implicit_game_edits(self):
        before=dict(self.memory.data)
        script=visual_preferences_script().replace('crosshair_style = "plus"','crosshair_style = "dot"')
        self.lua.execute(script.split('{$lua}',1)[1].split('{$asm}',1)[0])
        self.assertEqual(self.runtime.visualOptions.crosshair_style,'dot')
        self.assertEqual(before,self.memory.data)

    def test_auto_shoot_releases_on_focus_loss(self):
        self.runtime.enable('auto_shoot',0)
        self.assertEqual(self.memory.read(self.p+0x204,1),b'\1')
        self.focused=False;self.runtime.tick()
        self.assertEqual(self.memory.read(self.p+0x204,1),b'\0')

    def test_wrong_fingerprint_prevents_changes(self):
        self.lua.globals().md5file=lambda path:'wrong'
        with self.assertRaises(Exception):self.runtime.enable('health',700)
        self.assertEqual(int.from_bytes(self.memory.read(self.p+0xEC,4),'little'),100)

    def test_actual_enable_lua_block_runs(self):
        script=trainer_script('health',500)
        block=script.split('{$lua}',1)[1].split('{$asm}',1)[0]
        self.lua.execute(block)
        self.assertEqual(int.from_bytes(self.memory.read(self.p+0xEC,4),'little'),500)
        self.runtime.disable('health')

    def test_refill_and_jump_use_live_fields(self):
        self.memory.put(self.p+0x140,'int',0)
        self.memory.put(self.p+0x11C,'int',35)
        self.runtime.enable('auto_refill',0)
        self.assertEqual(int.from_bytes(self.memory.read(self.p+0x140,4),'little'),20)
        self.assertEqual(int.from_bytes(self.memory.read(self.p+0x11C,4),'little'),15)
        self.memory.put(self.p+0x5D,'byte',1);self.keys={0x20}
        self.runtime.enable('bunnyhop',0)
        self.assertEqual(self.memory.read(self.p+0x5F,1),b'\1')
        self.keys.clear();self.runtime.tick()
        self.assertEqual(self.memory.read(self.p+0x5F,1),b'\0')

    def test_head_aim_script_aligns_and_releases_for_stale_target(self):
        bot,arr=0x2100000,0x2500000
        self.memory.initialize_player(bot)
        self.memory.put(self.memory.base+0x18AC04,'uint',arr)
        self.memory.put(self.memory.base+0x18AC08,'int',1)
        self.memory.put(self.memory.base+0x18AC0C,'int',1)
        self.memory.put(arr,'uint',bot)
        self.memory.put(self.p+0x30C,'int',1)
        self.memory.put(bot+0x77,'byte',1)
        self.memory.put(self.memory.base+0x17F10C,'int',1000)
        self.memory.put(bot+0xE4,'int',995)
        for off,v in zip((4,8,12,0x3F8,0x3FC,0x400),(20.,20.,8.,20.,20.,8.3)):
            self.memory.put(bot+off,'float',v)
        self.runtime.options.cone=180;self.runtime.options.smoothing=1
        self.runtime.enable('headshot',0)
        self.assertEqual(self.memory.read(self.p+0x204,1),b'\1')
        self.memory.put(bot+0xE4,'int',0);self.runtime.tick()
        self.assertEqual(self.memory.read(self.p+0x204,1),b'\0')
