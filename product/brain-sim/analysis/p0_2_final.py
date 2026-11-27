import sys, math, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'product/brain-sim'))
# reuse realistic_link_masses() without running the sibling's main section
src=open(HERE / 'p0_2_real_mass.py').read().split("sim = L.SimLamp")[0]
g={'__name__':'rm','__file__':str(HERE / 'p0_2_real_mass.py')}; exec(src,g)
import lamp as L, mujoco, numpy as np
SIM=str(ROOT / 'hardware/simulation'); REC=str(ROOT / 'product/brain-sim/recordings')
sim=L.SimLamp(SIM,REC); m,d=sim.m,sim.d
m.geom_contype[:]=1; m.geom_conaffinity[:]=1
JOINTS=['base_yaw','base_pitch','elbow_pitch','wrist_roll','wrist_pitch']
adr={j:sim.jmap[j][1] for j in JOINTS}; rng={j:sim.jmap[j][2] for j in JOINTS}
span={j:rng[j][1]-rng[j][0] for j in JOINTS}; mid={j:(rng[j][1]+rng[j][0])/2 for j in JOINTS}
# CORRECTED affine mapping: CSV norm(-100..100) -> model rad
SIGN={'base_yaw':1,'base_pitch':1,'elbow_pitch':-1,'wrist_roll':1,'wrist_pitch':-1}
HYP={'base_pitch':0,'elbow_pitch':1,'wrist_pitch':1}
COEF={}
for j in JOINTS:
    s=SIGN[j]
    if j in ('base_yaw','wrist_roll'): COEF[j]=(0.0, s*0.9*math.pi/180)
    else: COEF[j]=(mid[j] if HYP[j]==0 else 0.0, s*span[j]/200)
def setq(f):
    for j in JOINTS: d.qpos[adr[j]]=COEF[j][0]+COEF[j][1]*f[j]
    d.qvel[:]=0
bid={mujoco.mj_id2name(m,mujoco.mjtObj.mjOBJ_BODY,i):i for i in range(m.nbody)}
hb=bid['diffuser']; gb=m.geom_bodyid
base_b={0,bid['scs215_v5']}
exported={n:(m.body_mass[m.body(n).id], m.body_ipos[m.body(n).id].copy(), m.body_inertia[m.body(n).id].copy()) for n in ['scs215_v5','lamparm__wrist_head','lamparm__base_elbow','lamparm__elbow_wrist','lamparm__wrist_head_2','diffuser']}
def apply(mm,head_extra=0.0):
    for n,(M,C) in mm.items():
        b=m.body(n).id
        if n=='diffuser': M+=head_extra
        m.body_mass[b]=M; m.body_ipos[b]=C; m.body_inertia[b]=exported[n][2]*(M/exported[n][0])
ru=g['realistic_link_masses'](False); rl=g['realistic_link_masses'](True)
head_real=ru['diffuser'][0]*1000
cases={'exported+50g':({n:(exported[n][0],exported[n][1]) for n in exported},0.050),
       'realistic-upper':(ru,0.0),'realistic-lower':(rl,0.0),
       'NEW-A-180g':(ru,0.180-head_real/1000),'NEW-A-230g':(ru,0.230-head_real/1000)}
print('realistic head print mass g=',round(head_real,1))
res={}
for cname,(mm,extra) in cases.items():
    apply(mm,extra)
    T={j:[] for j in ['base_pitch','elbow_pitch','wrist_pitch']}; reach=[]; marg=[]; pen=0
    for name,fr in sim.rec.items():
        for k in range(0,len(fr),3):
            setq(fr[k]); mujoco.mj_forward(m,d)
            for j in T: T[j].append(abs(d.qfrc_bias[adr[j]])/9.80665*100)
            hp=d.xpos[hb]; reach.append(np.linalg.norm(hp[:2])*1000)
            cx,cy,_=d.subtree_com[0]; marg.append(min(95-abs(cx*1000),80-abs(cy*1000)))
            for c in range(d.ncon):
                ct=d.contact[c]
                if ct.dist<-0.003 and (gb[ct.geom1] not in base_b or gb[ct.geom2] not in base_b): pen+=1
    r={j:(round(max(T[j]),1),round(float(np.percentile(T[j],50)),1)) for j in T}
    res[cname]={'torque_max_p50':r,'reach_p50_max':(round(float(np.percentile(reach,50)),0),round(max(reach),0)),
                'cog_min_margin_mm':round(min(marg),1),'pen_frames':pen}
    print(cname, res[cname])
json.dump(res,open(HERE / 'p0_2_final_torques.json','w'),indent=1)
# ---- rest pose search (model space) ----
apply(ru,0.180-head_real/1000)
cands=[]
for p in range(-60,119,6):
  for e in range(-160,19,6):
    for w in range(-45,132,10):
      d.qpos[adr['base_yaw']]=0; d.qpos[adr['wrist_roll']]=0
      d.qpos[adr['base_pitch']]=math.radians(p); d.qpos[adr['elbow_pitch']]=math.radians(e); d.qpos[adr['wrist_pitch']]=math.radians(w)
      d.qvel[:]=0; mujoco.mj_forward(m,d)
      hp=d.xpos[hb]; cx,cy,_=d.subtree_com[0]
      if hp[2]>0.20 or abs(cx)>0.060 or abs(cy)>0.060: continue
      bad=False
      for c in range(d.ncon):
        ct=d.contact[c]
        if ct.dist<-0.003 and (gb[ct.geom1] not in base_b or gb[ct.geom2] not in base_b): bad=True
      if bad: continue
      tq=max(abs(d.qfrc_bias[adr[j]]) for j in ['base_pitch','elbow_pitch','wrist_pitch'])/9.80665*100
      cands.append((round(hp[2]*1000),round(math.hypot(cx,cy)*1000,1),round(tq,1),p,e,w))
cands.sort(key=lambda c:(c[0],c[1]))
print('rest candidates (headz_mm, cog_mm, maxT_kgcm, pitch, elbow, wrist):', len(cands))
for c in cands[:10]: print('  ',c)
json.dump(cands[:40],open(HERE / 'p0_2_rest_cands.json','w'))
