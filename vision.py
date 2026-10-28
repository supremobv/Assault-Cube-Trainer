"""Read-only visual geometry shared by previews and the external overlay."""
import math


def project(point, origin, yaw, pitch, roll, fov, width, height):
    values=(*point,*origin,yaw,pitch,roll,fov,width,height)
    if not all(math.isfinite(v) for v in values) or not 1<fov<179 or width<=0 or height<=0:
        return None
    y,p,r=map(math.radians,(yaw,pitch,roll))
    d=tuple(a-b for a,b in zip(point,origin))
    right=d[0]*math.cos(y)+d[1]*math.sin(y)
    forward=d[0]*math.sin(y)*math.cos(p)-d[1]*math.cos(y)*math.cos(p)+d[2]*math.sin(p)
    up=-d[0]*math.sin(y)*math.sin(p)+d[1]*math.cos(y)*math.sin(p)+d[2]*math.cos(p)
    if forward<=.1:return None
    right,up=right*math.cos(r)-up*math.sin(r),right*math.sin(r)+up*math.cos(r)
    focal=width/(2*math.tan(math.radians(fov)/2))
    return width/2+right*focal/forward,height/2-up*focal/forward


def bot_box(bot, scene, width, height):
    # Use the body origin, never a rendered head tag that can be stale behind walls.
    x,y,z=bot['position'];eye=bot['eye_height']
    args=(scene['position'],scene['yaw'],scene['pitch'],scene['roll'],scene['fov'],width,height)
    top=project((x,y,z+.8),*args);bottom=project((x,y,z-eye),*args)
    if top is None or bottom is None:return None
    h=abs(bottom[1]-top[1]);w=h*.42
    if h<2 or h>height*4:return None
    cx=(top[0]+bottom[0])/2;left=cx-w/2;upper=min(top[1],bottom[1])
    if left+w<0 or left>width or upper+h<0 or upper>height:return None
    return left,upper,w,h


def radar_point(position, origin, yaw, radius, size=180):
    if radius<=0:return None
    x,y=position[0]-origin[0],position[1]-origin[1]
    if math.hypot(x,y)>radius:return None
    a=math.radians(yaw);scale=(size/2-8)/radius
    return size/2+(x*math.cos(a)+y*math.sin(a))*scale,size/2-(x*math.sin(a)-y*math.cos(a))*scale


def bearing_marker(bot,scene,width,height):
    if bot_box(bot,scene,width,height) is not None:return None
    x,y=bot['position'][0]-scene['position'][0],bot['position'][1]-scene['position'][1]
    a=math.radians(scene['yaw']);dx=x*math.cos(a)+y*math.sin(a);dy=-(x*math.sin(a)-y*math.cos(a))
    if abs(dx)+abs(dy)<.01 or width<64 or height<64:return None
    scale=min((width/2-24)/max(abs(dx),.0001),(height/2-24)/max(abs(dy),.0001))
    return width/2+dx*scale,height/2+dy*scale,math.atan2(dy,dx)


def cone_radius(cone,fov,width):
    return width/(2*math.tan(math.radians(fov)/2))*math.tan(math.radians(min(80,cone)))
