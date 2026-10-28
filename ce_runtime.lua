-- RangeLab CE runtime. Embedded into each opt-in feature, never a table startup script.
if _G.RangeLabCE and _G.RangeLabCE.version~=10 and _G.RangeLabCE.stopAll then _G.RangeLabCE.stopAll() end
if not _G.RangeLabCE or _G.RangeLabCE.version ~= 10 then
  local R={version=10,enabled={},saved={},options={cone=35,smoothing=4,range=250,tolerance=0.6,team=true,activation='alt'}}
  _G.RangeLabCE=R
  R.labels=@LABELS@
  R.bounds=@LIMITS@
  R.offline=@OFFLINE@
  R.stock=@STOCK@
@NATIVE@
  R.visualOptions=@VDEFAULTS@
  local visualBounds=@VBOUNDS@
  function R.configureVisuals(values)
    for key,value in pairs(values)do
      local default=R.visualOptions[key];assert(default~=nil,'Unknown visual setting')
      local bounds=visualBounds[key]
      if bounds then assert(type(value)=='number'and value==math.floor(value)and value>=bounds[1]and value<=bounds[2],'Invalid visual size')
      elseif type(default)=='boolean'then assert(type(value)=='boolean','Expected true or false')
      elseif key=='crosshair_style'then assert(value=='plus'or value=='dot'or value=='circle','Unknown crosshair style')
      else assert(type(value)=='string'and value:match('^#%x%x%x%x%x%x$'),'Expected #RRGGBB')end
    end
    for key,value in pairs(values)do R.visualOptions[key]=value end
  end
  local firearms={1,2,3,4,5,6,8}
  local combat={auto_aim=true,headshot=true,auto_shoot=true,triggerbot=true}
  local function rd(a,k)
    local v
    if k=='float' then v=readFloat(a)
    elseif k=='short' then v=readSmallInteger(a,true)
    elseif k=='byte' then local b=readBytes(a,1,true);v=b and b[1]
    else v=readInteger(a,k~='uint') end
    assert(v~=nil,'Unreadable game field');return v
  end
  local function wr(a,k,v)
    local ok
    if k=='float' then ok=writeFloat(a,v)
    elseif k=='short' then ok=writeSmallInteger(a,v)
    elseif k=='byte' then ok=writeBytes(a,v)
    else ok=writeInteger(a,v) end
    assert(ok~=false,'Game write failed')
  end
  local sizes={byte=1,short=2,float=4,int=4,uint=4}
  local function vec(p,off)return {rd(p+off,'float'),rd(p+off+4,'float'),rd(p+off+8,'float')}end
  local function dist(a,b)return math.sqrt((a[1]-b[1])^2+(a[2]-b[2])^2+(a[3]-b[3])^2)end
  local function delta(a,b)return (a-b+180)%360-180 end
  local function angles(a,b)
    local x,y,z=b[1]-a[1],b[2]-a[2],b[3]-a[3]
    local flat=math.sqrt(x*x+y*y);if flat<0.000001 then return nil end
    return math.deg(math.atan(x,-y))%360,math.deg(math.atan(z,flat))
  end
  function R.player()
    assert(R.pid==getOpenedProcessID(),'Reattach, then disable/re-enable trainer entries')
    local p=rd(R.base+0x18AC00,'uint')
    assert(p>0x10000 and p<0x7fff0000,'Player is not ready')
    local vt=rd(p,'uint');assert(vt>=R.base and vt<R.base+0x1B9000,'Player layout mismatch')
    local h,g=rd(p+0xEC,'int'),rd(p+0xFC,'int')
    assert(h>=-10000 and h<=10000 and g>=0 and g<9,'Player field mismatch');return p
  end
  function R.guard()
    local pid,base=getOpenedProcessID(),getAddressSafe('ac_client.exe')
    assert(pid~=0 and base,'Attach CE to ac_client.exe first')
    assert(getModuleSize('ac_client.exe')==0x1B9000,'Unsupported module layout')
    local path
    for _,m in ipairs(enumModules())do if m.Name:lower()=='ac_client.exe' then path=m.PathToFile end end
    assert(path and md5file(path):lower()=='@MD5@','Unsupported executable fingerprint')
    if R.pid and R.pid~=pid then
      R.timer.Enabled=false;R.enabled={};R.saved={};R.native={};R.nativeAllocations={};R.attack=nil;R.jump=nil;R.speed=nil;R.locked=nil;R.entry=nil;R.paused=nil;R.lastOnline=nil;R.hideVisuals()
    end
    R.pid,R.base=pid,base
    local p=R.player()
    assert(readString(base+0x16BCC0,23)=='knife','Weapon table mismatch')
    for i=0,8 do local w=rd(p+0x33C+i*4,'uint');assert(rd(w+8,'uint')==p and rd(w+12,'uint')==base+0x16BCC0+i*104,'Weapon references mismatch')end
    return p
  end
  function R.weapon(p,i)
    local w=rd(p+0x33C+i*4,'uint');assert(w>0x10000 and w<0x7fff0000 and rd(w+4,'int')==i and rd(w+8,'uint')==p,'Weapon object mismatch');return w
  end
  function R.online()
    local connected=rd(R.base+0x18ABC8,'int');assert(connected==0 or connected==1,'Connection state mismatch')
    return connected==1
  end
  function R.enforceMultiplayer()
    local online=R.online()
    if online then
      local remove={};for name in pairs(R.enabled)do if R.offline[name]then remove[#remove+1]=name end end
      for _,name in ipairs(remove)do R.turnOff(name)end
      if not R.lastOnline then
        for i,fields in ipairs(R.stock)do for off,value in pairs(fields)do wr(R.base+0x16BCC0+(i-1)*104+off,'short',value)end end
        print('RangeLab multiplayer: restored stock weapon sizes, damage and timings. Respawn once to resync server health/ammo. Offline-only controls are unavailable.')
      end
    end
    R.lastOnline=online
  end
  function R.teamMode()
    local mode=rd(R.base+0x18ABF8,'int')
    return ({[0]=true,[4]=true,[5]=true,[7]=true,[11]=true,[13]=true,[14]=true,[16]=true,[17]=true,[20]=true,[21]=true})[mode]or false
  end
  function R.allied(a,b)return R.teamMode()and(a==0 or a==1)and a==b end
  function R.bots(includePlayers)
    local arr,cap,n=rd(R.base+0x18AC04,'uint'),rd(R.base+0x18AC08,'int'),rd(R.base+0x18AC0C,'int')
    assert(n>=0 and n<=cap and cap<=128 and (n==0 or arr>0x10000 and arr<0x7fff0000),'Entity vector mismatch')
    local now=rd(R.base+0x17F10C,'int');local result={}
    for i=0,n-1 do
      local q=rd(arr+i*4,'uint')
      if q~=R.player()and q>0x10000 and q<0x7fff0000 then
        local ok,b=pcall(function()
          local vt=rd(q,'uint');local kind=rd(q+0x77,'byte')
          if vt<R.base or vt>=R.base+0x1B9000 or not(kind==1 or includePlayers and kind==0)then return nil end
          local pos,head=vec(q,4),vec(q,0x3F8)
          for _,v in ipairs(pos)do if v~=v or math.abs(v)>4096 then return nil end end
          local valid=head[1]>=0 and dist(pos,head)<4
          local age=now-rd(q+0xE4,'int')
          return {p=q,type=kind,pos=pos,head=head,valid=valid,rendered=valid and age>=0 and age<=150,health=rd(q+0xEC,'int'),armour=rd(q+0xF0,'int'),state=rd(q+0x76,'byte'),team=rd(q+0x30C,'int'),eye=rd(q+0x50,'float'),name=readString(q+0x205,20)or'Player'}
        end)
        if ok and b then result[#result+1]=b end
      end
    end
    return result
  end
  function R.releaseAttack()
    if R.attack then pcall(function()if R.player()==R.attack then wr(R.attack+0x204,'byte',0)end end)end;R.attack=nil
  end
  function R.releaseJump()
    if R.jump then pcall(function()if R.player()==R.jump then wr(R.jump+0x5F,'byte',0)end end)end;R.jump=nil
  end
  function R.releaseSpeed()
    if R.speed then pcall(function()if R.player()==R.speed then wr(R.speed+0x74,'byte',0);wr(R.speed+0x75,'byte',0)end end)end;R.speed=nil
  end
  function R.savewrite(name,a,k,v,owner,isbot)
    local key=tostring(a)..':'..k;local saved=R.saved[name]
    if not saved[key]then saved[key]={a=a,k=k,bytes=assert(readBytes(a,sizes[k],true)),owner=owner,bot=isbot}end
    wr(a,k,v)
  end
  function R.restore(name)
    local saved=R.saved[name];if not saved or not next(saved)then R.saved[name]=nil;return end
    local p=R.player();local members={}
    for _,b in ipairs(R.bots())do members[b.p]=true end
    local failed=false
    for key,s in pairs(saved)do
      if s.owner and (s.bot and not members[s.owner] or not s.bot and s.owner~=p)then saved[key]=nil
      else local ok=pcall(function()assert(writeBytes(s.a,s.bytes)~=false,'Restore failed')end);if ok then saved[key]=nil else failed=true end end
    end
    if not next(saved)then R.saved[name]=nil end
    assert(not failed,'Restore incomplete; retry disabling the feature')
  end
  function R.equip(p,i)
    local w=R.weapon(p,i);R.releaseAttack();wr(p+0xFC,'int',i)
    for _,off in ipairs({0x364,0x368,0x36C,0x370})do wr(p+off,'uint',w)end
    wr(p+0xF4,'int',i);wr(p+0xF8,'int',i);wr(p+0x310,'int',0)
  end
  function R.disable(name)
    if R.pid==getOpenedProcessID()then R.nativeDisable(name)end
    R.enabled[name]=nil
    if R.pid~=getOpenedProcessID() or readInteger(R.base+0x18AC00)==nil then R.saved[name]=nil
    else
      if name=='noclip'then R.finishNoclip()end
      if name=='akimbo' and not R.online()and rd(R.player()+0xFC,'int')==8 then local p=R.player();R.equip(p,rd(p+0xF4,'int'))end
      R.restore(name)
    end
    if combat[name]or name=='automatic'then R.releaseAttack()end
    if name=='bunnyhop'then R.releaseJump()end
    if name=='speed_hack'then R.releaseSpeed()end
    if name=='target_lock'or name=='auto_aim'or name=='headshot'then R.locked=nil end
    if R.hideVisuals and not(R.enabled.wall_esp or R.enabled.radar or R.enabled.crosshair or R.enabled.aim_circle or R.enabled.offscreen_arrows or R.enabled.visual_ping)then R.hideVisuals()end
    if not next(R.enabled)then R.timer.Enabled=false;R.paused=nil end
  end
  function R.turnOff(name)
    if not R.enabled[name]then return end
    if getAddressList then
      local record=getAddressList().getMemoryRecordByDescription(R.labels[name])
      if record and record.Active then record.Active=false;if not R.enabled[name]then return end end
    end
    R.disable(name)
  end
  function R.stopAll()
    if R.pid==getOpenedProcessID()then R.nativeReset()end
    local keys={};for key in pairs(R.enabled)do keys[#keys+1]=key end
    for _,key in ipairs(keys)do R.turnOff(key)end
    for key in pairs(R.saved)do R.restore(key)end
    R.releaseAttack();R.releaseJump();R.releaseSpeed();R.locked=nil;R.timer.Enabled=false
    if R.hideVisuals then R.hideVisuals()end
  end
  function R.finishNoclip()
    local entry=R.entry
    if entry and not R.online()and R.player()==entry.p and rd(entry.p+0x76,'byte')==0 and rd(entry.p+0xEC,'int')>0 then
      R.moveTo(entry.p,entry.pos)
    end
    R.entry=nil
  end
  function R.moveTo(p,pos)
    local eye=rd(p+0x50,'float')
    for i=1,3 do wr(p+i*4,'float',pos[i]);wr(p+0x24+i*4,'float',pos[i]-(i==3 and eye or 0))end
    for _,off in ipairs({0x10,0x14,0x18,0x1C,0x20,0x24,0x78})do wr(p+off,'float',0)end
    for _,off in ipairs({0x74,0x75,0x5F})do wr(p+off,'byte',0)end
  end
  function R.flightTick(p,alive,focus)
    local entry=R.entry;local now=getTickCount()
    local dt=math.max(0,math.min(0.05,(now-entry.time)/1000));entry.time=now
    if not alive then R.turnOff('noclip');return end
    if focus then
      local function key(k)return isKeyPressed(k)and 1 or 0 end
      local f,r,u=key(0x57)-key(0x53),key(0x44)-key(0x41),key(0x20)-key(0x11)
      local yaw,pitch=math.rad(rd(p+0x34,'float')),math.rad(rd(p+0x38,'float'))
      local d={f*math.sin(yaw)*math.cos(pitch)+r*math.cos(yaw),-f*math.cos(yaw)*math.cos(pitch)+r*math.sin(yaw),f*math.sin(pitch)+u}
      local length=math.sqrt(d[1]^2+d[2]^2+d[3]^2)
      if length>0 then
        local speed=R.enabled.noclip*(isKeyPressed(0x10)and 2 or 1);local candidate={};local valid=true
        for i=1,3 do candidate[i]=entry.current[i]+d[i]/length*speed*dt;if candidate[i]~=candidate[i]or math.abs(candidate[i])>4096 then valid=false end end
        if valid then entry.current=candidate end
      end
    end
    R.moveTo(p,entry.current)
  end
@VISUALS@
  function R.edits(name,value,p)
    if name=='model_wallhack'or name=='wall_shots'then return {}end
    local result={};local function put(a,k,v,owner)result[#result+1]={a,k,v,owner}end
    local function pl(off,k,v)put(p+off,k,v,p)end
    if name=='health'then pl(0xEC,'int',value)
    elseif name=='armour'then pl(0xF0,'int',value)
    elseif name=='magazines'or name=='reserves'then for _,i in ipairs(firearms)do pl((name=='magazines'and 0x128 or 0x104)+i*4,'int',value)end
    elseif name=='grenades'then pl(0x144,'int',value)
    elseif name=='slow_fall'then pl(0x48,'int',0)
    elseif name=='hover'then pl(12,'float',value);pl(0x30,'float',value-rd(p+0x50,'float'));pl(0x18,'float',0);pl(0x24,'float',0);pl(0x48,'int',0)
    elseif name=='view_lock'then pl(0x34,'float',value[1]);pl(0x38,'float',value[2])
    elseif name=='fov'then put(R.base+0x18A7CC,'float',value)
    elseif name=='scope_fov'then put(R.base+0x18A834,'int',value)
    elseif name=='crouch_hold'then pl(0x63,'byte',1)
    elseif name=='stable_camera'then for _,off in ipairs({0x3C,0x40,0x32C,0x330})do pl(off,'float',0)end
    elseif name=='no_cooldown'then local i=rd(p+0xFC,'int');if i~=0 and i~=7 then pl(0x14C+i*4,'int',0)end
    elseif name=='akimbo'then pl(0x100,'byte',1);put(R.weapon(p,8)+0x2C,'int',rd(R.base+0x17F10C,'int')+30000,p)
    elseif name=='scope_lock'or name=='scope_settle'then
      if rd(p+0xFC,'int')==5 then local w=R.weapon(p,5)
        if name=='scope_lock'then put(w+0x28,'byte',1,p);pl(0x66,'byte',1)
        else put(w+0x2C,'int',rd(R.base+0x17F10C,'int')-181,p)end
      end
    else
      local fields={no_recoil={{0x54,0},{0x58,0},{0x5A,0},{0x5E,0},{0x60,0}},no_spread={{0x52,0}},rapid_fire={{0x48,value}},fast_reload={{0x46,value}},automatic={{0x66,1}},large_mags={{0x56,value}},damage={{0x4A,value}}}
      if fields[name]then for _,i in ipairs(firearms)do if name~='damage'or i~=3 then
        for _,field in ipairs(fields[name])do put(R.base+0x16BCC0+i*104+field[1],name=='automatic'and'byte'or'short',field[2])end
      end end end
    end
    return result
  end
  function R.target(bots,src,yaw,pitch,team,head)
    local best,score
    for _,b in ipairs(bots)do
      if b.state==0 and b.health>0 and (not R.options.team or not R.allied(team,b.team))and b.rendered and(not head or b.valid)then
        local point=head and b.head or {b.pos[1],b.pos[2],b.pos[3]-b.eye*0.45}
        local d=dist(src,point);local y,t=angles(src,point)
        if y and d>=0.5 and d<=R.options.range then
          local err=math.sqrt(delta(y,yaw)^2+(t-pitch)^2)
          if err<=R.options.cone then
            local rank=R.enabled.nearest_target and d or err
            if R.enabled.target_lock and R.locked==b.p then rank=-1 end
            if not score or rank<score then best={p=b.p,yaw=y,pitch=t,error=err};score=rank end
          end
        end
      end
    end
    return best
  end
  function R.tick()
    R.enforceMultiplayer()
    local p=R.player()
    if R.entry and R.entry.p~=p then R.turnOff('noclip')end
    local state=rd(p+0x76,'byte')
    local alive=state==0 and rd(p+0xEC,'int')>0
    local bots
    for name,value in pairs(R.enabled)do
      for _,edit in ipairs(R.edits(name,value,p))do
        if not edit[4]or alive then R.savewrite(name,edit[1],edit[2],edit[3],edit[4])end
      end
    end
    if R.enabled.freeze_bots or R.enabled.fragile_bots or R.enabled.bot_health or R.enabled.bot_armour then
      bots=R.bots();local team=rd(p+0x30C,'int')
      for _,b in ipairs(bots)do if b.state==0 and b.health>0 and(not R.options.team or not R.allied(team,b.team))then
        if R.enabled.freeze_bots then R.savewrite('freeze_bots',b.p+0x44,'float',0,b.p,true)end
        if R.enabled.fragile_bots then R.savewrite('fragile_bots',b.p+0xEC,'int',1,b.p,true)end
        if R.enabled.bot_health then R.savewrite('bot_health',b.p+0xEC,'int',R.enabled.bot_health,b.p,true)end
        if R.enabled.bot_armour then R.savewrite('bot_armour',b.p+0xF0,'int',R.enabled.bot_armour,b.p,true)end
      end end
    end
    local focus=getForegroundProcess()==R.pid
    if R.enabled.noclip then R.flightTick(p,alive,focus)end
    if R.enabled.speed_hack and alive and focus then
      local function key(k)return isKeyPressed(k)and 1 or 0 end
      wr(p+0x74,'byte',((key(0x57)-key(0x53))*R.enabled.speed_hack)%256)
      wr(p+0x75,'byte',((key(0x41)-key(0x44))*R.enabled.speed_hack)%256);R.speed=p
    else R.releaseSpeed()end
    R.updateVisuals(p,focus,bots)
    if R.enabled.bunnyhop and alive and focus and isKeyPressed(0x20)then
      if rd(p+0x5D,'byte')~=0 then wr(p+0x5F,'byte',1);R.jump=p end
    else R.releaseJump()end
    local gun=rd(p+0xFC,'int');local firearm=gun~=0 and gun~=7
    if R.enabled.auto_refill and alive and firearm then
      local ammo=rd(p+0x104+gun*4,'int')
      if ammo>0 and rd(p+0x128+gun*4,'int')<=0 then
        local amount=math.min(ammo,rd(R.base+0x16BCC0+gun*104+0x56,'short'))
        wr(p+0x128+gun*4,'int',amount);wr(p+0x104+gun*4,'int',ammo-amount);wr(p+0x14C+gun*4,'int',0);wr(R.weapon(p,gun)+0x20,'int',0)
      end
    end
    if not alive or not focus or not firearm or rd(p+0x310,'int')~=0 then R.releaseAttack();return end
    local fire=R.enabled.automatic and isKeyPressed(1)
    local engaged=R.options.activation=='always'or isKeyPressed(R.options.activation=='right_mouse'and 2 or 0x12)
    if engaged then
      if R.enabled.auto_shoot then fire=true end
      if R.enabled.auto_aim or R.enabled.headshot or R.enabled.triggerbot then
        local yaw,pitch=rd(p+0x34,'float'),rd(p+0x38,'float')
        local t=R.target(R.bots(true),vec(p,4),yaw,pitch,rd(p+0x30C,'int'),R.enabled.headshot)
        R.locked=t and t.p or nil
        if t and (R.enabled.auto_aim or R.enabled.headshot)then
          yaw=(yaw+delta(t.yaw,yaw)/R.options.smoothing)%360;pitch=math.max(-89,math.min(89,pitch+(t.pitch-pitch)/R.options.smoothing))
          wr(p+0x34,'float',yaw);wr(p+0x38,'float',pitch)
          if R.enabled.headshot and math.sqrt(delta(t.yaw,yaw)^2+(t.pitch-pitch)^2)<=R.options.tolerance then fire=true end
        end
        if t and R.enabled.triggerbot and t.error<=R.options.tolerance then fire=true end
      end
    end
    if fire and rd(p+0x128+gun*4,'int')>0 then wr(p+0x204,'byte',1);R.attack=p else R.releaseAttack()end
  end
  R.timer=createTimer(nil,false);R.timer.Interval=12
  R.timer.OnTimer=function()
    local ok,err=pcall(R.tick)
    if not ok then R.timer.Enabled=false;R.paused=tostring(err);pcall(R.nativeReset);R.releaseAttack();R.releaseJump();R.releaseSpeed();R.hideVisuals();print('RangeLab paused: '..tostring(err)..'. Uncheck controls to restore before retrying.')end
  end
  function R.enable(name,value)
    local p=R.guard();assert(not R.paused,'Disable all trainer controls before retrying after an error')
    R.enforceMultiplayer()
    assert(not(R.online()and R.offline[name]),'Offline only: '..(R.offline[name]or''))
    assert(R.labels[name],'Unknown trainer control')
    local bound=R.bounds[name];if bound then assert(type(value)=='number'and value==value and value>=bound[1]and value<=bound[2],'Preset is outside supported bounds')end
    assert(not R.saved[name]or not next(R.saved[name]),'Restoration pending; disable this feature first')
    if name=='noclip'or name=='hover'or name=='bunnyhop'or name=='speed_hack'then
      for _,other in ipairs({'noclip','hover','bunnyhop','speed_hack'})do if other~=name then R.turnOff(other)end end
    end
    if name=='noclip'or name=='hover'then assert(rd(p+0x76,'byte')==0 and rd(p+0xEC,'int')>0,'Start from a living practice player')end
    if name=='noclip'then R.entry={p=p,pos=vec(p,4),current=vec(p,4),time=getTickCount()}end
    if name=='hover'then value=rd(p+12,'float')end
    if name=='fragile_bots'then R.turnOff('bot_health')end
    if name=='bot_health'then R.turnOff('fragile_bots')end
    if name=='auto_refill'then R.turnOff('magazines');R.turnOff('reserves')end
    if name=='magazines'or name=='reserves'then R.turnOff('auto_refill')end
    if name=='auto_aim'or name=='headshot'then R.turnOff('view_lock');R.turnOff(name=='auto_aim'and'headshot'or'auto_aim')end
    if name=='view_lock'then R.turnOff('auto_aim');R.turnOff('headshot');value={rd(p+0x34,'float'),rd(p+0x38,'float')}end
    if name=='headshot'or name=='auto_shoot'or name=='triggerbot'then
      for _,other in ipairs({'headshot','auto_shoot','triggerbot'})do if other~=name then R.turnOff(other)end end
    end
    R.saved[name]={};R.enabled[name]=value
    if name=='model_wallhack'or name=='wall_shots'then
      local ok,err=pcall(R.nativeEnable,name)
      if not ok then R.enabled[name]=nil;R.saved[name]=nil;error(err)end
    end
    local ok,err=pcall(R.tick)
    if not ok then R.enabled[name]=nil;pcall(R.nativeDisable,name);if name=='noclip'then pcall(R.finishNoclip)end;pcall(R.restore,name);R.hideVisuals();error(err)end
    R.timer.Enabled=true
  end
end
