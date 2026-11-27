import sys, math, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'product/brain-sim'))
src=open(HERE / 'p0_2_real_mass.py').read().split("sim = L.SimLamp")[0]
g={'__name__':'rm','__file__':str(HERE / 'p0_2_real_mass.py')}; exec(src,g)
import lamp as L, mujoco, numpy as np
SIM=str(ROOT / 'hardware/simulation'); REC=str(ROOT / 'product/brain-sim/recordings')
sim=L.SimLamp(SIM,REC); m,d=sim.m,sim.d
m.geom_contype[:]=1; m.geom_conaffinity[:]=1
JOINTS=['base_yaw','base_pitch','elbow_pitch','wrist_roll','wrist_pitch']
adr={j:sim.jmap[j][1] for j in JOINTS}; rng={j:sim.jmap[j][2] for j in JOINTS}
span={j:rng[j][1]-rng[j][0] for j in JOINTS}; mid={j:(rng[j][1]+rng[j][0])/2 for j in JOINTS}
SIGN={'base_yaw':1,'base_pitch':1,'elbow_pitch':-1,'wrist_roll':1,'wrist_pitch':-1}
HYP={'base_pitch':0,'elbow_pitch':1,'wrist_pitch':1}
COEF={}
for j in JOINTS:
    s=SIGN[j]
    if j in ('base_yaw','wrist_roll'): COEF[j]=(0.0,s*0.9*math.pi/180)
    else: COEF[j]=(mid[j] if HYP[j]==0 else 0.0, s*span[j]/200)
bid={mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_BODY,i):i for i in range(m.nbody)}
hb=bid['diffuser']; gb=m.geom_bodyid; base_b={0,bid['scs215_v5']}
exported={n:(m.body_mass[m.body(n).id], m.body_ipos[m.body(n).id].copy(), m.body_inertia[m.body(n).id].copy()) for n in ['scs215_v5','lamparm__wrist_head','lamparm__base_elbow','lamparm__elbow_wrist','lamparm__wrist_head_2','diffuser']}
def apply(mm,head_extra=0.0):
    for n,(M,C) in mm.items():
        b=m.body(n).id
        if n=='diffuser': M+=head_extra
        m.body_mass[b]=M; m.body_ipos[b]=C; m.body_inertia[b]=exported[n][2]*(M/exported[n][0])
ru=g['realistic_link_masses'](False); head_real=ru['diffuser'][0]*1000
apply(ru,0.180-head_real/1000)
Mtot=float(m.body_mass.sum()); print('total mass kg=',round(Mtot,3),'timestep=',m.opt.timestep)
def setdeg(p,e,w,yaw=0.0,roll=0.0):
    d.qpos[adr['base_yaw']]=math.radians(yaw); d.qpos[adr['wrist_roll']]=math.radians(roll)
    d.qpos[adr['base_pitch']]=math.radians(p); d.qpos[adr['elbow_pitch']]=math.radians(e); d.qpos[adr['wrist_pitch']]=math.radians(w)
    d.qvel[:]=0
def setq(f):
    for j in JOINTS: d.qpos[adr[j]]=COEF[j][0]+COEF[j][1]*f[j]
    d.qvel[:]=0
def grav():
    return {j:round(abs(d.qfrc_bias[adr[j]])/9.80665*100,2) for j in ['base_pitch','elbow_pitch','wrist_pitch']}
def cogmm():
    c=d.subtree_com[0]; return round(float(np.hypot(c[0],c[1]))*1000,1), round(min(95-abs(c[0]*1000),80-abs(c[1]*1000)),1)
def pen():
    n=0
    for c in range(d.ncon):
        ct=d.contact[c]
        if ct.dist<-0.003 and (gb[ct.geom1] not in base_b or gb[ct.geom2] not in base_b): n+=1
    return n
cands=json.load(open(HERE / 'p0_2_rest_cands.json'))
out={'total_mass_kg':round(Mtot,3),'rest':[],'release':{},'fold':{},'ballast':{}}
for c in cands:
    hz,cg,tq,p,e,w=c
    setdeg(p,e,w); mujoco.mj_forward(m,d)
    out['rest'].append({'deg':(p,e,w),'head_z_mm':hz,'cog_mm':cogmm()[0],'tip_margin_mm':cogmm()[1],'grav_kgcm':grav(),'pen':pen()})
print('REST:',json.dumps(out['rest']))
dt=m.opt.timestep
def release(tag,setter,secs=3.0):
    setter(); mujoco.mj_forward(m,d)
    h0=d.xpos[hb].copy(); q0=d.qpos.copy()
    fr=m.actuator_forcerange.copy(); m.actuator_forcerange[:]=0
    for _ in range(int(secs/dt)): mujoco.mj_step(m,d)
    h1=d.xpos[hb].copy(); c1=d.subtree_com[0]
    drift=max(abs(d.qpos[adr[j]]-q0[adr[j]]) for j in JOINTS)*180/math.pi
    contacts=sorted({mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_BODY,gb[d.contact[i].geom1])+'|'+mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_BODY,gb[d.contact[i].geom2]) for i in range(d.ncon) if d.contact[i].dist<0.001})
    m.actuator_forcerange[:]=fr
    out['release'][tag]={'head_drop_mm':round((h0[2]-h1[2])*1000,1),'head_z_after_mm':round(h1[2]*1000,1),'max_joint_drift_deg':round(drift,1),'cog_after_mm':round(float(np.hypot(c1[0],c1[1]))*1000,1),'cog_after_xy_mm':[round(c1[0]*1000,1),round(c1[1]*1000,1)],'tip_margin_after_mm':round(min(95-abs(c1[0]*1000),80-abs(c1[1]*1000)),1),'contacts_end':contacts}
    print('RELEASE',tag,out['release'][tag])
for i,c in enumerate(cands[:3]):
    release(f'rest{i}_{c[3]},{c[4]},{c[5]}', lambda p=c[3],e=c[4],w=c[5]: setdeg(p,e,w))
release('idle_C2', lambda: setq(sim.rec['idle'][1682]))
release('qpos0', lambda: setdeg(0,0,0))
# fold paths: idle -> rest0, qpos0 -> rest0 ; linear + staged(wrist->elbow->pitch)
p,e,w=cands[0][3],cands[0][4],cands[0][5]
start_idle=np.array([COEF[j][0]+COEF[j][1]*sim.rec['idle'][1682][j] for j in JOINTS])
start_zero=np.zeros(5)
end=np.array([0.0,math.radians(p),math.radians(e),0.0,math.radians(w)])
def path(tag,a,b,staged):
    worst=1e9; wp=0; wt=0
    N=48
    for s in range(N+1):
        t=s/N
        if staged:
            q=a.copy()
            q[4]=a[4]+(b[4]-a[4])*min(1,t*3)
            q[2]=a[2]+(b[2]-a[2])*min(1,max(0,t*3-1))
            q[1]=a[1]+(b[1]-a[1])*min(1,max(0,t*3-2))
        else: q=a+(b-a)*t
        for k,j in enumerate(JOINTS): d.qpos[adr[j]]=q[k]
        d.qvel[:]=0; mujoco.mj_forward(m,d)
        worst=min(worst,cogmm()[1]); wp=max(wp,pen()); wt=max(wt,max(grav().values()))
    out['fold'][tag]={'min_tip_margin_mm':round(worst,1),'max_pen':wp,'max_hold_kgcm':round(wt,1)}
    print('FOLD',tag,out['fold'][tag])
path('idle->rest0_linear',start_idle,end,False)
path('idle->rest0_staged',start_idle,end,True)
path('zero->rest0_linear',start_zero,end,False)
r0=cands[0][1]
for gate in (22,40,50):
    out['ballast'][f'gate{gate}']=round(Mtot*(r0/gate-1),2)
out['ballast']['cog_with_500g']=round(r0*Mtot/(Mtot+0.5),1)
out['ballast']['cog_with_1000g']=round(r0*Mtot/(Mtot+1.0),1)
print('BALLAST',out['ballast'])
json.dump(out,open(HERE / 'p0_2_release.json','w'),indent=1,ensure_ascii=False)
