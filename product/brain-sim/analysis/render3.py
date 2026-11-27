import sys, math, struct, zlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'product/brain-sim'))
import lamp as L, mujoco, numpy as np
SIM=str(ROOT / 'hardware/simulation'); REC=str(ROOT / 'product/brain-sim/recordings')
sim=L.SimLamp(SIM,REC); m,d=sim.m,sim.d
JOINTS=['base_yaw','base_pitch','elbow_pitch','wrist_roll','wrist_pitch']
adr={j:sim.jmap[j][1] for j in JOINTS}; rng={j:sim.jmap[j][2] for j in JOINTS}
span={j:rng[j][1]-rng[j][0] for j in JOINTS}; mid={j:(rng[j][1]+rng[j][0])/2 for j in JOINTS}
def coef(signs,hyp):
    c={}
    for idx,j in enumerate(JOINTS):
        s=signs[idx]
        if j in ('base_yaw','wrist_roll'): c[j]=(0.0,s*0.9*math.pi/180)
        else:
            h=hyp[['base_pitch','elbow_pitch','wrist_pitch'].index(j)]
            c[j]=(mid[j] if h==0 else 0.0, s*span[j]/200)
    return c
W,H=1000,640
img=np.full((H,W,3),18,np.uint8)
def line(p0,p1,col,w=2):
    n=int(max(abs(p1[0]-p0[0]),abs(p1[1]-p0[1]))*2)+1
    for t in np.linspace(0,1,n):
        x=int(p0[0]+(p1[0]-p0[0])*t); y=int(p0[1]+(p1[1]-p0[1])*t)
        img[max(0,y-w):y+w+1,max(0,x-w):x+w+1]=col
def png(path):
    raw=b''.join(b'\x00'+img[y].tobytes() for y in range(H))
    def chunk(t,data): return struct.pack('>I',len(data))+t+data+struct.pack('>I',zlib.crc32(t+data)&0xffffffff)
    open(path,'wb').write(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',W,H,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
names=['scs215_v5','lamparm__base_elbow','lamparm__elbow_wrist','lamparm__wrist_head_2','diffuser']
emit=np.array([-0.7535,0.6575,0.0])
def draw(tag,c,f,path):
    if c is None:
        d.qpos[:]=0
    else:
        for j in JOINTS: d.qpos[adr[j]]=c[j][0]+c[j][1]*f[j]
    d.qvel[:]=0; mujoco.mj_forward(m,d)
    P=[d.xpos[m.body(n).id].copy() for n in names]
    cog=d.subtree_com[0].copy(); hp=d.xpos[m.body('diffuser').id]
    e=d.xmat[m.body('diffuser').id].reshape(3,3)@emit
    pts=P+[cog,hp+e*0.12]
    minx=min(p[0] for p in pts)-0.12; maxx=max(p[0] for p in pts)+0.12
    maxz=max(p[2] for p in pts)+0.10; minz=-0.05
    s=min((W-40)/(maxx-minx),(H-60)/(maxz-minz))
    tx=lambda x:(x-minx)*s+20; tz=lambda z:H-30-(z-minz)*s
    img[:]=18
    line((0,tz(0)),(W,tz(0)),(90,90,90),1)
    line((tx(-0.095),tz(0)),(tx(0.095),tz(0)),(0,200,120),3)
    line((tx(-0.095),tz(0.04)),(tx(0.095),tz(0.04)),(0,120,80),1)
    for a,b in zip(P[:-1],P[1:]): line((tx(a[0]),tz(a[2])),(tx(b[0]),tz(b[2])),(230,230,230),3)
    line((tx(hp[0]),tz(hp[2])),(tx(hp[0]+e[0]*0.12),tz(hp[2]+e[2]*0.12)),(255,200,0),2)
    line((tx(cog[0]),tz(cog[2])),(tx(cog[0]),tz(0)),(255,80,80),1)
    line((tx(cog[0])-6,tz(cog[2])),(tx(cog[0])+6,tz(cog[2])),(255,80,80),2)
    png(path); print(tag,'head_mm=',(hp*1000).round(0),'cog_mm=',(cog*1000).round(0))
f=sim.rec['idle'][1682]
draw('qpos0',None,None,'/tmp/r_qpos0.png')
draw('C1',coef((1,1,1,1,1),(0,0,0)),f,'/tmp/r_C1.png')
draw('C2',coef((1,1,-1,1,-1),(0,1,1)),f,'/tmp/r_C2.png')
