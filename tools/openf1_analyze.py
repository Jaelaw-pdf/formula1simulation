import json,os,glob,collections,statistics as st
import numpy as np
MAP={'Melbourne':'aus','Shanghai':'chn','Suzuka':'jpn','Sakhir':'bhr','Jeddah':'sau','Miami':'mia','Montreal':'can','Monte Carlo':'mon','Catalunya':'esp','Spielberg':'aut','Silverstone':'gbr','Spa-Francorchamps':'bel','Hungaroring':'hun','Zandvoort':'ned','Monza':'ita','Madring':'mad','Baku':'aze','Singapore':'sgp','Austin':'usa','Mexico City':'mex','Interlagos':'bra','Las Vegas':'lvg','Lusail':'qat','Yas Marina Circuit':'abu'}
C={'SOFT':'S','MEDIUM':'M','HARD':'H','INTERMEDIATE':'I','WET':'W'}
def L(k,e):
  try:
    d=json.load(open(f'raw/{k}/{e}.json'));return d if isinstance(d,list) else []
  except Exception: return []
races=[]
for sf in sorted(glob.glob('raw/*/session.json')):
  s=json.load(open(sf));k=s['session_key'];tid=MAP.get(s['circuit_short_name'])
  stints=L(k,'stints');laps=L(k,'laps')
  if not tid or len(stints)<20 or len(laps)<300: continue
  year=int(s['date_start'][:4])
  nlaps=max(l['lap_number'] for l in laps)
  drv={d['driver_number']:d.get('team_name') for d in L(k,'drivers')}
  # SC / VSC laps from race control
  rc=L(k,'race_control');neutral=set();sc=vsc=0;red=0
  cur=None
  for m in sorted(rc,key=lambda m:m['date']):
    msg=(m.get('message') or '').upper();ln=m.get('lap_number') or 0
    if 'VIRTUAL SAFETY CAR DEPLOYED' in msg: vsc+=1;cur=('V',ln)
    elif 'SAFETY CAR DEPLOYED' in msg: sc+=1;cur=('S',ln)
    elif ('ENDING' in msg or 'IN THIS LAP' in msg) and cur:
      for x in range(cur[1],ln+2): neutral.add(x)
      cur=None
    if (m.get('flag') or '')=='RED': red+=1
  # per driver stints
  bd0=collections.defaultdict(list)
  for x in stints:
    if x.get('compound') and x.get('lap_start') is not None and x.get('lap_end') is not None: bd0[x['driver_number']].append(dict(x))
  pits=L(k,'pit');pl=collections.defaultdict(set)
  for p in pits:
    if p.get('lap_number'): pl[p['driver_number']].add(p['lap_number'])
  bd={}
  for dn,v in bd0.items():
    v=sorted(v,key=lambda x:x['stint_number']);m=[]
    for x in v:
      if m:
        pv=m[-1];pitted=any(pv['lap_end']-1<=q<=x['lap_start']+1 for q in pl[dn]) if pl[dn] else True
        cont=(x.get('tyre_age_at_start') or 0)>=(pv.get('tyre_age_at_start') or 0)+(pv['lap_end']-pv['lap_start']+1)-1 and (x.get('tyre_age_at_start') or 0)>0
        if x['compound']==pv['compound'] and (not pitted or cont):
          pv['lap_end']=max(pv['lap_end'],x['lap_end']);continue
      m.append(x)
    bd[dn]=m
  wet=sum(1 for v in bd.values() if any(C.get(x['compound'],'?') in 'IW' for x in v))
  races.append(dict(k=k,year=year,tid=tid,nlaps=nlaps,drv=drv,bd=bd,laps=laps,neutral=neutral,sc=sc,vsc=vsc,red=red,wet=wet>len(bd)*.3,pit=L(k,'pit')))
json.dump([{'k':r['k'],'year':r['year'],'tid':r['tid']} for r in races],open('races_index.json','w'))
print('usable races',len(races),'wet',sum(r['wet'] for r in races))

# ---------- strategies ----------
strat=collections.defaultdict(lambda:{'seq':collections.Counter(),'stops':collections.Counter(),'first':[],'len':collections.defaultdict(list),'n':0,'races':0,'sc':0,'vsc':0,'yrs':set()})
for r in races:
  T=strat[r['tid']];T['races']+=1;T['any']=T.get('any',0)+(r['sc']>0 or r['vsc']>0);T['sc']+=r['sc']>0;T['vsc']+=r['vsc']>0;T['yrs'].add(r['year'])
  if r['wet'] or (r['tid'],r['year']) in {('mon',2025),('qat',2025)}: continue  # 특수 규정(의무 2스톱/스틴트 상한) 제외
  for dn,v in r['bd'].items():
    v=sorted(v,key=lambda x:x['stint_number']);seq=''.join(C.get(x['compound'],'?') for x in v)
    if v[-1]['lap_end']<r['nlaps']-1 or not set(seq)<=set('SMH'): continue
    # merge stints split by data glitches (same compound & contiguous with no new tyre)
    T['n']+=1;T['seq'][seq]+=1;T['stops'][len(seq)-1]+=1
    if len(v)>1: T['first'].append(v[0]['lap_end']/r['nlaps'])
    for x in v:
      n=x['lap_end']-x['lap_start']+1
      if x is not v[-1] or True: T['len'][C[x['compound']]].append(n)
out={}
for tid,T in sorted(strat.items()):
  n=max(1,T['n'])
  out[tid]={'races':T['races'],'years':sorted(T['yrs']),'drivers':T['n'],'sc_rate':round(T['sc']/T['races'],2),'vsc_rate':round(T['vsc']/T['races'],2),'neutral_rate':round(T.get('any',0)/T['races'],2),
    'stops':{k:round(v/n,3) for k,v in sorted(T['stops'].items())},
    'seq':{k:round(v/n,3) for k,v in T['seq'].most_common(8)},
    'first_stop_frac':round(st.median(T['first']),3) if T['first'] else None,
    'stint_med':{c:int(st.median(T['len'][c])) for c in 'SMH' if len(T['len'][c])>=5},
    'stint_p90':{c:int(np.percentile(T['len'][c],90)) for c in 'SMH' if len(T['len'][c])>=5}}
json.dump(out,open('strategy.json','w'),indent=1)

# ---------- degradation fit per dry race ----------
degs=[]
for r in races:
  if r['wet']: continue
  rows=[]
  for dn,v in r['bd'].items():
    for x in v:
      c=C.get(x['compound'])
      if c not in ('S','M','H'): continue
      for l in range(x['lap_start'],x['lap_end']+1): pass
  lap_by={(l['driver_number'],l['lap_number']):l for l in r['laps']}
  for dn,v in r['bd'].items():
    v=sorted(v,key=lambda x:x['stint_number'])
    for x in v:
      c=C.get(x['compound'])
      if c not in ('S','M','H'): continue
      a0=x.get('tyre_age_at_start') or 0
      for ln in range(x['lap_start']+1,x['lap_end']):   # skip out-lap and in-lap
        l=lap_by.get((dn,ln))
        if not l or not l.get('lap_duration') or l.get('is_pit_out_lap') or ln<=2: continue
        if ln in r['neutral'] or ln-1 in r['neutral']: continue
        rows.append((dn,ln,c,a0+ln-x['lap_start'],l['lap_duration']))
  if len(rows)<400: continue
  # remove slow outliers (traffic, mistakes): > 103% of driver's median
  med={d:st.median([q[4] for q in rows if q[0]==d]) for d in set(q[0] for q in rows)}
  rows=[q for q in rows if q[4]<med[q[0]]*1.03]
  ds=sorted(set(q[0] for q in rows));di={d:i for i,d in enumerate(ds)}
  comps=sorted(set(q[2] for q in rows))
  if len(comps)<2: continue
  # columns: driver dummies | lap(fuel) | compound offsets (vs first) | age slope per compound
  nd=len(ds);X=[];y=[]
  for d,ln,c,age,t in rows:
    v=[0]*nd;v[di[d]]=1;v.append(ln)
    v+= [1 if c==cc else 0 for cc in comps[1:]]
    v+= [age if c==cc else 0 for cc in comps]
    X.append(v);y.append(t)
  X=np.array(X,float);y=np.array(y,float)
  b,*_=np.linalg.lstsq(X,y,rcond=None)
  res={'tid':r['tid'],'year':r['year'],'fuel':b[nd],'n':len(rows)}
  base=comps[0]
  offs={base:0.0};offs.update({cc:b[nd+1+i] for i,cc in enumerate(comps[1:])})
  slopes={cc:b[nd+len(comps)+i] for i,cc in enumerate(comps)}
  cnt=collections.Counter(q[2] for q in rows)
  res['off']={k:round(v,3) for k,v in offs.items()};res['slope']={k:round(v,4) for k,v in slopes.items()};res['cnt']=dict(cnt)
  degs.append(res)
json.dump(degs,open('deg.json','w'),indent=1)

# ---------- pit loss: (in-lap + out-lap) - 2 * driver's median green lap ----------
pl=collections.defaultdict(list)
for r in races:
  lap_by={(l['driver_number'],l['lap_number']):l.get('lap_duration') for l in r['laps']}
  for p in r['pit']:
    dn,ln=p['driver_number'],p.get('lap_number')
    if not ln or ln in r['neutral'] or ln+1 in r['neutral'] or ln-1 in r['neutral']: continue
    a,b2=lap_by.get((dn,ln)),lap_by.get((dn,ln+1))
    g=[lap_by.get((dn,x)) for x in range(max(3,ln-6),ln-1)]+[lap_by.get((dn,x)) for x in range(ln+3,ln+8)]
    g=[x for x in g if x]
    if a and b2 and len(g)>=4:
      loss=a+b2-2*st.median(g)
      if 10<loss<45: pl[r['tid']].append(loss)
json.dump({k:round(st.median(v),1) for k,v in pl.items() if len(v)>=8},open('pitloss.json','w'),indent=1)
print('done')
