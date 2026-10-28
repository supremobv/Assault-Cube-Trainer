  -- Native patches run only when explicitly enabled, and only offline.
  R.native={};R.nativeAllocations={}
  local function u32(v)return string.pack('<I4',v%0x100000000)end
  local function rel(op,a,b)return string.char(op)..u32(b-a-5)end
  local function hexbytes(s)return (s:gsub('.',function(c)return string.format('%02X ',c:byte())end))end
  local function bytes(a,n)
    local t=assert(readBytes(a,n,true),'Native code read failed')
    return string.char(table.unpack(t))
  end
  local function nativeWrite(a,s)
    assert(autoAssemble(string.format('%X:\ndb %s',a,hexbytes(s))),'Native patch write failed')
    assert(bytes(a,#s)==s,'Native patch verification failed')
  end
  local function paused(fn)
    pause()
    local ok,err=pcall(fn)
    unpause()
    if not ok then error(err)end
  end
  function R.nativePlan(name,cave)
    local b=R.base
    if name=='model_wallhack'then
      local push=assert(getAddressSafe('opengl32.glPushAttrib'),'Open a rendered game level first')
      local pop=assert(getAddressSafe('opengl32.glPopAttrib'),'OpenGL export unavailable')
      local code='\x9c\x60\x68'..u32(0x2100)..'\xb8'..u32(push)..'\xff\xd0'
      code=code..'\x68'..u32(0xB71)..'\xff\x15'..u32(b+0x125290)..'\x6a\x00\xff\x15'..u32(b+0x125240)..'\x61\x9d'
      code=code..rel(0xE8,cave+#code,b+0x67FA0)..'\x9c\x60\xb8'..u32(pop)..'\xff\xd0\x61\x9d\xc3'
      code=code..string.rep('\x90',0x100-#code)..string.pack('<f',-1)
      return code,{{b+0x62C79,'\xf3\x0f\x10\x1d'..u32(b+0x15BC88),'\xf3\x0f\x10\x1d'..u32(cave+0x100)},
                   {b+0x56C7E,rel(0xE8,b+0x56C7E,b+0x67FA0),rel(0xE8,b+0x56C7E,cave)}}
    end
    assert(name=='wall_shots','Unknown native control')
    return string.pack('<f',1),{{b+0x56BA2,'\xf3\x0f\x10\x2d'..u32(b+0x16BA98),'\xf3\x0f\x10\x2d'..u32(cave)},
                              {b+0x56C5E,rel(0xE8,b+0x56C5E,b+0xCCA80),string.rep('\x90',5)}}
  end
  function R.nativeEnable(name)
    assert(not R.online(),'Native controls currently support offline practice only')
    assert(not R.native[name],'Native patch already active')
    local cave=R.nativeAllocations[name]
    if not cave then cave=assert(allocateMemory(4096,nil,0x40),'Native allocation failed');R.nativeAllocations[name]=cave end
    local code,patches=R.nativePlan(name,cave)
    paused(function()
      for _,p in ipairs(patches)do assert(bytes(p[1],#p[2])==p[2],'Native code mismatch; restart the game and close other trainers')end
      nativeWrite(cave,code)
      local applied={}
      local ok,err=pcall(function()
        for _,p in ipairs(patches)do applied[#applied+1]=p;nativeWrite(p[1],p[3])end
      end)
      R.native[name]=applied
      if not ok then
        for i=#applied,1,-1 do nativeWrite(applied[i][1],applied[i][2])end
        R.native[name]=nil;error(err)
      end
    end)
  end
  function R.nativeDisable(name)
    local patches=R.native[name];if not patches then return end
    paused(function()
      for _,p in ipairs(patches)do local s=bytes(p[1],#p[2]);assert(s==p[2]or s==p[3],'Another tool changed the native patch; restart game to recover')end
      for i=#patches,1,-1 do nativeWrite(patches[i][1],patches[i][2])end
    end)
    R.native[name]=nil
  end
  function R.nativeReset()
    local keys={};for key in pairs(R.native)do keys[#keys+1]=key end
    for _,key in ipairs(keys)do R.nativeDisable(key)end
  end
