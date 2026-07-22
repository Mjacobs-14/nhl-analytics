import json, sys

from _fetch import load

# SQL lives in queries.py (EDGE)
rows, OUT = load('edge')

def n1(x): return None if x is None else round(float(x), 1)
def n2(x): return None if x is None else round(float(x), 2)

FLAT = []
teams = set()
for r in rows:
    if r['top_skating_speed_mph'] is None:
        continue
    tm = r.get('primary_team') or ''
    if tm:
        teams.add(tm)
    FLAT.append([
        r['full_name'], r['position'], str(r['season']), r['games_played'],
        n2(r['top_skating_speed_mph']), n2(r['bursts_per_game']), n2(r['avg_skating_distance_per_game']),
        n1(r['top_shot_speed_mph']), n1(r['offensive_zone_time_pct']),
        n1(r['skating_speed_percentile']), n1(r['shot_speed_percentile']), n1(r['distance_skated_percentile']),
        tm,
    ])

teams = sorted(teams)
seasons = sorted({r[2] for r in FLAT})
assert 4 <= len(seasons) <= 6, seasons
assert 1500 < len(FLAT) < 5000, len(FLAT)
assert 30 <= len(teams) <= 70, len(teams)
for r in FLAT:
    assert 15 < r[4] < 27, r[:5]            # top speed mph plausible
    assert 0 <= (r[5] or 0) < 20, r          # bursts/game
print(f"OK: {len(FLAT)} player-seasons, {len(teams)} teams, {len(seasons)} seasons ({seasons[0]}..{seasons[-1]})")

FLAT_JS = json.dumps(FLAT, separators=(',', ':'))
TEAMS_JS = json.dumps(teams, separators=(',', ':'))

html = r'''<meta charset="utf-8">
<title>NHL Edge — Skater Athleticism</title>
<style>
:root{
  --paper:#faf8f6;--panel:#fff;--ink:#191512;--ink-2:#6a625b;--ink-3:#a49a90;
  --line:#e9e4dd;--fwd:#e0562a;--def:#2a78d6;--chip:#f0ebe4;--grid:#ece6de;
}
@media (prefers-color-scheme:dark){:root{
  --paper:#161311;--panel:#201c19;--ink:#f3efe9;--ink-2:#aba297;--ink-3:#6f665d;
  --line:#34302b;--fwd:#f26b3c;--def:#4c93e8;--chip:#2a2521;--grid:#2c2824;
}}
:root[data-theme=dark]{--paper:#161311;--panel:#201c19;--ink:#f3efe9;--ink-2:#aba297;--ink-3:#6f665d;
  --line:#34302b;--fwd:#f26b3c;--def:#4c93e8;--chip:#2a2521;--grid:#2c2824;}
:root[data-theme=light]{--paper:#faf8f6;--panel:#fff;--ink:#191512;--ink-2:#6a625b;--ink-3:#a49a90;
  --line:#e9e4dd;--fwd:#e0562a;--def:#2a78d6;--chip:#f0ebe4;--grid:#ece6de;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 "Segoe UI",system-ui,sans-serif;
  font-variant-numeric:tabular-nums;padding:26px clamp(14px,4vw,46px) 46px;}
h1{font-size:clamp(21px,3vw,29px);letter-spacing:-.02em;margin:0 0 3px;font-weight:750;}
.sub{color:var(--ink-2);margin:0 0 18px;max-width:70ch;}
.bar{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:16px;}
select,input[type=search]{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:7px 10px;font:inherit;}
input[type=search]{width:190px}
.chip{border:1px solid var(--line);background:var(--chip);color:var(--ink-2);border-radius:999px;padding:6px 13px;
  font:600 13px/1 inherit;cursor:pointer;display:inline-flex;gap:7px;align-items:center;}
.chip .sw{width:10px;height:10px;border-radius:50%;}
.chip[aria-pressed=true]{color:var(--ink);border-color:var(--ink-3);}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;}
.seg button{background:var(--panel);color:var(--ink-2);border:0;padding:7px 13px;font:600 13px/1 inherit;cursor:pointer;}
.seg button[aria-pressed=true]{background:var(--fwd);color:#fff;}
.chip:focus-visible,select:focus-visible,input:focus-visible,.seg button:focus-visible{outline:2px solid var(--fwd);outline-offset:2px;}
.wrap{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:10px 8px 6px;}
#cv{width:100%;display:block;cursor:crosshair;}
.note{color:var(--ink-3);font-size:12.5px;margin-top:13px;max-width:84ch;}
#tip{position:fixed;pointer-events:none;background:var(--panel);border:1px solid var(--line);border-radius:9px;
  padding:9px 12px;font-size:12.5px;box-shadow:0 6px 20px rgba(0,0,0,.18);opacity:0;z-index:9;max-width:250px;}
#tip .nm{font-weight:750;font-size:13.5px;margin-bottom:4px;}
#tip .rowg{display:grid;grid-template-columns:auto auto;gap:2px 12px;color:var(--ink-2);}
#tip .rowg b{color:var(--ink);font-weight:650;text-align:right;}
#tip .pct{margin-top:5px;padding-top:5px;border-top:1px solid var(--line);color:var(--ink-3);font-size:11.5px;}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:6px;}
th,td{padding:6px 10px;text-align:right;border-bottom:1px solid var(--line);}
th{color:var(--ink-2);font-weight:600;white-space:nowrap;}
th:first-child,td:first-child{text-align:left;}
th:nth-child(2),td:nth-child(2){text-align:center;}
#tblwrap{display:none;max-height:540px;overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:0 8px 8px;}
.cap{color:var(--ink-2);font-size:12.5px;margin:11px 2px 0;min-height:1.1em;}
.cap b{color:var(--ink);}
</style>
<h1>Speed &amp; Motor</h1>
<p class="sub">NHL Edge skater tracking — top speed, how often they hit top gear, and how far they skate.
Athleticism is roster, not system, so this lives on its own. Regular season, min 20 GP, 2021–2026.</p>
<div class="bar">
  <select id="season" aria-label="Season"></select>
  <select id="team" aria-label="Team"></select>
  <span class="seg" role="group" aria-label="X axis">
    <button id="mBurst" aria-pressed="true">Speed bursts</button>
    <button id="mDist" aria-pressed="false">Distance skated</button>
  </span>
  <button class="chip" id="cF" aria-pressed="true"><span class="sw" style="background:var(--fwd)"></span>Forwards</button>
  <button class="chip" id="cD" aria-pressed="true"><span class="sw" style="background:var(--def)"></span>Defense</button>
  <input type="search" id="find" placeholder="Find a player…" aria-label="Find a player">
  <button class="chip" id="tbl" aria-pressed="false">Table</button>
</div>
<div class="wrap" id="cvwrap"><canvas id="cv"></canvas></div>
<div id="tblwrap"><table id="t"><thead></thead><tbody></tbody></table></div>
<p class="cap" id="cap"></p>
<p class="note" id="note"></p>
<div id="tip" role="status"></div>
<script>
const F=__FLAT__;
const TEAMS=__TEAMS__;
const C={name:0,pos:1,season:2,gp:3,spd:4,burst:5,dist:6,shot:7,ozone:8,spdP:9,shotP:10,distP:11,team:12};
const isF=p=>p!=='D';
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const seasons=[...new Set(F.map(r=>r[C.season]))].sort().reverse();
const bySeason={};F.forEach(r=>{(bySeason[r[C.season]]=bySeason[r[C.season]]||[]).push(r);});
const sel=document.getElementById('season'),teamSel=document.getElementById('team');
seasons.forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k.slice(0,4)+'–'+k.slice(6);sel.appendChild(o);});
{const o=document.createElement('option');o.value='';o.textContent='All NHL';teamSel.appendChild(o);
 TEAMS.forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;teamSel.appendChild(o);});}
let st={season:seasons[0],mode:'burst',team:'',F:true,D:true,find:'',table:false,focus:null};
const cv=document.getElementById('cv'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
let pts=[],geom=null;
const XI=()=>st.mode==='burst'?C.burst:C.dist;
const XL=()=>st.mode==='burst'?'Speed bursts over 20 mph, per game  →':'Miles skated per game  →';

function rows(){return bySeason[st.season].filter(r=>(isF(r[C.pos])?st.F:st.D)&&r[XI()]!=null&&(!st.team||r[C.team]===st.team));}
// a player's (x=current axis, y=top speed) across every Edge season — career path
function careerPath(name){const p=[];seasons.slice().sort().forEach(s=>{
  const r=bySeason[s].find(r=>r[C.name]===name&&r[XI()]!=null&&r[C.spd]!=null);
  if(r)p.push({season:s,x:r[XI()],y:r[C.spd]});});return p;}
function draw(){
  pts=rows().map(r=>({r,x:r[XI()],y:r[C.spd]}));
  const path=st.focus?careerPath(st.focus):null;
  const W=Math.max(360,cv.parentElement.clientWidth-16),H=Math.max(430,Math.min(560,innerHeight*.62)),dpr=devicePixelRatio||1;
  cv.width=W*dpr;cv.height=H*dpr;cv.style.height=H+'px';ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,W,H);
  const P={l:60,r:16,t:20,b:48};
  // axes fixed to the whole league (not the team filter) so teams are comparable
  const league=bySeason[st.season].filter(r=>(isF(r[C.pos])?st.F:st.D)&&r[XI()]!=null);
  const xs=league.map(r=>r[XI()]),ys=league.map(r=>r[C.spd]);
  const cpx=path?path.map(p=>p.x):[],cpy=path?path.map(p=>p.y):[];
  const x0=0,x1=Math.max(...xs,...cpx)*1.05,y0=Math.min(...ys,...cpy)-.4,y1=Math.max(...ys,...cpy)+.3;
  const X=v=>P.l+(v-x0)/(x1-x0)*(W-P.l-P.r),Y=v=>H-P.b-(v-y0)/(y1-y0)*(H-P.t-P.b);
  geom={X,Y,W,H};
  ctx.strokeStyle=css('--grid');ctx.fillStyle=css('--ink-3');ctx.font='11px system-ui';ctx.lineWidth=1;ctx.textAlign='center';
  for(let i=0;i<=5;i++){const vx=x0+(x1-x0)*i/5;ctx.globalAlpha=.6;ctx.beginPath();ctx.moveTo(X(vx),P.t);ctx.lineTo(X(vx),H-P.b);ctx.stroke();
    ctx.globalAlpha=1;ctx.fillText(vx.toFixed(st.mode==='burst'?1:1),X(vx),H-P.b+15);}
  ctx.textAlign='right';
  for(let i=0;i<=5;i++){const vy=y0+(y1-y0)*i/5;ctx.globalAlpha=.6;ctx.beginPath();ctx.moveTo(P.l,Y(vy));ctx.lineTo(W-P.r,Y(vy));ctx.stroke();
    ctx.globalAlpha=1;ctx.fillText(vy.toFixed(1),P.l-7,Y(vy)+4);}
  const q=st.find.trim().toLowerCase();
  pts.forEach(p=>{p.px=X(p.x);p.py=Y(p.y);const hit=q&&p.r[C.name].toLowerCase().includes(q);
    ctx.globalAlpha=(st.focus||q)?(hit?1:.1):.72;ctx.fillStyle=isF(p.r[C.pos])?css('--fwd'):css('--def');
    ctx.beginPath();ctx.arc(p.px,p.py,hit?6:4,0,7);ctx.fill();
    if(hit){ctx.globalAlpha=1;ctx.strokeStyle=css('--panel');ctx.lineWidth=2;ctx.stroke();
      ctx.fillStyle=css('--ink');ctx.font='700 12px system-ui';ctx.textAlign='left';ctx.fillText(p.r[C.name],p.px+9,p.py+4);}});
  ctx.globalAlpha=1;
  if(path){
    const fr=F.find(r=>r[C.name]===st.focus);const fc=isF(fr?fr[C.pos]:'C')?css('--fwd'):css('--def');
    ctx.strokeStyle=fc;ctx.lineWidth=2.2;ctx.globalAlpha=.9;ctx.beginPath();
    path.forEach((p,i)=>{const px=X(p.x),py=Y(p.y);i?ctx.lineTo(px,py):ctx.moveTo(px,py);});ctx.stroke();
    ctx.globalAlpha=1;ctx.font='700 10.5px system-ui';ctx.textAlign='center';
    path.forEach((p,i)=>{const px=X(p.x),py=Y(p.y),last=i===path.length-1;
      ctx.fillStyle=fc;ctx.strokeStyle=css('--panel');ctx.lineWidth=2;
      ctx.beginPath();ctx.arc(px,py,last?6:4,0,7);ctx.fill();ctx.stroke();
      ctx.fillStyle=css('--ink-2');ctx.fillText("'"+p.season.slice(2,4),px,py-9);});
  } else if(!q){const lab=new Set();const pick=f=>pts.reduce((a,b)=>f(a,b)?a:b);
    [pick((a,b)=>a.y>b.y),pick((a,b)=>a.x>b.x),pick((a,b)=>a.x+ (a.y-y0)>b.x+(b.y-y0))].forEach(p=>lab.add(p));
    ctx.font='700 11.5px system-ui';
    lab.forEach(p=>{ctx.strokeStyle=css('--panel');ctx.lineWidth=2;ctx.beginPath();ctx.arc(p.px,p.py,5.5,0,7);
      ctx.fillStyle=isF(p.r[C.pos])?css('--fwd'):css('--def');ctx.fill();ctx.stroke();
      ctx.fillStyle=css('--ink');ctx.textAlign=p.px>W-140?'right':'left';
      ctx.fillText(p.r[C.name],p.px+(p.px>W-140?-9:9),p.py+4);});}
  ctx.fillStyle=css('--ink-2');ctx.font='600 12px system-ui';ctx.textAlign='center';ctx.fillText(XL(),(P.l+W-P.r)/2,H-8);
  ctx.save();ctx.translate(14,(P.t+H-P.b)/2);ctx.rotate(-Math.PI/2);ctx.fillText('Top skating speed (mph)  →',0,0);ctx.restore();
  document.getElementById('cap').innerHTML=st.focus
    ? '<b>'+st.focus+'</b> — skating path across '+(path?path.length:0)+' seasons (labelled by year). Click the dot again or elsewhere to clear.'
    : '';
  document.getElementById('note').textContent='Up = higher top gear. Right = '+(st.mode==='burst'?'hits 20+ mph more often (sustained speed).':'covers more ground per game (workload).')+' Colour = position. Search or click any dot to trace a player’s skating year over year; hover for percentiles.';
}
cv.addEventListener('mousemove',e=>{if(!geom||st.table)return;
  const rc=cv.getBoundingClientRect(),mx=(e.clientX-rc.left)*geom.W/rc.width,my=(e.clientY-rc.top)*geom.H/rc.height;
  let best=null,bd=200;pts.forEach(p=>{const dx=p.px-mx,dy=p.py-my,d=dx*dx+dy*dy;if(d<bd){bd=d;best=p;}});
  if(best){const r=best.r;
    tip.innerHTML='<div class="nm">'+r[C.name]+' · '+r[C.pos]+(r[C.team]?' · '+r[C.team]:'')+' · '+r[C.gp]+'GP</div><div class="rowg">'+
      '<span>Top speed</span><b>'+r[C.spd].toFixed(2)+' mph</b>'+
      '<span>20+ bursts/gm</span><b>'+(r[C.burst]==null?'—':r[C.burst].toFixed(2))+'</b>'+
      '<span>Miles/game</span><b>'+(r[C.dist]==null?'—':r[C.dist].toFixed(2))+'</b>'+
      '<span>Shot speed</span><b>'+(r[C.shot]==null?'—':r[C.shot].toFixed(1)+' mph')+'</b></div>'+
      '<div class="pct">Percentiles — speed '+(r[C.spdP]??'—')+' · shot '+(r[C.shotP]??'—')+' · distance '+(r[C.distP]??'—')+'</div>';
    tip.style.opacity=1;tip.style.left=Math.min(e.clientX+14,innerWidth-260)+'px';tip.style.top=(e.clientY-10)+'px';}
  else tip.style.opacity=0;});
cv.addEventListener('mouseleave',()=>tip.style.opacity=0);
cv.addEventListener('click',e=>{if(!geom||st.table)return;
  const rc=cv.getBoundingClientRect(),mx=(e.clientX-rc.left)*geom.W/rc.width,my=(e.clientY-rc.top)*geom.H/rc.height;
  let best=null,bd=260;pts.forEach(p=>{const dx=p.px-mx,dy=p.py-my,d=dx*dx+dy*dy;if(d<bd){bd=d;best=p;}});
  st.focus=best?((st.focus===best.r[C.name])?null:best.r[C.name]):null;draw();});
function tbl(){const q=st.find.trim().toLowerCase();
  const rs=rows().filter(r=>!q||r[C.name].toLowerCase().includes(q)).sort((a,b)=>b[C.spd]-a[C.spd]);
  document.querySelector('#t thead').innerHTML='<tr><th>Player</th><th>Pos</th><th>Team</th><th>GP</th><th>Top mph</th><th>Bursts/gm</th><th>Mi/gm</th><th>Shot mph</th></tr>';
  document.querySelector('#t tbody').innerHTML=rs.map(r=>'<tr><td>'+r[C.name]+'</td><td>'+r[C.pos]+'</td><td>'+(r[C.team]||'—')+'</td><td>'+r[C.gp]+'</td><td>'+r[C.spd].toFixed(2)+'</td><td>'+(r[C.burst]==null?'—':r[C.burst].toFixed(2))+'</td><td>'+(r[C.dist]==null?'—':r[C.dist].toFixed(2))+'</td><td>'+(r[C.shot]==null?'—':r[C.shot].toFixed(1))+'</td></tr>').join('');}
const press=(id,on)=>document.getElementById(id).setAttribute('aria-pressed',on);
function refresh(){if(st.table)tbl();else draw();}
sel.onchange=()=>{st.season=sel.value;refresh();};
teamSel.onchange=()=>{st.team=teamSel.value;refresh();};
document.getElementById('mBurst').onclick=()=>{st.mode='burst';press('mBurst',1);press('mDist',0);refresh();};
document.getElementById('mDist').onclick=()=>{st.mode='dist';press('mDist',1);press('mBurst',0);refresh();};
[['cF','F'],['cD','D']].forEach(p=>{const b=document.getElementById(p[0]);b.onclick=()=>{st[p[1]]=!st[p[1]];press(p[0],st[p[1]]);refresh();};});
// global search: focus/trace the best-matching player across ALL seasons (finds retired players too)
document.getElementById('find').oninput=e=>{st.find=e.target.value;const q=st.find.trim().toLowerCase();
  const m=q?F.find(r=>r[C.name].toLowerCase().includes(q)):null;st.focus=m?m[C.name]:null;refresh();};
document.getElementById('tbl').onclick=e=>{st.table=!st.table;press('tbl',st.table);
  document.getElementById('tblwrap').style.display=st.table?'block':'none';
  document.getElementById('cvwrap').style.display=st.table?'none':'block';refresh();};
new MutationObserver(()=>refresh()).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',()=>refresh());
addEventListener('resize',()=>{if(!st.table)draw();});
draw();
</script>'''
html = html.replace('__FLAT__', FLAT_JS).replace('__TEAMS__', TEAMS_JS)
from _fetch import write_page
write_page(OUT, html)
print(f"wrote {OUT}: {len(html)} bytes")
