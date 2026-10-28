  -- External overlay in CE's own process. No render hooks or remote code execution.
  local function api(name,...)
    local a=getAddressSafe('user32.'..name,true)
    assert(a,'Missing local Windows API: '..name)
    return executeCodeLocalEx(a,...)
  end
  function R.hideVisuals()
    if R.visual then R.visual.form.hide();R.visual.scene=nil end
  end
  function R.project(point,s,w,h)
    local y,p,r=math.rad(s.yaw),math.rad(s.pitch),math.rad(s.roll)
    local x,dy,z=point[1]-s.pos[1],point[2]-s.pos[2],point[3]-s.pos[3]
    local right=x*math.cos(y)+dy*math.sin(y)
    local forward=x*math.sin(y)*math.cos(p)-dy*math.cos(y)*math.cos(p)+z*math.sin(p)
    local up=-x*math.sin(y)*math.sin(p)+dy*math.cos(y)*math.sin(p)+z*math.cos(p)
    if forward<=0.1 or s.fov<=1 or s.fov>=179 then return nil end
    right,up=right*math.cos(r)-up*math.sin(r),right*math.sin(r)+up*math.cos(r)
    local f=w/(2*math.tan(math.rad(s.fov)/2))
    return w/2+right*f/forward,h/2-up*f/forward
  end
  function R.drawVisuals()
    local v=R.visual;if not v or not v.scene then return end
    local s,c,w,h=v.scene,v.paint.Canvas,v.paint.Width,v.paint.Height;local prefs=R.visualOptions
    local function hex(value)return tonumber(value:sub(2,3),16)+tonumber(value:sub(4,5),16)*256+tonumber(value:sub(6,7),16)*65536 end
    c.Brush.Color=0x010101;c.fillRect(0,0,w,h)
    local function round(v)return math.floor(v+0.5)end
    local function line(x,y,a,b)c.line(round(x),round(y),round(a),round(b))end
    local function text(x,y,t)c.textOut(round(x),round(y),t)end
    local function ellipse(x,y,a,b)c.ellipse(round(x),round(y),round(a),round(b))end
    c.Font.Color=hex(prefs.ally_color);c.Font.Size=prefs.esp_text_size;c.Pen.Width=prefs.esp_line_width
    local function color(b)return hex(b.allied and prefs.ally_color or prefs.enemy_color)end
    local function outline(x,y,bw,bh)
      line(x,y,x+bw,y);line(x+bw,y,x+bw,y+bh);line(x+bw,y+bh,x,y+bh);line(x,y+bh,x,y)
    end
    if R.enabled.aim_circle then
      local radius=w/(2*math.tan(math.rad(s.fov)/2))*math.tan(math.rad(math.min(80,R.options.cone)))
      c.Pen.Color=0xC7E274
      -- Use short line segments so the circle leaves its interior transparent.
      for i=0,63 do local a,b=i*math.pi/32,(i+1)*math.pi/32
        line(w/2+radius*math.cos(a),h/2+radius*math.sin(a),w/2+radius*math.cos(b),h/2+radius*math.sin(b))
      end
    end
    if R.enabled.offscreen_arrows then
      local yaw=math.rad(s.yaw)
      for _,b in ipairs(s.bots)do if dist(s.pos,b.pos)<=(R.enabled.wall_esp or 250)then
        local sx,sy=R.project(b.pos,s,w,h)
        if not sx or sx<0 or sx>w or sy<0 or sy>h then
          local x,y=b.pos[1]-s.pos[1],b.pos[2]-s.pos[2]
          local dx,dy=x*math.cos(yaw)+y*math.sin(yaw),-(x*math.sin(yaw)-y*math.cos(yaw))
          if math.abs(dx)+math.abs(dy)>0.01 and w>64 and h>64 then
            local scale=math.min((w/2-24)/math.max(math.abs(dx),0.0001),(h/2-24)/math.max(math.abs(dy),0.0001))
            local px,py=w/2+dx*scale,h/2+dy*scale;local a=math.atan(dy,dx)
            c.Pen.Color=color(b)
            for _,turn in ipairs({-0.65,0.65})do line(px,py,px-12*math.cos(a+turn),py-12*math.sin(a+turn))end
          end
        end
      end end
    end
    if R.enabled.wall_esp then
      for _,b in ipairs(s.bots)do if dist(s.pos,b.pos)<=R.enabled.wall_esp then
        local tx,ty=R.project({b.pos[1],b.pos[2],b.pos[3]+0.8},s,w,h)
        local bx,by=R.project({b.pos[1],b.pos[2],b.pos[3]-b.eye},s,w,h)
        if tx and bx then
          local bh=math.abs(by-ty);local bw=bh*0.42;local x=(tx+bx)/2-bw/2;local y=math.min(ty,by)
          if bh>=2 and bh<h*4 and x+bw>=0 and x<=w and y+bh>=0 and y<=h then
            c.Pen.Color=color(b);c.Font.Color=color(b)
            if prefs.esp_boxes then outline(x,y,bw,bh)end
            local labels={}
            if prefs.esp_names then labels[#labels+1]=b.name or'Player'end
            if prefs.esp_health then
              labels[#labels+1]=b.health..'HP';c.Pen.Color=hex(prefs.ally_color)
              line(x-4,y+bh,x-4,y+bh*(1-math.max(0,math.min(1,b.health/100))))
            end
            if prefs.esp_armour then
              labels[#labels+1]=b.armour..'AR';c.Pen.Color=0xFFB878
              line(x,y+bh+4,x+bw*math.max(0,math.min(1,b.armour/100)),y+bh+4)
            end
            if prefs.esp_distance then labels[#labels+1]=math.floor(dist(s.pos,b.pos))..'u'end
            text(x,math.max(0,y-16),table.concat(labels,' '))
            if R.enabled.esp_tracers then c.Pen.Color=color(b);line(w/2,h-4,x+bw/2,y+bh)end
          end
        end
      end end
    end
    if R.enabled.radar then
      local size=math.min(prefs.radar_size,w-32,h-32);local left,top=w-size-16,16
      c.Brush.Color=0x20170E;c.fillRect(left,top,left+size,top+size);c.Pen.Color=0xC7E274
      outline(left,top,size,size);line(left+size/2,top+24,left+size/2,top+size-8);line(left+8,top+size/2,left+size-8,top+size/2)
      c.Font.Color=0xC7E274;text(left+8,top+4,'BOT RADAR '..R.enabled.radar..'u')
      local a=math.rad(s.yaw);local scale=(size/2-8)/R.enabled.radar
      for _,b in ipairs(s.bots)do
        local dx,dy=b.pos[1]-s.pos[1],b.pos[2]-s.pos[2]
        if math.sqrt(dx*dx+dy*dy)<=R.enabled.radar then
          local x=left+size/2+(dx*math.cos(a)+dy*math.sin(a))*scale
          local y=top+size/2-(dx*math.sin(a)-dy*math.cos(a))*scale
          c.Brush.Color=color(b);c.Pen.Color=color(b);ellipse(x-3,y-3,x+3,y+3)
        end
      end
      c.Pen.Color=0xC7E274;c.Brush.Color=0xC7E274;ellipse(left+size/2-2,top+size/2-2,left+size/2+2,top+size/2+2)
    end
    if R.enabled.crosshair then
      c.Pen.Color=hex(prefs.crosshair_color);c.Pen.Width=prefs.crosshair_width
      local x,y=w/2,h/2;local size,gap=prefs.crosshair_size,math.min(prefs.crosshair_gap,prefs.crosshair_size-1)
      if prefs.crosshair_style=='plus'then
        line(x-size,y,x-gap,y);line(x+gap,y,x+size,y);line(x,y-size,x,y-gap);line(x,y+gap,x,y+size)
      elseif prefs.crosshair_style=='circle'then
        for i=0,63 do local a,b=i*math.pi/32,(i+1)*math.pi/32;line(x+size*math.cos(a),y+size*math.sin(a),x+size*math.cos(b),y+size*math.sin(b))end
      else c.Brush.Color=hex(prefs.crosshair_color);ellipse(x-size/4,y-size/4,x+size/4,y+size/4)end
    end
    if R.enabled.visual_ping then c.Font.Color=hex(prefs.ally_color);text(16,16,'PING DISPLAY: '..R.enabled.visual_ping..' ms (visual only)')end
  end
  function R.updateVisuals(p,focus,bots)
    if not(R.enabled.wall_esp or R.enabled.radar or R.enabled.crosshair or R.enabled.aim_circle or R.enabled.offscreen_arrows or R.enabled.visual_ping)or not focus then R.hideVisuals();return end
    if not R.visual then
      local form=createForm(false);form.Caption='RangeLab CE practice overlay';form.BorderStyle='bsNone';form.Color=0x010101
      form.DoNotSaveInTable=true;form.setLayeredAttributes(0x010101,255,1)
      local paint=createPaintBox(form);paint.Align='alClient';paint.OnPaint=R.drawVisuals
      local stream=createMemoryStream();stream.Size=24
      R.visual={form=form,paint=paint,stream=stream}
      -- WS_EX_TRANSPARENT | WS_EX_NOACTIVATE, in CE's local process only.
      local style=api('GetWindowLongA',form.Handle,-20)
      api('SetWindowLongA',form.Handle,-20,style | 0x20 | 0x08000000)
    end
    local v=R.visual;local hwnd=api('GetForegroundWindow')
    assert(getWindowProcessID(hwnd)==R.pid,'Game window changed')
    local mem=v.stream.Memory
    if api('GetClientRect',hwnd,mem)==0 then R.hideVisuals();return end
    writeIntegerLocal(mem+16,0);writeIntegerLocal(mem+20,0)
    if api('ClientToScreen',hwnd,mem+16)==0 then R.hideVisuals();return end
    local w,h=readIntegerLocal(mem+8),readIntegerLocal(mem+12)
    if w<=0 or h<=0 then R.hideVisuals();return end
    if not v.form.Visible then
      v.form.show()
      -- Keep LCL's visibility state in sync; undo focus only if show activated this form.
      if api('GetForegroundWindow')==v.form.Handle then api('SetForegroundWindow',hwnd)end
    end
    -- Actual HWND placement uses physical client coordinates and never takes focus.
    api('SetWindowPos',v.form.Handle,-1,readIntegerLocal(mem+16),readIntegerLocal(mem+20),w,h,0x0010|0x0040)
    local s={pos=vec(p,4),yaw=rd(p+0x34,'float'),pitch=rd(p+0x38,'float'),roll=rd(p+0x3C,'float'),fov=rd(R.base+0x18A7CC,'float'),team=rd(p+0x30C,'int'),bots={}}
    if rd(p+0xFC,'int')==5 and rd(R.weapon(p,5)+0x28,'byte')~=0 then s.fov=rd(R.base+0x18A834,'int')end
    for _,b in ipairs(R.bots(true))do
      b.allied=R.allied(s.team,b.team)
      if b.state==0 and b.health>0 and(b.team==0 or b.team==1)and(R.enabled.esp_allies or not b.allied)then s.bots[#s.bots+1]=b end
    end
    v.scene=s;v.paint.repaint()
  end
