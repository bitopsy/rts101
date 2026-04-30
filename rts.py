"""
TOTAL RECURSION — v3
New in v3:
  - Fullscreen mode
  - Commander can move (right-click to move commander)
  - Click to select any unit/building
  - Build range limit (structures must be within commander range)
  - Unit production range limit (factory must be within commander range)
  - Tab selects your commander
  - Click minimap to jump to location
  - Smarter AI with verbose thought panel
  - Air, Naval, Defence units
"""
import pygame, math, random, sys, array, collections
from typing import Optional, List, Dict
from enum import Enum, auto

# ── display (resolved after pygame.init) ─────────────────────────────────────
pygame.init()
info = pygame.display.Info()
SCREEN_W = info.current_w
SCREEN_H = info.current_h
MAP_W, MAP_H = 4800, 4800
TILE = 32
FPS  = 60
UI_H = 200
MINIMAP_W = 220
MINIMAP_H = 220
BUILD_RANGE     = 700   # max distance from commander to place a structure
PRODUCE_RANGE   = 700   # max distance from commander to produce units

# ── Palette ───────────────────────────────────────────────────────────────────
C_BG          = (10, 14, 20)
C_GRID        = (20, 28, 36)
C_TERRAIN     = (30, 46, 34)
C_TERRAIN2    = (24, 38, 28)
C_TERRAIN3    = (36, 54, 40)
C_WATER       = (8, 20, 42)
C_WATER2      = (12, 28, 52)
C_MOUNTAIN    = (52, 50, 48)
C_MOUNTAIN2   = (68, 64, 60)
C_METAL_D     = (85, 108, 98)
C_P1          = (50, 150, 230)
C_P1_DARK     = (15, 65, 130)
C_P1_GLOW     = (100, 180, 255)
C_P2          = (230, 70, 50)
C_P2_DARK     = (130, 25, 15)
C_P2_GLOW     = (255, 120, 100)
C_SEL         = (80, 220, 100)
C_HEALTH_G    = (50, 210, 50)
C_HEALTH_Y    = (210, 195, 30)
C_HEALTH_R    = (210, 50, 30)
C_ENERGY      = (230, 195, 30)
C_METAL       = (150, 210, 190)
C_TEXT        = (195, 210, 205)
C_TEXT_DIM    = (90, 105, 100)
C_UI_BG       = (8, 12, 18)
C_UI_PANEL    = (16, 22, 30)
C_UI_BORDER   = (35, 55, 50)
C_UI_HI       = (45, 80, 70)
C_BULLET      = (255, 235, 90)
C_EXPLOSION   = [(255,220,60),(255,140,20),(200,60,10),(120,30,5)]
C_LASER       = (60, 210, 255)
C_LASER2      = (150, 240, 255)
C_SHELL       = (255, 170, 50)
C_MISSILE     = (220, 180, 60)
C_SMOKE       = (75, 85, 95)
C_NOTIFY_GOOD = (60, 220, 100)
C_NOTIFY_BAD  = (220, 60, 60)
C_NOTIFY_INFO = (180, 200, 220)
C_WATER_SHIP  = (40, 90, 130)
C_BUILD_RANGE = (100, 180, 255, 30)
C_AI_THINK_BG = (8, 14, 10)
C_AI_THINK_BD = (30, 60, 40)
C_AI_THINK_TX = (80, 200, 100)
C_AI_THINK_DIM= (50, 110, 60)

# ── Enums ─────────────────────────────────────────────────────────────────────
class Difficulty(Enum):
    EASY   = "Easy"
    MEDIUM = "Medium"
    HARD   = "Hard"

DIFF = {
    Difficulty.EASY:   dict(eco=0.7,  biv=120, ar=(25,45), w0=4,  wm=10, ag=0.4, rh=0.25, bo=0),
    Difficulty.MEDIUM: dict(eco=1.0,  biv=80,  ar=(12,25), w0=6,  wm=20, ag=0.65,rh=0.15, bo=150),
    Difficulty.HARD:   dict(eco=1.5,  biv=45,  ar=(6,14),  w0=10, wm=35, ag=0.95,rh=0.08, bo=400),
}

class Team(Enum):
    PLAYER = 1
    AI     = 2

class Domain(Enum):
    GROUND = auto()
    AIR    = auto()
    NAVAL  = auto()

class UState(Enum):
    IDLE       = auto()
    MOVING     = auto()
    ATTACKING  = auto()
    RETREATING = auto()
    PATROLLING = auto()

class BT(Enum):
    COMMANDER   = auto()
    SOLAR       = auto()
    METAL_X     = auto()
    FACTORY     = auto()
    TURRET      = auto()
    LAB         = auto()
    AIRPAD      = auto()
    SHIPYARD    = auto()
    SHIELD_GEN  = auto()
    AA_GUN      = auto()
    COASTAL_BAT = auto()

class UT(Enum):
    SCOUT      = auto()
    SOLDIER    = auto()
    TANK       = auto()
    ARTILLERY  = auto()
    RAIDER     = auto()
    FIGHTER    = auto()
    BOMBER     = auto()
    GUNBOAT    = auto()
    CARRIER    = auto()

BSPECS: Dict[BT, dict] = {
    BT.COMMANDER:  dict(name="Commander",    hp=1500, size=2, mc=0,   ec=0,    bt=0,   mg=2,  eg=15,  cb=True,  wpn=dict(r=150,d=22,cd=50,p="laser"),  dom=Domain.GROUND, movable=True),
    BT.SOLAR:      dict(name="Solar Coll",   hp=400,  size=2, mc=50,  ec=0,    bt=200, mg=0,  eg=20,  cb=False, wpn=None,                               dom=Domain.GROUND),
    BT.METAL_X:    dict(name="Metal Extr",   hp=500,  size=2, mc=60,  ec=0,    bt=240, mg=3,  eg=-1,  cb=False, wpn=None,                               dom=Domain.GROUND),
    BT.FACTORY:    dict(name="Factory",      hp=1200, size=3, mc=200, ec=500,  bt=600, mg=0,  eg=-5,  cb=False, wpn=None,                               dom=Domain.GROUND, produces=[UT.SCOUT,UT.SOLDIER,UT.TANK,UT.ARTILLERY,UT.RAIDER]),
    BT.TURRET:     dict(name="Laser Turret", hp=600,  size=2, mc=80,  ec=100,  bt=300, mg=0,  eg=-3,  cb=False, wpn=dict(r=230,d=20,cd=38,p="laser"),  dom=Domain.GROUND),
    BT.LAB:        dict(name="Adv. Lab",     hp=1000, size=3, mc=400, ec=1000, bt=900, mg=0,  eg=-10, cb=False, wpn=None,                               dom=Domain.GROUND, produces=[UT.TANK,UT.ARTILLERY,UT.RAIDER]),
    BT.AIRPAD:     dict(name="Air Pad",      hp=800,  size=3, mc=250, ec=600,  bt=700, mg=0,  eg=-8,  cb=False, wpn=None,                               dom=Domain.GROUND, produces=[UT.FIGHTER,UT.BOMBER]),
    BT.SHIPYARD:   dict(name="Shipyard",     hp=900,  size=3, mc=300, ec=700,  bt=750, mg=0,  eg=-6,  cb=False, wpn=None,                               dom=Domain.NAVAL,  produces=[UT.GUNBOAT,UT.CARRIER]),
    BT.SHIELD_GEN: dict(name="Shield Gen",   hp=700,  size=2, mc=150, ec=300,  bt=400, mg=0,  eg=-8,  cb=False, wpn=None,                               dom=Domain.GROUND),
    BT.AA_GUN:     dict(name="AA Gun",       hp=500,  size=2, mc=100, ec=150,  bt=350, mg=0,  eg=-4,  cb=False, wpn=dict(r=270,d=32,cd=32,p="missile"),dom=Domain.GROUND, aa=True),
    BT.COASTAL_BAT:dict(name="Coastal Batt", hp=800,  size=3, mc=350, ec=800,  bt=800, mg=0,  eg=-12, cb=False, wpn=dict(r=520,d=110,cd=180,p="shell"),dom=Domain.GROUND),
}

USPECS: Dict[UT, dict] = {
    UT.SCOUT:    dict(name="Scout",    hp=80,  spd=2.8, mc=40,  ec=100,  bt=150,  sight=220, dom=Domain.GROUND, wpn=dict(r=120,d=8, cd=28,p="bullet"), sz=10),
    UT.SOLDIER:  dict(name="Soldier",  hp=180, spd=1.8, mc=80,  ec=200,  bt=250,  sight=180, dom=Domain.GROUND, wpn=dict(r=140,d=15,cd=38,p="bullet"), sz=12),
    UT.TANK:     dict(name="Tank",     hp=500, spd=1.4, mc=180, ec=400,  bt=500,  sight=200, dom=Domain.GROUND, wpn=dict(r=170,d=42,cd=58,p="shell"),  sz=16),
    UT.ARTILLERY:dict(name="Artillery",hp=240, spd=1.0, mc=220, ec=600,  bt=600,  sight=360, dom=Domain.GROUND, wpn=dict(r=400,d=90,cd=115,p="shell"), sz=15),
    UT.RAIDER:   dict(name="Raider",   hp=320, spd=2.2, mc=150, ec=350,  bt=400,  sight=240, dom=Domain.GROUND, wpn=dict(r=155,d=32,cd=48,p="laser"),  sz=13),
    UT.FIGHTER:  dict(name="Fighter",  hp=160, spd=3.8, mc=200, ec=500,  bt=500,  sight=300, dom=Domain.AIR,    wpn=dict(r=160,d=25,cd=30,p="bullet"), sz=11),
    UT.BOMBER:   dict(name="Bomber",   hp=280, spd=2.2, mc=350, ec=800,  bt=800,  sight=280, dom=Domain.AIR,    wpn=dict(r=120,d=90,cd=120,p="bomb"),  sz=14),
    UT.GUNBOAT:  dict(name="Gunboat",  hp=400, spd=1.2, mc=180, ec=400,  bt=600,  sight=250, dom=Domain.NAVAL,  wpn=dict(r=220,d=50,cd=70,p="shell"),  sz=16),
    UT.CARRIER:  dict(name="Carrier",  hp=1200,spd=0.7, mc=500, ec=1200, bt=1200, sight=300, dom=Domain.NAVAL,  wpn=dict(r=180,d=30,cd=50,p="missile"),sz=22),
}

BUILD_FROM_CMD = [BT.SOLAR, BT.METAL_X, BT.FACTORY, BT.TURRET, BT.LAB,
                  BT.AIRPAD, BT.SHIPYARD, BT.SHIELD_GEN, BT.AA_GUN, BT.COASTAL_BAT]

# ── Helpers ───────────────────────────────────────────────────────────────────
def dist(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])
def lerp_c(c1, c2, t):
    t=max(0.,min(1.,t)); return tuple(int(c1[i]+t*(c2[i]-c1[i])) for i in range(3))
def tc(team, dark=False, glow=False):
    if team==Team.PLAYER: return C_P1_GLOW if glow else (C_P1_DARK if dark else C_P1)
    return C_P2_GLOW if glow else (C_P2_DARK if dark else C_P2)
def gfx_glow(surf, color, pos, r, a=60):
    if r<2: return
    s=pygame.Surface((r*4+2,r*4+2),pygame.SRCALPHA)
    for ri in range(r,0,-3): pygame.draw.circle(s,(*color,int(a*ri/r)),(r*2+1,r*2+1),ri)
    surf.blit(s,(pos[0]-r*2-1,pos[1]-r*2-1))
def rrect(surf,color,rect,rad=4,bw=0,bc=None):
    pygame.draw.rect(surf,color,rect,border_radius=rad)
    if bw and bc: pygame.draw.rect(surf,bc,rect,bw,border_radius=rad)

# ── Sound ─────────────────────────────────────────────────────────────────────
class Sound:
    def __init__(self):
        try: pygame.mixer.pre_init(44100,-16,1,512); pygame.mixer.init(); self.ok=True
        except: self.ok=False
        self.vol=0.3; self._s={}; self._cd={}
        if self.ok: self._gen()
    def _w(self,s): return pygame.mixer.Sound(buffer=array.array('h',[max(-32767,min(32767,int(v))) for v in s]))
    def _sine(self,f,d,v=0.4,dc=6):
        n=int(44100*d); return [v*32767*math.sin(2*math.pi*f*i/44100)*math.exp(-i/n*dc) for i in range(n)]
    def _noise(self,d,v=0.5,dc=8):
        n=int(44100*d); return [v*32767*random.uniform(-1,1)*math.exp(-i/n*dc) for i in range(n)]
    def _gen(self):
        try:
            s=[]; n=int(44100*0.12)
            for i in range(n):
                t=i/44100; f=1200-600*t/0.12
                s.append(0.22*32767*math.sin(2*math.pi*f*t)*math.exp(-t*12))
            self._s['laser']=self._w(s)
            s=self._noise(0.06,0.18,15)
            for i in range(len(s)): t=i/44100; s[i]+=0.12*32767*math.sin(2*math.pi*280*t)*math.exp(-t*22)
            self._s['bullet']=self._w(s)
            s=self._noise(0.18,0.32,6)
            for i in range(len(s)): t=i/44100; s[i]+=0.22*32767*math.sin(2*math.pi*75*t)*math.exp(-t*4)
            self._s['shell']=self._w(s)
            s=[];ms=[]
            for i in range(int(44100*0.15)):
                t=i/44100; f=800+400*t/0.15; ms.append(0.18*32767*math.sin(2*math.pi*f*t)*math.exp(-t*5))
            ms+=self._noise(0.1,0.3,10); self._s['missile']=self._w(ms)
            s=self._noise(0.5,0.6,4)
            for i in range(len(s)): t=i/44100; s[i]+=0.4*32767*math.sin(2*math.pi*40*t)*math.exp(-t*3)
            self._s['bomb']=self._w(s)
            s=self._noise(0.35,0.45,5)
            for i in range(len(s)): t=i/44100; s[i]+=0.28*32767*math.sin(2*math.pi*55*t)*math.exp(-t*5)
            self._s['exp_s']=self._w(s)
            s=self._noise(0.65,0.65,3)
            for i in range(len(s)):
                t=i/44100; s[i]+=0.38*32767*math.sin(2*math.pi*40*t)*math.exp(-t*3); s[i]+=0.18*32767*math.sin(2*math.pi*80*t)*math.exp(-t*4)
            self._s['exp_b']=self._w(s)
            mel=[440,550,660]; out=[]
            for f in mel: out+=self._sine(f,0.08,0.18,8)
            self._s['done']=self._w(out)
            self._s['placed']=self._w(self._sine(330,0.1,0.14,9)+self._sine(440,0.1,0.14,9))
            atk=[]
            for _ in range(3): atk+=self._sine(620,0.05,0.28,12)+self._sine(390,0.05,0.28,12)
            self._s['atk']=self._w(atk)
            self._s['sel']=self._w(self._sine(480,0.06,0.10,14))
            self._s['cmd_move']=self._w(self._sine(360,0.08,0.12,10)+self._sine(480,0.06,0.10,12))
        except: self.ok=False
    def play(self,name,cd=0):
        if not self.ok or name not in self._s: return
        now=pygame.time.get_ticks()
        if self._cd.get(name,0)>now: return
        try:
            snd=self._s[name]; snd.set_volume(self.vol); snd.play()
            if cd>0: self._cd[name]=now+int(cd*1000/FPS)
        except: pass

# ── Notifications ─────────────────────────────────────────────────────────────
class Notif:
    def __init__(self,text,color,dur=120): self.text=text;self.color=color;self.dur=dur;self.age=0
    def tick(self): self.age+=1; return self.age<self.dur
    def alpha(self):
        if self.age<15: return int(255*self.age/15)
        if self.age>self.dur-30: return int(255*(self.dur-self.age)/30)
        return 255

class Notifs:
    def __init__(self,font): self.q=[];self.font=font
    def add(self,text,color=C_NOTIFY_INFO,dur=120):
        if any(n.text==text and n.age<30 for n in self.q): return
        if len(self.q)>6: self.q.pop(0)
        self.q.append(Notif(text,color,dur))
    def draw(self,surf):
        self.q=[n for n in self.q if n.tick()]
        by=SCREEN_H-UI_H-28
        for i,n in enumerate(reversed(self.q)):
            a=n.alpha(); t=self.font.render(n.text,True,n.color)
            s=pygame.Surface((t.get_width()+16,t.get_height()+6),pygame.SRCALPHA)
            s.fill((0,0,0,min(160,a))); s.blit(t,(8,3))
            surf.blit(s,(SCREEN_W//2-s.get_width()//2,by-i*26))

# ── Shake ─────────────────────────────────────────────────────────────────────
class Shake:
    def __init__(self): self.s=0.;self.ox=self.oy=0
    def add(self,v): self.s=min(self.s+v,14.)
    def update(self):
        if self.s>0.1: self.ox=int(random.uniform(-self.s,self.s));self.oy=int(random.uniform(-self.s,self.s));self.s*=0.82
        else: self.s=0;self.ox=self.oy=0

# ── Particles ─────────────────────────────────────────────────────────────────
class Pt:
    __slots__=('x','y','vx','vy','color','life','ml','sz','grav')
    def __init__(self,x,y,vx,vy,color,life,sz=2,grav=0.):
        self.x=float(x);self.y=float(y);self.vx=float(vx);self.vy=float(vy)
        self.color=color;self.life=life;self.ml=life;self.sz=sz;self.grav=grav
    def update(self): self.x+=self.vx;self.y+=self.vy;self.vy+=self.grav;self.vx*=0.96;self.vy*=0.96;self.life-=1;return self.life>0
    def draw(self,surf,cam):
        sx,sy=cam.w2s(self.x,self.y); r=max(1,int(self.sz*cam.zoom))
        a=int(255*self.life/self.ml); s=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
        pygame.draw.circle(s,(*self.color,a),(r+1,r+1),r); surf.blit(s,(sx-r-1,sy-r-1))

class Particles:
    def __init__(self): self.p=[]
    def emit(self,x,y,n,spd,color,life=30,sz=2,grav=0.):
        for _ in range(n):
            a=random.uniform(0,math.pi*2); s=random.uniform(spd*0.4,spd)
            self.p.append(Pt(x,y,math.cos(a)*s,math.sin(a)*s,color,random.randint(life//2,life),sz,grav))
    def thrust(self,x,y,ang,color,n=3):
        for _ in range(n):
            a=ang+math.pi+random.uniform(-0.5,0.5); s=random.uniform(0.5,2.2)
            self.p.append(Pt(x,y,math.cos(a)*s,math.sin(a)*s,color,random.randint(8,20),random.uniform(1,3),0.04))
    def draw(self,surf,cam):
        self.p=[p for p in self.p if p.update()]
        for p in self.p: p.draw(surf,cam)

# ── Terrain ───────────────────────────────────────────────────────────────────
class Terrain:
    def __init__(self,w,h):
        self.tw=w//TILE;self.th=h//TILE;self.data=[];self.metal=[]
        self._gen()
    def _noise(self,x,y,sc=6):
        v=0;amp=1.0;freq=1.0
        for _ in range(4):
            sx=x*freq/self.tw*sc;sy=y*freq/self.th*sc;ix,iy=int(sx),int(sy);fx,fy=sx-ix,sy-iy
            def h(px,py): return math.sin(px*127.1+py*311.7)*43758.5453%1
            val=(h(ix,iy)*(1-fx)+h(ix+1,iy)*fx)*(1-fy)+(h(ix,iy+1)*(1-fx)+h(ix+1,iy+1)*fx)*fy
            v+=val*amp;amp*=0.5;freq*=2
        return v
    def _gen(self):
        random.seed(42)
        raw=[[self._noise(x,y) for x in range(self.tw)] for y in range(self.th)]
        mn=min(v for r in raw for v in r);mx=max(v for r in raw for v in r)
        for y in range(self.th):
            rt=[];rm=[]
            for x in range(self.tw):
                n=(raw[y][x]-mn)/(mx-mn)
                t=1 if n<0.25 else(2 if n>0.78 else 0)
                rt.append(t);rm.append(t==0 and random.random()<0.018)
            self.data.append(rt);self.metal.append(rm)
        for dx in range(10):
            for dy in range(10):
                self.data[2+dy][2+dx]=0
                self.data[self.th-4-dy][self.tw-4-dx]=0
    def tile_at(self,wx,wy):
        tx,ty=int(wx//TILE),int(wy//TILE)
        if 0<=tx<self.tw and 0<=ty<self.th: return self.data[ty][tx]
        return 2
    def walkable(self,wx,wy): return self.tile_at(wx,wy)==0
    def is_water(self,wx,wy): return self.tile_at(wx,wy)==1
    def metal_deps(self):
        return [((x+0.5)*TILE,(y+0.5)*TILE) for y in range(self.th) for x in range(self.tw) if self.metal[y][x]]

# ── Camera ────────────────────────────────────────────────────────────────────
class Camera:
    def __init__(self): self.x=200.;self.y=200.;self.zoom=1.0;self.speed=12
    def clamp(self):
        self.x=max(0,min(MAP_W-SCREEN_W/self.zoom,self.x))
        self.y=max(0,min(MAP_H-(SCREEN_H-UI_H)/self.zoom,self.y))
    def w2s(self,wx,wy): return int((wx-self.x)*self.zoom),int((wy-self.y)*self.zoom)
    def s2w(self,sx,sy): return sx/self.zoom+self.x,sy/self.zoom+self.y
    def center_on(self,wx,wy): self.x=wx-SCREEN_W/2/self.zoom;self.y=wy-(SCREEN_H-UI_H)/2/self.zoom;self.clamp()
    def update(self,keys):
        spd=self.speed/self.zoom
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: self.x-=spd
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.x+=spd
        if keys[pygame.K_UP]    or keys[pygame.K_w]: self.y-=spd
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: self.y+=spd
        self.clamp()
    def zi(self): self.zoom=min(3.0,self.zoom*1.1)
    def zo(self): self.zoom=max(0.25,self.zoom/1.1)

# ── Projectile ────────────────────────────────────────────────────────────────
class Proj:
    def __init__(self,x,y,tx,ty,dmg,pt,team,tdom=None):
        self.x=float(x);self.y=float(y);self.tx=float(tx);self.ty=float(ty)
        self.dmg=dmg;self.pt=pt;self.team=team;self.tdom=tdom
        dx,dy=tx-x,ty-y;l=math.hypot(dx,dy) or 1
        spd={'laser':10,'bullet':6,'shell':4.5,'missile':7,'bomb':3}[pt]
        self.vx=dx/l*spd;self.vy=dy/l*spd;self.alive=True;self.trail=[]
    def update(self,entities):
        self.trail.append((self.x,self.y))
        if len(self.trail)>10: self.trail.pop(0)
        self.x+=self.vx;self.y+=self.vy
        for e in entities:
            if e.team==self.team or not e.alive: continue
            if self.tdom and getattr(e,'dom',None)!=self.tdom: continue
            if dist((self.x,self.y),(e.x,e.y))<e.radius+5:
                e.take_damage(self.dmg);self.alive=False;return True
        if dist((self.x,self.y),(self.tx,self.ty))<max(abs(self.vx),abs(self.vy))+3: self.alive=False
        return False
    def draw(self,surf,cam):
        if not self.alive: return
        sx,sy=cam.w2s(self.x,self.y)
        if self.pt=="laser":
            for i in range(1,len(self.trail)):
                p1=cam.w2s(*self.trail[i-1]);p2=cam.w2s(*self.trail[i])
                pygame.draw.line(surf,(*C_LASER,int(140*i/len(self.trail))),p1,p2,2)
            pygame.draw.circle(surf,C_LASER2,(sx,sy),4);gfx_glow(surf,C_LASER,(sx,sy),8,40)
        elif self.pt=="bullet":
            if len(self.trail)>=2: pygame.draw.line(surf,(*C_BULLET,100),cam.w2s(*self.trail[-2]),(sx,sy),2)
            pygame.draw.circle(surf,C_BULLET,(sx,sy),3)
        elif self.pt=="missile":
            if len(self.trail)>=2: pygame.draw.line(surf,(*C_MISSILE,100),cam.w2s(*self.trail[-2]),(sx,sy),2)
            pygame.draw.circle(surf,C_MISSILE,(sx,sy),4);gfx_glow(surf,C_MISSILE,(sx,sy),6,35)
        elif self.pt=="bomb":
            pygame.draw.circle(surf,(80,70,40),(sx+2,sy+2),6);pygame.draw.circle(surf,(190,150,60),(sx,sy),6)
        else:
            pygame.draw.circle(surf,C_SHELL,(sx,sy),5);gfx_glow(surf,C_SHELL,(sx,sy),8,45)

# ── Explosion ─────────────────────────────────────────────────────────────────
class Explosion:
    def __init__(self,x,y,sz=1.,parts=None,sound=None):
        self.x=x;self.y=y;self.t=0;self.life=int(35+sz*8);self.sz=sz
        self.debris=[(random.uniform(-4,4)*sz,random.uniform(-4,4)*sz,random.randint(4,14),random.choice(C_EXPLOSION)) for _ in range(16)]
        if parts:
            for _ in range(int(8*sz)):
                a=random.uniform(0,math.pi*2);s=random.uniform(0.5,2)*sz
                parts.p.append(Pt(x,y,math.cos(a)*s,math.sin(a)*s,C_SMOKE,random.randint(40,80),random.uniform(3,6)*sz,-0.03))
        if sound: sound.play('exp_b' if sz>1.5 else 'exp_s',cd=3)
    def update(self): self.t+=1;return self.t<self.life
    def draw(self,surf,cam):
        sx,sy=cam.w2s(self.x,self.y);p=self.t/self.life
        r=int(self.sz*22*math.sin(p*math.pi)*(1+p*0.5))
        if r>0:
            al=int(255*(1-p)**1.5);col=lerp_c(C_EXPLOSION[min(int(p*4),3)],(20,15,8),p)
            s=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
            pygame.draw.circle(s,(*col,al),(r+2,r+2),r)
            if p<0.3:
                cr=int(r*(1-p/0.3)*0.5); pygame.draw.circle(s,(255,240,200,min(255,int(al*1.4))),(r+2,r+2),cr)
            surf.blit(s,(sx-r-2,sy-r-2))
        for dx,dy,pr,col in self.debris:
            pygame.draw.circle(surf,lerp_c(col,(40,20,10),p),(sx+int(dx*(1-p)**0.8*18),sy+int(dy*(1-p)**0.8*18)),max(1,int(pr*(1-p)**0.5)))

# ── Entity ────────────────────────────────────────────────────────────────────
class Entity:
    _idc=0
    def __init__(self,x,y,team):
        Entity._idc+=1;self.id=Entity._idc
        self.x=float(x);self.y=float(y);self.team=team;self.alive=True
        self.hp=100;self.max_hp=100;self.radius=16;self.weapon=None
        self.fire_cd=0;self.target=None;self._exploded=False
    def take_damage(self,d): self.hp=max(0,self.hp-d); self.alive=self.hp>0
    def hfrac(self): return max(0,self.hp/self.max_hp)
    def hcolor(self):
        f=self.hfrac()
        return lerp_c(C_HEALTH_Y,C_HEALTH_G,(f-0.5)*2) if f>0.5 else lerp_c(C_HEALTH_R,C_HEALTH_Y,f*2)
    def draw_hbar(self,surf,cam,w=30):
        sx,sy=cam.w2s(self.x,self.y-self.radius-10)
        pygame.draw.rect(surf,(20,20,20),(sx-w//2-1,sy-1,w+2,6))
        pygame.draw.rect(surf,(40,40,40),(sx-w//2,sy,w,4))
        cw=int(w*self.hfrac())
        if cw>0: pygame.draw.rect(surf,self.hcolor(),(sx-w//2,sy,cw,4))
    def try_fire(self,entities,projs,sound=None):
        if not self.weapon: return
        if self.fire_cd>0: self.fire_cd=max(0,self.fire_cd-1);return
        wpn=self.weapon;rng=wpn['r'];aa=getattr(self,'aa_only',False)
        for e in entities:
            if e.team==self.team or not e.alive: continue
            if aa and getattr(e,'dom',Domain.GROUND)!=Domain.AIR: continue
            if dist((self.x,self.y),(e.x,e.y))<rng: self.target=e;break
        if self.target and self.target.alive and dist((self.x,self.y),(self.target.x,self.target.y))<rng:
            tdom=getattr(self.target,'dom',None)
            projs.append(Proj(self.x,self.y,self.target.x,self.target.y,wpn['d'],wpn['p'],self.team,tdom))
            self.fire_cd=wpn['cd']
            if sound: sound.play(wpn['p'],cd=2)
        else: self.target=None

# ── Building ──────────────────────────────────────────────────────────────────
class Building(Entity):
    def __init__(self,x,y,team,btype):
        super().__init__(x,y,team)
        sp=BSPECS[btype];self.btype=btype;self.name=sp['name']
        self.hp=sp['hp'];self.max_hp=sp['hp'];self.size=sp['size']
        self.radius=sp['size']*TILE//2;self.metal_gen=sp['mg'];self.energy_gen=sp['eg']
        self.can_build=sp.get('cb',False);self.weapon=sp.get('wpn')
        self.produces=sp.get('produces',[]);self.dom=sp.get('dom',Domain.GROUND)
        self.aa_only=sp.get('aa',False);self.movable=sp.get('movable',False)
        self.build_queue=[];self.rally=None;self._phase=random.uniform(0,math.pi*2)
        self._shield_hp=200 if btype==BT.SHIELD_GEN else 0
        self._shield_max=200;self.shield_radius=200
        # Commander movement
        self.move_target=None;self._ang=0.

    def enqueue(self,utype,eco,player_cmd=None):
        sp=USPECS[utype]
        if player_cmd and dist((player_cmd.x,player_cmd.y),(self.x,self.y))>PRODUCE_RANGE:
            return False,'out_of_range'
        if eco.metal>=sp['mc'] and eco.energy>=sp['ec']:
            eco.metal-=sp['mc'];eco.energy-=sp['ec']
            self.build_queue.append([utype,sp['bt'],sp['bt']]);return True,'ok'
        return False,'no_funds'

    def dequeue(self,idx,eco):
        if 0<=idx<len(self.build_queue):
            item=self.build_queue[idx];sp=USPECS[item[0]]
            frac=item[2]/item[1];eco.metal+=sp['mc']*frac;eco.energy+=sp['ec']*frac
            self.build_queue.pop(idx)

    def update_prod(self):
        if not self.build_queue: return None
        item=self.build_queue[0];item[2]-=1
        if item[2]<=0: self.build_queue.pop(0);return item[0]
        return None

    def update_move(self,terrain):
        if not self.movable or not self.move_target: return
        dx=self.move_target[0]-self.x;dy=self.move_target[1]-self.y
        l=math.hypot(dx,dy)
        if l<4: self.move_target=None;return
        spd=1.2;self._ang=math.atan2(dy,dx)
        nx,ny=self.x+dx/l*spd,self.y+dy/l*spd
        if terrain.walkable(nx,ny): self.x,self.y=nx,ny
        self.x=max(self.radius,min(MAP_W-self.radius,self.x))
        self.y=max(self.radius,min(MAP_H-self.radius,self.y))
        if self.rally is None: self.rally=(self.x+self.radius*2,self.y)

    def update_shield(self,all_e):
        if self.btype!=BT.SHIELD_GEN or not self.alive: return
        if self._shield_hp<self._shield_max: self._shield_hp=min(self._shield_max,self._shield_hp+0.05)
        for e in all_e:
            if e.team!=self.team or not e.alive or e is self: continue
            if dist((self.x,self.y),(e.x,e.y))<self.shield_radius: e._shielded=True

    def draw(self,surf,cam,selected=False,tick=0):
        sx,sy=cam.w2s(self.x,self.y)
        ps=int(self.size*TILE*cam.zoom)
        if ps<3: return
        color=tc(self.team);dark=tc(self.team,dark=True);gl=tc(self.team,glow=True)
        ph=tick*0.04+self._phase

        # Shadow
        ss=pygame.Surface((ps+8,ps+8),pygame.SRCALPHA)
        pygame.draw.rect(ss,(0,0,0,50),(4,4,ps,ps),border_radius=4)
        surf.blit(ss,(sx-ps//2-4,sy-ps//2-4))
        rrect(surf,(22,32,28),(sx-ps//2,sy-ps//2,ps,ps),4)
        rrect(surf,dark,(sx-ps//2+2,sy-ps//2+2,ps-4,ps-4),3)
        rrect(surf,color,(sx-ps//2+4,sy-ps//2+4,ps-8,ps-8),2)
        inner=max(4,ps//3)

        if self.btype==BT.SOLAR:
            pc=lerp_c(C_ENERGY,(255,240,180),0.5+0.5*math.sin(ph))
            for i in range(3): pygame.draw.rect(surf,pc,(sx-inner+i*inner,sy-inner//2,inner-2,inner),border_radius=1)
            gfx_glow(surf,C_ENERGY,(sx,sy),inner,int(25+15*math.sin(ph)))
        elif self.btype==BT.METAL_X:
            a=ph*0.5;pts=[(sx+int(math.cos(a+i*math.pi/2)*inner),sy+int(math.sin(a+i*math.pi/2)*inner)) for i in range(4)]
            pygame.draw.polygon(surf,C_METAL,pts);pygame.draw.polygon(surf,(180,230,210),pts,2)
        elif self.btype==BT.COMMANDER:
            gfx_glow(surf,gl,(sx,sy),int(inner*(0.7+0.3*math.sin(ph*1.5))*1.5),45)
            pygame.draw.circle(surf,(240,240,200),(sx,sy),inner)
            pygame.draw.circle(surf,(200,200,150),(sx,sy),inner-3)
            for i in range(6):
                a=i*math.pi/3+ph*0.2
                pygame.draw.circle(surf,(160,160,120),(sx+int(math.cos(a)*inner*0.6),sy+int(math.sin(a)*inner*0.6)),2)
            if self.move_target:
                tx2,ty2=cam.w2s(*self.move_target)
                pygame.draw.line(surf,(*gl,80),(sx,sy),(tx2,ty2),1)
        elif self.btype in (BT.FACTORY,BT.LAB):
            nt=8 if self.btype==BT.LAB else 6;gpts=[]
            for i in range(nt*2):
                ang=i*math.pi/nt+ph*(0.5 if self.btype==BT.LAB else 0.3)
                r2=(inner-2) if i%2==0 else int((inner-2)*0.68)
                gpts.append((sx+int(math.cos(ang)*r2),sy+int(math.sin(ang)*r2)))
            if len(gpts)>=3: pygame.draw.polygon(surf,dark,gpts);pygame.draw.polygon(surf,gl,gpts,1)
            pygame.draw.circle(surf,dark,(sx,sy),(inner-2)//3)
        elif self.btype==BT.TURRET:
            pygame.draw.circle(surf,(50,70,60),(sx,sy),inner+2);pygame.draw.circle(surf,(70,90,80),(sx,sy),inner)
            ta=(math.atan2(cam.w2s(self.target.x,self.target.y)[1]-sy,cam.w2s(self.target.x,self.target.y)[0]-sx)
                if self.target and self.target.alive else ph*0.3)
            bx2=sx+int(math.cos(ta)*(inner+6));by2=sy+int(math.sin(ta)*(inner+6))
            pygame.draw.line(surf,C_LASER2,(sx,sy),(bx2,by2),max(2,ps//8));gfx_glow(surf,C_LASER,(sx,sy),inner//2,20)
        elif self.btype==BT.AIRPAD:
            pygame.draw.line(surf,(200,200,200),(sx-inner,sy),(sx+inner,sy),3)
            pygame.draw.line(surf,(200,200,200),(sx,sy-inner),(sx,sy+inner),3)
            gfx_glow(surf,(180,180,220),(sx,sy),inner,20)
        elif self.btype==BT.SHIPYARD:
            pygame.draw.rect(surf,C_WATER_SHIP,(sx-inner,sy-inner//2,inner*2,inner),border_radius=3)
            pygame.draw.rect(surf,(60,110,160),(sx-inner+2,sy-inner//2+2,inner*2-4,inner-4),border_radius=2)
            gfx_glow(surf,(40,100,180),(sx,sy),inner,22)
        elif self.btype==BT.SHIELD_GEN:
            pulse=0.7+0.3*math.sin(ph*2)
            gfx_glow(surf,(80,140,255),(sx,sy),int(inner*pulse*1.8),35)
            pts=[(sx+int(math.cos(i*math.pi/3)*inner*pulse),sy+int(math.sin(i*math.pi/3)*inner*pulse)) for i in range(6)]
            pygame.draw.polygon(surf,(60,100,220),pts,2)
            if self._shield_hp>0:
                sr=int(self.shield_radius*cam.zoom)
                ss=pygame.Surface((sr*2+4,sr*2+4),pygame.SRCALPHA)
                a2=int(20*self._shield_hp/self._shield_max)
                pygame.draw.circle(ss,(80,140,255,a2),(sr+2,sr+2),sr)
                pygame.draw.circle(ss,(80,140,255,50),(sr+2,sr+2),sr,2)
                surf.blit(ss,(sx-sr-2,sy-sr-2))
        elif self.btype==BT.AA_GUN:
            pygame.draw.circle(surf,(60,80,70),(sx,sy),inner)
            for side in [-1,1]:
                pygame.draw.line(surf,(140,180,160),(sx+side*inner//3,sy),(sx+int(side*inner*0.4),sy-inner),max(2,ps//10))
        elif self.btype==BT.COASTAL_BAT:
            pygame.draw.circle(surf,(60,70,65),(sx,sy),inner+2)
            ta=(math.atan2(cam.w2s(self.target.x,self.target.y)[1]-sy,cam.w2s(self.target.x,self.target.y)[0]-sx)
                if self.target and self.target.alive else ph*0.1)
            pygame.draw.line(surf,(160,180,160),(sx,sy),(sx+int(math.cos(ta)*(inner+10)),sy+int(math.sin(ta)*(inner+10))),max(4,ps//6))
            gfx_glow(surf,C_SHELL,(sx,sy),inner//2,15)

        if self.build_queue:
            item=self.build_queue[0];prog=1.-item[2]/item[1];bw=ps-4
            pygame.draw.rect(surf,(20,20,20),(sx-bw//2,sy+ps//2+3,bw,5),border_radius=2)
            pw=int(bw*prog)
            if pw>0: pygame.draw.rect(surf,C_ENERGY,(sx-bw//2,sy+ps//2+3,pw,5),border_radius=2)

        if selected:
            gs=pygame.Surface((ps+20,ps+20),pygame.SRCALPHA)
            pygame.draw.rect(gs,(*C_SEL,30),(0,0,ps+20,ps+20),border_radius=6)
            pygame.draw.rect(gs,(*C_SEL,140),(4,4,ps+12,ps+12),2,border_radius=5)
            surf.blit(gs,(sx-ps//2-10,sy-ps//2-10))

        self.draw_hbar(surf,cam,w=ps)

# ── Unit ──────────────────────────────────────────────────────────────────────
class Unit(Entity):
    def __init__(self,x,y,team,utype):
        super().__init__(x,y,team)
        sp=USPECS[utype];self.utype=utype;self.name=sp['name']
        self.hp=sp['hp'];self.max_hp=sp['hp'];self.speed=sp['spd']
        self.sight=sp['sight'];self.weapon=sp['wpn'];self.dom=sp['dom']
        self.radius=sp['sz'];self.state=UState.IDLE
        self.move_target=None;self.attack_target=None;self.fire_cd=0
        self._phase=random.uniform(0,math.pi*2);self._ang=0.
        self._alt=random.uniform(0,math.pi*2);self._shielded=False

    def command_move(self,wx,wy): self.move_target=(wx,wy);self.attack_target=None;self.state=UState.MOVING
    def command_attack(self,t): self.attack_target=t;self.state=UState.ATTACKING

    def update(self,all_e,projs,terrain,parts=None,sound=None):
        self.fire_cd=max(0,self.fire_cd-1);self._shielded=False
        if self.dom==Domain.GROUND: self._steer(all_e)
        if self.state==UState.ATTACKING and self.attack_target:
            if not self.attack_target.alive: self.attack_target=None;self.state=UState.IDLE;return
            d=dist((self.x,self.y),(self.attack_target.x,self.attack_target.y))
            if d>self.weapon['r']: self.move_target=(self.attack_target.x,self.attack_target.y);self._move(terrain,parts)
            else: self.move_target=None;self._fire(self.attack_target,projs,sound)
        elif self.state in (UState.MOVING,UState.RETREATING) and self.move_target:
            self._move(terrain,parts)
            if dist((self.x,self.y),self.move_target)<10: self.move_target=None;self.state=UState.IDLE
        if self.state in (UState.IDLE,UState.MOVING) and self.weapon:
            for e in all_e:
                if e.team==self.team or not e.alive: continue
                if dist((self.x,self.y),(e.x,e.y))<self.weapon['r']:
                    self._fire(e,projs,sound);break

    def _move(self,terrain,parts=None):
        if not self.move_target: return
        dx=self.move_target[0]-self.x;dy=self.move_target[1]-self.y
        l=math.hypot(dx,dy)
        if l<2: return
        self._ang=math.atan2(dy,dx);nx,ny=self.x+dx/l*self.speed,self.y+dy/l*self.speed
        if self.dom==Domain.GROUND:
            if terrain.walkable(nx,ny): self.x,self.y=nx,ny
            elif terrain.walkable(self.x+dx/l*self.speed,self.y): self.x+=dx/l*self.speed
            elif terrain.walkable(self.x,self.y+dy/l*self.speed): self.y+=dy/l*self.speed
        elif self.dom==Domain.AIR: self.x,self.y=nx,ny
        elif self.dom==Domain.NAVAL:
            if terrain.is_water(nx,ny): self.x,self.y=nx,ny
            elif terrain.is_water(self.x+dx/l*self.speed,self.y): self.x+=dx/l*self.speed
            elif terrain.is_water(self.x,self.y+dy/l*self.speed): self.y+=dy/l*self.speed
        self.x=max(self.radius,min(MAP_W-self.radius,self.x))
        self.y=max(self.radius,min(MAP_H-self.radius,self.y))
        if parts and random.random()<0.35:
            col=tc(self.team,glow=True)
            if self.dom==Domain.AIR: parts.thrust(self.x,self.y,self._ang,col,3)
            elif self.speed>1.5: parts.thrust(self.x,self.y,self._ang,col,2)

    def _steer(self,entities):
        sx=sy=0.
        for e in entities:
            if e is self or not e.alive or not hasattr(e,'speed'): continue
            if getattr(e,'dom',Domain.GROUND)!=Domain.GROUND: continue
            d=dist((self.x,self.y),(e.x,e.y));md=self.radius+e.radius+2
            if 0<d<md: f=(md-d)/md*0.5;sx+=(self.x-e.x)/d*f;sy+=(self.y-e.y)/d*f
        self.x=max(self.radius,min(MAP_W-self.radius,self.x+sx))
        self.y=max(self.radius,min(MAP_H-self.radius,self.y+sy))

    def _fire(self,target,projs,sound=None):
        if self.fire_cd>0: return
        tdom=getattr(target,'dom',None)
        projs.append(Proj(self.x,self.y,target.x,target.y,self.weapon['d'],self.weapon['p'],self.team,tdom))
        self.fire_cd=self.weapon['cd']
        if sound: sound.play(self.weapon['p'],cd=2)

    def draw(self,surf,cam,selected=False,tick=0):
        sx,sy=cam.w2s(self.x,self.y)
        r=max(3,int(self.radius*cam.zoom))
        color=tc(self.team);dark=tc(self.team,dark=True);gl=tc(self.team,glow=True)
        ang=self._ang;ph=tick*0.05+self._phase

        if self.dom==Domain.AIR:
            bob=int(3*math.sin(tick*0.08+self._alt))
            ss=pygame.Surface((r*3,r*2),pygame.SRCALPHA)
            pygame.draw.ellipse(ss,(0,0,0,35),(0,0,r*3,r*2))
            surf.blit(ss,(sx-r*3//2,sy+r//2+4-bob))
            sy-=bob
        if self.dom==Domain.NAVAL:
            ws=pygame.Surface((r*4,r*2),pygame.SRCALPHA)
            pygame.draw.ellipse(ws,(*C_WATER2,55),(0,0,r*4,r*2))
            surf.blit(ws,(sx-r*2,sy-r//2))
        if self._shielded:
            gfx_glow(surf,(80,140,255),(sx,sy),r+6,25)

        if self.utype==UT.TANK:
            perp=ang+math.pi/2;bx2=int(math.cos(ang)*r);by2=int(math.sin(ang)*r)
            rx=int(math.cos(perp)*r*0.55);ry=int(math.sin(perp)*r*0.55)
            pts=[(sx+bx2+rx,sy+by2+ry),(sx+bx2-rx,sy+by2-ry),(sx-bx2-rx,sy-by2-ry),(sx-bx2+rx,sy-by2+ry)]
            pygame.draw.polygon(surf,dark,[(p[0]+2,p[1]+2) for p in pts])
            pygame.draw.polygon(surf,color,pts)
            for side in [-1,1]:
                tx2=int(math.cos(perp)*r*0.7)*side;ty2=int(math.sin(perp)*r*0.7)*side
                pygame.draw.line(surf,(30,40,35),(sx-bx2+tx2,sy-by2+ty2),(sx+bx2+tx2,sy+by2+ty2),max(2,r//4))
            pygame.draw.circle(surf,dark,(sx+1,sy+1),r//2+2);pygame.draw.circle(surf,gl,(sx,sy),r//2+1);pygame.draw.circle(surf,dark,(sx,sy),r//2-1)
            ta=(math.atan2(cam.w2s(self.attack_target.x,self.attack_target.y)[1]-sy,cam.w2s(self.attack_target.x,self.attack_target.y)[0]-sx)
                if self.attack_target and self.attack_target.alive else ang)
            pygame.draw.line(surf,C_TEXT,(sx,sy),(sx+int(math.cos(ta)*(r+5)),sy+int(math.sin(ta)*(r+5))),max(2,r//5))
        elif self.utype==UT.ARTILLERY:
            a1=ang-math.pi/2;a2=ang+math.pi/2
            pts=[(sx+int(math.cos(ang)*r*1.2),sy+int(math.sin(ang)*r*1.2)),
                 (sx+int(math.cos(a1)*r*0.7),sy+int(math.sin(a1)*r*0.7)),
                 (sx+int(math.cos(a2)*r*0.7),sy+int(math.sin(a2)*r*0.7))]
            pygame.draw.polygon(surf,dark,[(p[0]+3,p[1]+3) for p in pts])
            pygame.draw.polygon(surf,color,pts);pygame.draw.polygon(surf,gl,pts,2)
            ta=(math.atan2(cam.w2s(self.attack_target.x,self.attack_target.y)[1]-sy,cam.w2s(self.attack_target.x,self.attack_target.y)[0]-sx)
                if self.attack_target and self.attack_target.alive else ang)
            pygame.draw.line(surf,C_TEXT,(sx,sy),(sx+int(math.cos(ta)*r*1.9),sy+int(math.sin(ta)*r*1.9)),max(3,r//4))
        elif self.utype==UT.SCOUT:
            pygame.draw.circle(surf,dark,(sx+2,sy+2),r);pygame.draw.circle(surf,color,(sx,sy),r);pygame.draw.circle(surf,gl,(sx,sy),r//2)
            pygame.draw.circle(surf,(220,235,235),(sx+int(math.cos(ang)*r*0.7),sy+int(math.sin(ang)*r*0.7)),max(1,r//4))
        elif self.utype==UT.SOLDIER:
            pygame.draw.circle(surf,dark,(sx+2,sy+2),r);pygame.draw.circle(surf,color,(sx,sy),r)
            hx=sx+int(math.cos(ang)*r*0.35);hy=sy+int(math.sin(ang)*r*0.35);pygame.draw.circle(surf,gl,(hx,hy),r//2+1)
            for side in [-1,1]: pygame.draw.line(surf,color,(sx,sy),(sx+int(math.cos(ang+side*1.4)*r*0.85),sy+int(math.sin(ang+side*1.4)*r*0.85)),max(1,r//4))
        elif self.utype==UT.RAIDER:
            perp=ang+math.pi/2
            pts=[(sx+int(math.cos(ang)*r*1.1),sy+int(math.sin(ang)*r*1.1)),(sx+int(math.cos(perp)*r*0.55),sy+int(math.sin(perp)*r*0.55)),
                 (sx+int(math.cos(ang+math.pi)*r*0.75),sy+int(math.sin(ang+math.pi)*r*0.75)),(sx-int(math.cos(perp)*r*0.55),sy-int(math.sin(perp)*r*0.55))]
            pygame.draw.polygon(surf,dark,[(p[0]+2,p[1]+2) for p in pts]);pygame.draw.polygon(surf,color,pts);pygame.draw.polygon(surf,gl,pts,1)
            gfx_glow(surf,gl,(sx,sy),r//2,20)
        elif self.utype==UT.FIGHTER:
            perp=ang+math.pi/2
            nose=(sx+int(math.cos(ang)*r*1.3),sy+int(math.sin(ang)*r*1.3))
            tail=(sx+int(math.cos(ang+math.pi)*r*0.9),sy+int(math.sin(ang+math.pi)*r*0.9))
            pygame.draw.line(surf,dark,(nose[0]+1,nose[1]+1),(tail[0]+1,tail[1]+1),max(3,r//3));pygame.draw.line(surf,color,nose,tail,max(3,r//3))
            wl=(sx+int(math.cos(perp)*r*1.1)+int(math.cos(ang+math.pi)*r*0.2),sy+int(math.sin(perp)*r*1.1)+int(math.sin(ang+math.pi)*r*0.2))
            wr=(sx-int(math.cos(perp)*r*1.1)+int(math.cos(ang+math.pi)*r*0.2),sy-int(math.sin(perp)*r*1.1)+int(math.sin(ang+math.pi)*r*0.2))
            pygame.draw.line(surf,gl,wl,nose,max(2,r//4));pygame.draw.line(surf,gl,wr,nose,max(2,r//4))
            gfx_glow(surf,gl,tail,r//2,28)
        elif self.utype==UT.BOMBER:
            perp=ang+math.pi/2
            nose=(sx+int(math.cos(ang)*r),sy+int(math.sin(ang)*r))
            tail=(sx+int(math.cos(ang+math.pi)*r*0.8),sy+int(math.sin(ang+math.pi)*r*0.8))
            pygame.draw.line(surf,dark,(nose[0]+1,nose[1]+1),(tail[0]+1,tail[1]+1),max(5,r//2));pygame.draw.line(surf,color,nose,tail,max(5,r//2))
            wl=(sx+int(math.cos(perp)*r*1.4),sy+int(math.sin(perp)*r*1.4));wr=(sx-int(math.cos(perp)*r*1.4),sy-int(math.sin(perp)*r*1.4))
            pygame.draw.line(surf,color,wl,wr,max(2,r//4));pygame.draw.circle(surf,(80,60,30),(sx,sy),r//3)
        elif self.utype==UT.GUNBOAT:
            perp=ang+math.pi/2;hw=int(r*0.6)
            pts=[(sx+int(math.cos(ang)*r*1.3),sy+int(math.sin(ang)*r*1.3)),(sx+int(math.cos(perp)*hw),sy+int(math.sin(perp)*hw)),
                 (sx+int(math.cos(ang+math.pi)*r*0.9),sy+int(math.sin(ang+math.pi)*r*0.9)),(sx-int(math.cos(perp)*hw),sy-int(math.sin(perp)*hw))]
            pygame.draw.polygon(surf,dark,[(p[0]+2,p[1]+2) for p in pts]);pygame.draw.polygon(surf,C_WATER_SHIP,pts);pygame.draw.polygon(surf,gl,pts,1)
            ta=(math.atan2(cam.w2s(self.attack_target.x,self.attack_target.y)[1]-sy,cam.w2s(self.attack_target.x,self.attack_target.y)[0]-sx)
                if self.attack_target and self.attack_target.alive else ang)
            pygame.draw.circle(surf,(50,80,110),(sx,sy),r//2)
            pygame.draw.line(surf,C_TEXT,(sx,sy),(sx+int(math.cos(ta)*(r+4)),sy+int(math.sin(ta)*(r+4))),max(2,r//4))
        elif self.utype==UT.CARRIER:
            perp=ang+math.pi/2;hw=int(r*0.7)
            pts=[(sx+int(math.cos(ang)*r*1.5),sy+int(math.sin(ang)*r*1.5)),(sx+int(math.cos(perp)*hw),sy+int(math.sin(perp)*hw)),
                 (sx+int(math.cos(ang+math.pi)*r*1.2),sy+int(math.sin(ang+math.pi)*r*1.2)),(sx-int(math.cos(perp)*hw),sy-int(math.sin(perp)*hw))]
            pygame.draw.polygon(surf,dark,[(p[0]+3,p[1]+3) for p in pts]);pygame.draw.polygon(surf,C_WATER_SHIP,pts);pygame.draw.polygon(surf,(60,110,155),pts,2)
            pygame.draw.line(surf,(180,200,200),(sx+int(math.cos(ang)*r*1.3),sy+int(math.sin(ang)*r*1.3)),
                             (sx+int(math.cos(ang+math.pi)*r),sy+int(math.sin(ang+math.pi)*r)),2)
            gfx_glow(surf,gl,(sx,sy),r//2,18)

        if selected:
            pygame.draw.circle(surf,C_SEL,(sx,sy),r+4,2);gfx_glow(surf,C_SEL,(sx,sy),r+4,18)
        self.draw_hbar(surf,cam,w=r*2+6)
        if selected and self.move_target:
            tx2,ty2=cam.w2s(*self.move_target); pygame.draw.line(surf,(*C_SEL,65),(sx,sy),(tx2,ty2),1)

# ── Economy ───────────────────────────────────────────────────────────────────
class Economy:
    def __init__(self,bm=0,be=0):
        self.metal=200.+bm;self.energy=500.+be
        self.max_metal=1500.;self.max_energy=3000.
        self.metal_rate=0.;self.energy_rate=0.
    def tick(self,buildings,mult=1.):
        self.metal_rate=self.energy_rate=0.
        for b in buildings:
            if not b.alive: continue
            self.metal_rate+=b.metal_gen*mult;self.energy_rate+=b.energy_gen*mult
        self.metal=max(0,min(self.max_metal,self.metal+self.metal_rate/FPS))
        self.energy=max(0,min(self.max_energy,self.energy+self.energy_rate/FPS))
    def can_afford_b(self,bt): sp=BSPECS[bt];return self.metal>=sp['mc'] and self.energy>=sp['ec']
    def pay_b(self,bt): sp=BSPECS[bt];self.metal-=sp['mc'];self.energy-=sp['ec']

# ── AI Think Log ──────────────────────────────────────────────────────────────
class AIThinkLog:
    """Circular buffer of AI thought messages for the verbose panel."""
    def __init__(self,maxlines=20):
        self.lines=collections.deque(maxlen=maxlines)
        self.ages=collections.deque(maxlen=maxlines)
        self._tick=0
    def log(self,msg,important=False):
        prefix="▶ " if important else "  "
        self.lines.append(prefix+msg)
        self.ages.append(self._tick)
    def tick(self): self._tick+=1
    def draw(self,surf,font,x,y,w,h):
        rrect(surf,C_AI_THINK_BG,(x,y,w,h),6,1,C_AI_THINK_BD)
        title=font.render("AI THINKING",True,C_AI_THINK_TX)
        surf.blit(title,(x+8,y+5))
        pygame.draw.line(surf,C_AI_THINK_BD,(x+4,y+20),(x+w-4,y+20))
        lh=14; ly=y+24
        for i,(line,age) in enumerate(zip(self.lines,self.ages)):
            if ly+lh>y+h: break
            recency=max(0,1.-(self._tick-age)/300.)
            col=lerp_c(C_AI_THINK_DIM,C_AI_THINK_TX,recency)
            t=font.render(line[:w//7],True,col)
            surf.blit(t,(x+4,ly)); ly+=lh

# ── AI ────────────────────────────────────────────────────────────────────────
class AI:
    def __init__(self,team,eco,buildings,units,difficulty=Difficulty.MEDIUM):
        self.team=team;self.eco=eco;self.buildings=buildings;self.units=units
        self.difficulty=difficulty;self.p=DIFF[difficulty]
        self.tick=0;self.atk_timer=FPS*random.randint(*self.p['ar'])
        self.wave_size=self.p['w0'];self._prev_cmd_hp=1.
        self.think=AIThinkLog(22)
        self._last_threat_unit=None
        self._strategy="EXPAND"  # EXPAND / DEFEND / ATTACK / REBUILD
        self._strat_timer=0

    def update(self,all_e,projs,terrain,mdeps,notifs=None,sound=None):
        self.tick+=1;self.think.tick();p=self.p
        my_b=[b for b in self.buildings if b.team==self.team and b.alive]
        my_u=[u for u in self.units if u.team==self.team and u.alive]
        cmd=next((b for b in my_b if b.btype==BT.COMMANDER),None)
        facs=[b for b in my_b if b.btype in (BT.FACTORY,BT.LAB,BT.AIRPAD,BT.SHIPYARD)]
        en=[e for e in all_e if e.team!=self.team and e.alive]
        en_b=[e for e in en if isinstance(e,Building)]
        en_u=[e for e in en if isinstance(e,Unit)]

        # ── Situation assessment ──────────────────────────────────────────────
        my_power=len(my_u)+len(my_b)*2
        en_power=len(en_u)+len(en_b)*2
        near_threat=[e for e in en if cmd and dist((cmd.x,cmd.y),(e.x,e.y))<500]
        is_under_attack=len(near_threat)>0
        eco_ok=self.eco.metal>100 and self.eco.energy>200
        have_army=len(my_u)>=self.wave_size

        # ── Strategy decision (every 3 seconds) ──────────────────────────────
        self._strat_timer-=1
        if self._strat_timer<=0:
            self._strat_timer=FPS*3
            old=self._strategy
            if is_under_attack and cmd and cmd.hfrac()<0.5:
                self._strategy="DEFEND"
            elif not eco_ok and len(facs)==0:
                self._strategy="REBUILD"
            elif have_army and not is_under_attack:
                self._strategy="ATTACK"
            else:
                self._strategy="EXPAND"
            if old!=self._strategy:
                self.think.log(f"Strategy → {self._strategy}",important=True)

        self.think.log(f"T{self.tick} [{self._strategy}] U:{len(my_u)} B:{len(my_b)} M:{int(self.eco.metal)} E:{int(self.eco.energy)}")

        # ── Economy / build phase ─────────────────────────────────────────────
        if cmd and self.tick%p['biv']==0:
            solars=[b for b in my_b if b.btype==BT.SOLAR]
            extrs=[b for b in my_b if b.btype==BT.METAL_X]
            fabs=[b for b in my_b if b.btype==BT.FACTORY]
            turrets=[b for b in my_b if b.btype==BT.TURRET]
            aa_guns=[b for b in my_b if b.btype==BT.AA_GUN]
            airpads=[b for b in my_b if b.btype==BT.AIRPAD]
            labs=[b for b in my_b if b.btype==BT.LAB]
            shields=[b for b in my_b if b.btype==BT.SHIELD_GEN]

            # Metal extractors on nearby deposits
            placed=[(b.x,b.y) for b in extrs]
            for dep in sorted(mdeps,key=lambda d:dist(d,(cmd.x,cmd.y))):
                if dist(dep,(cmd.x,cmd.y))>BUILD_RANGE: continue
                if any(dist(dep,pm)<TILE*2 for pm in placed): continue
                if self._try_place(BT.METAL_X,dep[0],dep[1],terrain,cmd):
                    self.think.log(f"Build Metal Extractor @ {int(dep[0])},{int(dep[1])}",True)
                break

            # Solar for energy
            want_solar=int(2+self.tick/1200*(1+p['ag']))
            if len(solars)<want_solar:
                ox,oy=random.randint(-250,250),random.randint(-250,250)
                if self._try_place(BT.SOLAR,cmd.x+ox,cmd.y+oy,terrain,cmd):
                    self.think.log(f"Build Solar (have {len(solars)}, want {want_solar})",True)

            # Factory
            want_fabs=int(1+self.tick/2000*(1+p['ag']))
            if len(fabs)<want_fabs:
                ox,oy=random.randint(-300,300),random.randint(-300,300)
                if self._try_place(BT.FACTORY,cmd.x+ox,cmd.y+oy,terrain,cmd):
                    self.think.log(f"Build Factory (have {len(fabs)}, want {want_fabs})",True)

            # Turrets for defense
            want_turrets=int(2+p['ag']*5)
            if len(fabs)>=1 and len(turrets)<want_turrets and self.eco.metal>80:
                ox,oy=random.randint(-350,350),random.randint(-350,350)
                if self._try_place(BT.TURRET,cmd.x+ox,cmd.y+oy,terrain,cmd):
                    self.think.log(f"Build Turret (have {len(turrets)}, want {want_turrets})",True)

            # AA guns
            if self.difficulty!=Difficulty.EASY and len(fabs)>=1 and len(aa_guns)<int(1+p['ag']*3):
                ox,oy=random.randint(-300,300),random.randint(-300,300)
                if self._try_place(BT.AA_GUN,cmd.x+ox,cmd.y+oy,terrain,cmd):
                    self.think.log("Build AA Gun",True)

            # Air pad on medium/hard
            if self.difficulty!=Difficulty.EASY and len(fabs)>=1 and len(airpads)<int(p['ag']*2) and self.eco.metal>250:
                ox,oy=random.randint(-280,280),random.randint(-280,280)
                if self._try_place(BT.AIRPAD,cmd.x+ox,cmd.y+oy,terrain,cmd):
                    self.think.log("Build Airpad",True)

            # Shield generator near commander on hard
            if self.difficulty==Difficulty.HARD and len(shields)<2 and self.eco.metal>150:
                ox,oy=random.randint(-180,180),random.randint(-180,180)
                if self._try_place(BT.SHIELD_GEN,cmd.x+ox,cmd.y+oy,terrain,cmd):
                    self.think.log("Build Shield Gen",True)

            # Lab on hard
            if self.difficulty==Difficulty.HARD and len(fabs)>=2 and len(labs)<2 and self.eco.metal>400:
                ox,oy=random.randint(-260,260),random.randint(-260,260)
                if self._try_place(BT.LAB,cmd.x+ox,cmd.y+oy,terrain,cmd):
                    self.think.log("Build Lab",True)

        # ── Move commander toward resources / safety ──────────────────────────
        if cmd and self.tick%FPS==0:
            if self._strategy=="DEFEND" and near_threat:
                # Back away from threat
                threat=near_threat[0]
                dx=cmd.x-threat.x;dy=cmd.y-threat.y
                l=math.hypot(dx,dy) or 1
                cmd.move_target=(cmd.x+dx/l*300,cmd.y+dy/l*300)
                self.think.log("CMD retreating from threat",True)
            elif self._strategy=="EXPAND" and self.tick%(FPS*20)==0:
                # Wander toward unclaimed metal
                free_deps=[d for d in mdeps if not any(dist(d,(b.x,b.y))<TILE*2 for b in self.buildings if b.alive)]
                if free_deps:
                    target=min(free_deps,key=lambda d:dist(d,(cmd.x,cmd.y)))
                    if dist(target,(cmd.x,cmd.y))>200:
                        cmd.move_target=(target[0],target[1])
                        self.think.log(f"CMD moving toward deposit at {int(target[0])},{int(target[1])}",True)

        # ── Unit production ───────────────────────────────────────────────────
        for fac in facs:
            max_q=3 if self.difficulty==Difficulty.HARD else 2
            if len(fac.build_queue)<max_q and self.eco.metal>60 and self.eco.energy>150:
                utypes=fac.produces
                if utypes:
                    if self.difficulty==Difficulty.EASY:
                        ut=random.choice(utypes)
                    elif self.difficulty==Difficulty.MEDIUM:
                        wts=[3 if u in (UT.SOLDIER,UT.TANK,UT.FIGHTER) else 1 for u in utypes]
                        ut=random.choices(utypes,weights=wts)[0]
                    else:
                        # Hard: context-aware unit selection
                        air_threat=any(getattr(e,'dom',None)==Domain.AIR for e in en_u)
                        if air_threat and UT.FIGHTER in utypes:
                            ut=UT.FIGHTER; self.think.log("Queuing Fighter (air threat detected)")
                        else:
                            wts=[1 if u==UT.SCOUT else 4 if u in (UT.TANK,UT.ARTILLERY,UT.BOMBER) else 3 for u in utypes]
                            ut=random.choices(utypes,weights=wts)[0]
                    fac.enqueue(ut,self.eco)
                    self.think.log(f"Queue {USPECS[ut]['name']} at {fac.name}")

        # ── Attack waves ──────────────────────────────────────────────────────
        self.atk_timer-=1
        if self.atk_timer<=0 and have_army:
            lo,hi=self.p['ar'];self.atk_timer=FPS*random.randint(lo,hi)
            self.wave_size=min(self.wave_size+2,self.p['wm'])
            if en_b:
                # Prioritise commander, then most-damaged building
                tgt=(next((e for e in en_b if e.btype==BT.COMMANDER),None) or
                     min(en_b,key=lambda e:e.hfrac()))
                self.think.log(f"WAVE → attack {tgt.name}",True)
                ground_u=[u for u in my_u if u.dom==Domain.GROUND]
                air_u=[u for u in my_u if u.dom==Domain.AIR]
                naval_u=[u for u in my_u if u.dom==Domain.NAVAL]
                if self.difficulty==Difficulty.HARD and len(ground_u)>12:
                    # Split attack: half to main target, half harass
                    split=len(ground_u)//2
                    for u in ground_u[:split]: u.command_move(tgt.x+random.uniform(-60,60),tgt.y+random.uniform(-60,60))
                    alt=en_b[random.randint(0,len(en_b)-1)]
                    for u in ground_u[split:]: u.command_move(alt.x+random.uniform(-80,80),alt.y+random.uniform(-80,80))
                    self.think.log(f"Split attack: {split} on {tgt.name}, {len(ground_u)-split} on {alt.name}")
                else:
                    for u in ground_u: u.command_move(tgt.x+random.uniform(-70,70),tgt.y+random.uniform(-70,70))
                for u in air_u: u.command_move(tgt.x+random.uniform(-40,40),tgt.y+random.uniform(-40,40))
                for u in naval_u:
                    sea_tgt=en_b[random.randint(0,len(en_b)-1)]
                    u.command_move(sea_tgt.x+random.uniform(-80,80),sea_tgt.y+random.uniform(-80,80))

        # ── Micro-management: defend & retreat ────────────────────────────────
        for u in my_u:
            if u.state==UState.IDLE and en:
                near=min(en,key=lambda e:dist((u.x,u.y),(e.x,e.y)))
                react=u.weapon['r']*1.4 if u.weapon else 0
                if dist((u.x,u.y),(near.x,near.y))<react:
                    u.command_attack(near)
                    self.think.log(f"{u.name} auto-engage {near.name}")
            if u.hfrac()<p['rh'] and cmd and u.state!=UState.RETREATING:
                u.state=UState.RETREATING
                u.move_target=(cmd.x+random.uniform(-80,80),cmd.y+random.uniform(-80,80))
                self.think.log(f"{u.name} retreating (HP {int(u.hfrac()*100)}%)",True)

        # ── Commander HP alert ────────────────────────────────────────────────
        if cmd and notifs:
            f=cmd.hfrac()
            if f<0.3 and self._prev_cmd_hp>=0.3:
                notifs.add("⚠ ENEMY COMMANDER CRITICAL!",C_NOTIFY_GOOD,180)
                self.think.log("OWN CMD CRITICAL — need healing!",True)
            self._prev_cmd_hp=f

    def _try_place(self,btype,wx,wy,terrain,cmd):
        sp=BSPECS[btype]
        if not self.eco.can_afford_b(btype): return False
        wx=round(wx/TILE)*TILE+sp['size']*TILE//2
        wy=round(wy/TILE)*TILE+sp['size']*TILE//2
        if cmd and dist((cmd.x,cmd.y),(wx,wy))>BUILD_RANGE: return False
        needs_water=btype==BT.SHIPYARD
        if needs_water:
            if not terrain.is_water(wx,wy): return False
        elif not terrain.walkable(wx,wy): return False
        r=sp['size']*TILE//2+10
        if any(dist((wx,wy),(b.x,b.y))<r+b.radius for b in self.buildings if b.alive): return False
        self.eco.pay_b(btype)
        self.buildings.append(Building(wx,wy,self.team,btype))
        return True

# ── Build Ghost ───────────────────────────────────────────────────────────────
class BuildGhost:
    def __init__(self,btype,terrain,buildings,player_cmd):
        self.btype=btype;self.terrain=terrain;self.buildings=buildings;self.cmd=player_cmd
        self.wx=self.wy=0.;self.valid=False;self.reason=""
    def update(self,wx,wy):
        sp=BSPECS[self.btype];size=sp['size']
        self.wx=round(wx/TILE)*TILE+size*TILE//2
        self.wy=round(wy/TILE)*TILE+size*TILE//2
        needs_water=self.btype==BT.SHIPYARD
        if needs_water:
            if not self.terrain.is_water(self.wx,self.wy): self.valid=False;self.reason="Needs water";return
        elif not self.terrain.walkable(self.wx,self.wy): self.valid=False;self.reason="Not walkable";return
        if self.cmd and dist((self.cmd.x,self.cmd.y),(self.wx,self.wy))>BUILD_RANGE:
            self.valid=False;self.reason="Out of build range";return
        r=size*TILE//2
        if any(dist((self.wx,self.wy),(b.x,b.y))<r+b.radius+4 for b in self.buildings if b.alive):
            self.valid=False;self.reason="Blocked by building";return
        self.valid=True;self.reason=""
    def draw(self,surf,cam,font):
        sp=BSPECS[self.btype];ps=int(sp['size']*TILE*cam.zoom)
        sx,sy=cam.w2s(self.wx,self.wy)
        c=(60,200,100,80) if self.valid else (220,60,40,80)
        out=(60,200,80) if self.valid else (220,60,40)
        s=pygame.Surface((ps,ps),pygame.SRCALPHA);s.fill(c)
        pygame.draw.rect(s,(*out,200),(0,0,ps,ps),2);surf.blit(s,(sx-ps//2,sy-ps//2))
        lbl=font.render(sp['name'],True,out);surf.blit(lbl,(sx-lbl.get_width()//2,sy-lbl.get_height()//2))
        info=self.reason if not self.valid else f"M:{sp['mc']} E:{sp['ec']}"
        ct=font.render(info,True,(*out,200));surf.blit(ct,(sx-ct.get_width()//2,sy+ps//2+4))

# ── UI ────────────────────────────────────────────────────────────────────────
class UI:
    def __init__(self,fs,fm,fl): self.fs=fs;self.fm=fm;self.fl=fl

    def draw(self,surf,eco,sel,tick,mpos,build_range_center=None,cam=None):
        pr=pygame.Rect(0,SCREEN_H-UI_H,SCREEN_W-MINIMAP_W,UI_H)
        ps=pygame.Surface((pr.width,pr.height));ps.fill(C_UI_BG)
        for i in range(0,pr.height,3): pygame.draw.line(ps,C_GRID,(0,i),(pr.width,i))
        surf.blit(ps,pr.topleft)
        pygame.draw.line(surf,C_UI_BORDER,(0,SCREEN_H-UI_H),(SCREEN_W,SCREEN_H-UI_H),1)

        # Build range circle overlay
        if build_range_center and cam:
            cx,cy=cam.w2s(*build_range_center)
            r=int(BUILD_RANGE*cam.zoom)
            rs=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
            pygame.draw.circle(rs,(100,180,255,18),(r+2,r+2),r)
            pygame.draw.circle(rs,(100,180,255,55),(r+2,r+2),r,2)
            surf.blit(rs,(cx-r-2,cy-r-2))

        self._eco(surf,eco,tick)
        if sel: self._sel(surf,sel,eco,mpos)
        else: self._help(surf)

    def _eco(self,surf,eco,tick):
        y=SCREEN_H-UI_H+8
        self._rbar(surf,10,y,eco.metal,eco.max_metal,eco.metal_rate,C_METAL,"M")
        self._rbar(surf,10,y+30,eco.energy,eco.max_energy,eco.energy_rate,C_ENERGY,"E")

    def _rbar(self,surf,x,y,val,mx,rate,col,icon):
        bw=220;surf.blit(self.fm.render(icon,True,col),(x,y+1))
        pygame.draw.rect(surf,(18,26,34),(x+18,y+2,bw,16),border_radius=3)
        fw=int(bw*max(0,val/mx))
        if fw>0:
            pygame.draw.rect(surf,(*col,150),(x+18,y+2,fw,16),border_radius=3)
            sh=pygame.Surface((fw,6),pygame.SRCALPHA);sh.fill((*col,50));surf.blit(sh,(x+18,y+2))
        pygame.draw.rect(surf,(*col,65),(x+18,y+2,bw,16),1,border_radius=3)
        surf.blit(self.fs.render(f"{int(val)}/{int(mx)}  {rate:+.1f}/s",True,(195,210,205)),(x+22,y+4))

    def _sel(self,surf,sel,eco,mpos):
        x0,y0=14,SCREEN_H-UI_H+66
        if isinstance(sel,list):
            surf.blit(self.fm.render(f"{len(sel)} units selected",True,C_TEXT),(x0,y0))
            types={}
            for u in sel: types[u.name]=types.get(u.name,0)+1
            dy=22
            for name,count in list(types.items())[:4]:
                surf.blit(self.fs.render(f"  {count}× {name}",True,C_TEXT_DIM),(x0,y0+dy));dy+=16
            return
        name=getattr(sel,'name','?')
        rrect(surf,C_UI_PANEL,(x0-4,y0-4,190,26),3)
        surf.blit(self.fm.render(name,True,tc(sel.team,glow=True)),(x0,y0))
        hc=sel.hcolor()
        surf.blit(self.fs.render(f"HP {sel.hp}/{sel.max_hp} ({int(sel.hfrac()*100)}%)",True,hc),(x0,y0+22))
        pygame.draw.rect(surf,(20,20,20),(x0,y0+36,165,5),border_radius=2)
        cw=int(165*sel.hfrac())
        if cw>0: pygame.draw.rect(surf,hc,(x0,y0+36,cw,5),border_radius=2)
        extra_y=y0+48
        if isinstance(sel,Building):
            if sel.movable: surf.blit(self.fs.render("Right-click to move commander",True,(140,200,140)),(x0,extra_y));extra_y+=14
            if sel.btype==BT.COMMANDER: self._cmd_menu(surf,eco,x0+205,SCREEN_H-UI_H+8)
            elif sel.produces: self._fac_panel(surf,sel,eco,x0+205,SCREEN_H-UI_H+8,mpos)
        if isinstance(sel,Unit):
            dom_str=sel.dom.name.capitalize()
            surf.blit(self.fs.render(f"[{dom_str}] Spd:{sel.speed:.1f} Rng:{sel.weapon['r'] if sel.weapon else 0}",True,C_TEXT_DIM),(x0,extra_y))

    def _cmd_menu(self,surf,eco,x0,y0):
        surf.blit(self.fs.render("BUILD  [Tab=select cmd]  [1-0 keys]",True,C_TEXT_DIM),(x0,y0+2))
        pygame.draw.line(surf,C_UI_BORDER,(x0,y0+14),(x0+580,y0+14))
        cols=5
        for i,btype in enumerate(BUILD_FROM_CMD):
            sp=BSPECS[btype];col=i%cols;row=i//cols
            cx=x0+col*118;cy=y0+18+row*58
            can=eco.can_afford_b(btype)
            rrect(surf,C_UI_HI if can else C_UI_PANEL,(cx,cy,115,54),4,1,(80,120,100) if can else C_UI_BORDER)
            key=str(i+1) if i<9 else "0"
            surf.blit(self.fs.render(f"[{key}]",True,(200,220,200) if can else (70,80,75)),(cx+4,cy+4))
            surf.blit(self.fs.render(sp['name'],True,C_TEXT if can else C_TEXT_DIM),(cx+26,cy+4))
            mc=C_METAL if eco.metal>=sp['mc'] else C_HEALTH_R
            ec=C_ENERGY if eco.energy>=sp['ec'] else C_HEALTH_R
            surf.blit(self.fs.render(f"M:{sp['mc']}",True,mc),(cx+4,cy+32))
            surf.blit(self.fs.render(f"E:{sp['ec']}",True,ec),(cx+65,cy+32))

    def _fac_panel(self,surf,fac,eco,x0,y0,mpos):
        surf.blit(self.fs.render(f"PRODUCE  {fac.name}  [1-{len(fac.produces)}]",True,C_TEXT_DIM),(x0,y0+2))
        pygame.draw.line(surf,C_UI_BORDER,(x0,y0+14),(x0+600,y0+14))
        for i,utype in enumerate(fac.produces):
            sp=USPECS[utype];cx=x0+i*118;cy=y0+18
            can=eco.metal>=sp['mc'] and eco.energy>=sp['ec']
            rrect(surf,C_UI_HI if can else C_UI_PANEL,(cx,cy,115,54),4,1,(80,120,100) if can else C_UI_BORDER)
            dom_col={'GROUND':C_TEXT,'AIR':(180,200,255),'NAVAL':(100,180,220)}[sp['dom'].name]
            surf.blit(self.fs.render(f"[{i+1}]",True,(200,220,200) if can else (70,80,75)),(cx+4,cy+4))
            surf.blit(self.fs.render(sp['name'],True,dom_col if can else C_TEXT_DIM),(cx+26,cy+4))
            surf.blit(self.fs.render(f"M:{sp['mc']}",True,C_METAL),(cx+4,cy+32))
            surf.blit(self.fs.render(f"E:{sp['ec']}",True,C_ENERGY),(cx+65,cy+32))
        # Queue
        qx=x0;qy=y0+80
        surf.blit(self.fs.render("BUILD QUEUE  [X=cancel last]",True,C_TEXT_DIM),(qx,qy))
        qy+=14;sw=92;sh=34;gap=4
        if fac.build_queue:
            for qi,item in enumerate(fac.build_queue[:6]):
                utype2,total,rem=item[0],item[1],item[2]
                usp=USPECS[utype2];bx2=qx+qi*(sw+gap);by2=qy
                is_act=(qi==0)
                hov=pygame.Rect(bx2,by2,sw,sh).collidepoint(*mpos) if mpos else False
                rrect(surf,(30,52,46) if is_act else (18,28,26),(bx2,by2,sw,sh),3,1,
                      C_ENERGY if is_act else ((80,105,92) if hov else C_UI_BORDER))
                surf.blit(self.fs.render(usp['name'],True,C_TEXT if is_act else C_TEXT_DIM),(bx2+4,by2+3))
                if is_act:
                    prog=1.-rem/total;pw=int((sw-8)*prog)
                    pygame.draw.rect(surf,(18,26,22),(bx2+4,by2+18,sw-8,8),border_radius=2)
                    if pw>0: pygame.draw.rect(surf,C_ENERGY,(bx2+4,by2+18,pw,8),border_radius=2)
                    pt2=self.fs.render(f"{int(prog*100)}%",True,C_ENERGY)
                    surf.blit(pt2,(bx2+sw//2-pt2.get_width()//2,by2+18))
                elif hov: surf.blit(self.fs.render("[X]cancel",True,C_HEALTH_R),(bx2+4,by2+16))
                else: surf.blit(self.fs.render(f"#{qi+1}",True,C_TEXT_DIM),(bx2+4,by2+16))
        else:
            surf.blit(self.fs.render("Empty — press 1-5",True,C_TEXT_DIM),(qx,qy+4))

    def _help(self,surf):
        x0,y0=14,SCREEN_H-UI_H+66
        for i,h in enumerate([
            "Left click / drag: select   Right click: move / attack / rally",
            "Commander selected → right-click to MOVE IT   Tab: select commander",
            "1-0: build structure (cmd) or queue unit (factory)   X: cancel queue",
            "+/- or scroll: zoom   Arrows/WASD: pan   Del: self-destruct   Esc: cancel",
        ]): surf.blit(self.fs.render(h,True,C_TEXT_DIM),(x0,y0+i*20))

# ── Minimap ───────────────────────────────────────────────────────────────────
class Minimap:
    def __init__(self):
        self.rect=pygame.Rect(SCREEN_W-MINIMAP_W,SCREEN_H-MINIMAP_H,MINIMAP_W,MINIMAP_H)
        self._cache=None
    def _render(self,terrain):
        s=pygame.Surface((MINIMAP_W,MINIMAP_H));sx=MINIMAP_W/terrain.tw;sy=MINIMAP_H/terrain.th
        for ty in range(terrain.th):
            for tx in range(terrain.tw):
                t=terrain.data[ty][tx]
                c=C_WATER if t==1 else(C_MOUNTAIN if t==2 else(C_TERRAIN2 if (tx+ty)%2==0 else C_TERRAIN))
                if terrain.metal[ty][tx]: c=C_METAL_D
                pygame.draw.rect(s,c,(int(tx*sx),int(ty*sy),max(1,int(sx)+1),max(1,int(sy)+1)))
        return s
    def draw(self,surf,terrain,buildings,units,cam,tick):
        if self._cache is None or tick%600==0: self._cache=self._render(terrain)
        s=self._cache.copy()
        for b in buildings:
            if not b.alive: continue
            pygame.draw.rect(s,tc(b.team),(int(b.x/MAP_W*MINIMAP_W)-2,int(b.y/MAP_H*MINIMAP_H)-2,5,5))
        for u in units:
            if not u.alive: continue
            col=tc(u.team) if u.dom==Domain.GROUND else((180,200,255) if u.dom==Domain.AIR else(80,150,210))
            pygame.draw.circle(s,col,(int(u.x/MAP_W*MINIMAP_W),int(u.y/MAP_H*MINIMAP_H)),2)
        vx=int(cam.x/MAP_W*MINIMAP_W);vy=int(cam.y/MAP_H*MINIMAP_H)
        vw=int((SCREEN_W/cam.zoom)/MAP_W*MINIMAP_W);vh=int(((SCREEN_H-UI_H)/cam.zoom)/MAP_H*MINIMAP_H)
        pygame.draw.rect(s,(180,200,190),(vx,vy,vw,vh),1)
        pygame.draw.rect(surf,(10,16,22),self.rect);surf.blit(s,self.rect)
        pygame.draw.rect(surf,C_UI_BORDER,self.rect,2)
    def world_from_click(self,mx,my):
        if not self.rect.collidepoint(mx,my): return None
        return (mx-self.rect.x)/MINIMAP_W*MAP_W,(my-self.rect.y)/MINIMAP_H*MAP_H

# ── Difficulty screen ─────────────────────────────────────────────────────────
def diff_screen(screen,clock):
    ft=pygame.font.SysFont("monospace",44,bold=True)
    fs=pygame.font.SysFont("monospace",13)
    fb=pygame.font.SysFont("monospace",22,bold=True)
    opts=[(Difficulty.EASY,"EASY",C_HEALTH_G,"Slower AI · small waves · reduced economy","[1]"),
          (Difficulty.MEDIUM,"MEDIUM",C_ENERGY,"Balanced · scales over time · fair fights","[2]"),
          (Difficulty.HARD,"HARD",C_P2,"Aggressive · air+naval · split attacks · verbose AI","[3]")]
    sel=None;tick=0
    while sel is None:
        tick+=1;screen.fill(C_BG)
        for gx in range(0,SCREEN_W,40): pygame.draw.line(screen,C_GRID,(gx,0),(gx,SCREEN_H))
        for gy in range(0,SCREEN_H,40): pygame.draw.line(screen,C_GRID,(0,gy),(SCREEN_W,gy))
        t=ft.render("TOTAL RECURSION",True,C_P1_GLOW);screen.blit(t,(SCREEN_W//2-t.get_width()//2,int(SCREEN_H*0.18)))
        sub=fs.render("select difficulty",True,C_TEXT_DIM);screen.blit(sub,(SCREEN_W//2-sub.get_width()//2,int(SCREEN_H*0.3)))
        mx,my=pygame.mouse.get_pos();bw,bh=320,94;by0=int(SCREEN_H*0.35)
        for i,(diff,label,color,desc,key) in enumerate(opts):
            bx=SCREEN_W//2-bw//2;by=by0+i*(bh+20);rect=pygame.Rect(bx,by,bw,bh)
            hov=rect.collidepoint(mx,my)
            rrect(screen,lerp_c(C_UI_PANEL,C_UI_HI,0.7 if hov else 0),rect,8,2,color if hov else C_UI_BORDER)
            if hov: gfx_glow(screen,color,(bx+bw//2,by+bh//2),bw//3,18)
            lt=fb.render(label,True,color if hov else lerp_c(color,C_TEXT_DIM,0.4))
            screen.blit(lt,(bx+bw//2-lt.get_width()//2,by+12))
            screen.blit(fs.render(key,True,C_TEXT_DIM),(bx+10,by+14))
            screen.blit(fs.render(desc,True,C_TEXT_DIM),(bx+bw//2-fs.size(desc)[0]//2,by+52))
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit();sys.exit()
            if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                for i,(diff,*_) in enumerate(opts):
                    bx=SCREEN_W//2-bw//2;by=by0+i*(bh+20)
                    if pygame.Rect(bx,by,bw,bh).collidepoint(mx,my): sel=diff
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_1: sel=Difficulty.EASY
                if ev.key==pygame.K_2: sel=Difficulty.MEDIUM
                if ev.key==pygame.K_3: sel=Difficulty.HARD
        pygame.display.flip();clock.tick(60)
    return sel

# ── Game ──────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self,difficulty):
        self.screen=pygame.display.set_mode((SCREEN_W,SCREEN_H),pygame.FULLSCREEN)
        pygame.display.set_caption("TOTAL RECURSION v3")
        self.clock=pygame.time.Clock()
        self.fs=pygame.font.SysFont("monospace",12)
        self.fm=pygame.font.SysFont("monospace",14,bold=True)
        self.fl=pygame.font.SysFont("monospace",20,bold=True)
        self.fxl=pygame.font.SysFont("monospace",52,bold=True)
        self.fs_think=pygame.font.SysFont("monospace",11)

        self.difficulty=difficulty
        self.sound=Sound();self.parts=Particles();self.shake=Shake()
        self.notifs=Notifs(self.fs)
        self.cam=Camera();self.terrain=Terrain(MAP_W,MAP_H);self.mdeps=self.terrain.metal_deps()

        # ── Shared lists — never reassigned ──────────────────────────────────
        self.buildings: List[Building]=[]
        self.units: List[Unit]=[]
        self.projs: List[Proj]=[]
        self.explosions: List[Explosion]=[]

        dp=DIFF[difficulty]
        self.player_eco=Economy()
        self.ai_eco=Economy(bm=dp['bo'],be=dp['bo']*2)
        self.ai_eco_mult=dp['eco']

        p_cmd=Building(3*TILE*2+TILE,3*TILE*2+TILE,Team.PLAYER,BT.COMMANDER)
        a_cmd=Building(MAP_W-3*TILE*2-TILE,MAP_H-3*TILE*2-TILE,Team.AI,BT.COMMANDER)
        self.buildings+=[p_cmd,a_cmd]

        self.ai=AI(Team.AI,self.ai_eco,self.buildings,self.units,difficulty)
        self.ui=UI(self.fs,self.fm,self.fl);self.minimap=Minimap()

        self.cam.center_on(p_cmd.x,p_cmd.y)

        self.selected: List[Entity]=[]
        self.drag_start=None;self.drag_end=None
        self.build_mode=False;self.ghost=None;self.pending_bt=None

        self.tick=0;self.game_over=None;self._atk_cd=0
        self.show_think=True  # AI verbose panel toggle
        self._tsurf=None;self._build_tsurf()
        self.notifs.add(f"Difficulty: {difficulty.value}  |  Tab=select commander  |  V=toggle AI log",C_NOTIFY_INFO,200)

    def _build_tsurf(self):
        s=pygame.Surface((MAP_W,MAP_H))
        for ty in range(self.terrain.th):
            for tx in range(self.terrain.tw):
                t=self.terrain.data[ty][tx]
                if t==0: col=[C_TERRAIN,C_TERRAIN2,C_TERRAIN3][(tx*7+ty*13)%3]
                elif t==1: col=C_WATER if (tx+ty)%2==0 else C_WATER2
                else: col=C_MOUNTAIN if (tx+ty)%2==0 else C_MOUNTAIN2
                pygame.draw.rect(s,col,(tx*TILE,ty*TILE,TILE,TILE))
        for dep in self.mdeps:
            pygame.draw.circle(s,C_METAL_D,(int(dep[0]),int(dep[1])),TILE//3)
            pygame.draw.circle(s,(115,145,135),(int(dep[0]),int(dep[1])),TILE//3,1)
        for tx in range(0,MAP_W,TILE*4): pygame.draw.line(s,C_GRID,(tx,0),(tx,MAP_H))
        for ty in range(0,MAP_H,TILE*4): pygame.draw.line(s,C_GRID,(0,ty),(MAP_W,ty))
        self._tsurf=s

    def _all(self): return self.buildings+self.units
    def _player_cmd(self):
        return next((b for b in self.buildings if b.team==Team.PLAYER and b.btype==BT.COMMANDER and b.alive),None)

    def run(self):
        while True:
            self.clock.tick(FPS);self._events()
            if not self.game_over: self._update()
            self._draw();pygame.display.flip()

    def _events(self):
        mx,my=pygame.mouse.get_pos();mx-=self.shake.ox;my-=self.shake.oy
        in_ui=my>SCREEN_H-UI_H
        in_minimap=self.minimap.rect.collidepoint(mx,my)
        in_think=(self.show_think and SCREEN_W-MINIMAP_W<=mx<=SCREEN_W and 0<=my<=SCREEN_H-MINIMAP_H-UI_H-10)

        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit();sys.exit()
            if ev.type==pygame.KEYDOWN: self._key(ev.key)
            if ev.type==pygame.MOUSEWHEEL:
                if not in_ui:
                    if ev.y>0: self.cam.zi()
                    else: self.cam.zo()
            if ev.type==pygame.MOUSEBUTTONDOWN:
                if ev.button==4 and not in_ui: self.cam.zi()
                if ev.button==5 and not in_ui: self.cam.zo()

                if ev.button==1:
                    wp=self.minimap.world_from_click(mx,my)
                    if wp:
                        # click minimap → center camera there
                        self.cam.center_on(*wp)
                    elif in_ui or in_think:
                        pass  # ignore clicks in panels
                    else:
                        if self.build_mode and self.ghost and self.ghost.valid: self._place_b()
                        else: self.drag_start=(mx,my)

                if ev.button==3:
                    wp=self.minimap.world_from_click(mx,my)
                    if wp:
                        self._rclick(*wp)
                    elif not in_ui and not in_think:
                        wx,wy=self.cam.s2w(mx,my)
                        if self.build_mode: self._cancel_b()
                        else: self._rclick(wx,wy)

            if ev.type==pygame.MOUSEBUTTONUP:
                if ev.button==1 and self.drag_start:
                    if self.drag_end: self._box_sel()
                    else: self._lclick(*self.drag_start)
                    self.drag_start=None;self.drag_end=None

            if ev.type==pygame.MOUSEMOTION:
                if self.drag_start:
                    if abs(mx-self.drag_start[0])>4 or abs(my-self.drag_start[1])>4:
                        self.drag_end=(mx,my)
                if self.ghost:
                    wx,wy=self.cam.s2w(mx,my);self.ghost.update(wx,wy)

    def _key(self,key):
        if key==pygame.K_ESCAPE:
            if self.build_mode: self._cancel_b()
            else: self.selected.clear()
            return
        if key==pygame.K_F11:
            pygame.display.toggle_fullscreen()
        if key==pygame.K_v: self.show_think=not self.show_think
        if key in (pygame.K_EQUALS,pygame.K_PLUS): self.cam.zi()
        if key==pygame.K_MINUS: self.cam.zo()

        # Tab: select commander and center on it
        if key==pygame.K_TAB:
            cmd=self._player_cmd()
            if cmd:
                self.selected=[cmd];self.cam.center_on(cmd.x,cmd.y)
                self.sound.play('sel',cd=5)
                self.notifs.add("Commander selected",C_NOTIFY_INFO,60)
            return

        if key in (pygame.K_DELETE,pygame.K_BACKSPACE):
            for e in self.selected:
                if e.alive and not (isinstance(e,Building) and e.movable):
                    e.take_damage(e.hp)
                    self.explosions.append(Explosion(e.x,e.y,2. if isinstance(e,Building) else 1.,self.parts,self.sound))

        if key==pygame.K_x:
            facs=[e for e in self.selected if isinstance(e,Building) and e.produces and e.team==Team.PLAYER]
            for fac in facs:
                if fac.build_queue:
                    fac.dequeue(len(fac.build_queue)-1,self.player_eco)
                    self.notifs.add("Queue item cancelled",C_NOTIFY_INFO,60)

        # Number keys
        num=-1
        if pygame.K_1<=key<=pygame.K_9: num=key-pygame.K_1
        if key==pygame.K_0: num=9
        if num>=0:
            cmds=[e for e in self.selected if isinstance(e,Building) and e.btype==BT.COMMANDER and e.team==Team.PLAYER]
            if cmds and num<len(BUILD_FROM_CMD):
                btype=BUILD_FROM_CMD[num]
                if self.player_eco.can_afford_b(btype):
                    self._enter_b(btype,cmds[0])
                else: self.notifs.add("Cannot afford!",C_NOTIFY_BAD,80)
                return
            facs=[e for e in self.selected if isinstance(e,Building) and e.produces and e.team==Team.PLAYER]
            if facs and num<len(facs[0].produces):
                fac=facs[0];ut=facs[0].produces[num]
                cmd=self._player_cmd()
                ok,reason=fac.enqueue(ut,self.player_eco,cmd)
                if ok: self.notifs.add(f"Queued: {USPECS[ut]['name']}",C_NOTIFY_INFO,70)
                elif reason=='out_of_range': self.notifs.add("Factory out of commander range!",C_NOTIFY_BAD,100)
                else: self.notifs.add("Cannot afford!",C_NOTIFY_BAD,80)

    def _enter_b(self,btype,player_cmd):
        self.build_mode=True;self.pending_bt=btype
        self.ghost=BuildGhost(btype,self.terrain,self.buildings,player_cmd)
    def _cancel_b(self): self.build_mode=False;self.ghost=None;self.pending_bt=None

    def _place_b(self):
        if not self.pending_bt or not self.ghost: return
        btype=self.pending_bt
        if not self.player_eco.can_afford_b(btype): self.notifs.add("Cannot afford!",C_NOTIFY_BAD,80);return
        self.player_eco.pay_b(btype)
        b=Building(self.ghost.wx,self.ghost.wy,Team.PLAYER,btype)
        if btype==BT.METAL_X:
            near=min(self.mdeps,key=lambda d:dist(d,(b.x,b.y)),default=None)
            if near and dist(near,(b.x,b.y))<TILE*2: b.x,b.y=near
        self.buildings.append(b)
        self.sound.play('placed')
        self.notifs.add(f"Built: {BSPECS[btype]['name']}",C_NOTIFY_GOOD,90)
        if not (pygame.key.get_mods()&pygame.KMOD_SHIFT): self._cancel_b()

    def _rclick(self,wx,wy):
        if not self.selected: return
        # Commander movement
        cmd_sel=[e for e in self.selected if isinstance(e,Building) and e.movable and e.team==Team.PLAYER]
        if cmd_sel:
            cmd=cmd_sel[0]
            if self.terrain.walkable(wx,wy):
                cmd.move_target=(wx,wy)
                self.sound.play('cmd_move',cd=5)
                self.notifs.add("Commander moving",C_NOTIFY_INFO,60)
            return
        # Attack or move units
        target=self._at(wx,wy,enemy_only=True)
        for e in self.selected:
            if isinstance(e,Unit) and e.team==Team.PLAYER:
                if target: e.command_attack(target)
                else: e.command_move(wx,wy)
        for e in self.selected:
            if isinstance(e,Building) and e.produces: e.rally=(wx,wy)

    def _at(self,wx,wy,enemy_only=False):
        best=None;bd=1e9
        for e in self._all():
            if not e.alive: continue
            if enemy_only and e.team==Team.PLAYER: continue
            d=dist((wx,wy),(e.x,e.y))
            if d<e.radius+6 and d<bd: best=e;bd=d
        return best

    def _lclick(self,mx,my):
        wx,wy=self.cam.s2w(mx,my);e=self._at(wx,wy)
        mods=pygame.key.get_mods()
        if e:
            if mods&pygame.KMOD_SHIFT:
                if e in self.selected: self.selected.remove(e)
                else: self.selected.append(e)
            else:
                if self.selected!=[e]: self.sound.play('sel',cd=5)
                self.selected=[e]
        elif not (mods&pygame.KMOD_SHIFT): self.selected.clear()

    def _box_sel(self):
        if not self.drag_start or not self.drag_end: return
        x1,y1=min(self.drag_start[0],self.drag_end[0]),min(self.drag_start[1],self.drag_end[1])
        x2,y2=max(self.drag_start[0],self.drag_end[0]),max(self.drag_start[1],self.drag_end[1])
        sel=[]
        for e in self._all():
            if not e.alive: continue
            sx,sy=self.cam.w2s(e.x,e.y)
            if x1<=sx<=x2 and y1<=sy<=y2: sel.append(e)
        mods=pygame.key.get_mods()
        if mods&pygame.KMOD_SHIFT: self.selected+=sel
        else: self.selected=sel
        pl=[e for e in self.selected if e.team==Team.PLAYER]
        if pl: self.selected=pl

    def _update(self):
        self.tick+=1
        all_e=self._all()
        pb=[b for b in self.buildings if b.team==Team.PLAYER]
        ab=[b for b in self.buildings if b.team==Team.AI]
        self.player_eco.tick(pb,1.);self.ai_eco.tick(ab,self.ai_eco_mult)

        for b in self.buildings:
            if b.alive:
                b.update_move(self.terrain)
                if b.btype==BT.SHIELD_GEN: b.update_shield(all_e)

        # Production
        new_units=[]
        for b in self.buildings:
            if not b.alive: continue
            eco=self.player_eco if b.team==Team.PLAYER else self.ai_eco
            res=b.update_prod()
            if res:
                rally=b.rally if b.rally else (b.x+b.radius*2,b.y)
                ang=random.uniform(0,math.pi*2);sr=b.radius+20
                u=Unit(rally[0]+math.cos(ang)*sr,rally[1]+math.sin(ang)*sr,b.team,res)
                new_units.append(u)
                if b.team==Team.PLAYER:
                    self.sound.play('done')
                    self.notifs.add(f"Unit ready: {USPECS[res]['name']}",C_NOTIFY_GOOD,80)
        self.units.extend(new_units)

        for u in self.units:
            if u.alive: u.update(all_e,self.projs,self.terrain,self.parts,self.sound)
        for b in self.buildings:
            if b.alive and b.weapon: b.try_fire(all_e,self.projs,self.sound)

        hit_player=False
        for p in self.projs:
            hit=p.update(all_e)
            if hit and p.team==Team.AI: hit_player=True
        if hit_player and self._atk_cd<=0:
            self._atk_cd=FPS*8;self.sound.play('atk')
            self.notifs.add("⚠ UNDER ATTACK!",C_NOTIFY_BAD,160)
        self._atk_cd=max(0,self._atk_cd-1)

        p_cmd=self._player_cmd()
        for e in all_e:
            if not e.alive and not e._exploded:
                e._exploded=True
                sz=2. if isinstance(e,Building) else 1.
                self.explosions.append(Explosion(e.x,e.y,sz,self.parts,self.sound))
                if p_cmd:
                    d=dist((p_cmd.x,p_cmd.y),(e.x,e.y))
                    self.shake.add(max(0,(600-d)/600*10*sz))

        # In-place cleanup (preserves list identity for AI)
        for lst in (self.buildings,self.units,self.projs):
            i=len(lst)-1
            while i>=0:
                item=lst[i]
                alive=item.alive if hasattr(item,'alive') else item.alive
                if not alive: lst.pop(i)
                i-=1
        i=len(self.explosions)-1
        while i>=0:
            if not self.explosions[i].update(): self.explosions.pop(i)
            i-=1
        self.selected=[e for e in self.selected if e.alive]

        self.ai.update(all_e,self.projs,self.terrain,self.mdeps,self.notifs,self.sound)

        keys=pygame.key.get_pressed();self.cam.update(keys)
        mx,my=pygame.mouse.get_pos();edge=20;spd=10/self.cam.zoom
        if mx<edge: self.cam.x-=spd
        if mx>SCREEN_W-edge: self.cam.x+=spd
        if my<edge: self.cam.y-=spd
        if my>SCREEN_H-UI_H-edge: self.cam.y+=spd
        self.cam.clamp();self.shake.update()

        pc=[b for b in self.buildings if b.team==Team.PLAYER and b.btype==BT.COMMANDER and b.alive]
        ac=[b for b in self.buildings if b.team==Team.AI and b.btype==BT.COMMANDER and b.alive]
        if not pc and not self.game_over: self.game_over="lose"
        if not ac and not self.game_over: self.game_over="win"

    def _draw(self):
        surf=self.screen;cam=self.cam;ox,oy=self.shake.ox,self.shake.oy
        surf.fill(C_BG)
        ds=pygame.Surface((SCREEN_W,SCREEN_H)) if (ox or oy) else surf
        if ox or oy: ds.fill(C_BG)

        vx=int(cam.x*cam.zoom);vy=int(cam.y*cam.zoom)
        scaled=pygame.transform.scale(self._tsurf,(int(MAP_W*cam.zoom),int(MAP_H*cam.zoom)))
        ds.blit(scaled,(-vx,-vy))

        # Build range ring when commander selected
        p_cmd=self._player_cmd()
        if p_cmd and any(isinstance(e,Building) and e.btype==BT.COMMANDER for e in self.selected):
            cx,cy=cam.w2s(p_cmd.x,p_cmd.y);r=int(BUILD_RANGE*cam.zoom)
            rs=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
            pygame.draw.circle(rs,(100,180,255,15),(r+2,r+2),r)
            pygame.draw.circle(rs,(100,180,255,50),(r+2,r+2),r,2)
            ds.blit(rs,(cx-r-2,cy-r-2))

        # Weapon range rings
        for e in self.selected:
            if isinstance(e,Building) and e.weapon and e.btype!=BT.COMMANDER:
                sx,sy=cam.w2s(e.x,e.y);r=int(e.weapon['r']*cam.zoom)
                rs=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
                pygame.draw.circle(rs,(*C_LASER,15),(r+2,r+2),r)
                pygame.draw.circle(rs,(*C_LASER,50),(r+2,r+2),r,1)
                ds.blit(rs,(sx-r-2,sy-r-2))

        # Air shadows
        for u in self.units:
            if u.alive and u.dom==Domain.AIR:
                sx,sy=cam.w2s(u.x,u.y);r=max(3,int(u.radius*cam.zoom))
                ss=pygame.Surface((r*3,r*2),pygame.SRCALPHA)
                pygame.draw.ellipse(ss,(0,0,0,30),(0,0,r*3,r*2))
                ds.blit(ss,(sx-r*3//2,sy+r//2+6))

        for b in self.buildings:
            if b.alive: b.draw(ds,cam,b in self.selected,self.tick)
        for u in self.units:
            if u.alive: u.draw(ds,cam,u in self.selected,self.tick)
        for p in self.projs: p.draw(ds,cam)
        for ex in self.explosions: ex.draw(ds,cam)
        self.parts.draw(ds,cam)

        # Drag box
        if self.drag_start and self.drag_end:
            x1,y1=self.drag_start;x2,y2=self.drag_end
            rect=pygame.Rect(min(x1,x2),min(y1,y2),abs(x2-x1),abs(y2-y1))
            s2=pygame.Surface((max(1,rect.width),max(1,rect.height)),pygame.SRCALPHA)
            s2.fill((60,200,100,18));ds.blit(s2,rect.topleft)
            pygame.draw.rect(ds,C_SEL,rect,1)

        if self.ghost: self.ghost.draw(ds,cam,self.fs)
        if ox or oy: surf.blit(ds,(ox,oy))

        # ── UI overlays (no shake) ────────────────────────────────────────────
        mx,my=pygame.mouse.get_pos()
        single=self.selected[0] if len(self.selected)==1 else(self.selected if len(self.selected)>1 else None)
        self.ui.draw(surf,self.player_eco,single,self.tick,(mx,my),
                     build_range_center=(p_cmd.x,p_cmd.y) if (p_cmd and self.build_mode) else None,
                     cam=cam)

        self.minimap.draw(surf,self.terrain,self.buildings,self.units,cam,self.tick)

        # AI think panel (right side, above minimap)
        if self.show_think:
            panel_h=SCREEN_H-MINIMAP_H-UI_H-10
            if panel_h>60:
                self.ai.think.draw(surf,self.fs_think,SCREEN_W-MINIMAP_W,0,MINIMAP_W,panel_h)

        # HUD
        diff_t=self.fs.render(f"AI:{self.difficulty.value}  V=toggle log",True,C_TEXT_DIM)
        surf.blit(diff_t,(SCREEN_W-MINIMAP_W+4,SCREEN_H-MINIMAP_H-16))
        fps_t=self.fs.render(f"FPS:{int(self.clock.get_fps())}  U:{len(self.units)}  B:{len(self.buildings)}",True,C_TEXT_DIM)
        surf.blit(fps_t,(8,8))
        self.notifs.draw(surf)

        if self.game_over:
            ov=pygame.Surface((SCREEN_W,SCREEN_H-UI_H),pygame.SRCALPHA);ov.fill((0,0,0,140));surf.blit(ov,(0,0))
            msg="VICTORY!" if self.game_over=="win" else "DEFEAT!"
            col=C_SEL if self.game_over=="win" else C_P2
            t=self.fxl.render(msg,True,col);surf.blit(t,(SCREEN_W//2-t.get_width()//2,(SCREEN_H-UI_H)//2-t.get_height()//2))
            gfx_glow(surf,col,(SCREEN_W//2,(SCREEN_H-UI_H)//2),130,40)
            sub=self.fm.render("Press Escape to exit",True,C_TEXT_DIM)
            surf.blit(sub,(SCREEN_W//2-sub.get_width()//2,(SCREEN_H-UI_H)//2+60))
            if pygame.key.get_pressed()[pygame.K_ESCAPE]: pygame.quit();sys.exit()

if __name__=="__main__":
    clock=pygame.time.Clock()
    # Use current display for difficulty screen too
    screen=pygame.display.set_mode((SCREEN_W,SCREEN_H),pygame.FULLSCREEN)
    diff=diff_screen(screen,clock)
    Game(diff).run()
