import json, sys
from collections import defaultdict

from _fetch import load

# SQL lives in queries.py (QUADRANTS)
rows, OUT = load('quadrants')

players = []      # "name|pos"
pidx = {}
teams = set()
for r in rows:
    nm = r['full_name']
    if nm not in pidx:
        pidx[nm] = len(players)
        players.append(nm + '|' + (r['position'] or ''))
    if r.get('primary_team'):
        teams.add(r['primary_team'])
teams = sorted(teams)
tix = {t: i for i, t in enumerate(teams)}

by_season = defaultdict(list)
for r in rows:
    i = pidx[r['full_name']]
    gp = int(r['gp']); ppg = round(float(r['ppg']) * 100); s60 = round(float(r['sog_per_60']) * 10)
    ti = tix.get(r.get('primary_team'), -1)
    by_season[str(r['season'])].append(f"{i}.{gp}.{ppg}.{s60}.{ti}")

seasons = sorted(by_season)
assert len(seasons) == 8, seasons
assert 900 < len(players) < 2000, len(players)
assert 30 <= len(teams) <= 70, len(teams)
for p in players:
    assert '`' not in p and '${' not in p
print(f"OK: {len(players)} players, {sum(len(v) for v in by_season.values())} rows, {len(teams)} teams, {len(seasons)} seasons")

DICT_S = ';'.join(players)
TEAMS_S = ';'.join(teams)
SEASONS_JS = ',\n'.join(f'"{k}":`{";".join(v)}`' for k, v in sorted(by_season.items()))

html = r'''<meta charset="utf-8">
<title>Shot Volume vs. Output — NHL Quadrants</title>
<style>
:root{--paper:#fcfcfb;--ink:#17181a;--ink-2:#5a5e66;--ink-3:#9094a0;--line:#e4e4e0;--card:#fff;--f:#2a78d6;--d:#1baf7a;--chipbg:#f1f1ee;}
@media (prefers-color-scheme:dark){:root{--paper:#1a1a19;--ink:#f2f2ef;--ink-2:#a8acb5;--ink-3:#6e727c;--line:#33332f;--card:#222221;--f:#3987e5;--d:#199e70;--chipbg:#2a2a28;}}
:root[data-theme="dark"]{--paper:#1a1a19;--ink:#f2f2ef;--ink-2:#a8acb5;--ink-3:#6e727c;--line:#33332f;--card:#222221;--f:#3987e5;--d:#199e70;--chipbg:#2a2a28;}
:root[data-theme="light"]{--paper:#fcfcfb;--ink:#17181a;--ink-2:#5a5e66;--ink-3:#9094a0;--line:#e4e4e0;--card:#fff;--f:#2a78d6;--d:#1baf7a;--chipbg:#f1f1ee;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 "Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums;padding:26px clamp(14px,4vw,44px) 42px;}
h1{font-size:clamp(20px,3vw,27px);letter-spacing:-.02em;margin:0 0 2px;font-weight:700;}
.sub{color:var(--ink-2);margin:0 0 18px;max-width:70ch;}
.bar{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:14px;}
select,input[type=search]{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:7px 10px;font:inherit;}
input[type=search]{width:190px}
.chip{border:1px solid var(--line);background:var(--chipbg);color:var(--ink-2);border-radius:999px;padding:6px 13px;font:600 13px/1 inherit;cursor:pointer;display:inline-flex;gap:7px;align-items:center;}
.chip .sw{width:10px;height:10px;border-radius:50%;}
.chip[aria-pressed=true]{color:var(--ink);border-color:var(--ink-3);}
.chip:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--f);outline-offset:2px;}
.wrap{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 6px 4px;}
#cv{width:100%;display:block;cursor:crosshair;}
.counts{display:flex;gap:16px;flex-wrap:wrap;color:var(--ink-2);font-size:13px;margin:12px 2px 0;}
.counts b{color:var(--ink);font-weight:700;}
.cap{color:var(--ink-2);font-size:12.5px;margin:11px 2px 0;min-height:1.1em;}
.cap b{color:var(--ink);}
.note{color:var(--ink-3);font-size:12.5px;margin-top:10px;max-width:82ch;}
#tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 11px;font-size:13px;box-shadow:0 4px 14px rgba(0,0,0,.14);opacity:0;z-index:9;}
#tip .nm{font-weight:700;}#tip .q{color:var(--ink-2);font-size:12px;}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:6px;}
th,td{padding:6px 10px;text-align:right;border-bottom:1px solid var(--line);}
th{color:var(--ink-2);font-weight:600;white-space:nowrap;}
th:first-child,td:first-child{text-align:left;}th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3){text-align:center;}
#tblwrap{display:none;max-height:520px;overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--card);padding:0 8px 8px;}
.qtag{font-size:11.5px;padding:2px 8px;border-radius:999px;background:var(--chipbg);color:var(--ink-2);white-space:nowrap;}
</style>
<h1>Firing Blanks or Firing on All Cylinders?</h1>
<p class="sub">Every skater&rsquo;s shot volume (SOG/60) against production (points per game), regular season, min 20 GP.
Quadrant lines are the league median. Filter by team, or search any player &mdash; even retired ones &mdash; to trace their career.</p>
<div class="bar">
  <select id="season" aria-label="Season"></select>
  <select id="team" aria-label="Team"></select>
  <button class="chip" id="cF" aria-pressed="true"><span class="sw" style="background:var(--f)"></span>Forwards</button>
  <button class="chip" id="cD" aria-pressed="true"><span class="sw" style="background:var(--d)"></span>Defense</button>
  <input type="search" id="find" placeholder="Trace any player…" aria-label="Find a player">
  <button class="chip" id="tbl" aria-pressed="false">Table view</button>
</div>
<div class="wrap" id="cvwrap"><canvas id="cv"></canvas></div>
<div id="tblwrap"><table id="t"><thead></thead><tbody></tbody></table></div>
<div class="counts" id="counts"></div>
<p class="cap" id="cap"></p>
<p class="note">Quadrants &mdash; <b>Engines</b>: high volume, high output &middot; <b>Playmakers</b>: modest volume, high output &middot;
<b>Volume, no payoff</b>: shoots a lot, produces little &middot; <b>Quiet nights</b>: neither. Axes stay fixed to the league so
teams are comparable. Traded players sit with their most-played team that season. Click a dot (or search) to trace a career.</p>
<div id="tip" role="status"></div>
<script>
const DICT=`__DICT__`.split(';').map(s=>{const i=s.lastIndexOf('|');return{n:s.slice(0,i),p:s.slice(i+1)};});
const TEAMS=`__TEAMS__`.split(';');
const RAW={__SEASONS__};
const isF=p=>p!=='D';
const SEASONS=Object.keys(RAW).sort().reverse();
const parse=k=>RAW[k].split(';').map(r=>{const[a,g,pp,ss,ti]=r.split('.');const d=DICT[+a];
  return{i:+a,n:d.n,p:d.p,team:+ti>=0?TEAMS[+ti]:'',gp:+g,ppg:+pp/100,s60:+ss/10};});
function careerPath(idx){const path=[];SEASONS.slice().sort().forEach(k=>{
  const row=RAW[k].split(';').map(r=>r.split('.')).find(a=>+a[0]===idx);
  if(row)path.push({season:k,s60:+row[3]/10,ppg:+row[2]/100});});return path;}
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const sel=document.getElementById('season'),teamSel=document.getElementById('team');
SEASONS.forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k.slice(0,4)+'–'+k.slice(6);sel.appendChild(o);});
{const o=document.createElement('option');o.value='';o.textContent='All NHL';teamSel.appendChild(o);
 TEAMS.forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;teamSel.appendChild(o);});}
let state={season:SEASONS[0],team:'',F:true,D:true,find:'',table:false,focus:null};
const median=a=>{const b=[...a].sort((x,y)=>x-y),m=b.length>>1;return b.length%2?b[m]:(b[m-1]+b[m])/2;};
const cv=document.getElementById('cv'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
let pts=[],meds=[0,0],dom={xmax:14,ymax:1.6},geom=null;
function quad(d){return d.s60>=meds[0]?(d.ppg>=meds[1]?'Engines':'Volume, no payoff'):(d.ppg>=meds[1]?'Playmakers':'Quiet nights');}
function load(){const all=parse(state.season);
  meds=[median(all.map(d=>d.s60)),median(all.map(d=>d.ppg))];
  dom={xmax:Math.max(14,...all.map(d=>d.s60))*1.05,ymax:Math.max(1.6,...all.map(d=>d.ppg))*1.06};
  pts=all.filter(d=>(isF(d.p)?state.F:state.D)&&(!state.team||d.team===state.team));
  render();counts();if(state.table)tbl();}
function counts(){const c={};pts.forEach(d=>{const q=quad(d);c[q]=(c[q]||0)+1;});
  document.getElementById('counts').innerHTML=['Engines','Playmakers','Volume, no payoff','Quiet nights']
   .map(q=>'<span><b>'+(c[q]||0)+'</b> '+q.toLowerCase()+'</span>').join('');}
function render(){
  const path=state.focus!=null?careerPath(state.focus):null;
  const W=Math.max(360,cv.parentElement.clientWidth-14),H=Math.max(420,Math.min(560,innerHeight*.62)),dpr=devicePixelRatio||1;
  cv.width=W*dpr;cv.height=H*dpr;cv.style.height=H+'px';ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,W,H);
  const P={l:52,r:16,t:26,b:44},
    xmax=Math.max(dom.xmax,...(path?path.map(p=>p.s60):[])),
    ymax=Math.max(dom.ymax,...(path?path.map(p=>p.ppg):[])),
    X=v=>P.l+(v/xmax)*(W-P.l-P.r),Y=v=>H-P.b-(v/ymax)*(H-P.t-P.b);
  geom={X,Y,W,H};
  ctx.strokeStyle=css('--line');ctx.lineWidth=1;ctx.fillStyle=css('--ink-3');ctx.font='11.5px system-ui';ctx.textAlign='center';
  for(let x=0;x<=xmax;x+=2){ctx.globalAlpha=.55;ctx.beginPath();ctx.moveTo(X(x),P.t);ctx.lineTo(X(x),H-P.b);ctx.stroke();ctx.globalAlpha=1;ctx.fillText(x,X(x),H-P.b+16);}
  ctx.textAlign='right';
  for(let y=0;y<=ymax;y+=.25){ctx.globalAlpha=.55;ctx.beginPath();ctx.moveTo(P.l,Y(y));ctx.lineTo(W-P.r,Y(y));ctx.stroke();ctx.globalAlpha=1;ctx.fillText(y.toFixed(2),P.l-7,Y(y)+4);}
  ctx.save();ctx.setLineDash([5,4]);ctx.strokeStyle=css('--ink-3');ctx.lineWidth=1.4;
  ctx.beginPath();ctx.moveTo(X(meds[0]),P.t);ctx.lineTo(X(meds[0]),H-P.b);ctx.stroke();
  ctx.beginPath();ctx.moveTo(P.l,Y(meds[1]));ctx.lineTo(W-P.r,Y(meds[1]));ctx.stroke();ctx.restore();
  ctx.fillStyle=css('--ink-3');ctx.font='600 11px system-ui';ctx.textAlign='left';
  ctx.fillText('league median '+meds[0].toFixed(1)+' SOG/60',X(meds[0])+6,P.t+11);
  ctx.fillText(meds[1].toFixed(2)+' PPG',P.l+6,Y(meds[1])-6);
  ctx.font='700 12px system-ui';ctx.globalAlpha=.7;
  ctx.textAlign='left';ctx.fillText('PLAYMAKERS',P.l+10,P.t+26);
  ctx.textAlign='right';ctx.fillText('ENGINES',W-P.r-10,P.t+26);ctx.fillText('VOLUME, NO PAYOFF',W-P.r-10,H-P.b-12);
  ctx.textAlign='left';ctx.fillText('QUIET NIGHTS',P.l+10,H-P.b-12);ctx.globalAlpha=1;
  pts.forEach(d=>{d.px=X(d.s60);d.py=Y(d.ppg);
    ctx.globalAlpha=state.focus!=null?.12:.8;ctx.fillStyle=isF(d.p)?css('--f'):css('--d');
    ctx.beginPath();ctx.arc(d.px,d.py,4.5,0,7);ctx.fill();});
  ctx.globalAlpha=1;
  if(path){const fc=isF(DICT[state.focus].p)?css('--f'):css('--d');
    ctx.strokeStyle=fc;ctx.lineWidth=2.2;ctx.globalAlpha=.9;ctx.beginPath();
    path.forEach((p,i)=>{const px=X(p.s60),py=Y(p.ppg);i?ctx.lineTo(px,py):ctx.moveTo(px,py);});ctx.stroke();
    ctx.globalAlpha=1;ctx.font='700 10.5px system-ui';ctx.textAlign='center';
    path.forEach((p,i)=>{const px=X(p.s60),py=Y(p.ppg),last=i===path.length-1;
      ctx.fillStyle=fc;ctx.strokeStyle=css('--card');ctx.lineWidth=2;ctx.beginPath();ctx.arc(px,py,last?6:4,0,7);ctx.fill();ctx.stroke();
      ctx.fillStyle=css('--ink-2');ctx.fillText("'"+p.season.slice(2,4),px,py-9);});
  }else{const score=(d,sx,sy)=>sx*(d.s60-meds[0])/xmax+sy*(d.ppg-meds[1])/ymax;
    [['Volume, no payoff',1,-1],['Engines',1,1],['Playmakers',-1,1]].forEach(qd=>{
      const cand=pts.filter(d=>quad(d)===qd[0]);if(!cand.length)return;
      const d=cand.reduce((a,b)=>score(a,qd[1],qd[2])>score(b,qd[1],qd[2])?a:b);
      ctx.font='700 12px system-ui';ctx.strokeStyle=css('--card');ctx.lineWidth=2;
      ctx.beginPath();ctx.arc(d.px,d.py,5.5,0,7);ctx.fillStyle=isF(d.p)?css('--f'):css('--d');ctx.fill();ctx.stroke();
      ctx.fillStyle=css('--ink');ctx.textAlign=d.px>W-130?'right':'left';ctx.fillText(d.n,d.px+(d.px>W-130?-9:9),d.py+4);});}
  ctx.fillStyle=css('--ink-2');ctx.font='600 12px system-ui';ctx.textAlign='center';ctx.fillText('Shots on goal per 60 minutes',(P.l+W-P.r)/2,H-10);
  ctx.save();ctx.translate(13,(P.t+H-P.b)/2);ctx.rotate(-Math.PI/2);ctx.fillText('Points per game',0,0);ctx.restore();
  const f=state.focus!=null?DICT[state.focus]:null;
  document.getElementById('cap').innerHTML=f?'<b>'+f.n+'</b> — career path across '+(path?path.length:0)+' seasons (labelled by year). Clear the search or click the dot again to reset.':'';}
cv.addEventListener('mousemove',e=>{if(!geom||state.table)return;
  const r=cv.getBoundingClientRect(),mx=(e.clientX-r.left)*geom.W/r.width,my=(e.clientY-r.top)*geom.H/r.height;
  let best=null,bd=196;pts.forEach(d=>{const dx=d.px-mx,dy=d.py-my,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;best=d;}});
  if(best){tip.innerHTML='<div class="nm">'+best.n+' · '+best.p+(best.team?' · '+best.team:'')+'</div>'+
    best.ppg.toFixed(2)+' PPG · '+best.s60.toFixed(1)+' SOG/60 · '+best.gp+' GP<div class="q">'+quad(best)+'</div>';
    tip.style.opacity=1;tip.style.left=Math.min(e.clientX+14,innerWidth-200)+'px';tip.style.top=(e.clientY-14)+'px';}
  else tip.style.opacity=0;});
cv.addEventListener('mouseleave',()=>{tip.style.opacity=0;});
cv.addEventListener('click',e=>{if(!geom||state.table)return;
  const r=cv.getBoundingClientRect(),mx=(e.clientX-r.left)*geom.W/r.width,my=(e.clientY-r.top)*geom.H/r.height;
  let best=null,bd=260;pts.forEach(d=>{const dx=d.px-mx,dy=d.py-my,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;best=d;}});
  state.focus=best?((state.focus===best.i)?null:best.i):null;
  if(state.focus==null){document.getElementById('find').value='';state.find='';}render();});
function tbl(){const q=state.find.trim().toLowerCase();
  const rows=pts.filter(d=>!q||d.n.toLowerCase().includes(q)).sort((a,b)=>b.s60-a.s60);
  document.querySelector('#t thead').innerHTML='<tr><th>Player</th><th>Pos</th><th>Team</th><th>GP</th><th>PPG</th><th>SOG/60</th><th></th></tr>';
  document.querySelector('#t tbody').innerHTML=rows.map(d=>'<tr><td>'+d.n+'</td><td>'+d.p+'</td><td>'+(d.team||'—')+'</td><td>'+d.gp+'</td><td>'+d.ppg.toFixed(2)+'</td><td>'+d.s60.toFixed(1)+'</td><td><span class="qtag">'+quad(d)+'</span></td></tr>').join('');}
document.getElementById('tbl').onclick=e=>{state.table=!state.table;e.currentTarget.setAttribute('aria-pressed',state.table);
  document.getElementById('tblwrap').style.display=state.table?'block':'none';
  document.getElementById('cvwrap').style.display=state.table?'none':'block';
  if(state.table){tbl();}else{render();}};
sel.onchange=()=>{state.season=sel.value;load();};
teamSel.onchange=()=>{state.team=teamSel.value;load();};
[['cF','F'],['cD','D']].forEach(pair=>{const b=document.getElementById(pair[0]);
  b.onclick=()=>{state[pair[1]]=!state[pair[1]];b.setAttribute('aria-pressed',state[pair[1]]);load();};});
document.getElementById('find').oninput=e=>{state.find=e.target.value;const q=state.find.trim().toLowerCase();
  state.focus=q?(()=>{const i=DICT.findIndex(d=>d.n.toLowerCase().includes(q));return i>=0?i:null;})():null;
  if(state.table){tbl();}else{render();}};
new MutationObserver(()=>render()).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>render());
addEventListener('resize',()=>{if(!state.table)render();});
load();
</script>'''

html = html.replace('__DICT__', DICT_S).replace('__TEAMS__', TEAMS_S).replace('__SEASONS__', SEASONS_JS)
from _fetch import write_page
write_page(OUT, html)
print(f"wrote {OUT}: {len(html)} bytes")
