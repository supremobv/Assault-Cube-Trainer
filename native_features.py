"""Opt-in, fingerprint-bound x86 patches for local practice.

Executable allocations stay alive until the game exits: a render thread may still
be returning from a restored call site. No DLL, driver, or disk EXE is modified.
"""
import ctypes
from ctypes import wintypes
from contextlib import contextmanager
import struct

KEYS={'model_wallhack','wall_shots'}
U=lambda n:struct.pack('<I',n&0xffffffff)

def relative(op,source,target):return bytes([op])+U(target-source-5)

def plan(name,base,cave,push_attrib=0,pop_attrib=0):
    """Return cave bytes and (address, expected bytes, replacement) patches."""
    if name=='model_wallhack':
        # Main player-only batch flush. Preserve GL depth/enables and CPU state.
        code=bytes.fromhex('9c60')+b'\x68'+U(0x2100)+b'\xb8'+U(push_attrib)+bytes.fromhex('ffd0')
        code+=b'\x68'+U(0xB71)+b'\xff\x15'+U(base+0x125290) # glDisable(GL_DEPTH_TEST)
        code+=bytes.fromhex('6a00ff15')+U(base+0x125240) # glDepthMask(GL_FALSE)
        code+=bytes.fromhex('619d')
        code+=relative(0xE8,cave+len(code),base+0x67FA0) # endmodelbatches(cl=true)
        code+=bytes.fromhex('9c60b8')+U(pop_attrib)+bytes.fromhex('ffd0619dc3')
        # Radius < 0 skips only renderclient's geometry occlusion test.
        return code.ljust(0x100,b'\x90')+struct.pack('<f',-1.),[
            (base+0x62C79,bytes.fromhex('f30f101d')+U(base+0x15BC88),bytes.fromhex('f30f101d')+U(cave+0x100)),
            (base+0x56C7E,relative(0xE8,base+0x56C7E,base+0x67FA0),relative(0xE8,base+0x56C7E,cave))]
    if name=='wall_shots':
        # Inlined readdepth: unproject far plane instead of the wall depth, then
        # leave the ray endpoint unclipped. Does not change damage/ammo/cooldown.
        return struct.pack('<f',1.),[
            (base+0x56BA2,bytes.fromhex('f30f102d')+U(base+0x16BA98),bytes.fromhex('f30f102d')+U(cave)),
            (base+0x56C5E,relative(0xE8,base+0x56C5E,base+0xCCA80),b'\x90'*5)]
    raise ValueError('Unknown native feature')

class WindowsPatchMemory:
    def __init__(self,memory):
        self.memory=memory;self.handle=memory.pm.process_handle
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.nt=ctypes.WinDLL('ntdll')
        self.kernel.VirtualAllocEx.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_size_t,wintypes.DWORD,wintypes.DWORD]
        self.kernel.VirtualAllocEx.restype=ctypes.c_void_p
        self.kernel.VirtualProtectEx.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_size_t,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD)]
        self.kernel.FlushInstructionCache.argtypes=[wintypes.HANDLE,ctypes.c_void_p,ctypes.c_size_t]
        self.nt.NtSuspendProcess.argtypes=[wintypes.HANDLE];self.nt.NtSuspendProcess.restype=ctypes.c_long
        self.nt.NtResumeProcess.argtypes=[wintypes.HANDLE];self.nt.NtResumeProcess.restype=ctypes.c_long

    def allocate(self):
        address=self.kernel.VirtualAllocEx(self.handle,None,4096,0x3000,0x40)
        if not address or address>0xffffffff:raise OSError('Could not allocate x86 patch memory')
        return address

    def gl_exports(self):
        # Read the target's x86 OpenGL module, not Python's 64-bit module.
        import pymem.process,pefile,os
        module=pymem.process.module_from_name(self.handle,'opengl32.dll')
        if not module:raise OSError('Open a rendered game level first')
        path=module.filename
        pe=pefile.PE(path,fast_load=True)
        if pe.FILE_HEADER.Machine!=0x14c:
            pe.close()
            # WOW64 enumeration can return System32's logical DLL path to a
            # 64-bit reader. That file is x64; the target loaded SysWOW64's x86 DLL.
            path=os.path.join(os.environ['SystemRoot'],'SysWOW64','opengl32.dll')
            pe=pefile.PE(path,fast_load=True)
        try:
            if pe.FILE_HEADER.Machine!=0x14c:raise OSError('Expected the target\'s x86 OpenGL module')
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_EXPORT']])
            exports={s.name.decode():module.lpBaseOfDll+s.address for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name and not s.forwarder}
            result=exports['glPushAttrib'],exports['glPopAttrib']
            image=pe.get_memory_mapped_image()
            for address in result:
                rva=address-module.lpBaseOfDll
                if self.memory.read(address,16)!=image[rva:rva+16]:raise OSError('OpenGL export bytes do not match the target module')
            return result
        finally:pe.close()

    @contextmanager
    def paused(self):
        if self.nt.NtSuspendProcess(self.handle)<0:raise OSError('Could not pause the game for a code update')
        try:yield
        finally:
            if self.nt.NtResumeProcess(self.handle)<0:raise OSError('Could not resume game process')

    def write(self,address,data):
        old=wintypes.DWORD()
        if not self.kernel.VirtualProtectEx(self.handle,address,len(data),0x40,ctypes.byref(old)):raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.memory.write(address,data)
            if self.memory.read(address,len(data))!=data:raise OSError('Native write verification failed')
            if not self.kernel.FlushInstructionCache(self.handle,address,len(data)):raise ctypes.WinError(ctypes.get_last_error())
        finally:
            restored=wintypes.DWORD()
            if not self.kernel.VirtualProtectEx(self.handle,address,len(data),old.value,ctypes.byref(restored)):raise ctypes.WinError(ctypes.get_last_error())

class NativeFeatures:
    def __init__(self,memory,backend=None):
        self.memory=memory;self.backend=backend or WindowsPatchMemory(memory)
        self.active={};self.allocations={}

    def enable(self,name):
        if name in self.active:raise RuntimeError('Native control already active')
        if name not in self.allocations:self.allocations[name]=self.backend.allocate()
        cave=self.allocations[name]
        exports=self.backend.gl_exports()if name=='model_wallhack'else(0,0)
        code,patches=plan(name,self.memory.base,cave,*exports)
        with self.backend.paused():
            for address,original,replacement in patches:
                if self.memory.read(address,len(original))!=original:raise RuntimeError('Native code mismatch: close other trainers or restart the game')
            self.backend.write(cave,code)
            applied=[]
            try:
                for patch in patches:
                    # Journal before writing so partial-write failures can restore.
                    applied.append(patch);self.backend.write(patch[0],patch[2])
            except Exception:
                self.active[name]=applied
                for patch in reversed(applied):self.backend.write(patch[0],patch[1])
                self.active.pop(name,None)
                raise
            self.active[name]=patches

    def disable(self,name):
        patches=self.active.get(name)
        if not patches:return
        with self.backend.paused():
            for address,original,replacement in patches:
                current=self.memory.read(address,len(original))
                if current not in (original,replacement):raise RuntimeError('Native patch changed by another tool; restart the game to recover')
            for address,original,replacement in reversed(patches):self.backend.write(address,original)
        self.active.pop(name,None)

    def reset(self):
        for name in list(self.active):self.disable(name)
