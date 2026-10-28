import unittest
from contextlib import contextmanager
from native_features import NativeFeatures,plan
from test_engine import Memory
from test_combat import Inputs
from engine import Engine

class Backend:
    def __init__(self,m):self.m=m;self.paused_now=False;self.count=0;self.fail_once=None
    def allocate(self):self.count+=1;return 0x30000000+self.count*4096
    def gl_exports(self):return 0x70001000,0x70002000
    @contextmanager
    def paused(self):
        self.paused_now=True
        try:yield
        finally:self.paused_now=False
    def write(self,a,data):
        assert self.paused_now
        if a==self.fail_once:self.fail_once=None;raise OSError('write failure')
        self.m.write(a,data)

class NativeTests(unittest.TestCase):
    def setUp(self):
        self.m=Memory();self.backend=Backend(self.m);self.native=NativeFeatures(self.m,self.backend)
        for name in ('model_wallhack','wall_shots'):
            for a,o,r in plan(name,self.m.base,0x30001000,*self.backend.gl_exports())[1]:self.m.write(a,o)

    def test_both_controls_restore_exact_executable_bytes(self):
        before=dict(self.m.data)
        for name in ('model_wallhack','wall_shots'):self.native.enable(name)
        self.native.reset()
        for a,v in before.items():self.assertEqual(self.m.data[a],v)
        self.assertFalse(self.native.active);self.assertFalse(self.backend.paused_now)

    def test_code_mismatch_refuses_activation(self):
        address=plan('model_wallhack',self.m.base,0)[1][0][0]
        self.m.write(address,b'\xcc')
        with self.assertRaisesRegex(RuntimeError,'mismatch'):self.native.enable('model_wallhack')
        self.assertFalse(self.native.active);self.assertFalse(self.backend.paused_now)

    def test_partial_install_rolls_back_and_resumes(self):
        patches=plan('model_wallhack',self.m.base,0)[1]
        self.backend.fail_once=patches[1][0]
        with self.assertRaises(OSError):self.native.enable('model_wallhack')
        for a,o,r in patches:self.assertEqual(self.m.read(a,len(o)),o)
        self.assertFalse(self.backend.paused_now)

    def test_restore_conflict_is_preserved_for_recovery(self):
        self.native.enable('model_wallhack');a=self.native.active['model_wallhack'][0][0]
        self.m.write(a,b'\xcc')
        with self.assertRaisesRegex(RuntimeError,'another tool'):self.native.disable('model_wallhack')
        self.assertIn('model_wallhack',self.native.active)
        self.assertEqual(self.m.read(a,1),b'\xcc');self.assertFalse(self.backend.paused_now)

    def test_toggle_reuses_allocations(self):
        for _ in range(4):self.native.enable('model_wallhack');self.native.disable('model_wallhack')
        self.assertEqual(self.backend.count,1)

    def test_online_transition_restores_native_patches(self):
        e=Engine(self.m,Inputs());e.native=self.native;e.set_feature('model_wallhack',True)
        self.m.put(self.m.base+0x18ABC8,'int',1);e.tick()
        self.assertNotIn('model_wallhack',e.enabled);self.assertFalse(self.native.active)

    def test_lua_and_python_native_machine_code_are_identical(self):
        from test_ce_runtime import CERuntimeTests
        fixture=CERuntimeTests();fixture.setUp();r=fixture.runtime
        r.guard()
        for name in ('model_wallhack','wall_shots'):
            code,patches=plan(name,self.m.base,0x30001000,*self.backend.gl_exports())
            # Latin-1 preserves arbitrary machine-code bytes across lupa.
            actual=fixture.lua.eval('function(n,a)return (RangeLabCE.nativePlan(n,a):gsub(".",function(c)return string.format("%02x",c:byte())end))end')(name,0x30001000)
            self.assertEqual(actual,code.hex())
            r.enable(name,0);r.disable(name)
            for a,o,v in patches:self.assertEqual(fixture.memory.read(a,len(o)),o)
