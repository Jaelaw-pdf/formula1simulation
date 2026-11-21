const fs=require('fs');const P=JSON.parse(process.argv[2]);const WARM=JSON.parse(process.argv[3]);const RWM=1.1,SIG=3;
const real=JSON.parse(fs.readFileSync('strategy.json'));const tdeg=JSON.parse(fs.readFileSync('trackdeg.json'));const pitl=JSON.parse(fs.readFileSync('pitloss.json'));
const html=fs.readFileSync('/home/claude/formula1simulation/index.html','utf8');
const TR=[...html.matchAll(/\{id:'(\w+)',n:'[^']*',p:'[^']*',laps:(\d+),base:([\d.]+),ot:([\d.]+),deg:([\d.]+),rain:[\d.]+,sc:([\d.]+),st:\d,pit:(\d+)\}/g)].map(m=>({id:m[1],laps:+m[2],ot:+m[4],deg:+m[5],sc:+m[6],pit:+m[7]}));
const tyreLoss=(k,w)=>{const C=P[k];w=Math.max(0,w);return C.off+C.lin*C.life*w+C.cur*w*w*w+(w>1?(w-1)*C.life*.45:0)};
const warmOf=(k,a,f)=>{const W=WARM[k];if(a>1)return 0;return W[a]*(f?.5:1)};
function opt(t,d){const deg=d*RWM,laps=t.laps,pit=(pitl[t.id]?Math.round(pitl[t.id]):t.pit)-2.5+2.6,traf=+(.8+5*Math.pow(Math.max(0,1-t.ot),1.5)).toFixed(2);
 const T={};['S','M','H'].forEach(k=>{const w=deg/P[k].life;T[k]=[0,1].map(u=>{const a=[0];let s=0,we=u?.12:0;for(let n=0;n<=laps;n++){s+=tyreLoss(k,we);we+=w;a.push(s)}return a})});
 const sets={S:2,M:3,H:2};const uf=seq=>{const c={S:0,M:0,H:0};return seq.map(k=>{c[k]++;return c[k]>sets[k]?1:0})};
 const pt=(seq,lp)=>{const u=uf(seq);const b=[0,...lp,laps];let x=0;for(let i=0;i<seq.length;i++){const n=b[i+1]-b[i];if(n<1)return Infinity;x+=T[seq[i]][u[i]][n]+warmOf(seq[i],0,!i)+warmOf(seq[i],1,!i)}return x+(pit+traf)*(seq.length-1)};
 const bf=seq=>{const u=uf(seq);const mx=seq.map((k,i)=>Math.floor((1.08-(u[i]?.12:0))*P[k].life/deg));let best=null;
  if(seq.length===2){for(let p=1;p<laps;p++){if(p>mx[0]||laps-p>mx[1])continue;const v=pt(seq,[p]);if(!best||v<best.t)best={seq,laps:[p],t:v}}}
  else for(let p=1;p<laps-1&&p<=mx[0];p+=1)for(let q=p+1;q<laps&&q-p<=mx[1];q++){if(laps-q>mx[2])continue;const v=pt(seq,[p,q]);if(!best||v<best.t)best={seq,laps:[p,q],t:v}}return best};
 const K=['S','M','H'],s1=[],s2=[];K.forEach(a=>K.forEach(b=>{if(a!==b)s1.push([a,b])}));K.forEach(a=>K.forEach(b=>K.forEach(c=>{if(new Set([a,b,c]).size>=2)s2.push([a,b,c])})));
 const b1=s1.map(bf).filter(Boolean).sort((a,b)=>a.t-b.t)[0],b2=s2.map(bf).filter(Boolean).sort((a,b)=>a.t-b.t)[0];
 return{d:(b2?b2.t:Infinity)-(b1?b1.t:Infinity),b1,b2}}
const out={};
for(const t of TR){const r=real[t.id];const prior=t.id==='qat'?t.deg:Math.sqrt(t.deg*(tdeg[t.id]||t.deg));
 if(!r||r.drivers<15){out[t.id]={deg:+prior.toFixed(2),p1:null};console.log(t.id,'no data, deg',prior.toFixed(2));continue}
 const share=Math.min(.95,Math.max(.05,r.stops['1']||0));const target=SIG*Math.log(share/(1-share));
 let best=null;for(let d=.5;d<=1.6001;d+=.02){const o=opt(t,d);const dd=isFinite(o.d)?o.d:(o.b1?40:-40);const err=Math.abs(dd-target)+2*Math.abs(Math.log(d/prior));if(!best||err<best.err)best={d,err,dd,o}}
 const p1=1/(1+Math.exp(-best.dd/SIG));out[t.id]={deg:+best.d.toFixed(2),p1:+p1.toFixed(2),real1:share};
 console.log(t.id.padEnd(4),'old',t.deg,'prior',prior.toFixed(2),'-> fit',best.d.toFixed(2),'| 1stop real',(share*100).toFixed(0)+'%','model',(p1*100).toFixed(0)+'%','| best1',best.o.b1?best.o.b1.seq.join('')+'@'+best.o.b1.laps:'-','best2',best.o.b2?best.o.b2.seq.join('')+'@'+best.o.b2.laps.join('/'):'-')}
fs.writeFileSync('trackfit.json',JSON.stringify(out));
