"""
TOTAL RECURSION v4 — Enhanced Edition
• Pseudo-3D isometric rendering with height, shadows, depth sorting
• 20 unit types: Ground / Air / Naval / Mech / Psionic
• Full stats panel (F1): kills, damage, economy sparklines
• 5-phase AI: Scout→Expand→Fortify→Attack→Dominate + verbose log
• Commander moves; build/produce range enforced
• Fullscreen, Tab=select commander, minimap click to jump
• Sound, particles, screen shake, build queue with cancel
"""
import pygame, math, random, sys, array, collections
from typing import List, Dict, Optional
from enum import Enum, auto

pygame.init()
_info = pygame.display.Info()
SCREEN_W = _info.current_w
SCREEN_H = _info.current_h
MAP_W, MAP_H = 5120, 5120
TILE         = 40
FPS          = 60
UI_H         = 210
SIDE_W       = 250
MINIMAP_W    = 220
MINIMAP_H    = 220
BUILD_RANGE  = 800
PRODUCE_RANGE= 800

# ── ISO helpers ───────────────────────────────────────────────────────────────
ISO_SX = math.cos(math.radians(30))
ISO_SY = math.sin(math.radians(30)) * 0.5
SHADOW_OFF = 7

def iso(wx, wy, cam):
    rx = wx - cam.x; ry = wy - cam.y
    T = cam.tilt; z = cam.zoom
    sx = ((1-T)*rx + T*(rx-ry)*ISO_SX) * z
    sy = ((1-T)*ry + T*(rx+ry)*ISO_SY) * z
    return int(sx + (SCREEN_W - SIDE_W)//2), int(sy + (SCREEN_H - UI_H)//2)

def s2w(sx, sy, cam):
    sx -= (SCREEN_W - SIDE_W)//2; sy -= (SCREEN_H - UI_H)//2
    T = cam.tilt; z = cam.zoom
    A = z * (1-T + T*ISO_SX); B = -z * T * ISO_SX
    C = z * T * ISO_SY; D = z * (1-T + T*ISO_SY)
    det = A*D - B*C
    return (sx*D - sy*B)/det + cam.x, (sy*A - sx*C)/det + cam.y

def clamp_color(c):
    return tuple(max(0, min(255, v)) for v in c)

# ── Palette ───────────────────────────────────────────────────────────────────
C = {k: clamp_color(v) for k, v in {
    "bg":(6,10,16), "grid":(16,24,32),
    "g0":(28,44,32),"g1":(22,36,26),"g2":(34,50,38),
    "w0":(6,18,40), "w1":(10,26,52),
    "m0":(50,48,46),"m1":(65,62,58),
    "dep":(80,105,95),
    "p1":(55,155,235),"p1d":(18,70,140),"p1g":(110,190,255),
    "p2":(235,68,48), "p2d":(130,24,14),"p2g":(255,118,98),
    "sel":(85,225,105),
    "hg":(50,215,50),"hy":(215,198,30),"hr":(215,48,28),
    "en":(235,198,30),"mt":(155,215,195),
    "tx":(195,212,206),"txd":(88,103,98),
    "ubg":(7,11,17),"upan":(14,20,28),"ubrd":(32,52,48),"uhi":(42,78,68),
    "bul":(255,235,90),"las":(62,210,255),"las2":(150,240,255),
    "shl":(255,172,52),"mis":(220,182,62),"bom":(80,62,30),
    "pla":(180,62,255),"psi":(220,100,255),"smk":(72,82,92),
    "nok":(62,220,102),"nob":(220,60,60),"nin":(182,202,222),
    "abg":(7,13,9),"abd":(28,58,38),"atx":(78,202,102),"adm":(48,108,58),
    "sbg":(7,10,14),"sln":(42,62,52),
    "wsh":(38,88,128),
}.items()}
EXP = [(255,220,60),(255,140,20),(200,60,10),(120,30,5)]

def tc(team, dark=False, glow=False):
    if team.value==1: return C["p1g"] if glow else (C["p1d"] if dark else C["p1"])
    return C["p2g"] if glow else (C["p2d"] if dark else C["p2"])

def lerp_c(a, b, t):
    t=max(0.,min(1.,t)); return clamp_color(tuple(int(a[i]+t*(b[i]-a[i])) for i in range(3)))

def hcol(f):
    return lerp_c(C["hy"],C["hg"],(f-0.5)*2) if f>0.5 else lerp_c(C["hr"],C["hy"],f*2)

def dist(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])

def sfx_glow(surf,color,pos,r,a=60):
    if r<2: return
    s=pygame.Surface((r*4+2,r*4+2),pygame.SRCALPHA)
    for ri in range(r,0,-3): pygame.draw.circle(s,(*color,int(a*ri/r)),(r*2+1,r*2+1),ri)
    surf.blit(s,(pos[0]-r*2-1,pos[1]-r*2-1))

def rrect(surf,color,rect,rad=4,bw=0,bc=None):
    pygame.draw.rect(surf,clamp_color(color),rect,border_radius=rad)
    if bw and bc: pygame.draw.rect(surf,clamp_color(bc),rect,bw,border_radius=rad)

def shadow_el(surf,cx,cy,rx,ry):
    s=pygame.Surface((rx*2+2,ry*2+2),pygame.SRCALPHA)
    pygame.draw.ellipse(s,(0,0,0,38),(0,0,rx*2,ry*2)); surf.blit(s,(cx-rx,cy-ry))

def draw_box3d(surf,cx,cy,w,h,d,tc2,sc,fc,brd=1):
    top=[(cx,cy-d),(cx+w,cy),(cx,cy+d),(cx-w,cy)]
    right=[(cx+w,cy),(cx+w,cy+h),(cx,cy+d+h),(cx,cy+d)]
    left=[(cx,cy+d),(cx,cy+d+h),(cx-w,cy+h),(cx-w,cy)]
    for pts,col in [(right,sc),(left,fc),(top,tc2)]:
        pygame.draw.polygon(surf,clamp_color(col),pts)
        if brd: pygame.draw.polygon(surf,(0,0,0),pts,brd)

def draw_cyl3d(surf,cx,cy,r,h,tc2,sc):
    pygame.draw.ellipse(surf,clamp_color(sc),(cx-r,cy,r*2,h))
    pygame.draw.ellipse(surf,clamp_color(tc2),(cx-r,cy-r//2,r*2,r))

def draw_dome3d(surf,cx,cy,r,tc2,rc):
    pygame.draw.circle(surf,clamp_color(rc),(cx+2,cy+2),r)
    pygame.draw.circle(surf,clamp_color(tc2),(cx,cy),r)
    hl=lerp_c(tc2,(255,255,255),0.55)
    pygame.draw.circle(surf,clamp_color(hl),(cx-r//4,cy-r//4),max(2,r//3))

# ── Enums ─────────────────────────────────────────────────────────────────────
class Difficulty(Enum):
    EASY="Easy"; MEDIUM="Medium"; HARD="Hard"; BRUTAL="Brutal"

DIFF={
    Difficulty.EASY:  dict(eco=0.65,biv=130,ar=(28,50),w0=4, wm=10, ag=0.35,rh=0.30,bo=0),
    Difficulty.MEDIUM:dict(eco=1.0, biv=80, ar=(12,25),w0=7, wm=22, ag=0.65,rh=0.15,bo=200),
    Difficulty.HARD:  dict(eco=1.45,biv=50, ar=(7,15), w0=12,wm=35, ag=0.90,rh=0.08,bo=500),
    Difficulty.BRUTAL:dict(eco=1.9, biv=28, ar=(4,9),  w0=18,wm=60, ag=1.0, rh=0.04,bo=900),
}

class Team(Enum): PLAYER=1; AI=2
class Domain(Enum): GROUND=auto(); AIR=auto(); NAVAL=auto(); MECH=auto(); PSIONIC=auto()
class UState(Enum): IDLE=auto(); MOVING=auto(); ATTACKING=auto(); RETREATING=auto(); SCOUTING=auto()

class BT(Enum):
    COMMANDER=auto(); SOLAR=auto(); METAL_X=auto(); FACTORY=auto(); TURRET=auto()
    LAB=auto(); AIRPAD=auto(); SHIPYARD=auto(); SHIELD_GEN=auto(); AA_GUN=auto()
    COASTAL_BAT=auto(); PSI_TOWER=auto(); RESEARCH=auto(); RADAR=auto()

class UT(Enum):
    SCOUT=auto(); SOLDIER=auto(); TANK=auto(); ARTILLERY=auto(); RAIDER=auto()
    FIGHTER=auto(); BOMBER=auto(); GUNSHIP=auto()
    GUNBOAT=auto(); CARRIER=auto(); SUBMARINE=auto()
    MECH=auto(); GOLIATH=auto()
    PALADIN=auto(); STEALTH=auto()
    PSI_DRONE=auto(); MIND_BLADE=auto()
    MEDIC=auto(); ENGINEER=auto(); SIEGE=auto(); TITAN=auto()

BSPECS={
    BT.COMMANDER: dict(name="Commander",    hp=2000,sz=2,mc=0,  ec=0,   bt=0,   mg=3, eg=20, cb=True, wpn=dict(r=160,d=28,cd=45,p="laser"),  mov=True),
    BT.SOLAR:     dict(name="Solar Coll",   hp=450, sz=2,mc=55, ec=0,   bt=210, mg=0, eg=22, cb=False,wpn=None),
    BT.METAL_X:   dict(name="Metal Extr",   hp=550, sz=2,mc=65, ec=0,   bt=250, mg=4, eg=-1, cb=False,wpn=None),
    BT.FACTORY:   dict(name="Factory",      hp=1400,sz=3,mc=210,ec=550, bt=650, mg=0, eg=-6, cb=False,wpn=None,  prod=[UT.SCOUT,UT.SOLDIER,UT.TANK,UT.ARTILLERY,UT.RAIDER,UT.MEDIC,UT.ENGINEER]),
    BT.TURRET:    dict(name="Laser Turret", hp=700, sz=2,mc=85, ec=110, bt=320, mg=0, eg=-4, cb=False,wpn=dict(r=240,d=22,cd=36,p="laser")),
    BT.LAB:       dict(name="Adv. Lab",     hp=1100,sz=3,mc=420,ec=1100,bt=950, mg=0, eg=-12,cb=False,wpn=None,  prod=[UT.TANK,UT.ARTILLERY,UT.RAIDER,UT.MECH,UT.SIEGE,UT.PALADIN]),
    BT.AIRPAD:    dict(name="Air Pad",      hp=850, sz=3,mc=260,ec=650, bt=720, mg=0, eg=-9, cb=False,wpn=None,  prod=[UT.FIGHTER,UT.BOMBER,UT.GUNSHIP,UT.STEALTH]),
    BT.SHIPYARD:  dict(name="Shipyard",     hp=950, sz=3,mc=320,ec=750, bt=800, mg=0, eg=-7, cb=False,wpn=None,  prod=[UT.GUNBOAT,UT.CARRIER,UT.SUBMARINE]),
    BT.SHIELD_GEN:dict(name="Shield Gen",   hp=750, sz=2,mc=160,ec=320, bt=420, mg=0, eg=-9, cb=False,wpn=None),
    BT.AA_GUN:    dict(name="AA Gun",       hp=550, sz=2,mc=110,ec=160, bt=360, mg=0, eg=-5, cb=False,wpn=dict(r=280,d=35,cd=30,p="missile"),aa=True),
    BT.COASTAL_BAT:dict(name="Coastal Batt",hp=850, sz=3,mc=360,ec=850, bt=820, mg=0, eg=-14,cb=False,wpn=dict(r=540,d=120,cd=175,p="shell")),
    BT.PSI_TOWER: dict(name="Psi Tower",    hp=900, sz=2,mc=500,ec=1200,bt=1000,mg=0, eg=-15,cb=False,wpn=dict(r=300,d=50,cd=60,p="plasma"), prod=[UT.PSI_DRONE,UT.MIND_BLADE]),
    BT.RESEARCH:  dict(name="Research Ctr", hp=800, sz=3,mc=600,ec=1500,bt=1200,mg=0, eg=-20,cb=False,wpn=None,  prod=[UT.GOLIATH,UT.TITAN,UT.PALADIN,UT.STEALTH,UT.MIND_BLADE]),
    BT.RADAR:     dict(name="Radar Station",hp=400, sz=2,mc=120,ec=200, bt=300, mg=0, eg=-5, cb=False,wpn=None),
}

USPECS={
    UT.SCOUT:    dict(name="Scout",     hp=90,  spd=3.0,mc=45, ec=110, bt=160, sight=260,dom=Domain.GROUND,wpn=dict(r=125,d=9, cd=26,p="bullet"),sz=9, tier=1,desc="Fast recon"),
    UT.SOLDIER:  dict(name="Soldier",   hp=200, spd=1.9,mc=85, ec=210, bt=260, sight=190,dom=Domain.GROUND,wpn=dict(r=145,d=16,cd=36,p="bullet"),sz=11,tier=1,desc="Standard infantry"),
    UT.TANK:     dict(name="Tank",      hp=550, spd=1.5,mc=190,ec=420, bt=520, sight=210,dom=Domain.GROUND,wpn=dict(r=175,d=45,cd=56,p="shell"), sz=16,tier=1,desc="Armoured assault"),
    UT.ARTILLERY:dict(name="Artillery", hp=260, spd=1.1,mc=230,ec=620, bt=620, sight=380,dom=Domain.GROUND,wpn=dict(r=420,d=95,cd=110,p="shell"),sz=15,tier=1,desc="Long-range barrage"),
    UT.RAIDER:   dict(name="Raider",    hp=350, spd=2.3,mc=160,ec=370, bt=420, sight=250,dom=Domain.GROUND,wpn=dict(r=160,d=34,cd=46,p="laser"),sz=13,tier=1,desc="Fast attack"),
    UT.MEDIC:    dict(name="Medic",     hp=120, spd=2.0,mc=100,ec=250, bt=300, sight=200,dom=Domain.GROUND,wpn=None,sz=10,tier=1,desc="Heals nearby units",healer=True),
    UT.ENGINEER: dict(name="Engineer",  hp=140, spd=1.6,mc=120,ec=280, bt=350, sight=180,dom=Domain.GROUND,wpn=None,sz=10,tier=1,desc="Repairs buildings",builder=True),
    UT.FIGHTER:  dict(name="Fighter",   hp=170, spd=4.0,mc=210,ec=530, bt=520, sight=310,dom=Domain.AIR,   wpn=dict(r=170,d=28,cd=28,p="bullet"),sz=11,tier=1,desc="Air superiority"),
    UT.BOMBER:   dict(name="Bomber",    hp=300, spd=2.4,mc=370,ec=850, bt=820, sight=290,dom=Domain.AIR,   wpn=dict(r=125,d=95,cd=115,p="bomb"), sz=15,tier=2,desc="Ground strike"),
    UT.GUNSHIP:  dict(name="Gunship",   hp=450, spd=2.0,mc=440,ec=1000,bt=900, sight=270,dom=Domain.AIR,   wpn=dict(r=200,d=55,cd=55,p="missile"),sz=18,tier=2,desc="Heavy gunship"),
    UT.STEALTH:  dict(name="Stealth",   hp=200, spd=3.5,mc=500,ec=1200,bt=1000,sight=340,dom=Domain.AIR,   wpn=dict(r=190,d=60,cd=65,p="missile"),sz=12,tier=3,desc="Invisible strike"),
    UT.GUNBOAT:  dict(name="Gunboat",   hp=420, spd=1.3,mc=190,ec=420, bt=620, sight=260,dom=Domain.NAVAL, wpn=dict(r=230,d=52,cd=68,p="shell"), sz=16,tier=1,desc="Naval patrol"),
    UT.CARRIER:  dict(name="Carrier",   hp=1300,spd=0.8,mc=520,ec=1250,bt=1250,sight=310,dom=Domain.NAVAL, wpn=dict(r=190,d=32,cd=48,p="missile"),sz=24,tier=2,desc="Naval command"),
    UT.SUBMARINE:dict(name="Submarine", hp=380, spd=1.6,mc=280,ec=700, bt=800, sight=200,dom=Domain.NAVAL, wpn=dict(r=260,d=80,cd=90,p="missile"),sz=14,tier=2,desc="Stealth naval"),
    UT.MECH:     dict(name="Mech",      hp=800, spd=1.0,mc=350,ec=900, bt=900, sight=240,dom=Domain.MECH,  wpn=dict(r=200,d=70,cd=65,p="shell"), sz=20,tier=2,desc="Heavy walker"),
    UT.GOLIATH:  dict(name="Goliath",   hp=1500,spd=0.8,mc=600,ec=1500,bt=1400,sight=280,dom=Domain.MECH,  wpn=dict(r=230,d=120,cd=90,p="shell"),sz=26,tier=3,desc="Siege walker"),
    UT.SIEGE:    dict(name="Siege",     hp=400, spd=0.6,mc=300,ec=800, bt=700, sight=450,dom=Domain.GROUND,wpn=dict(r=500,d=150,cd=200,p="shell"),sz=18,tier=2,desc="Extreme range"),
    UT.PALADIN:  dict(name="Paladin",   hp=1200,spd=1.2,mc=700,ec=1800,bt=1500,sight=300,dom=Domain.MECH,  wpn=dict(r=220,d=90,cd=70,p="laser"), sz=24,tier=3,desc="Elite heavy"),
    UT.PSI_DRONE:dict(name="Psi Drone", hp=150, spd=3.2,mc=300,ec=700, bt=600, sight=300,dom=Domain.PSIONIC,wpn=dict(r=180,d=40,cd=40,p="plasma"),sz=10,tier=2,desc="Psionic attacker"),
    UT.MIND_BLADE:dict(name="MindBlade",hp=280, spd=2.8,mc=600,ec=1400,bt=1100,sight=350,dom=Domain.PSIONIC,wpn=dict(r=250,d=85,cd=70,p="plasma"),sz=14,tier=3,desc="Psionic assault"),
    UT.TITAN:    dict(name="TITAN",     hp=5000,spd=0.5,mc=2000,ec=5000,bt=3000,sight=400,dom=Domain.MECH, wpn=dict(r=280,d=250,cd=120,p="plasma"),sz=38,tier=4,desc="Ultimate unit"),
}

BUILD_FROM_CMD=[BT.SOLAR,BT.METAL_X,BT.FACTORY,BT.TURRET,BT.LAB,
                BT.AIRPAD,BT.SHIPYARD,BT.SHIELD_GEN,BT.AA_GUN,BT.COASTAL_BAT,
                BT.PSI_TOWER,BT.RESEARCH,BT.RADAR]

# ── Sound ─────────────────────────────────────────────────────────────────────
class Sound:
    def __init__(self):
        try: pygame.mixer.pre_init(44100,-16,1,512); pygame.mixer.init(); self.ok=True
        except: self.ok=False
        self.vol=0.28; self._s={}; self._cd={}
        if self.ok: self._gen()
    def _w(self,s): return pygame.mixer.Sound(buffer=array.array('h',[max(-32767,min(32767,int(v))) for v in s]))
    def _sine(self,f,d,v=0.35,dc=7):
        n=int(44100*d); return [v*32767*math.sin(2*math.pi*f*i/44100)*math.exp(-i/n*dc) for i in range(n)]
    def _noise(self,d,v=0.45,dc=8):
        n=int(44100*d); return [v*32767*random.uniform(-1,1)*math.exp(-i/n*dc) for i in range(n)]
    def _gen(self):
        try:
            s=[]; n=int(44100*0.12)
            for i in range(n):
                t=i/44100; f=1200-600*t/0.12
                s.append(0.20*32767*math.sin(2*math.pi*f*t)*math.exp(-t*12))
            self._s['laser']=self._w(s)
            s=self._noise(0.06,0.17,15)
            for i in range(len(s)): t=i/44100; s[i]+=0.11*32767*math.sin(2*math.pi*280*t)*math.exp(-t*22)
            self._s['bullet']=self._w(s)
            s=self._noise(0.18,0.30,6)
            for i in range(len(s)): t=i/44100; s[i]+=0.20*32767*math.sin(2*math.pi*75*t)*math.exp(-t*4)
            self._s['shell']=self._w(s)
            s=[]
            for i in range(int(44100*0.2)):
                t=i/44100; f=600+200*math.sin(t*30)
                s.append(0.18*32767*math.sin(2*math.pi*f*t)*math.exp(-t*8))
            self._s['plasma']=self._w(s)
            ms=[]
            for i in range(int(44100*0.15)):
                t=i/44100; ms.append(0.17*32767*math.sin(2*math.pi*(800+400*t/0.15)*t)*math.exp(-t*5))
            ms+=self._noise(0.1,0.28,10); self._s['missile']=self._w(ms)
            s=self._noise(0.5,0.58,4)
            for i in range(len(s)): t=i/44100; s[i]+=0.38*32767*math.sin(2*math.pi*40*t)*math.exp(-t*3)
            self._s['bomb']=self._w(s)
            s=self._noise(0.35,0.42,5)
            for i in range(len(s)): t=i/44100; s[i]+=0.26*32767*math.sin(2*math.pi*55*t)*math.exp(-t*5)
            self._s['exp_s']=self._w(s)
            s=self._noise(0.65,0.62,3)
            for i in range(len(s)):
                t=i/44100; s[i]+=0.36*32767*math.sin(2*math.pi*40*t)*math.exp(-t*3)
                s[i]+=0.16*32767*math.sin(2*math.pi*80*t)*math.exp(-t*4)
            self._s['exp_b']=self._w(s)
            out=[]
            for f in [440,550,660,880]: out+=self._sine(f,0.07,0.16,9)
            self._s['done']=self._w(out)
            self._s['placed']=self._w(self._sine(330,0.09,0.13,10)+self._sine(440,0.09,0.13,10))
            atk=[]
            for _ in range(3): atk+=self._sine(620,0.05,0.26,13)+self._sine(390,0.05,0.26,13)
            self._s['atk']=self._w(atk)
            self._s['sel']=self._w(self._sine(490,0.055,0.09,15))
            self._s['cmd_move']=self._w(self._sine(360,0.08,0.11,11)+self._sine(490,0.06,0.09,13))
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
    def __init__(self,text,color,dur=130): self.text=text;self.color=clamp_color(color);self.dur=dur;self.age=0
    def tick(self): self.age+=1; return self.age<self.dur
    def alpha(self):
        if self.age<12: return int(255*self.age/12)
        if self.age>self.dur-28: return int(255*(self.dur-self.age)/28)
        return 255

class Notifs:
    def __init__(self,font): self.q=[];self.font=font
    def add(self,text,color=None,dur=130):
        color=clamp_color(color) if color else C["nin"]
        if any(n.text==text and n.age<30 for n in self.q): return
        if len(self.q)>7: self.q.pop(0)
        self.q.append(Notif(text,color,dur))
    def draw(self,surf):
        self.q=[n for n in self.q if n.tick()]
        by=SCREEN_H-UI_H-28
        for i,n in enumerate(reversed(self.q)):
            a=n.alpha(); t=self.font.render(n.text,True,n.color)
            s=pygame.Surface((t.get_width()+16,t.get_height()+6),pygame.SRCALPHA)
            s.fill((0,0,0,min(155,a))); s.blit(t,(8,3))
            surf.blit(s,((SCREEN_W-SIDE_W)//2-s.get_width()//2,by-i*26))

# ── Screen Shake ──────────────────────────────────────────────────────────────
class Shake:
    def __init__(self): self.s=0.;self.ox=self.oy=0
    def add(self,v): self.s=min(self.s+v,16.)
    def update(self):
        if self.s>0.08: self.ox=int(random.uniform(-self.s,self.s));self.oy=int(random.uniform(-self.s,self.s));self.s*=0.80
        else: self.s=0;self.ox=self.oy=0

# ── Particles ─────────────────────────────────────────────────────────────────
class Pt:
    __slots__=('x','y','vx','vy','color','life','ml','sz','grav')
    def __init__(self,x,y,vx,vy,color,life,sz=2,grav=0.):
        self.x=float(x);self.y=float(y);self.vx=float(vx);self.vy=float(vy)
        self.color=clamp_color(color);self.life=life;self.ml=life;self.sz=sz;self.grav=grav
    def update(self):
        self.x+=self.vx;self.y+=self.vy;self.vy+=self.grav
        self.vx*=0.95;self.vy*=0.95;self.life-=1;return self.life>0
    def draw(self,surf,cam):
        sx,sy=iso(self.x,self.y,cam); r=max(1,int(self.sz*cam.zoom))
        a=int(255*self.life/self.ml)
        s=pygame.Surface((r*2+2,r*2+2),pygame.SRCALPHA)
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

# ── Stats ─────────────────────────────────────────────────────────────────────
class Stats:
    def __init__(self):
        self.kills=[0,0]; self.deaths=[0,0]
        self.dmg_dealt=[0.,0.]; self.dmg_taken=[0.,0.]
        self.bldgs_built=[0,0]; self.units_built=[0,0]
        self.eco_hist=[[],[]]  # (metal_rate,energy_rate)
        self.unit_hist=[[],[]]
        self._f=0
    def record(self,peco,aeco,pu,au):
        self._f+=1
        if self._f%FPS==0:
            for i,(eco,units) in enumerate([(peco,pu),(aeco,au)]):
                self.eco_hist[i].append((eco.metal_rate,eco.energy_rate))
                self.unit_hist[i].append(len(units))
                if len(self.eco_hist[i])>120: self.eco_hist[i].pop(0)
                if len(self.unit_hist[i])>120: self.unit_hist[i].pop(0)

# ── Terrain ───────────────────────────────────────────────────────────────────
class Terrain:
    def __init__(self,w,h):
        self.tw=w//TILE; self.th=h//TILE; self.data=[]; self.metal=[]
        self._gen()
    def _noise(self,x,y,sc=5):
        v=0;amp=1.;freq=1.
        for _ in range(4):
            sx=x*freq/self.tw*sc; sy=y*freq/self.th*sc
            ix,iy=int(sx),int(sy); fx,fy=sx-ix,sy-iy
            def h(px,py): return math.sin(px*127.1+py*311.7)*43758.5453%1
            val=(h(ix,iy)*(1-fx)+h(ix+1,iy)*fx)*(1-fy)+(h(ix,iy+1)*(1-fx)+h(ix+1,iy+1)*fx)*fy
            v+=val*amp; amp*=0.5; freq*=2
        return v
    def _gen(self):
        random.seed(1337)
        raw=[[self._noise(x,y) for x in range(self.tw)] for y in range(self.th)]
        mn=min(v for r in raw for v in r); mx=max(v for r in raw for v in r)
        for y in range(self.th):
            rt=[]; rm=[]
            for x in range(self.tw):
                n=(raw[y][x]-mn)/(mx-mn)
                t=1 if n<0.22 else(2 if n>0.80 else 0)
                rt.append(t); rm.append(t==0 and random.random()<0.016)
            self.data.append(rt); self.metal.append(rm)
        for dy in range(12):
            for dx in range(12):
                self.data[2+dy][2+dx]=0
                self.data[self.th-5-dy][self.tw-5-dx]=0
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
    def __init__(self): self.x=MAP_W/2; self.y=MAP_H/2; self.zoom=0.9; self.speed=14; self.tilt=1.0
    def clamp(self): self.x=max(0,min(MAP_W,self.x)); self.y=max(0,min(MAP_H,self.y))
    def w2s(self,wx,wy): return iso(wx,wy,self)
    def s2w(self,sx,sy): return s2w(sx,sy,self)
    def center_on(self,wx,wy): self.x=wx; self.y=wy; self.clamp()
    def update(self,keys):
        spd=self.speed/self.zoom
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: self.x-=spd; self.y+=spd
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.x+=spd; self.y-=spd
        if keys[pygame.K_UP]    or keys[pygame.K_w]: self.x-=spd; self.y-=spd
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: self.x+=spd; self.y+=spd
        self.clamp()
    def zi(self): self.zoom=min(3.0,self.zoom*1.12)
    def zo(self): self.zoom=max(0.18,self.zoom/1.12)

# ── Projectile ────────────────────────────────────────────────────────────────
class Proj:
    def __init__(self,x,y,tx,ty,dmg,pt,team,tdom=None,stats=None):
        self.x=float(x);self.y=float(y);self.tx=float(tx);self.ty=float(ty)
        self.dmg=dmg;self.pt=pt;self.team=team;self.tdom=tdom;self._stats=stats
        dx,dy=tx-x,ty-y; l=math.hypot(dx,dy) or 1
        spd={"laser":11,"bullet":7,"shell":5,"missile":7.5,"bomb":3.5,"plasma":9}.get(pt,6)
        self.vx=dx/l*spd; self.vy=dy/l*spd; self.alive=True; self.trail=[]
    def update(self,entities):
        self.trail.append((self.x,self.y))
        if len(self.trail)>10: self.trail.pop(0)
        self.x+=self.vx; self.y+=self.vy
        for e in entities:
            if e.team==self.team or not e.alive: continue
            if self.tdom and getattr(e,"dom",None)!=self.tdom: continue
            if dist((self.x,self.y),(e.x,e.y))<e.radius+5:
                e.take_damage(self.dmg,self.team,self._stats); self.alive=False; return True
        if dist((self.x,self.y),(self.tx,self.ty))<max(abs(self.vx),abs(self.vy))+3:
            self.alive=False
        return False
    def draw(self,surf,cam):
        if not self.alive: return
        sx,sy=cam.w2s(self.x,self.y)
        cmap={"laser":C["las"],"bullet":C["bul"],"shell":C["shl"],"missile":C["mis"],"bomb":C["bom"],"plasma":C["pla"]}
        col=cmap.get(self.pt,C["bul"])
        if self.pt in ("laser","plasma"):
            for i in range(1,len(self.trail)):
                p1=cam.w2s(*self.trail[i-1]); p2=cam.w2s(*self.trail[i])
                pygame.draw.line(surf,(*col,int(130*i/len(self.trail))),p1,p2,2)
            pygame.draw.circle(surf,col,(sx,sy),4); sfx_glow(surf,col,(sx,sy),9,50)
        elif self.pt=="bullet":
            if len(self.trail)>=2: pygame.draw.line(surf,(*col,95),cam.w2s(*self.trail[-2]),(sx,sy),2)
            pygame.draw.circle(surf,col,(sx,sy),3)
        elif self.pt in ("shell","missile"):
            if len(self.trail)>=2: pygame.draw.line(surf,(*col,90),cam.w2s(*self.trail[-2]),(sx,sy),2)
            pygame.draw.circle(surf,col,(sx,sy),5 if self.pt=="shell" else 4)
            sfx_glow(surf,col,(sx,sy),7,40)
        else:
            pygame.draw.circle(surf,(90,80,50),(sx+2,sy+2),6); pygame.draw.circle(surf,col,(sx,sy),6)

# ── Explosion ─────────────────────────────────────────────────────────────────
class Explosion:
    def __init__(self,x,y,sz=1.,parts=None,sound=None):
        self.x=x;self.y=y;self.t=0;self.life=int(38+sz*9);self.sz=sz
        self.debris=[(random.uniform(-4,4)*sz,random.uniform(-4,4)*sz,random.randint(4,14),random.choice(EXP)) for _ in range(18)]
        if parts:
            for _ in range(int(10*sz)):
                a=random.uniform(0,math.pi*2); s=random.uniform(0.5,2.2)*sz
                parts.p.append(Pt(x,y,math.cos(a)*s,math.sin(a)*s,C["smk"],random.randint(45,90),random.uniform(3,7)*sz,-0.025))
        if sound: sound.play("exp_b" if sz>1.5 else "exp_s",cd=3)
    def update(self): self.t+=1; return self.t<self.life
    def draw(self,surf,cam):
        sx,sy=cam.w2s(self.x,self.y); p=self.t/self.life
        r=int(self.sz*24*math.sin(p*math.pi)*(1+p*0.5))
        if r>0:
            al=int(255*(1-p)**1.5); col=lerp_c(EXP[min(int(p*4),3)],(18,12,6),p)
            s=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
            pygame.draw.circle(s,(*col,al),(r+2,r+2),r)
            if p<0.28:
                cr=int(r*(1-p/0.28)*0.55)
                pygame.draw.circle(s,(255,245,210,min(255,int(al*1.5))),(r+2,r+2),cr)
            surf.blit(s,(sx-r-2,sy-r-2))
        for dx,dy,pr,col in self.debris:
            px2=sx+int(dx*(1-p)**0.8*20); py2=sy+int(dy*(1-p)**0.8*20)
            pygame.draw.circle(surf,lerp_c(col,(38,18,8),p),(px2,py2),max(1,int(pr*(1-p)**0.5)))

# ── Entity ────────────────────────────────────────────────────────────────────
class Entity:
    _idc=0
    def __init__(self,x,y,team):
        Entity._idc+=1; self.id=Entity._idc
        self.x=float(x);self.y=float(y);self.team=team;self.alive=True
        self.hp=100;self.max_hp=100;self.radius=16
        self.weapon=None;self.fire_cd=0;self.target=None
        self._exploded=False;self._shielded=False
    def take_damage(self,d,atk_team=None,stats=None):
        actual=d*0.4 if self._shielded else d
        self.hp=max(0,self.hp-actual); self.alive=self.hp>0
        if stats and atk_team:
            ai=0 if atk_team==Team.PLAYER else 1
            di=1-ai
            stats.dmg_dealt[ai]+=actual; stats.dmg_taken[di]+=actual
    def hfrac(self): return max(0,self.hp/self.max_hp)
    def hcol(self): return hcol(self.hfrac())
    def draw_hbar(self,surf,cam,w=30,ey=0):
        sx,sy=cam.w2s(self.x,self.y); sy-=self.radius+14+ey
        pygame.draw.rect(surf,(18,18,18),(sx-w//2-1,sy-1,w+2,6))
        pygame.draw.rect(surf,(38,38,38),(sx-w//2,sy,w,4))
        cw=int(w*self.hfrac())
        if cw>0: pygame.draw.rect(surf,self.hcol(),(sx-w//2,sy,cw,4))
    def try_fire(self,entities,projs,sound=None,stats=None):
        if not self.weapon: return
        if self.fire_cd>0: self.fire_cd=max(0,self.fire_cd-1); return
        wpn=self.weapon; rng=wpn["r"]; aa=getattr(self,"aa_only",False)
        for e in entities:
            if e.team==self.team or not e.alive: continue
            if aa and getattr(e,"dom",Domain.GROUND)!=Domain.AIR: continue
            if dist((self.x,self.y),(e.x,e.y))<rng: self.target=e; break
        if self.target and self.target.alive and dist((self.x,self.y),(self.target.x,self.target.y))<rng:
            tdom=getattr(self.target,"dom",None)
            projs.append(Proj(self.x,self.y,self.target.x,self.target.y,wpn["d"],wpn["p"],self.team,tdom,stats))
            self.fire_cd=wpn["cd"]
            if sound: sound.play(wpn["p"],cd=2)
        else: self.target=None

# ── Building ──────────────────────────────────────────────────────────────────
class Building(Entity):
    def __init__(self,x,y,team,btype):
        super().__init__(x,y,team)
        sp=BSPECS[btype]; self.btype=btype; self.name=sp["name"]
        self.hp=sp["hp"]; self.max_hp=sp["hp"]; self.size=sp["sz"]
        self.radius=sp["sz"]*TILE//2
        self.metal_gen=sp["mg"]; self.energy_gen=sp["eg"]
        self.can_build=sp.get("cb",False); self.weapon=sp.get("wpn")
        self.produces=sp.get("prod",[]); self.movable=sp.get("mov",False)
        self.aa_only=sp.get("aa",False)
        self.build_queue=[]; self.rally=None; self._phase=random.uniform(0,math.pi*2)
        self._shield_hp=220 if btype==BT.SHIELD_GEN else 0; self._shield_max=220
        self.shield_radius=210; self.move_target=None; self._ang=0.

    def enqueue(self,utype,eco,player_cmd=None):
        sp=USPECS[utype]
        if player_cmd and dist((player_cmd.x,player_cmd.y),(self.x,self.y))>PRODUCE_RANGE:
            return False,"range"
        if eco.metal>=sp["mc"] and eco.energy>=sp["ec"]:
            eco.metal-=sp["mc"]; eco.energy-=sp["ec"]
            self.build_queue.append([utype,sp["bt"],sp["bt"]]); return True,"ok"
        return False,"funds"

    def dequeue(self,idx,eco):
        if 0<=idx<len(self.build_queue):
            item=self.build_queue[idx]; sp=USPECS[item[0]]
            frac=item[2]/item[1]; eco.metal+=sp["mc"]*frac; eco.energy+=sp["ec"]*frac
            self.build_queue.pop(idx)

    def update_prod(self):
        if not self.build_queue: return None
        item=self.build_queue[0]; item[2]-=1
        if item[2]<=0: self.build_queue.pop(0); return item[0]
        return None

    def update_move(self,terrain):
        if not self.movable or not self.move_target: return
        dx=self.move_target[0]-self.x; dy=self.move_target[1]-self.y
        l=math.hypot(dx,dy)
        if l<5: self.move_target=None; return
        self._ang=math.atan2(dy,dx)
        nx,ny=self.x+dx/l*1.3,self.y+dy/l*1.3
        if terrain.walkable(nx,ny): self.x,self.y=nx,ny
        self.x=max(self.radius,min(MAP_W-self.radius,self.x))
        self.y=max(self.radius,min(MAP_H-self.radius,self.y))

    def update_shield(self,all_e):
        if self.btype!=BT.SHIELD_GEN or not self.alive: return
        if self._shield_hp<self._shield_max: self._shield_hp=min(self._shield_max,self._shield_hp+0.06)
        for e in all_e:
            if e.team!=self.team or not e.alive or e is self: continue
            if dist((self.x,self.y),(e.x,e.y))<self.shield_radius: e._shielded=True

    def draw(self,surf,cam,selected=False,tick=0):
        sx,sy=cam.w2s(self.x,self.y)
        z=cam.zoom; ps=int(self.size*TILE*z); ph=tick*0.04+self._phase
        if ps<4: return
        color=tc(self.team); dark=tc(self.team,dark=True); gl=tc(self.team,glow=True)
        d=max(3,int(ps*0.18)); bw=max(4,ps//2)
        top_c=lerp_c(color,(255,255,255),0.25)
        side_c=lerp_c(dark,(0,0,0),0.3)
        front_c=lerp_c(dark,(255,255,255),0.10)

        # Ground shadow
        shadow_el(surf,sx+SHADOW_OFF,sy+SHADOW_OFF+d//2,bw,d//2)

        if self.btype==BT.COMMANDER:
            r=max(6,ps//3)
            draw_cyl3d(surf,sx,sy,r,d+4,top_c,side_c)
            pulse=int(r*(0.7+0.3*math.sin(ph*1.5))*1.4)
            sfx_glow(surf,gl,(sx,sy-d//2),pulse,42)
            for i in range(8):
                a=i*math.pi/4+ph*0.4
                rx2=sx+int(math.cos(a)*r*0.75); ry2=sy-d//2+int(math.sin(a)*r*0.4)
                pygame.draw.circle(surf,gl,(rx2,ry2),2)
            if self.move_target:
                tx2,ty2=cam.w2s(*self.move_target)
                pygame.draw.line(surf,(*gl,75),(sx,sy),(tx2,ty2),1)
        elif self.btype==BT.SOLAR:
            pc=lerp_c(C["en"],(255,240,180),0.3+0.3*math.sin(ph))
            draw_box3d(surf,sx,sy,bw//2,d,bw//2,pc,side_c,front_c)
            sfx_glow(surf,C["en"],(sx,sy-d),max(4,ps//4),18+int(12*math.sin(ph)))
        elif self.btype==BT.METAL_X:
            draw_box3d(surf,sx,sy,bw//2,d,bw//2,lerp_c(C["mt"],(200,240,230),0.3),side_c,front_c)
            a=ph*0.6; r=max(4,ps//5)
            pts=[(sx+int(math.cos(a+i*math.pi/2)*r),sy-d+int(math.sin(a+i*math.pi/2)*r*0.5)) for i in range(4)]
            pygame.draw.polygon(surf,C["mt"],pts); pygame.draw.polygon(surf,(200,240,230),pts,1)
        elif self.btype in (BT.FACTORY,BT.LAB):
            draw_box3d(surf,sx,sy,bw//2,d*2,bw//2,top_c,side_c,front_c)
            nt=10 if self.btype==BT.LAB else 7; gr=max(5,ps//4); gpts=[]
            for i in range(nt*2):
                ang=i*math.pi/nt+ph*(0.6 if self.btype==BT.LAB else 0.35)
                r2=gr if i%2==0 else int(gr*0.65)
                gpts.append((sx+int(math.cos(ang)*r2),sy-d*2+int(math.sin(ang)*r2*0.5)))
            if len(gpts)>=3: pygame.draw.polygon(surf,dark,gpts); pygame.draw.polygon(surf,gl,gpts,1)
            pygame.draw.circle(surf,dark,(sx,sy-d*2),gr//3)
        elif self.btype==BT.TURRET:
            draw_cyl3d(surf,sx,sy,max(5,ps//3),d,top_c,side_c)
            if self.target and self.target.alive:
                tsx,tsy=cam.w2s(self.target.x,self.target.y)
                ta=math.atan2(tsy-sy,tsx-sx)
            else: ta=ph*0.3
            bl=max(8,ps//3)
            bx2=sx+int(math.cos(ta)*bl); by2=sy-d+int(math.sin(ta)*bl*0.5)
            pygame.draw.line(surf,side_c,(sx+2,sy-d+1),(bx2+2,by2+1),max(3,ps//7))
            pygame.draw.line(surf,C["las2"],(sx,sy-d),(bx2,by2),max(3,ps//7))
            sfx_glow(surf,C["las"],(sx,sy-d),max(4,ps//5),18)
        elif self.btype==BT.AIRPAD:
            draw_box3d(surf,sx,sy,bw//2,d,bw//2,(100,110,120),(60,70,75),(70,80,85),brd=0)
            pygame.draw.line(surf,(200,210,200),(sx-bw//2+2,sy-d),(sx+bw//2-2,sy-d),2)
            pygame.draw.line(surf,(200,210,200),(sx,sy-d-bw//2+2),(sx,sy-d+bw//2-2),2)
            sfx_glow(surf,(170,180,220),(sx,sy-d),max(4,ps//4),16)
        elif self.btype==BT.SHIPYARD:
            draw_box3d(surf,sx,sy,bw//2,d,bw//3,(38,85,128),(22,55,90),(30,68,108))
            pygame.draw.ellipse(surf,(20,40,80),(sx-bw//2+2,sy-d-2,bw-4,max(4,d//2)))
            sfx_glow(surf,(40,100,180),(sx,sy-d),max(4,ps//4),20)
        elif self.btype==BT.SHIELD_GEN:
            draw_cyl3d(surf,sx,sy,max(5,ps//3),d,(80,140,255),(40,80,200))
            pulse=0.7+0.3*math.sin(ph*2.2)
            sfx_glow(surf,(80,140,255),(sx,sy-d),int(max(5,ps//3)*pulse*1.6),30)
            if self._shield_hp>0:
                sr=int(self.shield_radius*cam.zoom*ISO_SX)
                ry2=int(self.shield_radius*cam.zoom*ISO_SY)
                if sr>4:
                    ss2=pygame.Surface((sr*2+4,ry2*4+4),pygame.SRCALPHA)
                    a2=int(14*self._shield_hp/self._shield_max)
                    pygame.draw.ellipse(ss2,(80,140,255,a2),(0,ry2,sr*2+4,ry2*2+4))
                    pygame.draw.ellipse(ss2,(80,140,255,45),(0,ry2,sr*2+4,ry2*2+4),2)
                    surf.blit(ss2,(sx-sr-2,sy-ry2*2-2))
        elif self.btype==BT.AA_GUN:
            draw_cyl3d(surf,sx,sy,max(5,ps//3),d,(60,78,68),(35,52,42))
            for side in [-1,1]:
                ox=int(side*max(3,ps//5))
                pygame.draw.line(surf,(140,175,155),(sx+ox,sy-d),(sx+int(ox*0.5),sy-d-max(8,ps//3)),max(2,ps//8))
        elif self.btype==BT.COASTAL_BAT:
            draw_cyl3d(surf,sx,sy,max(6,ps//3),d*2,(62,70,65),(38,46,42))
            if self.target and self.target.alive:
                tsx,tsy=cam.w2s(self.target.x,self.target.y)
                ta=math.atan2(tsy-sy,tsx-sx)
            else: ta=ph*0.08
            bl=max(12,ps//2)
            pygame.draw.line(surf,(38,46,42),(sx+3,sy-d*2+1),(sx+int(math.cos(ta)*bl+3),sy-d*2+int(math.sin(ta)*bl*0.45+1)),max(5,ps//5))
            pygame.draw.line(surf,(160,180,158),(sx,sy-d*2),(sx+int(math.cos(ta)*bl),sy-d*2+int(math.sin(ta)*bl*0.45)),max(5,ps//5))
        elif self.btype==BT.PSI_TOWER:
            draw_cyl3d(surf,sx,sy,max(4,ps//4),d*3,(180,62,255),(100,30,160))
            sfx_glow(surf,C["psi"],(sx,sy-d*3),int(max(4,ps//4)*1.5),33)
            for i in range(5):
                a=i*math.pi*2/5+ph*1.5; r2=max(3,ps//4)
                pygame.draw.circle(surf,C["psi"],(sx+int(math.cos(a)*r2),sy-d*2+int(math.sin(a)*r2*0.5)),3)
        elif self.btype==BT.RESEARCH:
            draw_box3d(surf,sx,sy,bw//2,d*2,bw//2,lerp_c(color,(200,200,255),0.3),side_c,front_c)
            for i in range(10):
                a=i*math.pi/5+ph; r2=max(3,ps//6)
                pygame.draw.circle(surf,gl,(sx+int(math.cos(a)*r2),sy-d+int(i*d*0.18)),2)
        elif self.btype==BT.RADAR:
            draw_cyl3d(surf,sx,sy,max(4,ps//4),d,(80,100,90),(50,65,58))
            a=ph*2; dr=max(5,ps//3)
            pygame.draw.line(surf,gl,(sx,sy-d),(sx+int(math.cos(a)*dr),sy-d+int(math.sin(a)*dr*0.45)),2)
        else:
            draw_box3d(surf,sx,sy,bw//2,d,bw//2,top_c,side_c,front_c)

        if self.build_queue:
            item=self.build_queue[0]; prog=1.-item[2]/item[1]; bw2=ps-4
            pygame.draw.rect(surf,(18,18,18),(sx-bw2//2,sy+ps//3+4,bw2,5),border_radius=2)
            pw=int(bw2*prog)
            if pw>0: pygame.draw.rect(surf,C["en"],(sx-bw2//2,sy+ps//3+4,pw,5),border_radius=2)

        if selected:
            r2=max(8,ps//2+4)
            gs=pygame.Surface((r2*2+4,r2*2+4),pygame.SRCALPHA)
            pygame.draw.ellipse(gs,(*C["sel"],28),(0,r2//2,r2*2+4,r2+4))
            pygame.draw.ellipse(gs,(*C["sel"],135),(0,r2//2,r2*2+4,r2+4),2)
            surf.blit(gs,(sx-r2-2,sy-r2//2-2))
        self.draw_hbar(surf,cam,w=ps)

# ── Unit ──────────────────────────────────────────────────────────────────────
class Unit(Entity):
    def __init__(self,x,y,team,utype):
        super().__init__(x,y,team)
        sp=USPECS[utype]; self.utype=utype; self.name=sp["name"]
        self.hp=sp["hp"]; self.max_hp=sp["hp"]; self.speed=sp["spd"]
        self.sight=sp["sight"]; self.weapon=sp["wpn"]; self.dom=sp["dom"]
        self.radius=sp["sz"]; self.state=UState.IDLE
        self.move_target=None; self.attack_target=None; self.fire_cd=0
        self._phase=random.uniform(0,math.pi*2); self._ang=0.
        self._alt=random.uniform(0,math.pi*2); self.kills=0
        self._heal_cd=0; self._repair_cd=0
        self.stealth_active=False

    def command_move(self,wx,wy): self.move_target=(wx,wy);self.attack_target=None;self.state=UState.MOVING
    def command_attack(self,t): self.attack_target=t;self.state=UState.ATTACKING

    def update(self,all_e,projs,terrain,parts=None,sound=None,stats=None):
        self.fire_cd=max(0,self.fire_cd-1); self._shielded=False
        self.stealth_active=(self.utype==UT.STEALTH and self.state!=UState.ATTACKING)
        if self.dom==Domain.GROUND: self._steer(all_e)

        if USPECS[self.utype].get("healer"):
            self._heal_cd-=1
            if self._heal_cd<=0:
                self._heal_cd=45
                near=[u for u in all_e if isinstance(u,Unit) and u.team==self.team
                      and u is not self and dist((self.x,self.y),(u.x,u.y))<100 and u.hp<u.max_hp]
                if near:
                    t2=min(near,key=lambda u:u.hfrac()); t2.hp=min(t2.max_hp,t2.hp+20)
                    if parts: parts.emit(t2.x,t2.y,3,0.5,C["hg"],15,1)

        if USPECS[self.utype].get("builder"):
            self._repair_cd-=1
            if self._repair_cd<=0:
                self._repair_cd=60
                near=[b for b in all_e if isinstance(b,Building) and b.team==self.team
                      and dist((self.x,self.y),(b.x,b.y))<120 and b.hp<b.max_hp]
                if near:
                    t2=min(near,key=lambda b:b.hfrac()); t2.hp=min(t2.max_hp,t2.hp+15)

        if self.state==UState.ATTACKING and self.attack_target:
            if not self.attack_target.alive: self.attack_target=None; self.state=UState.IDLE; return
            d=dist((self.x,self.y),(self.attack_target.x,self.attack_target.y))
            rng=self.weapon["r"] if self.weapon else 0
            if d>rng: self.move_target=(self.attack_target.x,self.attack_target.y); self._move(terrain,parts)
            else: self.move_target=None; self._fire(self.attack_target,projs,sound,stats)
        elif self.state in (UState.MOVING,UState.RETREATING) and self.move_target:
            self._move(terrain,parts)
            if dist((self.x,self.y),self.move_target)<10: self.move_target=None; self.state=UState.IDLE
        if self.state in (UState.IDLE,UState.MOVING) and self.weapon:
            for e in all_e:
                if e.team==self.team or not e.alive: continue
                if dist((self.x,self.y),(e.x,e.y))<self.weapon["r"]:
                    self._fire(e,projs,sound,stats); break

    def _move(self,terrain,parts=None):
        if not self.move_target: return
        dx=self.move_target[0]-self.x; dy=self.move_target[1]-self.y
        l=math.hypot(dx,dy)
        if l<2: return
        self._ang=math.atan2(dy,dx); spd=self.speed
        nx,ny=self.x+dx/l*spd, self.y+dy/l*spd
        if self.dom==Domain.GROUND:
            if terrain.walkable(nx,ny): self.x,self.y=nx,ny
            elif terrain.walkable(self.x+dx/l*spd,self.y): self.x+=dx/l*spd
            elif terrain.walkable(self.x,self.y+dy/l*spd): self.y+=dy/l*spd
        elif self.dom in (Domain.AIR,Domain.PSIONIC): self.x,self.y=nx,ny
        elif self.dom==Domain.NAVAL:
            if terrain.is_water(nx,ny): self.x,self.y=nx,ny
            elif terrain.is_water(self.x+dx/l*spd,self.y): self.x+=dx/l*spd
            elif terrain.is_water(self.x,self.y+dy/l*spd): self.y+=dy/l*spd
        elif self.dom==Domain.MECH:
            if not terrain.is_water(nx,ny): self.x,self.y=nx,ny
        self.x=max(self.radius,min(MAP_W-self.radius,self.x))
        self.y=max(self.radius,min(MAP_H-self.radius,self.y))
        if parts and random.random()<0.32:
            col=tc(self.team,glow=True)
            if self.dom in (Domain.AIR,Domain.PSIONIC): parts.thrust(self.x,self.y,self._ang,col,4)
            elif spd>1.3: parts.thrust(self.x,self.y,self._ang,col,2)

    def _steer(self,entities):
        sx=sy=0.
        for e in entities:
            if e is self or not e.alive or not hasattr(e,"speed"): continue
            if getattr(e,"dom",Domain.GROUND) not in (Domain.GROUND,Domain.MECH): continue
            d=dist((self.x,self.y),(e.x,e.y)); md=self.radius+e.radius+2
            if 0<d<md: f=(md-d)/md*0.5; sx+=(self.x-e.x)/d*f; sy+=(self.y-e.y)/d*f
        self.x=max(self.radius,min(MAP_W-self.radius,self.x+sx))
        self.y=max(self.radius,min(MAP_H-self.radius,self.y+sy))

    def _fire(self,target,projs,sound=None,stats=None):
        if self.fire_cd>0 or not self.weapon: return
        tdom=getattr(target,"dom",None)
        projs.append(Proj(self.x,self.y,target.x,target.y,self.weapon["d"],self.weapon["p"],self.team,tdom,stats))
        self.fire_cd=self.weapon["cd"]
        if sound: sound.play(self.weapon["p"],cd=2)

    def _tang(self,cam,sx,sy,default):
        if self.attack_target and self.attack_target.alive:
            tsx,tsy=cam.w2s(self.attack_target.x,self.attack_target.y)
            return math.atan2(tsy-sy,tsx-sx)
        return default

    def draw(self,surf,cam,selected=False,tick=0):
        sx,sy=cam.w2s(self.x,self.y)
        z=cam.zoom; r=max(3,int(self.radius*z))
        color=tc(self.team); dark=tc(self.team,dark=True); gl=tc(self.team,glow=True)
        ang=self._ang; ph=tick*0.055+self._phase
        d=max(2,int(r*0.45))

        # Stealth: ghost only
        if self.stealth_active:
            s=pygame.Surface((r*2+4,r*2+4),pygame.SRCALPHA)
            pygame.draw.circle(s,(*gl,50),(r+2,r+2),r); surf.blit(s,(sx-r-2,sy-r-2))
            self.draw_hbar(surf,cam,w=r*2+4); return

        if self.dom==Domain.AIR:
            bob=int(4*math.sin(tick*0.09+self._alt))
            shadow_el(surf,sx+SHADOW_OFF,sy+r//2+8-bob,r,r//3); sy-=bob+6
        elif self.dom==Domain.PSIONIC:
            bob=int(3*math.sin(tick*0.07+self._alt))
            sfx_glow(surf,C["psi"],(sx,sy-bob),r+4,20); sy-=bob+4
        elif self.dom==Domain.NAVAL:
            ws=pygame.Surface((r*4,r*2),pygame.SRCALPHA)
            pygame.draw.ellipse(ws,(*C["w1"],50),(0,0,r*4,r*2)); surf.blit(ws,(sx-r*2,sy-r//2))
        else:
            shadow_el(surf,sx+SHADOW_OFF//2,sy+SHADOW_OFF//2,r,r//3)
        if self._shielded: sfx_glow(surf,(80,140,255),(sx,sy),r+7,26)

        top=lerp_c(color,(255,255,255),0.2)
        side=lerp_c(dark,(0,0,0),0.2)

        if self.utype==UT.TANK:
            perp=ang+math.pi/2
            bx=int(math.cos(ang)*r); by=int(math.sin(ang)*r)
            rx=int(math.cos(perp)*r*0.55); ry2=int(math.sin(perp)*r*0.55)
            pts=[(sx+bx+rx,sy+by+ry2),(sx+bx-rx,sy+by-ry2),(sx-bx-rx,sy-by-ry2),(sx-bx+rx,sy-by+ry2)]
            pygame.draw.polygon(surf,dark,[(p[0]+2,p[1]+2) for p in pts])
            pygame.draw.polygon(surf,top,pts)
            for sm in [-1,1]:
                tx2=int(math.cos(perp)*r*0.7)*sm; ty2=int(math.sin(perp)*r*0.7)*sm
                pygame.draw.line(surf,(30,40,35),(sx-bx+tx2,sy-by+ty2),(sx+bx+tx2,sy+by+ty2),max(2,r//4))
            pygame.draw.circle(surf,dark,(sx+1,sy-d+1),r//2+2); pygame.draw.circle(surf,gl,(sx,sy-d),r//2+1)
            pygame.draw.circle(surf,dark,(sx,sy-d),r//2-1)
            ta=self._tang(cam,sx,sy,ang)
            pygame.draw.line(surf,dark,(sx+1,sy-d+1),(sx+int(math.cos(ta)*(r+5))+1,sy-d+int(math.sin(ta)*(r+5)*0.5)+1),max(2,r//5))
            pygame.draw.line(surf,(200,215,210),(sx,sy-d),(sx+int(math.cos(ta)*(r+5)),sy-d+int(math.sin(ta)*(r+5)*0.5)),max(2,r//5))

        elif self.utype in (UT.MECH,UT.GOLIATH,UT.PALADIN,UT.TITAN):
            ht={"MECH":2,"GOLIATH":3,"PALADIN":2,"TITAN":4}.get(self.utype.name,2)
            sc={"MECH":1.0,"GOLIATH":1.3,"PALADIN":1.0,"TITAN":1.6}.get(self.utype.name,1.0)
            tc2=lerp_c(top,(220,230,255),0.4) if self.utype==UT.PALADIN else top
            draw_box3d(surf,sx,sy,int(r*sc),d*ht,int(r*sc),tc2,side,lerp_c(dark,(255,255,255),0.08))
            if self.utype==UT.TITAN: sfx_glow(surf,gl,(sx,sy-d*ht),int(r*1.3),48)
            ta=self._tang(cam,sx,sy,ang)
            col2=C["las2"] if self.utype==UT.PALADIN else (200,215,210)
            barrel_x=sx+int(math.cos(ta)*(int(r*sc)+8)); barrel_y=sy-d*ht+int(math.sin(ta)*(int(r*sc)+8)*0.5)
            pygame.draw.line(surf,side,(sx+2,sy-d*ht+1),(barrel_x+2,barrel_y+1),max(3,r//4))
            pygame.draw.line(surf,col2,(sx,sy-d*ht),(barrel_x,barrel_y),max(3,r//4))
            # Legs
            for sm in ([-1,1] if self.utype!=UT.TITAN else [-1,-.33,.33,1]):
                lx=sx+int(sm*r*0.8)
                pygame.draw.line(surf,dark,(lx,sy),(lx+int(sm*2),sy+d+3),max(2,r//5))

        elif self.utype==UT.ARTILLERY:
            a1=ang-math.pi/2; a2=ang+math.pi/2
            pts3=[(sx+int(math.cos(ang)*r*1.2),sy-d+int(math.sin(ang)*r*0.5)),
                  (sx+int(math.cos(a1)*r*0.7),sy-d+int(math.sin(a1)*r*0.35)),
                  (sx+int(math.cos(a2)*r*0.7),sy-d+int(math.sin(a2)*r*0.35))]
            ptsb=[(sx+int(math.cos(ang)*r*1.2),sy+int(math.sin(ang)*r*0.5)),
                  (sx+int(math.cos(a1)*r*0.7),sy+int(math.sin(a1)*r*0.35)),
                  (sx+int(math.cos(a2)*r*0.7),sy+int(math.sin(a2)*r*0.35))]
            pygame.draw.polygon(surf,side,[ptsb[0],pts3[0],pts3[1],ptsb[1]])
            pygame.draw.polygon(surf,lerp_c(dark,(255,255,255),0.05),[ptsb[0],pts3[0],pts3[2],ptsb[2]])
            pygame.draw.polygon(surf,top,pts3)
            ta=self._tang(cam,sx,sy,ang)
            pygame.draw.line(surf,(200,215,210),(sx,sy-d),(sx+int(math.cos(ta)*r*1.85),sy-d+int(math.sin(ta)*r*0.9)),max(3,r//4))

        elif self.utype==UT.SIEGE:
            draw_box3d(surf,sx,sy,int(r*0.8),d,int(r*1.2),top,side,lerp_c(dark,(255,255,255),0.06))
            ta=self._tang(cam,sx,sy,ang); bl=int(r*2.3)
            pygame.draw.line(surf,dark,(sx+2,sy-d+1),(sx+int(math.cos(ta)*bl+2),sy-d+int(math.sin(ta)*bl*0.45+1)),max(4,r//3))
            pygame.draw.line(surf,C["shl"],(sx,sy-d),(sx+int(math.cos(ta)*bl),sy-d+int(math.sin(ta)*bl*0.45)),max(4,r//3))

        elif self.utype in (UT.SCOUT,UT.SOLDIER,UT.RAIDER,UT.MEDIC,UT.ENGINEER):
            draw_dome3d(surf,sx,sy-d,r,top,dark)
            pygame.draw.ellipse(surf,side,(sx-r,sy-d//2,r*2,d))
            if self.utype==UT.MEDIC:
                pygame.draw.line(surf,(255,80,80),(sx-r//2,sy-d),(sx+r//2,sy-d),max(2,r//5))
                pygame.draw.line(surf,(255,80,80),(sx,sy-d-r//2),(sx,sy-d+r//2),max(2,r//5))
            elif self.utype==UT.ENGINEER:
                pygame.draw.line(surf,C["en"],(sx,sy-d-r//2),(sx+r//2,sy-d+r//2),max(2,r//5))

        elif self.utype==UT.FIGHTER:
            perp=ang+math.pi/2
            nose=(sx+int(math.cos(ang)*r*1.3),sy-d+int(math.sin(ang)*r*0.55))
            tail=(sx+int(math.cos(ang+math.pi)*r*0.9),sy-d+int(math.sin(ang+math.pi)*r*0.45))
            pygame.draw.line(surf,dark,(nose[0]+1,nose[1]+1),(tail[0]+1,tail[1]+1),max(3,r//3))
            pygame.draw.line(surf,top,nose,tail,max(3,r//3))
            for sm in [1,-1]:
                wt=(sx+int(math.cos(perp)*r*1.1*sm)+int(math.cos(ang+math.pi)*r*0.2),
                    sy-d+int(math.sin(perp)*r*0.55*sm)+int(math.sin(ang+math.pi)*r*0.1))
                pygame.draw.line(surf,gl,wt,nose,max(2,r//4))
            sfx_glow(surf,gl,tail,r//2,26)

        elif self.utype in (UT.BOMBER,UT.GUNSHIP,UT.STEALTH):
            perp=ang+math.pi/2
            nose=(sx+int(math.cos(ang)*r),sy-d+int(math.sin(ang)*r*0.5))
            tail=(sx+int(math.cos(ang+math.pi)*r*0.8),sy-d+int(math.sin(ang+math.pi)*r*0.4))
            lw=max(5,r//2) if self.utype==UT.BOMBER else (max(4,r//2) if self.utype==UT.GUNSHIP else max(3,r//3))
            pygame.draw.line(surf,dark,(nose[0]+1,nose[1]+1),(tail[0]+1,tail[1]+1),lw)
            pygame.draw.line(surf,top if self.utype!=UT.STEALTH else lerp_c(dark,(80,80,120),0.5),nose,tail,lw)
            wl=(sx+int(math.cos(perp)*r*1.4),sy-d+int(math.sin(perp)*r*0.7))
            wr=(sx-int(math.cos(perp)*r*1.4),sy-d-int(math.sin(perp)*r*0.7))
            pygame.draw.line(surf,top,wl,wr,max(2,r//4))
            if self.utype==UT.GUNSHIP:
                a2=ph*3
                for i in range(2):
                    rx2=sx+int(math.cos(a2+i*math.pi)*r*1.5)
                    ry2=sy-d*2+int(math.sin(a2+i*math.pi)*r*0.6)
                    pygame.draw.line(surf,gl,(sx,sy-d*2),(rx2,ry2),max(2,r//6))

        elif self.utype in (UT.GUNBOAT,UT.CARRIER,UT.SUBMARINE):
            perp=ang+math.pi/2; hw=int(r*(0.55 if self.utype==UT.GUNBOAT else 0.65))
            if self.utype==UT.SUBMARINE:
                draw_cyl3d(surf,sx,sy,r,d,(40,65,110),(22,45,80))
                pygame.draw.line(surf,(50,80,130),(sx,sy-d),(sx,sy-d-r),max(2,r//5))
            else:
                pts=[(sx+int(math.cos(ang)*r*1.4),sy+int(math.sin(ang)*r*0.45)),
                     (sx+int(math.cos(perp)*hw),sy+int(math.sin(perp)*hw*0.45)),
                     (sx+int(math.cos(ang+math.pi)*r*0.95),sy+int(math.sin(ang+math.pi)*r*0.45)),
                     (sx-int(math.cos(perp)*hw),sy-int(math.sin(perp)*hw*0.45))]
                pygame.draw.polygon(surf,dark,[(p[0]+2,p[1]+2) for p in pts])
                pygame.draw.polygon(surf,C["wsh"],pts)
                pygame.draw.polygon(surf,lerp_c(C["wsh"],(200,200,200),0.2),pts,1)
                if self.utype==UT.CARRIER:
                    pygame.draw.line(surf,(180,200,200),pts[0],pts[2],2); sfx_glow(surf,gl,(sx,sy),r//2,14)
                else:
                    ta=self._tang(cam,sx,sy,ang)
                    pygame.draw.line(surf,(200,215,210),(sx,sy),(sx+int(math.cos(ta)*(r+4)),sy+int(math.sin(ta)*(r+4)*0.4)),max(2,r//5))

        elif self.utype in (UT.PSI_DRONE,UT.MIND_BLADE):
            pr=int(r*1.1) if self.utype==UT.MIND_BLADE else r
            sfx_glow(surf,C["psi"],(sx,sy-d),pr+2,33)
            pts=[(sx+int(math.cos(ph+i*math.pi*2/5)*pr),sy-d+int(math.sin(ph+i*math.pi*2/5)*pr*0.5)) for i in range(5)]
            pygame.draw.polygon(surf,lerp_c(C["psi"],(60,20,100),0.5),pts)
            pygame.draw.polygon(surf,C["psi"],pts,1)

        else:
            draw_dome3d(surf,sx,sy-d,r,top,dark)

        if selected:
            sel_r=r+5
            gs=pygame.Surface((sel_r*2+4,sel_r*2+4),pygame.SRCALPHA)
            pygame.draw.ellipse(gs,(*C["sel"],28),(0,sel_r//2,sel_r*2+4,sel_r+4))
            pygame.draw.ellipse(gs,(*C["sel"],138),(0,sel_r//2,sel_r*2+4,sel_r+4),2)
            surf.blit(gs,(sx-sel_r-2,sy-sel_r//2-2))
        self.draw_hbar(surf,cam,w=r*2+6,ey=d)
        if selected and self.move_target:
            tx2,ty2=cam.w2s(*self.move_target)
            pygame.draw.line(surf,(*C["sel"],60),(sx,sy),(tx2,ty2),1)

# ── Economy ───────────────────────────────────────────────────────────────────
class Economy:
    def __init__(self,bm=0,be=0):
        self.metal=250.+bm; self.energy=600.+be
        self.max_metal=2000.; self.max_energy=4000.
        self.metal_rate=0.; self.energy_rate=0.
    def tick(self,buildings,mult=1.):
        self.metal_rate=self.energy_rate=0.
        for b in buildings:
            if not b.alive: continue
            self.metal_rate+=b.metal_gen*mult; self.energy_rate+=b.energy_gen*mult
        self.metal=max(0,min(self.max_metal,self.metal+self.metal_rate/FPS))
        self.energy=max(0,min(self.max_energy,self.energy+self.energy_rate/FPS))
    def can_afford_b(self,bt):
        sp=BSPECS[bt]; return self.metal>=sp["mc"] and self.energy>=sp["ec"]
    def pay_b(self,bt):
        sp=BSPECS[bt]; self.metal-=sp["mc"]; self.energy-=sp["ec"]

# ── AI Think Log ──────────────────────────────────────────────────────────────
class AILog:
    def __init__(self,maxlines=26):
        self.lines=collections.deque(maxlen=maxlines)
        self.ages=collections.deque(maxlen=maxlines)
        self._t=0
    def log(self,msg,imp=False):
        prefix="▶ " if imp else "  "
        self.lines.append(prefix+msg[:34])
        self.ages.append(self._t)
    def tick(self): self._t+=1
    def draw(self,surf,font,x,y,w,h):
        rrect(surf,C["abg"],(x,y,w,h),5,1,C["abd"])
        t=font.render("AI COGNITION",True,C["atx"]); surf.blit(t,(x+7,y+4))
        pygame.draw.line(surf,C["abd"],(x+4,y+18),(x+w-4,y+18))
        lh=13; ly=y+21
        for line,age in zip(self.lines,self.ages):
            if ly+lh>y+h: break
            rec=max(0,1.-(self._t-age)/240.)
            col=lerp_c(C["adm"],C["atx"],rec)
            surf.blit(font.render(line,True,col),(x+4,ly)); ly+=lh

# ── AI ────────────────────────────────────────────────────────────────────────
class AI:
    """5-phase AI: Scout → Expand → Fortify → Attack → Dominate"""
    def __init__(self,team,eco,buildings,units,difficulty=Difficulty.MEDIUM):
        self.team=team; self.eco=eco; self.buildings=buildings; self.units=units
        self.difficulty=difficulty; self.p=DIFF[difficulty]
        self.tick=0; self.atk_timer=FPS*random.randint(*self.p["ar"])
        self.wave_size=self.p["w0"]; self._prev_cmd_hp=1.
        self.log=AILog(); self.phase="SCOUT"
        self._phase_timer=0; self._harass_timer=0

    def update(self,all_e,projs,terrain,mdeps,notifs=None,sound=None,stats=None):
        self.tick+=1; self.log.tick()
        p=self.p
        my_b=[b for b in self.buildings if b.team==self.team and b.alive]
        my_u=[u for u in self.units    if u.team==self.team and u.alive]
        cmd=next((b for b in my_b if b.btype==BT.COMMANDER),None)
        facs=[b for b in my_b if b.btype in (BT.FACTORY,BT.LAB,BT.AIRPAD,BT.SHIPYARD,BT.PSI_TOWER,BT.RESEARCH)]
        en=[e for e in all_e if e.team!=self.team and e.alive]
        en_b=[e for e in en if isinstance(e,Building)]
        en_u=[e for e in en if isinstance(e,Unit)]

        solars=[b for b in my_b if b.btype==BT.SOLAR]
        extrs=[b for b in my_b if b.btype==BT.METAL_X]
        fabs=[b for b in my_b if b.btype==BT.FACTORY]
        turrets=[b for b in my_b if b.btype==BT.TURRET]
        aa_guns=[b for b in my_b if b.btype==BT.AA_GUN]
        airpads=[b for b in my_b if b.btype==BT.AIRPAD]
        labs=[b for b in my_b if b.btype==BT.LAB]
        shields=[b for b in my_b if b.btype==BT.SHIELD_GEN]
        psi_t=[b for b in my_b if b.btype==BT.PSI_TOWER]
        research=[b for b in my_b if b.btype==BT.RESEARCH]

        threat_radius=500 if cmd else 300
        near_threat=[e for e in en if cmd and dist((cmd.x,cmd.y),(e.x,e.y))<threat_radius]
        is_attacked=bool(near_threat)
        eco_ok=self.eco.metal>120 and self.eco.energy>250
        have_army=len(my_u)>=self.wave_size

        # Phase transitions every 4s
        self._phase_timer-=1
        if self._phase_timer<=0:
            self._phase_timer=FPS*4; old=self.phase
            if is_attacked and cmd and cmd.hfrac()<0.4: self.phase="FORTIFY"
            elif not eco_ok or len(fabs)==0: self.phase="EXPAND"
            elif have_army and len(fabs)>=1 and len(turrets)>=1: self.phase="ATTACK"
            elif len(my_b)>10 and have_army and self.tick>FPS*120: self.phase="DOMINATE"
            elif self.tick<FPS*30 and not fabs: self.phase="SCOUT"
            else: self.phase="EXPAND"
            if old!=self.phase: self.log.log(f"Phase: {old}→{self.phase}",imp=True)

        self.log.log(f"T{self.tick} [{self.phase}] U:{len(my_u)} B:{len(my_b)}")
        self.log.log(f"  M:{int(self.eco.metal)} E:{int(self.eco.energy)}")

        # Scout
        if self.phase=="SCOUT" and cmd and self.tick%int(FPS*8)==0:
            scouts=[u for u in my_u if u.utype in (UT.SCOUT,UT.FIGHTER) and u.state==UState.IDLE]
            for s in scouts[:2]:
                ang=random.uniform(0,math.pi*2)
                tx=max(100,min(MAP_W-100,cmd.x+math.cos(ang)*800))
                ty=max(100,min(MAP_H-100,cmd.y+math.sin(ang)*800))
                s.command_move(tx,ty); self.log.log(f"Scout→({int(tx)},{int(ty)})")

        # Build phase
        if cmd and self.tick%p["biv"]==0:
            placed=[(b.x,b.y) for b in extrs]
            for dep in sorted(mdeps,key=lambda d2:dist(d2,(cmd.x,cmd.y))):
                if dist(dep,(cmd.x,cmd.y))>BUILD_RANGE: continue
                if any(dist(dep,pm)<TILE*2 for pm in placed): continue
                if self._place(BT.METAL_X,dep[0],dep[1],terrain,cmd):
                    self.log.log(f"Built Metal@{int(dep[0])},{int(dep[1])}",imp=True)
                break

            want_s=int(3+self.tick/1000*(1+p["ag"]))
            if len(solars)<want_s:
                if self._place(BT.SOLAR,cmd.x+random.randint(-300,300),cmd.y+random.randint(-300,300),terrain,cmd):
                    self.log.log(f"Built Solar({len(solars)}→{want_s})",imp=True)

            want_f=max(1,int(1+self.tick/1800*(1+p["ag"])))
            if len(fabs)<want_f:
                if self._place(BT.FACTORY,cmd.x+random.randint(-350,350),cmd.y+random.randint(-350,350),terrain,cmd):
                    self.log.log(f"Built Factory({len(fabs)}→{want_f})",imp=True)

            want_t=int(2+p["ag"]*6)
            if len(fabs)>=1 and len(turrets)<want_t and self.eco.metal>90:
                if self._place(BT.TURRET,cmd.x+random.randint(-400,400),cmd.y+random.randint(-400,400),terrain,cmd):
                    self.log.log(f"Built Turret({len(turrets)}→{want_t})")

            if self.difficulty!=Difficulty.EASY:
                want_aa=int(1+p["ag"]*4)
                if len(aa_guns)<want_aa and len(fabs)>=1:
                    if self._place(BT.AA_GUN,cmd.x+random.randint(-350,350),cmd.y+random.randint(-350,350),terrain,cmd):
                        self.log.log(f"Built AA({len(aa_guns)}→{want_aa})")
                if len(fabs)>=1 and len(airpads)<int(p["ag"]*2) and self.eco.metal>260:
                    if self._place(BT.AIRPAD,cmd.x+random.randint(-300,300),cmd.y+random.randint(-300,300),terrain,cmd):
                        self.log.log("Built Airpad",imp=True)

            if self.difficulty in (Difficulty.HARD,Difficulty.BRUTAL):
                if len(fabs)>=2 and len(labs)<2 and self.eco.metal>420:
                    if self._place(BT.LAB,cmd.x+random.randint(-280,280),cmd.y+random.randint(-280,280),terrain,cmd):
                        self.log.log("Built Lab",imp=True)
                if len(shields)<2 and len(fabs)>=1 and self.eco.metal>160:
                    if self._place(BT.SHIELD_GEN,cmd.x+random.randint(-200,200),cmd.y+random.randint(-200,200),terrain,cmd):
                        self.log.log("Built Shield Gen",imp=True)
                if len(psi_t)<1 and self.eco.metal>500 and self.tick>FPS*180:
                    if self._place(BT.PSI_TOWER,cmd.x+random.randint(-250,250),cmd.y+random.randint(-250,250),terrain,cmd):
                        self.log.log("Built Psi Tower",imp=True)

            if self.difficulty==Difficulty.BRUTAL:
                if len(research)<1 and self.eco.metal>600 and self.tick>FPS*240:
                    if self._place(BT.RESEARCH,cmd.x+random.randint(-260,260),cmd.y+random.randint(-260,260),terrain,cmd):
                        self.log.log("Built Research Ctr",imp=True)

        # Commander movement
        if cmd and self.tick%(FPS*15)==0:
            if self.phase in ("EXPAND","DOMINATE"):
                free=[d for d in mdeps if not any(dist(d,(b.x,b.y))<TILE*3 for b in my_b)]
                if free:
                    near=min(free,key=lambda d:dist(d,(cmd.x,cmd.y)))
                    if dist(near,(cmd.x,cmd.y))>300:
                        cmd.move_target=near
                        self.log.log(f"CMD→deposit",imp=True)
            elif self.phase=="FORTIFY" and near_threat:
                t2=near_threat[0]; dx=cmd.x-t2.x; dy=cmd.y-t2.y; l=math.hypot(dx,dy) or 1
                cmd.move_target=(max(100,min(MAP_W-100,cmd.x+dx/l*350)),max(100,min(MAP_H-100,cmd.y+dy/l*350)))
                self.log.log("CMD retreating",imp=True)

        # Unit production with context awareness
        air_threat=any(getattr(u,"dom",Domain.GROUND)==Domain.AIR for u in en_u)
        naval_threat=any(getattr(u,"dom",Domain.GROUND)==Domain.NAVAL for u in en_u)
        ground_heavy=sum(1 for u in en_u if u.utype in (UT.TANK,UT.MECH,UT.GOLIATH,UT.TITAN))>3

        for fac in facs:
            max_q=4 if self.difficulty==Difficulty.BRUTAL else(3 if self.difficulty==Difficulty.HARD else 2)
            if len(fac.build_queue)<max_q and self.eco.metal>65 and self.eco.energy>160:
                utypes=fac.produces
                if utypes:
                    weights=[]
                    for u in utypes:
                        w=2
                        if self.difficulty==Difficulty.EASY: w=random.randint(1,3)
                        else:
                            if u==UT.SCOUT and self.phase=="SCOUT": w=5
                            if u in (UT.TANK,UT.MECH) and ground_heavy: w=4
                            if u in (UT.FIGHTER,UT.GUNSHIP) and air_threat: w=5
                            if u in (UT.GUNBOAT,UT.CARRIER) and naval_threat: w=4
                            if u in (UT.ARTILLERY,UT.SIEGE) and self.phase in ("ATTACK","DOMINATE"): w=5
                            if u in (UT.MEDIC,UT.ENGINEER) and self.phase=="FORTIFY": w=4
                            if u in (UT.TITAN,UT.GOLIATH) and self.phase=="DOMINATE": w=6
                            if self.difficulty==Difficulty.BRUTAL: w=int(w*1.4)
                        weights.append(w)
                    ut=random.choices(utypes,weights=weights[:len(utypes)])[0]
                    fac.enqueue(ut,self.eco)
                    self.log.log(f"Queue {USPECS[ut]['name']} ({fac.name[:8]})")

        # Attack wave
        self.atk_timer-=1
        if self.atk_timer<=0 and have_army and self.phase in ("ATTACK","DOMINATE"):
            lo,hi=self.p["ar"]; self.atk_timer=FPS*random.randint(lo,hi)
            self.wave_size=min(self.wave_size+2,self.p["wm"])
            if en_b:
                tgt=(next((e for e in en_b if e.btype==BT.COMMANDER),None) or min(en_b,key=lambda e:e.hfrac()))
                ground_u=[u for u in my_u if u.dom in (Domain.GROUND,Domain.MECH)]
                air_u=[u for u in my_u if u.dom==Domain.AIR]
                naval_u=[u for u in my_u if u.dom==Domain.NAVAL]
                psi_u=[u for u in my_u if u.dom==Domain.PSIONIC]
                arty=[u for u in ground_u if u.utype in (UT.ARTILLERY,UT.SIEGE)]
                assault=[u for u in ground_u if u not in arty]
                self.log.log(f"WAVE→{tgt.name} g:{len(assault)} a:{len(air_u)} arty:{len(arty)}",imp=True)
                # Artillery stays at range
                for u in arty:
                    d2=dist((u.x,u.y),(tgt.x,tgt.y))
                    safe=max(USPECS[u.utype]["wpn"]["r"]*0.75,180)
                    if d2>safe+50:
                        ang2=math.atan2(tgt.y-u.y,tgt.x-u.x)
                        u.command_move(max(50,min(MAP_W-50,tgt.x-math.cos(ang2)*safe)),max(50,min(MAP_H-50,tgt.y-math.sin(ang2)*safe)))
                # Split on hard/brutal
                if self.difficulty in (Difficulty.HARD,Difficulty.BRUTAL) and len(assault)>14:
                    split=len(assault)//2
                    for u in assault[:split]: u.command_move(tgt.x+random.uniform(-80,80),tgt.y+random.uniform(-80,80))
                    alt=en_b[random.randint(0,len(en_b)-1)]
                    for u in assault[split:]: u.command_move(alt.x+random.uniform(-90,90),alt.y+random.uniform(-90,90))
                    self.log.log(f"Split: {split}+{len(assault)-split}")
                else:
                    for u in assault: u.command_move(tgt.x+random.uniform(-80,80),tgt.y+random.uniform(-80,80))
                for u in air_u: u.command_move(tgt.x+random.uniform(-60,60),tgt.y+random.uniform(-60,60))
                for u in psi_u: u.command_move(tgt.x+random.uniform(-50,50),tgt.y+random.uniform(-50,50))
                for u in naval_u:
                    alt=en_b[random.randint(0,len(en_b)-1)]
                    u.command_move(alt.x+random.uniform(-100,100),alt.y+random.uniform(-100,100))

        # Brutal harassment
        if self.difficulty==Difficulty.BRUTAL:
            self._harass_timer-=1
            if self._harass_timer<=0 and en_b:
                self._harass_timer=FPS*random.randint(8,18)
                fast=[u for u in my_u if u.dom==Domain.AIR and u.state==UState.IDLE]
                if fast:
                    ht=random.choice(en_b)
                    for u in fast[:3]: u.command_move(ht.x+random.uniform(-50,50),ht.y+random.uniform(-50,50))
                    self.log.log(f"Harass {ht.name} x{len(fast[:3])}",imp=True)

        # Defend/retreat
        for u in my_u:
            if u.state==UState.IDLE and en:
                near=min(en,key=lambda e:dist((u.x,u.y),(e.x,e.y)))
                react=(u.weapon["r"]*1.5 if u.weapon else 0)
                if dist((u.x,u.y),(near.x,near.y))<react: u.command_attack(near)
            if u.hfrac()<p["rh"] and cmd and u.state!=UState.RETREATING:
                u.state=UState.RETREATING
                u.move_target=(cmd.x+random.uniform(-100,100),cmd.y+random.uniform(-100,100))
                self.log.log(f"{u.name} retreat HP:{int(u.hfrac()*100)}%",imp=True)

        if cmd and notifs:
            f=cmd.hfrac()
            if f<0.3 and self._prev_cmd_hp>=0.3:
                notifs.add("⚠ ENEMY COMMANDER CRITICAL!",C["nok"],200)
                self.log.log("OWN CMD CRITICAL!",imp=True)
            self._prev_cmd_hp=f

    def _place(self,btype,wx,wy,terrain,cmd):
        sp=BSPECS[btype]
        if not self.eco.can_afford_b(btype): return False
        wx=round(wx/TILE)*TILE+sp["sz"]*TILE//2
        wy=round(wy/TILE)*TILE+sp["sz"]*TILE//2
        if cmd and dist((cmd.x,cmd.y),(wx,wy))>BUILD_RANGE: return False
        if btype==BT.SHIPYARD:
            if not terrain.is_water(wx,wy): return False
        elif not terrain.walkable(wx,wy): return False
        r=sp["sz"]*TILE//2+12
        if any(dist((wx,wy),(b.x,b.y))<r+b.radius for b in self.buildings if b.alive): return False
        self.eco.pay_b(btype)
        self.buildings.append(Building(wx,wy,self.team,btype))
        return True

# ── Build Ghost ───────────────────────────────────────────────────────────────
class BuildGhost:
    def __init__(self,btype,terrain,buildings,player_cmd):
        self.btype=btype; self.terrain=terrain; self.buildings=buildings; self.cmd=player_cmd
        self.wx=self.wy=0.; self.valid=False; self.reason=""
    def update(self,wx,wy):
        sp=BSPECS[self.btype]; size=sp["sz"]
        self.wx=round(wx/TILE)*TILE+size*TILE//2
        self.wy=round(wy/TILE)*TILE+size*TILE//2
        if self.btype==BT.SHIPYARD:
            if not self.terrain.is_water(self.wx,self.wy): self.valid=False;self.reason="Needs water";return
        elif not self.terrain.walkable(self.wx,self.wy): self.valid=False;self.reason="Not walkable";return
        if self.cmd and dist((self.cmd.x,self.cmd.y),(self.wx,self.wy))>BUILD_RANGE:
            self.valid=False;self.reason="Out of build range";return
        r=size*TILE//2
        if any(dist((self.wx,self.wy),(b.x,b.y))<r+b.radius+6 for b in self.buildings if b.alive):
            self.valid=False;self.reason="Blocked";return
        self.valid=True;self.reason=""
    def draw(self,surf,cam,font):
        sp=BSPECS[self.btype]; ps=int(sp["sz"]*TILE*cam.zoom)
        sx,sy=cam.w2s(self.wx,self.wy)
        ok=self.valid; out=(62,202,82) if ok else (222,60,40)
        s=pygame.Surface((ps,ps),pygame.SRCALPHA); s.fill((*out,55))
        pygame.draw.rect(s,(*out,180),(0,0,ps,ps),2); surf.blit(s,(sx-ps//2,sy-ps//2))
        lbl=font.render(sp["name"],True,out); surf.blit(lbl,(sx-lbl.get_width()//2,sy-lbl.get_height()//2))
        info=self.reason if not ok else f"M:{sp['mc']} E:{sp['ec']}"
        ct=font.render(info,True,(*out,185)); surf.blit(ct,(sx-ct.get_width()//2,sy+ps//2+5))

# ── Stats Panel ───────────────────────────────────────────────────────────────
class StatsPanel:
    def __init__(self,fs,fm): self.fs=fs; self.fm=fm; self.show=False
    def toggle(self): self.show=not self.show
    def draw(self,surf,stats,peco,aeco,pu,au,buildings):
        if not self.show: return
        w=480; h=380; x=(SCREEN_W-SIDE_W-w)//2; y=(SCREEN_H-UI_H-h)//2
        rrect(surf,C["sbg"],(x,y,w,h),8,2,C["ubrd"])
        surf.blit(self.fm.render("BATTLE STATISTICS  [F1 to close]",True,C["tx"]),(x+12,y+8))
        pygame.draw.line(surf,C["ubrd"],(x+8,y+26),(x+w-8,y+26))
        cols=[C["p1"],C["p2"]]; names=["PLAYER","AI"]
        for ci,(cname,ccol) in enumerate(zip(names,cols)):
            cx=x+14+ci*(w//2)
            surf.blit(self.fm.render(cname,True,ccol),(cx,y+32))
            eco=peco if ci==0 else aeco
            units_list=pu if ci==0 else au
            bldg_count=len([b for b in buildings if b.team==(Team.PLAYER if ci==0 else Team.AI) and b.alive])
            rows=[
                f"Kills:     {stats.kills[ci]}",
                f"Deaths:    {stats.deaths[ci]}",
                f"Dmg Dealt: {int(stats.dmg_dealt[ci])}",
                f"Dmg Taken: {int(stats.dmg_taken[ci])}",
                f"Units:     {len(units_list)}",
                f"Buildings: {bldg_count}",
                f"Metal/s:   {eco.metal_rate:+.1f}",
                f"Energy/s:  {eco.energy_rate:+.1f}",
                f"Metal:     {int(eco.metal)}",
                f"Energy:    {int(eco.energy)}",
            ]
            for ri,text in enumerate(rows):
                surf.blit(self.fs.render(text,True,C["tx"]),(cx,y+50+ri*18))
        # Sparklines
        sy2=y+h-100; sw=w-24; sh=65
        pygame.draw.rect(surf,C["upan"],(x+12,sy2,sw,sh),border_radius=4)
        surf.blit(self.fs.render("Economy: metal rate history",True,C["txd"]),(x+16,sy2+2))
        for ci,ccol in enumerate(cols):
            hist=stats.eco_hist[ci]
            if len(hist)>2:
                vals=[h2[0] for h2 in hist]
                mn=min(vals); mx2=max(vals)
                if mx2==mn: mx2=mn+1
                pts=[]
                for i,v in enumerate(vals):
                    px2=x+14+int(i/(len(vals)-1)*(sw-4))
                    py2=sy2+sh-4-int((v-mn)/(mx2-mn)*(sh-20))
                    pts.append((px2,py2))
                if len(pts)>1: pygame.draw.lines(surf,ccol,False,pts,2)
        # Unit type breakdown
        if pu:
            types={}
            for u in pu: types[u.name]=types.get(u.name,0)+1
            tx2=x+14; ty2=y+h-28
            surf.blit(self.fs.render("Your units: "+" | ".join(f"{v}x{k}" for k,v in list(types.items())[:6]),True,C["txd"]),(tx2,ty2))

# ── UI ────────────────────────────────────────────────────────────────────────
class UI:
    def __init__(self,fs,fm,fl): self.fs=fs; self.fm=fm; self.fl=fl

    def draw(self,surf,eco,sel,tick,mpos):
        pw=SCREEN_W-SIDE_W
        pr=pygame.Rect(0,SCREEN_H-UI_H,pw,UI_H)
        ps=pygame.Surface((pr.width,pr.height)); ps.fill(C["ubg"])
        for i in range(0,pr.height,3): pygame.draw.line(ps,C["grid"],(0,i),(pr.width,i))
        surf.blit(ps,pr.topleft)
        pygame.draw.line(surf,C["ubrd"],(0,SCREEN_H-UI_H),(pw,SCREEN_H-UI_H),1)
        self._eco(surf,eco,tick)
        if sel: self._sel(surf,sel,eco,mpos)
        else: self._help(surf)

    def _eco(self,surf,eco,tick):
        y=SCREEN_H-UI_H+8
        self._rbar(surf,10,y,eco.metal,eco.max_metal,eco.metal_rate,C["mt"],"M")
        self._rbar(surf,10,y+30,eco.energy,eco.max_energy,eco.energy_rate,C["en"],"E")

    def _rbar(self,surf,x,y,val,mx,rate,col,icon):
        bw=230; surf.blit(self.fm.render(icon,True,col),(x,y+1))
        pygame.draw.rect(surf,(16,24,32),(x+20,y+2,bw,16),border_radius=3)
        fw=int(bw*max(0,val/mx))
        if fw>0:
            pygame.draw.rect(surf,(*col,142),(x+20,y+2,fw,16),border_radius=3)
            sh=pygame.Surface((fw,5),pygame.SRCALPHA); sh.fill((*col,46)); surf.blit(sh,(x+20,y+2))
        pygame.draw.rect(surf,(*col,60),(x+20,y+2,bw,16),1,border_radius=3)
        surf.blit(self.fs.render(f"{int(val)}/{int(mx)}  {rate:+.1f}/s",True,(192,210,204)),(x+24,y+4))

    def _sel(self,surf,sel,eco,mpos):
        x0,y0=12,SCREEN_H-UI_H+68
        if isinstance(sel,list):
            surf.blit(self.fm.render(f"{len(sel)} selected",True,C["tx"]),(x0,y0))
            types={}
            for u in sel: types[u.name]=types.get(u.name,0)+1
            dy=22
            for name,count in list(types.items())[:5]:
                surf.blit(self.fs.render(f"  {count}x {name}",True,C["txd"]),(x0,y0+dy)); dy+=15
            return
        rrect(surf,C["upan"],(x0-4,y0-4,195,28),3)
        surf.blit(self.fm.render(getattr(sel,"name","?"),True,tc(sel.team,glow=True)),(x0,y0))
        hc=sel.hcol()
        surf.blit(self.fs.render(f"HP {sel.hp}/{sel.max_hp} ({int(sel.hfrac()*100)}%)",True,hc),(x0,y0+22))
        pygame.draw.rect(surf,(18,18,18),(x0,y0+37,170,5),border_radius=2)
        cw=int(170*sel.hfrac())
        if cw>0: pygame.draw.rect(surf,hc,(x0,y0+37,cw,5),border_radius=2)
        ey=y0+50
        if isinstance(sel,Unit):
            sp=USPECS[sel.utype]
            surf.blit(self.fs.render(f"[{sel.dom.name}] T{sp['tier']} | Kills:{sel.kills} | Spd:{sel.speed:.1f}",True,C["txd"]),(x0,ey)); ey+=14
            surf.blit(self.fs.render(sp.get("desc",""),True,C["txd"]),(x0,ey)); ey+=14
            if sel.weapon: surf.blit(self.fs.render(f"Rng:{sel.weapon['r']} Dmg:{sel.weapon['d']} | Rclick=move/attack",True,C["txd"]),(x0,ey))
        if isinstance(sel,Building):
            if sel.movable: surf.blit(self.fs.render("Rclick=MOVE | Tab=select cmd",True,(140,200,140)),(x0,ey)); ey+=14
            if sel.btype==BT.COMMANDER: self._cmd_menu(surf,eco,x0+205,SCREEN_H-UI_H+8)
            elif sel.produces: self._fac_panel(surf,sel,eco,x0+205,SCREEN_H-UI_H+8,mpos)
            elif sel.weapon: surf.blit(self.fs.render(f"Rng:{sel.weapon['r']} Dmg:{sel.weapon['d']}",True,C["txd"]),(x0,ey))

    def _cmd_menu(self,surf,eco,x0,y0):
        surf.blit(self.fs.render("BUILD [1-0 keys]",True,C["txd"]),(x0,y0+2))
        pygame.draw.line(surf,C["ubrd"],(x0,y0+14),(x0+600,y0+14))
        cols=5
        for i,btype in enumerate(BUILD_FROM_CMD[:10]):
            sp=BSPECS[btype]; col=i%cols; row=i//cols
            cx=x0+col*118; cy=y0+18+row*58
            can=eco.can_afford_b(btype)
            rrect(surf,C["uhi"] if can else C["upan"],(cx,cy,115,54),4,1,(80,120,100) if can else C["ubrd"])
            key=str(i+1) if i<9 else "0"
            surf.blit(self.fs.render(f"[{key}]",True,(200,222,202) if can else (68,78,72)),(cx+4,cy+4))
            surf.blit(self.fs.render(sp["name"],True,C["tx"] if can else C["txd"]),(cx+26,cy+4))
            mc=C["mt"] if eco.metal>=sp["mc"] else C["hr"]
            ec2=C["en"] if eco.energy>=sp["ec"] else C["hr"]
            surf.blit(self.fs.render(f"M:{sp['mc']}",True,mc),(cx+4,cy+32))
            surf.blit(self.fs.render(f"E:{sp['ec']}",True,ec2),(cx+65,cy+32))

    def _fac_panel(self,surf,fac,eco,x0,y0,mpos):
        surf.blit(self.fs.render(f"{fac.name}  [1-{len(fac.produces)}]",True,C["txd"]),(x0,y0+2))
        pygame.draw.line(surf,C["ubrd"],(x0,y0+14),(x0+610,y0+14))
        for i,utype in enumerate(fac.produces[:6]):
            sp=USPECS[utype]; cx=x0+i*118; cy=y0+18
            can=eco.metal>=sp["mc"] and eco.energy>=sp["ec"]
            dom_col={"GROUND":C["tx"],"AIR":(180,202,255),"NAVAL":(102,182,222),"MECH":(222,182,102),"PSIONIC":(220,102,255)}[sp["dom"].name]
            rrect(surf,C["uhi"] if can else C["upan"],(cx,cy,115,54),4,1,(80,120,100) if can else C["ubrd"])
            surf.blit(self.fs.render(f"[{i+1}]T{sp['tier']}",True,(200,222,202) if can else (68,78,72)),(cx+4,cy+4))
            surf.blit(self.fs.render(sp["name"],True,dom_col if can else C["txd"]),(cx+4,cy+18))
            surf.blit(self.fs.render(f"M:{sp['mc']}",True,C["mt"]),(cx+4,cy+34))
            surf.blit(self.fs.render(f"E:{sp['ec']}",True,C["en"]),(cx+65,cy+34))
        # Queue
        qx=x0; qy=y0+80
        surf.blit(self.fs.render("BUILD QUEUE  [X=cancel last]",True,C["txd"]),(qx,qy))
        qy+=14; sw=94; sh=34; gap=4
        if fac.build_queue:
            for qi,item in enumerate(fac.build_queue[:6]):
                utype2,total,rem=item[0],item[1],item[2]; usp=USPECS[utype2]
                bx2=qx+qi*(sw+gap); by2=qy; is_act=(qi==0)
                hov=pygame.Rect(bx2,by2,sw,sh).collidepoint(*mpos) if mpos else False
                rrect(surf,(30,52,46) if is_act else (16,26,24),(bx2,by2,sw,sh),3,1,
                      C["en"] if is_act else ((78,104,90) if hov else C["ubrd"]))
                surf.blit(self.fs.render(usp["name"],True,C["tx"] if is_act else C["txd"]),(bx2+4,by2+3))
                if is_act:
                    prog=1.-rem/total; pw=int((sw-8)*prog)
                    pygame.draw.rect(surf,(16,24,22),(bx2+4,by2+18,sw-8,8),border_radius=2)
                    if pw>0: pygame.draw.rect(surf,C["en"],(bx2+4,by2+18,pw,8),border_radius=2)
                    pt2=self.fs.render(f"{int(prog*100)}%",True,C["en"])
                    surf.blit(pt2,(bx2+sw//2-pt2.get_width()//2,by2+18))
                elif hov: surf.blit(self.fs.render("[X]",True,C["hr"]),(bx2+4,by2+16))
                else: surf.blit(self.fs.render(f"#{qi+1}",True,C["txd"]),(bx2+4,by2+16))
        else:
            surf.blit(self.fs.render("Empty — press 1-6",True,C["txd"]),(qx,qy+4))

    def _help(self,surf):
        x0,y0=12,SCREEN_H-UI_H+68
        for i,h in enumerate([
            "Left click/drag: select   Right click: move/attack/rally",
            "Commander: Rclick=MOVE   Tab=select cmd   1-0: build structure",
            "Factory/Airpad: 1-6 queue unit   X: cancel queue   Del: destroy",
            "+/- scroll: zoom   WASD/arrows: pan   F1: stats   V: AI log   F11: fullscreen",
        ]): surf.blit(self.fs.render(h,True,C["txd"]),(x0,y0+i*20))

# ── Minimap ───────────────────────────────────────────────────────────────────
class Minimap:
    def __init__(self):
        self.rect=pygame.Rect(SCREEN_W-MINIMAP_W,SCREEN_H-MINIMAP_H,MINIMAP_W,MINIMAP_H)
        self._cache=None
    def _render(self,terrain):
        s=pygame.Surface((MINIMAP_W,MINIMAP_H))
        sx=MINIMAP_W/terrain.tw; sy=MINIMAP_H/terrain.th
        for ty in range(terrain.th):
            for tx in range(terrain.tw):
                t=terrain.data[ty][tx]
                col=C["w0"] if t==1 else(C["m0"] if t==2 else(C["g1"] if (tx+ty)%2==0 else C["g0"]))
                if terrain.metal[ty][tx]: col=C["dep"]
                pygame.draw.rect(s,col,(int(tx*sx),int(ty*sy),max(1,int(sx)+1),max(1,int(sy)+1)))
        return s
    def draw(self,surf,terrain,buildings,units,cam,tick):
        if self._cache is None or tick%600==0: self._cache=self._render(terrain)
        s=self._cache.copy()
        for b in buildings:
            if not b.alive: continue
            pygame.draw.rect(s,tc(b.team),(int(b.x/MAP_W*MINIMAP_W)-2,int(b.y/MAP_H*MINIMAP_H)-2,5,5))
        for u in units:
            if not u.alive: continue
            col=tc(u.team) if u.dom==Domain.GROUND else((178,198,255) if u.dom==Domain.AIR else(78,148,208))
            pygame.draw.circle(s,col,(int(u.x/MAP_W*MINIMAP_W),int(u.y/MAP_H*MINIMAP_H)),2)
        cx=int(cam.x/MAP_W*MINIMAP_W); cy=int(cam.y/MAP_H*MINIMAP_H)
        pygame.draw.line(s,(180,200,188),(cx-6,cy),(cx+6,cy),1)
        pygame.draw.line(s,(180,200,188),(cx,cy-6),(cx,cy+6),1)
        pygame.draw.rect(surf,(9,14,20),self.rect); surf.blit(s,self.rect)
        pygame.draw.rect(surf,C["ubrd"],self.rect,2)
    def world_from_click(self,mx,my):
        if not self.rect.collidepoint(mx,my): return None
        return (mx-self.rect.x)/MINIMAP_W*MAP_W,(my-self.rect.y)/MINIMAP_H*MAP_H

# ── Terrain renderer (iso tile-by-tile) ───────────────────────────────────────
def draw_terrain_iso(surf,terrain,cam):
    surf.fill(C["bg"])
    vw=SCREEN_W-SIDE_W; vh=SCREEN_H-UI_H
    # Step through world space in tile increments, only visible tiles
    step=max(1,int(TILE/cam.zoom*0.7))
    # Compute rough world bounds from screen corners
    corners=[s2w(0,0,cam),s2w(vw,0,cam),s2w(0,vh,cam),s2w(vw,vh,cam)]
    wx0=max(0,min(c[0] for c in corners)-TILE*6)
    wx1=min(MAP_W,max(c[0] for c in corners)+TILE*6)
    wy0=max(0,min(c[1] for c in corners)-TILE*6)
    wy1=min(MAP_H,max(c[1] for c in corners)+TILE*6)
    x=wx0
    while x<wx1:
        y=wy0
        while y<wy1:
            tx2=int(x//TILE); ty2=int(y//TILE)
            if 0<=tx2<terrain.tw and 0<=ty2<terrain.th:
                t=terrain.data[ty2][tx2]
                if t==0: col=[C["g0"],C["g1"],C["g2"]][(tx2*7+ty2*13)%3]
                elif t==1: col=C["w0"] if (tx2+ty2)%2==0 else C["w1"]
                else: col=C["m0"] if (tx2+ty2)%2==0 else C["m1"]
                if terrain.metal[ty2][tx2]: col=C["dep"]
                cx2,cy2=iso(x+TILE//2,y+TILE//2,cam)
                tw2=max(2,int(TILE*cam.zoom*ISO_SX*2))
                th2=max(1,int(TILE*cam.zoom*ISO_SY*2))
                pts=[(cx2,cy2-th2),(cx2+tw2//2,cy2),(cx2,cy2+th2),(cx2-tw2//2,cy2)]
                pygame.draw.polygon(surf,col,pts)
                # Mountain height block
                if t==2:
                    hd=max(3,int(TILE*cam.zoom*0.28))
                    rp=[(cx2,cy2+th2),(cx2+tw2//2,cy2),(cx2+tw2//2,cy2+hd),(cx2,cy2+th2+hd)]
                    lp=[(cx2,cy2+th2),(cx2,cy2+th2+hd),(cx2-tw2//2,cy2+hd),(cx2-tw2//2,cy2)]
                    pygame.draw.polygon(surf,C["m1"],rp)
                    pygame.draw.polygon(surf,lerp_c(C["m0"],(0,0,0),0.15),lp)
            y+=step
        x+=step
    # Grid dots at coarse level
    if cam.zoom>0.45:
        gx=wx0
        while gx<wx1:
            gy=wy0
            while gy<wy1:
                px,py=iso(gx,gy,cam)
                if 0<=px<vw and 0<=py<vh: pygame.draw.circle(surf,C["grid"],(px,py),1)
                gy+=TILE*4
            gx+=TILE*4

# ── Difficulty Screen ─────────────────────────────────────────────────────────
def diff_screen(screen,clock):
    ft=pygame.font.SysFont("monospace",42,bold=True)
    fs=pygame.font.SysFont("monospace",13)
    fb=pygame.font.SysFont("monospace",20,bold=True)
    opts=[
        (Difficulty.EASY,  "EASY",   C["hg"], "Relaxed · small waves · reduced economy",       "[1]"),
        (Difficulty.MEDIUM,"MEDIUM", C["en"], "Balanced · scales · fair combat",                "[2]"),
        (Difficulty.HARD,  "HARD",   C["p2"], "Aggressive · air+naval · split attacks",         "[3]"),
        (Difficulty.BRUTAL,"BRUTAL", C["psi"],"Relentless · harassment · Titan production",     "[4]"),
    ]
    sel=None; tick=0
    while sel is None:
        tick+=1; screen.fill(C["bg"])
        for gx in range(0,SCREEN_W,48): pygame.draw.line(screen,C["grid"],(gx,0),(gx,SCREEN_H))
        for gy in range(0,SCREEN_H,48): pygame.draw.line(screen,C["grid"],(0,gy),(SCREEN_W,gy))
        t=ft.render("TOTAL RECURSION  v4",True,C["p1g"])
        screen.blit(t,(SCREEN_W//2-t.get_width()//2,int(SCREEN_H*0.14)))
        sub=fs.render("20 unit types · Iso 3D · 5-phase AI · Full stats · 4 difficulty levels",True,C["txd"])
        screen.blit(sub,(SCREEN_W//2-sub.get_width()//2,int(SCREEN_H*0.26)))
        mx,my=pygame.mouse.get_pos(); bw,bh=310,96; by0=int(SCREEN_H*0.34)
        for i,(diff,label,color,desc,key) in enumerate(opts):
            bx=SCREEN_W//2-bw//2; by=by0+i*(bh+16); rect=pygame.Rect(bx,by,bw,bh)
            hov=rect.collidepoint(mx,my)
            rrect(screen,lerp_c(C["upan"],C["uhi"],0.7 if hov else 0),rect,8,2,color if hov else C["ubrd"])
            if hov: sfx_glow(screen,color,(bx+bw//2,by+bh//2),bw//3,16)
            lt=fb.render(label,True,color if hov else lerp_c(color,C["txd"],0.4))
            screen.blit(lt,(bx+bw//2-lt.get_width()//2,by+10))
            screen.blit(fs.render(key,True,C["txd"]),(bx+10,by+12))
            screen.blit(fs.render(desc,True,C["txd"]),(bx+bw//2-fs.size(desc)[0]//2,by+52))
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.MOUSEBUTTONDOWN and ev.button==1:
                for i,(diff,*_) in enumerate(opts):
                    bx=SCREEN_W//2-bw//2; by=by0+i*(bh+16)
                    if pygame.Rect(bx,by,bw,bh).collidepoint(mx,my): sel=diff
            if ev.type==pygame.KEYDOWN:
                if ev.key==pygame.K_1: sel=Difficulty.EASY
                if ev.key==pygame.K_2: sel=Difficulty.MEDIUM
                if ev.key==pygame.K_3: sel=Difficulty.HARD
                if ev.key==pygame.K_4: sel=Difficulty.BRUTAL
        pygame.display.flip(); clock.tick(60)
    return sel

# ── Game ──────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self,difficulty):
        self.screen=pygame.display.set_mode((SCREEN_W,SCREEN_H),pygame.FULLSCREEN)
        pygame.display.set_caption("TOTAL RECURSION v4")
        self.clock=pygame.time.Clock()
        self.fs=pygame.font.SysFont("monospace",12)
        self.fm=pygame.font.SysFont("monospace",14,bold=True)
        self.fl=pygame.font.SysFont("monospace",19,bold=True)
        self.fxl=pygame.font.SysFont("monospace",50,bold=True)
        self.fs_think=pygame.font.SysFont("monospace",11)

        self.difficulty=difficulty
        self.sound=Sound(); self.parts=Particles(); self.shake=Shake()
        self.notifs=Notifs(self.fs)
        self.cam=Camera(); self.terrain=Terrain(MAP_W,MAP_H); self.mdeps=self.terrain.metal_deps()
        self.stats=Stats()

        # Shared lists — never reassigned (AI holds references)
        self.buildings: List[Building]=[]
        self.units:     List[Unit]=[]
        self.projs:     List[Proj]=[]
        self.explosions:List[Explosion]=[]

        dp=DIFF[difficulty]
        self.player_eco=Economy()
        self.ai_eco=Economy(bm=dp["bo"],be=dp["bo"]*2)
        self.ai_eco_mult=dp["eco"]

        p_cmd=Building(3*TILE+TILE,3*TILE+TILE,Team.PLAYER,BT.COMMANDER)
        a_cmd=Building(MAP_W-4*TILE,MAP_H-4*TILE,Team.AI,BT.COMMANDER)
        self.buildings+=[p_cmd,a_cmd]

        self.ai=AI(Team.AI,self.ai_eco,self.buildings,self.units,difficulty)
        self.ui=UI(self.fs,self.fm,self.fl)
        self.minimap=Minimap()
        self.stats_panel=StatsPanel(self.fs,self.fm)

        self.cam.center_on(p_cmd.x,p_cmd.y)
        self.selected: List[Entity]=[]
        self.drag_start=None; self.drag_end=None
        self.build_mode=False; self.ghost=None; self.pending_bt=None
        self.tick=0; self.game_over=None; self._atk_cd=0
        self.show_think=True

        self.notifs.add(f"TOTAL RECURSION v4 — {difficulty.value} | Tab=CMD | F1=Stats | V=AI Log",C["nin"],220)

    def _player_cmd(self):
        return next((b for b in self.buildings if b.team==Team.PLAYER and b.btype==BT.COMMANDER and b.alive),None)
    def _all(self): return self.buildings+self.units

    def run(self):
        while True:
            self.clock.tick(FPS); self._events()
            if not self.game_over: self._update()
            self._draw(); pygame.display.flip()

    def _events(self):
        mx,my=pygame.mouse.get_pos(); mx-=self.shake.ox; my-=self.shake.oy
        in_ui=my>SCREEN_H-UI_H; in_side=mx>SCREEN_W-SIDE_W
        in_mini=self.minimap.rect.collidepoint(mx,my)
        for ev in pygame.event.get():
            if ev.type==pygame.QUIT: pygame.quit(); sys.exit()
            if ev.type==pygame.KEYDOWN: self._key(ev.key)
            if ev.type==pygame.MOUSEWHEEL:
                if not in_ui and not in_side:
                    if ev.y>0: self.cam.zi()
                    else: self.cam.zo()
            if ev.type==pygame.MOUSEBUTTONDOWN:
                if ev.button==4 and not in_ui: self.cam.zi()
                if ev.button==5 and not in_ui: self.cam.zo()
                if ev.button==1:
                    if in_mini:
                        wp=self.minimap.world_from_click(mx,my)
                        if wp: self.cam.center_on(*wp)
                    elif not in_ui and not in_side:
                        if self.build_mode and self.ghost and self.ghost.valid: self._place_b()
                        else: self.drag_start=(mx,my)
                if ev.button==3:
                    if in_mini:
                        wp=self.minimap.world_from_click(mx,my)
                        if wp: self._rclick(*wp)
                    elif not in_ui and not in_side:
                        wx,wy=self.cam.s2w(mx,my)
                        if self.build_mode: self._cancel_b()
                        else: self._rclick(wx,wy)
            if ev.type==pygame.MOUSEBUTTONUP:
                if ev.button==1 and self.drag_start:
                    if self.drag_end: self._box_sel()
                    else: self._lclick(*self.drag_start)
                    self.drag_start=None; self.drag_end=None
            if ev.type==pygame.MOUSEMOTION:
                if (pygame.key.get_mods()&pygame.KMOD_CTRL) and pygame.mouse.get_pressed()[0]:
                    self.cam.tilt=max(0.0,min(1.0,self.cam.tilt-ev.rel[1]*0.002))
                if self.drag_start:
                    if abs(mx-self.drag_start[0])>4 or abs(my-self.drag_start[1])>4:
                        self.drag_end=(mx,my)
                if self.ghost:
                    wx,wy=self.cam.s2w(mx,my); self.ghost.update(wx,wy)

    def _key(self,key):
        if key==pygame.K_ESCAPE:
            if self.build_mode: self._cancel_b()
            else: self.selected.clear()
            return
        if key==pygame.K_F11: pygame.display.toggle_fullscreen()
        if key==pygame.K_F1:  self.stats_panel.toggle()
        if key==pygame.K_v:   self.show_think=not self.show_think
        if key in (pygame.K_EQUALS,pygame.K_PLUS): self.cam.zi()
        if key==pygame.K_MINUS: self.cam.zo()
        if key==pygame.K_TAB:
            cmd=self._player_cmd()
            if cmd:
                self.selected=[cmd]; self.cam.center_on(cmd.x,cmd.y)
                self.sound.play("sel",cd=5); self.notifs.add("Commander selected",C["nin"],60)
            return
        if key in (pygame.K_DELETE,pygame.K_BACKSPACE):
            for e in self.selected:
                if e.alive and not (isinstance(e,Building) and e.movable):
                    e.take_damage(e.hp)
                    self.explosions.append(Explosion(e.x,e.y,2. if isinstance(e,Building) else 1.,self.parts,self.sound))
        if key==pygame.K_x:
            for e in self.selected:
                if isinstance(e,Building) and e.produces and e.team==Team.PLAYER and e.build_queue:
                    e.dequeue(len(e.build_queue)-1,self.player_eco)
                    self.notifs.add("Queue item cancelled",C["nin"],60)
        num=-1
        if pygame.K_1<=key<=pygame.K_9: num=key-pygame.K_1
        if key==pygame.K_0: num=9
        if num>=0:
            cmds=[e for e in self.selected if isinstance(e,Building) and e.btype==BT.COMMANDER and e.team==Team.PLAYER]
            if cmds and num<len(BUILD_FROM_CMD):
                btype=BUILD_FROM_CMD[num]
                if self.player_eco.can_afford_b(btype): self._enter_b(btype,cmds[0])
                else: self.notifs.add("Cannot afford!",C["nob"],80)
                return
            facs=[e for e in self.selected if isinstance(e,Building) and e.produces and e.team==Team.PLAYER]
            if facs and num<len(facs[0].produces):
                fac=facs[0]; ut=fac.produces[num]; cmd=self._player_cmd()
                ok,reason=fac.enqueue(ut,self.player_eco,cmd)
                if ok: self.notifs.add(f"Queued: {USPECS[ut]['name']}",C["nin"],70)
                elif reason=="range": self.notifs.add("Factory out of range!",C["nob"],100)
                else: self.notifs.add("Cannot afford!",C["nob"],80)

    def _enter_b(self,btype,player_cmd):
        self.build_mode=True; self.pending_bt=btype
        self.ghost=BuildGhost(btype,self.terrain,self.buildings,player_cmd)
    def _cancel_b(self): self.build_mode=False; self.ghost=None; self.pending_bt=None

    def _place_b(self):
        if not self.pending_bt or not self.ghost: return
        btype=self.pending_bt
        if not self.player_eco.can_afford_b(btype): self.notifs.add("Cannot afford!",C["nob"],80); return
        self.player_eco.pay_b(btype)
        b=Building(self.ghost.wx,self.ghost.wy,Team.PLAYER,btype)
        if btype==BT.METAL_X:
            near=min(self.mdeps,key=lambda d:dist(d,(b.x,b.y)),default=None)
            if near and dist(near,(b.x,b.y))<TILE*2: b.x,b.y=near
        self.buildings.append(b)
        self.stats.bldgs_built[0]+=1
        self.sound.play("placed")
        self.notifs.add(f"Built: {BSPECS[btype]['name']}",C["nok"],90)
        if not (pygame.key.get_mods()&pygame.KMOD_SHIFT): self._cancel_b()

    def _rclick(self,wx,wy):
        if not self.selected: return
        cmd_sel=[e for e in self.selected if isinstance(e,Building) and e.movable and e.team==Team.PLAYER]
        if cmd_sel:
            if self.terrain.walkable(wx,wy):
                cmd_sel[0].move_target=(wx,wy); self.sound.play("cmd_move",cd=5)
                self.notifs.add("Commander moving",C["nin"],60)
            return
        target=self._at(wx,wy,enemy_only=True)
        for e in self.selected:
            if isinstance(e,Unit) and e.team==Team.PLAYER:
                if target: e.command_attack(target)
                else: e.command_move(wx,wy)
        for e in self.selected:
            if isinstance(e,Building) and e.produces: e.rally=(wx,wy)

    def _at(self,wx,wy,enemy_only=False):
        best=None; bd=1e9
        for e in self._all():
            if not e.alive: continue
            if enemy_only and e.team==Team.PLAYER: continue
            d=dist((wx,wy),(e.x,e.y))
            if d<e.radius+7 and d<bd: best=e; bd=d
        return best

    def _lclick(self,mx,my):
        wx,wy=self.cam.s2w(mx,my); e=self._at(wx,wy)
        mods=pygame.key.get_mods()
        if e:
            if mods&pygame.KMOD_SHIFT:
                if e in self.selected: self.selected.remove(e)
                else: self.selected.append(e)
            else:
                if self.selected!=[e]: self.sound.play("sel",cd=5)
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
        self.player_eco.tick(pb,1.); self.ai_eco.tick(ab,self.ai_eco_mult)
        self.stats.record(self.player_eco,self.ai_eco,
                          [u for u in self.units if u.team==Team.PLAYER],
                          [u for u in self.units if u.team==Team.AI])
        for b in self.buildings:
            if b.alive:
                b.update_move(self.terrain)
                if b.btype==BT.SHIELD_GEN: b.update_shield(all_e)
        new_units=[]
        for b in self.buildings:
            if not b.alive: continue
            eco=self.player_eco if b.team==Team.PLAYER else self.ai_eco
            res=b.update_prod()
            if res:
                rally=b.rally if b.rally else (b.x+b.radius*2,b.y)
                ang=random.uniform(0,math.pi*2); sr=b.radius+22
                u=Unit(rally[0]+math.cos(ang)*sr,rally[1]+math.sin(ang)*sr,b.team,res)
                new_units.append(u)
                if b.team==Team.PLAYER:
                    self.sound.play("done"); self.stats.units_built[0]+=1
                    self.notifs.add(f"Unit ready: {USPECS[res]['name']}",C["nok"],80)
                else: self.stats.units_built[1]+=1
        self.units.extend(new_units)
        for u in self.units:
            if u.alive: u.update(all_e,self.projs,self.terrain,self.parts,self.sound,self.stats)
        for b in self.buildings:
            if b.alive and b.weapon: b.try_fire(all_e,self.projs,self.sound,self.stats)
        hit_player=False
        for p in self.projs:
            hit=p.update(all_e)
            if hit:
                ti=0 if p.team==Team.PLAYER else 1
                for e in all_e:
                    if not e.alive and not e._exploded:
                        self.stats.kills[ti]+=1; self.stats.deaths[1-ti]+=1
            if hit and p.team==Team.AI: hit_player=True
        if hit_player and self._atk_cd<=0:
            self._atk_cd=FPS*8; self.sound.play("atk")
            self.notifs.add("⚠ UNDER ATTACK!",C["nob"],170)
        self._atk_cd=max(0,self._atk_cd-1)
        p_cmd=self._player_cmd()
        for e in all_e:
            if not e.alive and not e._exploded:
                e._exploded=True
                sz=2.2 if isinstance(e,Building) else(3.5 if hasattr(e,"utype") and e.utype==UT.TITAN else 1.)
                self.explosions.append(Explosion(e.x,e.y,sz,self.parts,self.sound))
                if p_cmd:
                    d2=dist((p_cmd.x,p_cmd.y),(e.x,e.y))
                    self.shake.add(max(0,(700-d2)/700*12*sz))
        # In-place cleanup (preserves list identity for AI references)
        for lst in (self.buildings,self.units,self.projs):
            i=len(lst)-1
            while i>=0:
                if not lst[i].alive: lst.pop(i)
                i-=1
        i=len(self.explosions)-1
        while i>=0:
            if not self.explosions[i].update(): self.explosions.pop(i)
            i-=1
        self.selected=[e for e in self.selected if e.alive]
        self.ai.update(all_e,self.projs,self.terrain,self.mdeps,self.notifs,self.sound,self.stats)
        keys=pygame.key.get_pressed(); self.cam.update(keys)
        mx,my=pygame.mouse.get_pos(); edge=22; spd=12/self.cam.zoom
        if mx<edge:             self.cam.x-=spd; self.cam.y+=spd
        if mx>SCREEN_W-SIDE_W-edge: self.cam.x+=spd; self.cam.y-=spd
        if my<edge:             self.cam.x-=spd; self.cam.y-=spd
        if my>SCREEN_H-UI_H-edge: self.cam.x+=spd; self.cam.y+=spd
        self.cam.clamp(); self.shake.update()
        pc=[b for b in self.buildings if b.team==Team.PLAYER and b.btype==BT.COMMANDER and b.alive]
        ac=[b for b in self.buildings if b.team==Team.AI    and b.btype==BT.COMMANDER and b.alive]
        if not pc and not self.game_over: self.game_over="lose"
        if not ac and not self.game_over: self.game_over="win"

    def _draw(self):
        surf=self.screen; cam=self.cam; ox,oy=self.shake.ox,self.shake.oy
        vw=SCREEN_W-SIDE_W; vh=SCREEN_H-UI_H
        target=pygame.Surface((vw,vh)); target.fill(C["bg"])

        draw_terrain_iso(target,self.terrain,cam)

        # Build range ring (commander selected or build mode active)
        p_cmd=self._player_cmd()
        if p_cmd and (any(isinstance(e,Building) and e.btype==BT.COMMANDER for e in self.selected) or self.build_mode):
            cx,cy=cam.w2s(p_cmd.x,p_cmd.y)
            rx=int(BUILD_RANGE*cam.zoom*ISO_SX); ry2=int(BUILD_RANGE*cam.zoom*ISO_SY)
            if rx>4:
                rs=pygame.Surface((rx*2+4,ry2*4+4),pygame.SRCALPHA)
                pygame.draw.ellipse(rs,(100,182,255,14),(0,ry2,rx*2+4,ry2*2+4))
                pygame.draw.ellipse(rs,(100,182,255,50),(0,ry2,rx*2+4,ry2*2+4),2)
                target.blit(rs,(cx-rx-2,cy-ry2*2-2))

        # Weapon range for selected turrets
        for e in self.selected:
            if isinstance(e,Building) and e.weapon and e.btype not in (BT.COMMANDER,):
                sx2,sy2=cam.w2s(e.x,e.y); rr2=int(e.weapon["r"]*cam.zoom*ISO_SX)
                ry3=int(e.weapon["r"]*cam.zoom*ISO_SY)
                if rr2>4:
                    rs=pygame.Surface((rr2*2+4,ry3*4+4),pygame.SRCALPHA)
                    pygame.draw.ellipse(rs,(*C["las"],14),(0,ry3,rr2*2+4,ry3*2+4))
                    pygame.draw.ellipse(rs,(*C["las"],46),(0,ry3,rr2*2+4,ry3*2+4),1)
                    target.blit(rs,(sx2-rr2-2,sy2-ry3*2-2))

        # Depth-sort all entities by world Y (air last = on top)
        all_vis=sorted(
            [(e,e.y+(100000 if getattr(e,"dom",Domain.GROUND) in (Domain.AIR,Domain.PSIONIC) else 0))
             for e in self._all() if e.alive],
            key=lambda x:x[1]
        )
        for e,_ in all_vis:
            e.draw(target,cam,e in self.selected,self.tick)

        for p in self.projs:      p.draw(target,cam)
        for ex in self.explosions: ex.draw(target,cam)
        self.parts.draw(target,cam)

        # Drag selection box
        if self.drag_start and self.drag_end:
            x1,y1=self.drag_start; x2,y2=self.drag_end
            rect=pygame.Rect(min(x1,x2),min(y1,y2),abs(x2-x1),abs(y2-y1))
            s2=pygame.Surface((max(1,rect.width),max(1,rect.height)),pygame.SRCALPHA)
            s2.fill((62,202,102,16)); target.blit(s2,rect.topleft)
            pygame.draw.rect(target,C["sel"],rect,1)

        if self.ghost: self.ghost.draw(target,cam,self.fs)

        # Apply shake
        surf.fill(C["bg"])
        surf.blit(target,(ox,oy))

        # ── Right panel (AI log + stats strip) ───────────────────────────────
        px=SCREEN_W-SIDE_W; panel_h=SCREEN_H-MINIMAP_H-UI_H
        rrect(surf,C["abg"],(px,0,SIDE_W,panel_h),0,1,C["abd"])
        if self.show_think and panel_h>80:
            self.ai.log.draw(surf,self.fs_think,px,0,SIDE_W,panel_h)
        # Quick stats strip
        my_u=[u for u in self.units if u.team==Team.PLAYER]
        ai_u=[u for u in self.units if u.team==Team.AI]
        slines=[
            f"AI Phase: {self.ai.phase}",
            f"P Units: {len(my_u)}  AI: {len(ai_u)}",
            f"P Kills: {self.stats.kills[0]}  AI: {self.stats.kills[1]}",
            f"P Bldgs: {len([b for b in self.buildings if b.team==Team.PLAYER and b.alive])}",
            f"AI Bldgs:{len([b for b in self.buildings if b.team==Team.AI and b.alive])}",
            f"P Dmg:   {int(self.stats.dmg_dealt[0])}",
        ]
        for si,sl in enumerate(slines):
            surf.blit(self.fs.render(sl,True,C["adm"]),(px+5,panel_h-14-si*13))

        # ── Bottom UI ─────────────────────────────────────────────────────────
        self.ui.draw(surf,self.player_eco,
                     self.selected[0] if len(self.selected)==1 else(self.selected if len(self.selected)>1 else None),
                     self.tick,(pygame.mouse.get_pos()))
        self.minimap.draw(surf,self.terrain,self.buildings,self.units,cam,self.tick)
        surf.blit(self.fs.render(f"AI:{self.difficulty.value}  V=log  F1=stats  F11=fullscreen",True,C["txd"]),
                  (SCREEN_W-MINIMAP_W+4,SCREEN_H-MINIMAP_H-14))
        surf.blit(self.fs.render(f"FPS:{int(self.clock.get_fps())}  U:{len(self.units)}  B:{len(self.buildings)}",True,C["txd"]),(8,8))

        self.stats_panel.draw(surf,self.stats,self.player_eco,self.ai_eco,
                              [u for u in self.units if u.team==Team.PLAYER],
                              [u for u in self.units if u.team==Team.AI],
                              self.buildings)
        self.notifs.draw(surf)

        # ── Game over overlay ─────────────────────────────────────────────────
        if self.game_over:
            ov=pygame.Surface((SCREEN_W,SCREEN_H-UI_H),pygame.SRCALPHA)
            ov.fill((0,0,0,145)); surf.blit(ov,(0,0))
            msg="VICTORY!" if self.game_over=="win" else "DEFEAT!"
            col=C["hg"] if self.game_over=="win" else C["p2"]
            t=self.fxl.render(msg,True,col)
            surf.blit(t,(SCREEN_W//2-t.get_width()//2,(SCREEN_H-UI_H)//2-t.get_height()//2))
            sfx_glow(surf,col,(SCREEN_W//2,(SCREEN_H-UI_H)//2),140,42)
            sub=self.fm.render(f"Kills:{self.stats.kills[0]}  Deaths:{self.stats.deaths[0]}  |  Esc to exit",True,C["txd"])
            surf.blit(sub,(SCREEN_W//2-sub.get_width()//2,(SCREEN_H-UI_H)//2+65))
            if pygame.key.get_pressed()[pygame.K_ESCAPE]: pygame.quit(); sys.exit()

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__=="__main__":
    clock=pygame.time.Clock()
    screen=pygame.display.set_mode((SCREEN_W,SCREEN_H),pygame.FULLSCREEN)
    diff=diff_screen(screen,clock)
    Game(diff).run()
