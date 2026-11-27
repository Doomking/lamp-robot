import sys, math, struct, itertools
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'product/brain-sim'))
import lamp as L
import mujoco, numpy as np
import xml.etree.ElementTree as ET
SIM = ROOT / 'hardware/simulation'

def stl_vol_com(p):
    b = p.read_bytes(); n = struct.unpack('<I', b[80:84])[0]
    v=0.0; c=np.zeros(3)
    for i in range(n):
        off=84+i*50
        a=np.array(struct.unpack('<9f', b[off+12:off+48])).reshape(3,3)
        vt = np.dot(a[0], np.cross(a[1],a[2]))/6.0
        v += vt; c += vt*(a.sum(0))/4.0
    return abs(v)*1e9/1000, c/v  # cm3, centroid in STL frame (m)

def rpy_mat(r,p,y):
    cr,sr,cp,sp,cy,sy = math.cos(r),math.sin(r),math.cos(p),math.sin(p),math.cos(y),math.sin(y)
    return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
                     [-sp,   cp*sr,          cp*cr]])

PRINTS = {'lamp_base.stl','lamp_base_cover.stl','lamparm__base_elbow.stl','lamparm__elbow_wrist.stl','lamparm__wrist_head.stl','lamphead.stl','diffuser.stl'}
PLASTIC_OTHER = {'xg_ziji_16.stl','sg_ziji_15.stl','zk_122.stl','ge_27.stl'}
cache = {f: stl_vol_com(SIM/'assets'/f) for f in PRINTS|PLASTIC_OTHER|{'motor_1723_3.stl','pcb_chazuo_92.stl','金属舵盘_从动__v2.stl','金属舵盘_驱动__v2.stl'}}

def realistic_link_masses(other_printed=False, print_density=0.50, servo_g=55.0):
    t = ET.parse(SIM/'robot.urdf'); out={}
    for l in t.getroot().findall('link'):
        i = l.find('inertial')
        if i is None or float(i.find('mass').get('value')) < 1e-6: continue
        M=0.0; C=np.zeros(3)
        for v in l.findall('visual'):
            f = v.find('geometry/mesh').get('filename').split('/')[-1]
            vol, com = cache[f]
            o = v.find('origin'); xyz=np.array([float(x) for x in o.get('xyz').split()])
            rpy=[float(x) for x in o.get('rpy').split()]
            cw = xyz + rpy_mat(*rpy)@com
            if f in PRINTS: m = vol*print_density/1000
            elif f=='motor_1723_3.stl': m = servo_g/1000
            elif f=='pcb_chazuo_92.stl': m = vol*1.85/1000
            elif f.startswith('金属舵盘'): m = vol*2.7/1000
            else: m = vol*(0.50 if other_printed else 1.09)/1000
            M+=m; C+=m*cw
        out[l.get('name')] = (M, C/M if M>0 else C)
    return out

# Standalone quick check below is superseded by p0_2_final.py (rest search +
# corrected affine mapping); realistic_link_masses() above is the reusable part.
sim = L.SimLamp(str(SIM), str(ROOT / 'product/brain-sim/recordings'))
m,d = sim.m, sim.d
adr = {k:v[1] for k,v in sim.jmap.items()}
JN = ['base_pitch','elbow_pitch','wrist_roll','wrist_pitch']
exported = {n:(m.body_mass[m.body(n).id], m.body_ipos[m.body(n).id].copy(), m.body_inertia[m.body(n).id].copy()) for n in [b for b in ['scs215_v5','lamparm__wrist_head','lamparm__base_elbow','lamparm__elbow_wrist','lamparm__wrist_head_2','diffuser']]}
def apply_masses(mm, head_extra=0.0):
    for n,(M,C) in mm.items():
        bid=m.body(n).id
        if n=='diffuser': M+=head_extra
        m.body_mass[bid]=M; m.body_ipos[bid]=C
        m.body_inertia[bid]=exported[n][2]*(M/exported[n][0])
def q_from_norm(f):
    # corrected affine mapping (CSV = LeRobot normalized -100..100, not degrees)
    q={}
    for k,(slot,a,(lo,hi),(tc,kk)) in sim.jmap.items():
        v=f.get(k,0.0)
        if k in ('base_yaw','wrist_roll'): v=max(-100,min(100,v))
        q[k]=max(lo,min(hi,tc+kk*v))
    return q
def setq(q):
    d.qpos[:]=0
    for k,v in q.items(): d.qpos[adr[k]]=v
    d.qvel[:]=0; mujoco.mj_forward(m,d)

cases = [
  ('realistic-upper(other plastic solid)', realistic_link_masses(False), 0.050),
  ('realistic-lower(all printed 0.5)', realistic_link_masses(True), 0.050),
  ('realistic-upper + newA head 180g total', realistic_link_masses(False), 0.180-0.0933-0.050+0.050),
]
# note: head_extra adds to realistic head mass; realistic head print ~ (65.3+9.3)*0.5=37.3g; old-real=+50g electronics; newA total 180 => extra=180-37.3-50? define below properly
mmU = realistic_link_masses(False); mmL = realistic_link_masses(True)
head_print_U = mmU['diffuser'][0]
print("realistic head print mass:", round(head_print_U*1000,1),"g")
cases = [
  ('OLD-realistic-upper (head+50g electronics)', mmU, 0.050),
  ('OLD-realistic-lower (head+50g electronics)', mmL, 0.050),
  ('NEW-A-upper (head total 180g)', mmU, 0.180-head_print_U),
  ('NEW-A-lower (head total 180g)', mmL, 0.180-head_print_U),
  ('NEW-A-upper (head total 230g)', mmU, 0.230-head_print_U),
]
for cname, mm, extra in cases:
    apply_masses(mm, extra)
    mx={k:0.0 for k in JN}; mxinfo={}
    for name,frames in sim.rec.items():
        for fi,f in enumerate(frames):
            setq(q_from_norm(f))
            for k in JN:
                t=abs(d.qfrc_bias[adr[k]])
                if t>mx[k]: mx[k]=t; mxinfo[k]=(name,fi)
    print(f"\n=== recordings max |tau| {cname} ===")
    print("  " + "  ".join(f"{k}:{mx[k]/9.80665*100:.1f}kg·cm@{mxinfo[k]}" for k in JN[:2]))

# constrained workspace scan, NEW-A-upper 180g
apply_masses(mmU, 0.180-head_print_U)
m.geom_contype[:]=1; m.geom_conaffinity[:]=1
ARM_BODIES = {m.body(n).id for n in ['lamparm__base_elbow','lamparm__elbow_wrist','lamparm__wrist_head_2','diffuser']}
def valid_pose():
    for i in range(d.ncon):
        c=d.contact[i]
        if c.dist > -0.003: continue
        b1=m.geom_bodyid[c.geom1]; b2=m.geom_bodyid[c.geom2]
        if b1 in ARM_BODIES or b2 in ARM_BODIES: return False
    return True
ranges=[sim.jmap[k][2] for k in JN]
N=9; grids=[np.linspace(lo,hi,N) for lo,hi in ranges]
mx=np.zeros(4); arg=[None]*4; nvalid=0; ntot=0
for q in itertools.product(*grids):
    setq(dict(zip(JN,q))); ntot+=1
    if not valid_pose(): continue
    nvalid+=1
    t=np.array([abs(d.qfrc_bias[adr[k]]) for k in JN])
    for j in range(4):
        if t[j]>mx[j]: mx[j]=t[j]; arg[j]=q
print(f"\n=== constrained scan NEW-A-180g-upper: {nvalid}/{ntot} poses valid ===")
for j,k in enumerate(JN):
    pd={kk:round(math.degrees(vv),1) for kk,vv in zip(JN,arg[j])} if arg[j] else None
    print(f"  {k:12s} {mx[j]/9.80665*100:6.2f} kg·cm @ {pd}")
# CoG offset at worst shoulder pose + max over valid scan
setq(dict(zip(JN,arg[0])))
cog=d.subtree_com[0]
print("worst-shoulder pose CoG xy offset from base axis:", round(np.linalg.norm(cog[:2])*1000,1),"mm; CoG z:",round(cog[2]*1000,1),"mm")
