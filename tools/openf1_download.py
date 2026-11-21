import json,os,time,subprocess,sys
eps=['stints','laps','drivers','pit','race_control']
years=sys.argv[1:]
for y in years:
  for s in json.load(open(f's{y}.json')):
    k=s['session_key'];os.makedirs(f'raw/{k}',exist_ok=True)
    json.dump(s,open(f'raw/{k}/session.json','w'))
    for e in eps:
      f=f'raw/{k}/{e}.json'
      if os.path.exists(f) and os.path.getsize(f)>2: continue
      for att in range(6):
        r=subprocess.run(['curl','-s','-m','60','-w','%{http_code}','-o',f,f'https://api.openf1.org/v1/{e}?session_key={k}'],capture_output=True,text=True)
        if r.stdout in ('200','404'): break
        time.sleep(5*(att+1))
      time.sleep(0.6)
    try: n=len(json.load(open(f'raw/{k}/stints.json')))
    except Exception: n=-1
    print(y,s['circuit_short_name'],k,'stints',n,flush=True)
