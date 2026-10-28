"""Click-through Qt overlay; all game access is read-only."""
import ctypes
from ctypes import wintypes
import math
from PySide6.QtCore import Qt,QTimer,QRectF
from PySide6.QtGui import QColor,QPainter,QPen,QFont
from PySide6.QtWidgets import QWidget
from vision import bot_box,radar_point,bearing_marker,cone_radius


class GameWindow:
    def __init__(self):
        self.user=ctypes.WinDLL('user32',use_last_error=True)
        self.user.GetForegroundWindow.restype=wintypes.HWND
        self.user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
        self.user.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        self.user.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
        self.user.IsIconic.argtypes=[wintypes.HWND]

    def rectangle(self,pid):
        hwnd=self.user.GetForegroundWindow();owner=wintypes.DWORD()
        self.user.GetWindowThreadProcessId(hwnd,ctypes.byref(owner))
        if owner.value!=pid or self.user.IsIconic(hwnd):return None
        rect=wintypes.RECT();point=wintypes.POINT(0,0)
        if not self.user.GetClientRect(hwnd,ctypes.byref(rect)) or not self.user.ClientToScreen(hwnd,ctypes.byref(point)):return None
        if rect.right<=0 or rect.bottom<=0:return None
        return point.x,point.y,rect.right,rect.bottom


class PracticeOverlay(QWidget):
    def __init__(self,engine,window_source=None,parent=None):
        super().__init__(parent,Qt.WindowType.Tool|Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.WindowTransparentForInput|Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setWindowTitle('RangeLab — practice overlay')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.engine=engine;self.source=window_source;self.scene=None
        self.last_error=''
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(33)

    def refresh(self):
        if not self.engine.connected or self.engine.last_error or not self.engine.enabled.keys() & {'wall_esp','radar','crosshair','aim_circle','offscreen_arrows','visual_ping'}:
            self.scene=None;self.hide();return
        try:
            if self.source is None:self.source=GameWindow()
            rect=self.source.rectangle(self.engine.memory.pid)
            if rect is None:self.hide();return
            self.scene=self.engine.visual_snapshot()
            self.last_error=''
            scale=self.devicePixelRatioF()
            self.setGeometry(*(round(v/scale)for v in rect));self.show();self.update()
        except Exception as error:
            self.last_error=str(error)
            self.scene=None;self.hide()

    def paintEvent(self,event):
        if not self.scene:return
        c=QPainter(self);c.setRenderHint(QPainter.RenderHint.Antialiasing)
        s=self.scene;enabled=s['enabled'];v=s['visuals'];w,h=self.width(),self.height()
        c.setFont(QFont('Segoe UI',v['esp_text_size']))
        mint=QColor(v['ally_color']);orange=QColor(v['enemy_color'])
        if 'aim_circle' in enabled:
            radius=cone_radius(s['aim_cone'],s['fov'],w)
            c.setPen(QPen(QColor(116,226,199,150),1));c.setBrush(Qt.BrushStyle.NoBrush)
            c.drawEllipse(QRectF(w/2-radius,h/2-radius,radius*2,radius*2))
        if 'offscreen_arrows' in enabled:
            for b in s['bots']:
                if math.dist(s['position'],b['position'])>enabled.get('wall_esp',250):continue
                marker=bearing_marker(b,s,w,h)
                if marker:
                    x,y,a=marker;c.setPen(QPen(mint if b.get('allied',False) else orange,2))
                    for turn in (-.65,.65):c.drawLine(round(x),round(y),round(x-12*math.cos(a+turn)),round(y-12*math.sin(a+turn)))
        if 'wall_esp' in enabled:
            for b in s['bots']:
                distance=math.dist(s['position'],b['position'])
                if distance>enabled['wall_esp']:continue
                box=bot_box(b,s,w,h)
                if box:
                    x,y,bw,bh=box;color=mint if b.get('allied',False) else orange
                    c.setPen(QPen(color,v['esp_line_width']));c.setBrush(Qt.BrushStyle.NoBrush)
                    if v['esp_boxes']:c.drawRect(QRectF(x,y,bw,bh))
                    labels=[]
                    if v['esp_names']:labels.append(b['name'][:20])
                    if v['esp_health']:
                        c.fillRect(QRectF(x-5,y,3,bh),QColor('#20303a'))
                        hp=max(0,min(1,b['health']/100));c.fillRect(QRectF(x-5,y+bh*(1-hp),3,bh*hp),mint)
                        labels.append(f'{b["health"]} HP')
                    if v['esp_armour']:
                        ap=max(0,min(1,b['armour']/100));c.fillRect(QRectF(x,y+bh+4,bw*ap,3),QColor('#78b8ff'))
                        labels.append(f'{b["armour"]} AR')
                    if v['esp_distance']:labels.append(f'{distance:.0f}u')
                    c.drawText(round(x),max(12,round(y-5)),' · '.join(labels))
                    if 'esp_tracers' in enabled:c.drawLine(w//2,h-4,round(x+bw/2),round(y+bh))
        if 'radar' in enabled:
            size=min(v['radar_size'],w-32,h-32);left=w-size-16;top=16
            c.fillRect(QRectF(left,top,size,size),QColor(14,23,32,220));c.setPen(QPen(mint,1))
            c.drawRect(QRectF(left,top,size,size));c.drawLine(left+size//2,top+24,left+size//2,top+size-8)
            c.drawLine(left+8,top+size//2,left+size-8,top+size//2)
            c.drawText(left+8,top+16,f'BOT RADAR · {enabled["radar"]}u')
            for b in s['bots']:
                dot=radar_point(b['position'],s['position'],s['yaw'],enabled['radar'],size)
                if dot:
                    c.setBrush(mint if b.get('allied',False) else orange);c.drawEllipse(QRectF(left+dot[0]-3,top+dot[1]-3,6,6))
            c.setBrush(mint);c.drawEllipse(QRectF(left+size/2-2,top+size/2-2,4,4))
        if 'crosshair' in enabled:
            color=QColor(v['crosshair_color']);c.setPen(QPen(color,v['crosshair_width']));c.setBrush(Qt.BrushStyle.NoBrush)
            x,y=w//2,h//2;size,gap=v['crosshair_size'],min(v['crosshair_gap'],v['crosshair_size']-1)
            if v['crosshair_style']=='plus':
                for a,b,d,e in ((x-size,y,x-gap,y),(x+gap,y,x+size,y),(x,y-size,x,y-gap),(x,y+gap,x,y+size)):c.drawLine(a,b,d,e)
            elif v['crosshair_style']=='circle':c.drawEllipse(QRectF(x-size,y-size,size*2,size*2))
            else:
                c.setBrush(color);c.drawEllipse(QRectF(x-size/4,y-size/4,size/2,size/2))
        if 'visual_ping' in enabled:
            c.setPen(mint);c.drawText(16,24,f'PING DISPLAY: {enabled["visual_ping"]} ms (visual only)')
        c.end()
