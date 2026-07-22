import json, sys

from _fetch import load, load_extra

# SQL lives in queries.py (COACH_STYLE + COACH_CHANGE).
rows, OUT = load('coach_style')
changes = load_extra('coach_change')

def num(x):
    return None if x is None else round(float(x), 4)

# flat compact rows
FLAT = []
for r in rows:
    FLAT.append([
        r['coach'], r['team'], str(r['season']), r['gp'],
        num(r['cf_per_game']), num(r['xgf_per_game']), num(r['xg_per_shot_for']), num(r['avg_shot_dist_for']),
        num(r['tip_pct_for']), num(r['slap_pct_for']),
        num(r['ca_per_game']), num(r['xga_per_game']), num(r['xga_per_shot']), num(r['block_pct']),
        num(r['team_sv_pct']), num(r['gsax']),
        num(r['rush_for_pct']), num(r['rush_against_pct']),
    ])

seasons = sorted({r[2] for r in FLAT})
assert len(seasons) == 8, seasons
assert 200 < len(FLAT) < 400, len(FLAT)
rush_have = sum(1 for r in FLAT if r[16] is not None)
assert rush_have > 250, rush_have
for r in FLAT:
    assert 40 < r[4] < 90 and 0.07 < r[6] < 0.14, r[:8]
    if r[16] is not None:
        assert 5 < r[16] < 16, r
print(f"OK: {len(FLAT)} coach-seasons, {len(seasons)} seasons, {rush_have} with rush, {len(changes)} changes")

FLAT_JS = json.dumps(FLAT, separators=(',', ':'))
CHANGE_JS = json.dumps(changes, separators=(',', ':'))

html = r'''<meta charset="utf-8">
<title>Coach Fingerprints — NHL Style, Rush & Impact</title>
<style>
:root{
  --paper:#f7f7f4;--panel:#fff;--ink:#16181c;--ink-2:#585d67;--ink-3:#9297a2;
  --line:#e5e5e0;--accent:#2a78d6;--rush:#eb6834;--pos:#1baf7a;--neg:#e34948;--chip:#eeeee9;
}
@media (prefers-color-scheme:dark){:root{
  --paper:#141414;--panel:#1e1e1d;--ink:#f0f0ec;--ink-2:#a6aab3;--ink-3:#6b6f79;
  --line:#33332f;--accent:#3987e5;--rush:#d95926;--pos:#199e70;--neg:#e66767;--chip:#2a2a28;
}}
:root[data-theme=dark]{--paper:#141414;--panel:#1e1e1d;--ink:#f0f0ec;--ink-2:#a6aab3;--ink-3:#6b6f79;
  --line:#33332f;--accent:#3987e5;--rush:#d95926;--pos:#199e70;--neg:#e66767;--chip:#2a2a28;}
:root[data-theme=light]{--paper:#f7f7f4;--panel:#fff;--ink:#16181c;--ink-2:#585d67;--ink-3:#9297a2;
  --line:#e5e5e0;--accent:#2a78d6;--rush:#eb6834;--pos:#1baf7a;--neg:#e34948;--chip:#eeeee9;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 "Segoe UI",system-ui,sans-serif;
  font-variant-numeric:tabular-nums;padding:26px clamp(14px,4vw,46px) 46px;}
h1{font-size:clamp(21px,3vw,28px);letter-spacing:-.02em;margin:0 0 3px;font-weight:750;}
.sub{color:var(--ink-2);margin:0 0 18px;max-width:72ch;}
.bar{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:16px;}
select{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:7px 10px;font:inherit;}
.seg{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;}
.seg button{background:var(--panel);color:var(--ink-2);border:0;padding:7px 13px;font:600 13px/1 inherit;cursor:pointer;}
.seg button[aria-pressed=true]{background:var(--accent);color:#fff;}
.seg button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px;}
.wrap{background:var(--panel);border:1px solid var(--line);border-radius:13px;padding:10px 8px 6px;}
#cv{width:100%;display:block;cursor:crosshair;}
.note{color:var(--ink-3);font-size:12.5px;margin-top:13px;max-width:84ch;}
#tip{position:fixed;pointer-events:none;background:var(--panel);border:1px solid var(--line);border-radius:9px;
  padding:9px 12px;font-size:12.5px;box-shadow:0 6px 20px rgba(0,0,0,.16);opacity:0;z-index:9;max-width:270px;}
#tip .nm{font-weight:750;font-size:13.5px;margin-bottom:3px;}
#tip .rowg{display:grid;grid-template-columns:auto auto;gap:1px 12px;color:var(--ink-2);margin-top:5px;}
#tip .rowg b{color:var(--ink);font-weight:650;text-align:right;}
.tv{display:none;}
h2{font-size:16px;margin:24px 0 3px;font-weight:700;}
/* boards */
.board{display:flex;flex-direction:column;gap:2px;}
.chg{display:grid;grid-template-columns:200px 1fr 74px;gap:12px;align-items:center;padding:7px 10px;border-bottom:1px solid var(--line);}
.chg:hover{background:var(--chip);}
.chg .who{font-size:13px;}
.chg .who .arw{color:var(--ink-3);}
.chg .who .meta{color:var(--ink-3);font-size:11.5px;}
.chg .track{position:relative;height:20px;}
.chg .track .mid{position:absolute;left:50%;top:-3px;bottom:-3px;width:1px;background:var(--line);}
.chg .track .fill{position:absolute;top:3px;height:14px;border-radius:3px;}
.chg .val{text-align:right;font-weight:700;font-size:13.5px;}
.legend{color:var(--ink-3);font-size:12px;margin:8px 2px 0;max-width:84ch;}
/* consistency rows */
.cst{display:grid;grid-template-columns:150px 1fr 96px;gap:12px;align-items:center;padding:6px 10px;border-bottom:1px solid var(--line);}
.cst:hover{background:var(--chip);}
.cst .nm{font-size:13px;font-weight:600;}
.cst .nm .sub2{color:var(--ink-3);font-size:11px;font-weight:400;}
.cst .rtrack{position:relative;height:22px;}
.cst .rline{position:absolute;top:10px;height:3px;border-radius:2px;}
.cst .rdot{position:absolute;top:6px;width:11px;height:11px;border-radius:50%;border:2px solid var(--panel);}
.cst .sdot{position:absolute;top:8px;width:7px;height:7px;border-radius:50%;opacity:.55;}
.cst .rv{text-align:right;font-size:12.5px;color:var(--ink-2);}
.cst .rv b{color:var(--ink);}
.axl{display:flex;justify-content:space-between;color:var(--ink-3);font-size:11px;padding:2px 10px 0;}
input[type=search]{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:7px 10px;font:inherit;width:170px;}
.chip{border:1px solid var(--line);background:var(--chip);color:var(--ink-2);border-radius:999px;padding:6px 12px;font:600 13px/1 inherit;cursor:pointer;}
input:focus-visible,.chip:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
.cap{color:var(--ink-2);font-size:12.5px;margin:9px 2px 0;min-height:1.1em;}
.cap b{color:var(--ink);}
</style>

<h1>Coach Fingerprints</h1>
<p class="sub">How teams play under their coaches — what they generate, allow, and how they attack (rush vs. cycle),
plus which coaches impose a style year after year and which adapt. Regular season, min 20 GP.</p>

<div class="bar">
  <select id="season" aria-label="Season"></select>
  <span class="seg" role="group" aria-label="View">
    <button id="vMap" aria-pressed="true">Style map</button>
    <button id="vTime" aria-pressed="false">Style over time</button>
    <button id="vBoard" aria-pressed="false">Turnarounds</button>
  </span>
  <span class="seg" id="modeSeg" role="group" aria-label="Map mode">
    <button id="mDef" aria-pressed="true">Defense</button>
    <button id="mOff" aria-pressed="false">Offense</button>
    <button id="mRush" aria-pressed="false">Rush</button>
  </span>
  <input type="search" id="find" placeholder="Find a coach…" aria-label="Find a coach">
  <button class="chip" id="clr" style="display:none">✕ clear career</button>
</div>

<div class="tv" id="mapView" style="display:block">
  <div class="wrap"><canvas id="cv"></canvas></div>
  <p class="cap" id="mapCap"></p>
  <p class="note" id="mapNote"></p>
</div>

<div class="tv" id="timeView">
  <h2>Rush identity, season by season — imposers vs. adapters</h2>
  <p class="legend">Each coach's rush-shot share across the seasons they coached (min 3). The line spans their
    lowest→highest season, the big dot is their career average, small dots are individual seasons. A
    <b style="color:var(--accent)">short line</b> = a coach who imposes the same style regardless of roster; a
    <b style="color:var(--rush)">long line</b> = a coach whose style shifts season to season. Sorted by how much they vary.</p>
  <div class="axl" id="timeAx"></div>
  <div class="board" id="timeBoard"></div>
</div>

<div class="tv" id="boardView">
  <h2>Mid-season coaching changes — before vs. after</h2>
  <p class="legend">Same roster, same season: the least roster-confounded coach signal.
    <b style="color:var(--pos)">Green = improved</b>, <b style="color:var(--neg)">red = declined</b>. Min 10 games each side.</p>
  <div class="bar" style="margin:10px 0 6px">
    <span class="seg" id="metricSeg" role="group" aria-label="Metric">
      <button id="bXg" aria-pressed="true">xGF %</button>
      <button id="bGd" aria-pressed="false">Goal diff / game</button>
      <button id="bWin" aria-pressed="false">Win %</button>
    </span>
  </div>
  <div class="board" id="board"></div>
</div>

<div id="tip" role="status"></div>
<script>
const F=__FLAT__, CH=__CHANGE__;
const C={coach:0,team:1,season:2,gp:3,cf:4,xgf:5,xgpsF:6,dist:7,tip:8,slap:9,ca:10,xga:11,xgpsA:12,block:13,sv:14,gsax:15,rushF:16,rushA:17};
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const seasons=[...new Set(F.map(r=>r[C.season]))].sort().reverse();
const bySeason={};F.forEach(r=>{(bySeason[r[C.season]]=bySeason[r[C.season]]||[]).push(r);});
const sel=document.getElementById('season');
seasons.forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k.slice(0,4)+'–'+k.slice(6);sel.appendChild(o);});
let st={season:seasons[0],view:'map',mode:'def',metric:'xg',find:'',focus:null};
const median=a=>{const b=[...a].sort((x,y)=>x-y),m=b.length>>1;return b.length%2?b[m]:(b[m-1]+b[m])/2;};
// gp-weighted (x,y) per season for one coach, across all their teams — the career path
function careerPath(coach,M){
  const bs={};
  F.forEach(r=>{if(r[C.coach]!==coach||r[M.xi]==null||r[M.yi]==null)return;
    const s=r[C.season];if(!bs[s])bs[s]={w:0,x:0,y:0};
    bs[s].w+=r[C.gp];bs[s].x+=r[M.xi]*r[C.gp];bs[s].y+=r[M.yi]*r[C.gp];});
  return Object.keys(bs).sort().map(s=>({season:s,x:bs[s].x/bs[s].w,y:bs[s].y/bs[s].w}));
}

const cv=document.getElementById('cv'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
let pts=[],geom=null;

const MODES={
  def:{xi:C.ca,yi:C.xgpsA,fx:0,fy:3,xl:'Shots allowed / game  →  more volume',yl:'xG per shot allowed  →  more dangerous',
    q:{tl:'VOLUME SUPPRESSOR',tr:'LEAKY',bl:'LOCKDOWN',br:'BEND, DON’T BREAK'},col:'--accent',
    note:'Defensive identity. Left = fewer shots; down = lower danger per shot. Bottom-left is elite; top-left (few but dangerous) is the Carolina profile.'},
  off:{xi:C.cf,yi:C.xgpsF,fx:0,fy:3,xl:'Shots taken / game  →  more volume',yl:'xG per shot  →  higher quality',
    q:{tl:'SNIPERS',tr:'ENGINE',bl:'QUIET',br:'VOLUME SHOOTERS'},col:'--accent',
    note:'Offensive identity. Right = more shots; up = higher danger each. Top-right does both; top-left works for grade-A looks over volume.'},
  rush:{xi:C.rushF,yi:C.rushA,fx:1,fy:1,xl:'Rush shots for %  →  more transition offense',yl:'Rush shots allowed %  →  give up more rush',
    q:{tl:'BLEED RUSH',tr:'TRACK MEET',bl:'GRIND IT',br:'RUSH KINGS'},col:'--rush',
    note:'Rush vs. cycle. Right = more of your own offense off the rush; down = you suppress opponents’ rush chances. Bottom-right (rush a lot, allow little) is the ideal transition identity.'}
};

function drawMap(){
  const M=MODES[st.mode];
  pts=bySeason[st.season].filter(r=>r[M.xi]!=null&&r[M.yi]!=null).map(r=>({r,x:r[M.xi],y:r[M.yi]}));
  const path=st.focus?careerPath(st.focus,M):null;
  const W=Math.max(360,cv.parentElement.clientWidth-16),H=Math.max(430,Math.min(580,innerHeight*.62)),dpr=devicePixelRatio||1;
  cv.width=W*dpr;cv.height=H*dpr;cv.style.height=H+'px';ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,W,H);
  const P={l:64,r:18,t:22,b:52};
  const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);
  // domain includes the focused coach's whole career so the path never clips
  const allx=xs.concat(path?path.map(p=>p.x):[]),ally=ys.concat(path?path.map(p=>p.y):[]);
  const xmin=Math.min(...allx),xmax=Math.max(...allx),ymin=Math.min(...ally),ymax=Math.max(...ally);
  const padx=(xmax-xmin)*.08||1,pady=(ymax-ymin)*.08||.01;
  const x0=xmin-padx,x1=xmax+padx,y0=ymin-pady,y1=ymax+pady;
  const X=v=>P.l+(v-x0)/(x1-x0)*(W-P.l-P.r),Y=v=>H-P.b-(v-y0)/(y1-y0)*(H-P.t-P.b);
  geom={X,Y,W,H};const mx=median(xs),my=median(ys);
  ctx.strokeStyle=css('--line');ctx.fillStyle=css('--ink-3');ctx.font='11px system-ui';ctx.lineWidth=1;ctx.textAlign='center';
  for(let i=0;i<=4;i++){const vx=x0+(x1-x0)*i/4;ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(X(vx),P.t);ctx.lineTo(X(vx),H-P.b);ctx.stroke();
    ctx.globalAlpha=1;ctx.fillText(vx.toFixed(M.fx),X(vx),H-P.b+15);}
  ctx.textAlign='right';
  for(let i=0;i<=4;i++){const vy=y0+(y1-y0)*i/4;ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(P.l,Y(vy));ctx.lineTo(W-P.r,Y(vy));ctx.stroke();
    ctx.globalAlpha=1;ctx.fillText(vy.toFixed(M.fy),P.l-7,Y(vy)+4);}
  ctx.save();ctx.setLineDash([5,4]);ctx.strokeStyle=css('--ink-3');ctx.lineWidth=1.3;
  ctx.beginPath();ctx.moveTo(X(mx),P.t);ctx.lineTo(X(mx),H-P.b);ctx.stroke();
  ctx.beginPath();ctx.moveTo(P.l,Y(my));ctx.lineTo(W-P.r,Y(my));ctx.stroke();ctx.restore();
  ctx.fillStyle=css('--ink-3');ctx.font='700 11px system-ui';ctx.globalAlpha=.8;
  ctx.textAlign='left';ctx.fillText(M.q.tl,P.l+8,P.t+14);ctx.fillText(M.q.bl,P.l+8,H-P.b-9);
  ctx.textAlign='right';ctx.fillText(M.q.tr,W-P.r-8,P.t+14);ctx.fillText(M.q.br,W-P.r-8,H-P.b-9);ctx.globalAlpha=1;
  const q=st.find.trim().toLowerCase();
  pts.forEach(p=>{p.px=X(p.x);p.py=Y(p.y);
    const hit=q&&p.r[C.coach].toLowerCase().includes(q);
    ctx.globalAlpha=(st.focus||q)?(hit?.95:.14):.82;
    ctx.fillStyle=hit?css('--ink'):css(M.col);
    ctx.beginPath();ctx.arc(p.px,p.py,hit?6:5,0,7);ctx.fill();});
  ctx.globalAlpha=1;
  if(path){  // career trajectory of the focused coach
    ctx.strokeStyle=css(M.col);ctx.lineWidth=2.2;ctx.globalAlpha=.9;ctx.beginPath();
    path.forEach((p,i)=>{const px=X(p.x),py=Y(p.y);i?ctx.lineTo(px,py):ctx.moveTo(px,py);});ctx.stroke();
    ctx.globalAlpha=1;ctx.font='700 10.5px system-ui';ctx.textAlign='center';
    path.forEach((p,i)=>{const px=X(p.x),py=Y(p.y),last=i===path.length-1;
      ctx.fillStyle=css(M.col);ctx.strokeStyle=css('--panel');ctx.lineWidth=2;
      ctx.beginPath();ctx.arc(px,py,last?6:4,0,7);ctx.fill();ctx.stroke();
      ctx.fillStyle=css('--ink-2');ctx.fillText("'"+p.season.slice(2,4),px,py-9);});
  } else {  // label the four extremes when not focused
    const lab=new Set();const pick=(f)=>pts.reduce((a,b)=>f(a,b)?a:b);
    [pick((a,b)=>a.x<b.x),pick((a,b)=>a.x>b.x),pick((a,b)=>a.y<b.y),pick((a,b)=>a.y>b.y)].forEach(p=>lab.add(p));
    ctx.font='700 11.5px system-ui';
    lab.forEach(p=>{if(q&&!p.r[C.coach].toLowerCase().includes(q))return;
      ctx.globalAlpha=1;ctx.strokeStyle=css('--panel');ctx.lineWidth=2;ctx.beginPath();ctx.arc(p.px,p.py,5.5,0,7);ctx.fillStyle=css(M.col);ctx.fill();ctx.stroke();
      ctx.fillStyle=css('--ink');ctx.textAlign=p.px>W-150?'right':'left';
      ctx.fillText(p.r[C.coach].split(' ').slice(-1)[0]+' ('+p.r[C.team]+')',p.px+(p.px>W-150?-9:9),p.py+4);});
  }
  ctx.fillStyle=css('--ink-2');ctx.font='600 12px system-ui';ctx.textAlign='center';ctx.fillText(M.xl,(P.l+W-P.r)/2,H-8);
  ctx.save();ctx.translate(14,(P.t+H-P.b)/2);ctx.rotate(-Math.PI/2);ctx.fillText(M.yl,0,0);ctx.restore();
  document.getElementById('clr').style.display=st.focus?'inline-block':'none';
  document.getElementById('mapCap').innerHTML=st.focus
    ? '<b>'+st.focus+'</b> — career path across '+(path?path.length:0)+' seasons in this view (labelled by year). Click the dot again or ✕ to clear.'
    : '';
  document.getElementById('mapNote').textContent=M.note+' Dashed lines mark the season median. Hover for the fingerprint; click any dot to trace that coach’s career.';
}
cv.addEventListener('mousemove',e=>{if(!geom||st.view!=='map')return;
  const rc=cv.getBoundingClientRect(),mx=(e.clientX-rc.left)*geom.W/rc.width,my=(e.clientY-rc.top)*geom.H/rc.height;
  let best=null,bd=210;pts.forEach(p=>{const dx=p.px-mx,dy=p.py-my,d=dx*dx+dy*dy;if(d<bd){bd=d;best=p;}});
  if(best){const r=best.r,rf=r[C.rushF]==null?'—':r[C.rushF].toFixed(1),ra=r[C.rushA]==null?'—':r[C.rushA].toFixed(1);
    tip.innerHTML='<div class="nm">'+r[C.coach]+' · '+r[C.team]+' · '+r[C.gp]+'GP</div><div class="rowg">'+
      '<span>Shots for/gm</span><b>'+r[C.cf].toFixed(1)+'</b>'+
      '<span>xG per shot</span><b>'+r[C.xgpsF].toFixed(3)+'</b>'+
      '<span>Rush for %</span><b>'+rf+'</b>'+
      '<span>Net-front tip%</span><b>'+r[C.tip].toFixed(1)+'</b>'+
      '<span>Shots agst/gm</span><b>'+r[C.ca].toFixed(1)+'</b>'+
      '<span>xG/shot agst</span><b>'+r[C.xgpsA].toFixed(3)+'</b>'+
      '<span>Rush agst %</span><b>'+ra+'</b>'+
      '<span>Block %</span><b>'+r[C.block].toFixed(1)+'</b>'+
      '<span>GSAx</span><b>'+r[C.gsax].toFixed(1)+'</b></div>';
    tip.style.opacity=1;tip.style.left=Math.min(e.clientX+14,innerWidth-280)+'px';tip.style.top=(e.clientY-10)+'px';}
  else tip.style.opacity=0;});
cv.addEventListener('mouseleave',()=>tip.style.opacity=0);
cv.addEventListener('click',e=>{if(!geom||st.view!=='map')return;
  const rc=cv.getBoundingClientRect(),mx=(e.clientX-rc.left)*geom.W/rc.width,my=(e.clientY-rc.top)*geom.H/rc.height;
  let best=null,bd=260;pts.forEach(p=>{const dx=p.px-mx,dy=p.py-my,d=dx*dx+dy*dy;if(d<bd){bd=d;best=p;}});
  if(best){const c=best.r[C.coach];st.focus=(st.focus===c)?null:c;drawMap();}});

// ---- style over time (rush consistency) ----
function drawTime(){
  // gp-weighted rush_for per (coach,season), then per-coach spread
  const cs={};
  F.forEach(r=>{if(r[C.rushF]==null)return;const k=r[C.coach];(cs[k]=cs[k]||{}); const s=r[C.season];
    if(!cs[k][s])cs[k][s]={w:0,v:0}; cs[k][s].w+=r[C.gp]; cs[k][s].v+=r[C.rushF]*r[C.gp];});
  const coaches=[];
  for(const c in cs){const yrs=Object.keys(cs[c]).sort();if(yrs.length<3)continue;
    const vals=yrs.map(y=>cs[c][y].v/cs[c][y].w);
    const mn=Math.min(...vals),mx=Math.max(...vals),avg=vals.reduce((a,b)=>a+b,0)/vals.length;
    coaches.push({c,n:yrs.length,vals,mn,mx,avg,range:mx-mn});}
  coaches.sort((a,b)=>b.range-a.range);
  const lo=Math.min(...coaches.map(c=>c.mn))-.3,hi=Math.max(...coaches.map(c=>c.mx))+.3;
  const pos=v=>(v-lo)/(hi-lo)*100;
  document.getElementById('timeAx').innerHTML='<span>'+lo.toFixed(1)+'% rush</span><span>'+((lo+hi)/2).toFixed(1)+'%</span><span>'+hi.toFixed(1)+'%</span>';
  const el=document.getElementById('timeBoard');el.innerHTML='';
  const wide=coaches[Math.floor(coaches.length*0.33)].range; // threshold hue
  coaches.forEach(o=>{
    const col=o.range>=wide?'--rush':'--accent';
    const div=document.createElement('div');div.className='cst';
    let sdots=o.vals.map(v=>'<div class="sdot" style="left:calc('+pos(v)+'% - 3px);background:var('+col+')"></div>').join('');
    div.innerHTML=
      '<div class="nm">'+o.c+'<div class="sub2">'+o.n+' seasons</div></div>'+
      '<div class="rtrack">'+
        '<div class="rline" style="left:'+pos(o.mn)+'%;width:'+(pos(o.mx)-pos(o.mn))+'%;background:var('+col+');opacity:.4"></div>'+
        sdots+
        '<div class="rdot" style="left:calc('+pos(o.avg)+'% - 5px);background:var('+col+')"></div>'+
      '</div>'+
      '<div class="rv">avg <b>'+o.avg.toFixed(1)+'%</b> · ±'+o.range.toFixed(1)+'</div>';
    el.appendChild(div);
  });
}

// ---- turnarounds ----
function drawBoard(){
  const key=st.metric==='xg'?'d_xgf_pct':st.metric==='gd'?'d_goal_diff':'d_win_pct';
  const ob=st.metric==='xg'?'out_xgf_pct':st.metric==='gd'?'out_goal_diff':'out_win_pct';
  const ib=st.metric==='xg'?'in_xgf_pct':st.metric==='gd'?'in_goal_diff':'in_win_pct';
  const rows=[...CH].sort((a,b)=>b[key]-a[key]);
  const mxAbs=Math.max(...rows.map(r=>Math.abs(r[key])))*1.05,unit=st.metric==='gd'?'':'%';
  const el=document.getElementById('board');el.innerHTML='';
  rows.forEach(r=>{const d=r[key],frac=Math.abs(d)/mxAbs*50,pos=d>=0;
    const div=document.createElement('div');div.className='chg';
    div.innerHTML='<div class="who"><b>'+r.out_coach.split(' ').slice(-1)[0]+'</b> <span class="arw">→</span> <b>'+r.in_coach.split(' ').slice(-1)[0]+'</b>'+
      '<div class="meta">'+r.team+' · '+String(r.season).slice(0,4)+'-'+String(r.season).slice(6)+' · '+
      (+r[ob]).toFixed(st.metric==='gd'?2:1)+unit+' → '+(+r[ib]).toFixed(st.metric==='gd'?2:1)+unit+'</div></div>'+
      '<div class="track"><div class="mid"></div><div class="fill" style="'+(pos?('left:50%;width:'+frac+'%'):('right:50%;width:'+frac+'%'))+
      ';background:'+(pos?'var(--pos)':'var(--neg)')+'"></div></div>'+
      '<div class="val" style="color:'+(pos?'var(--pos)':'var(--neg)')+'">'+(pos?'+':'')+d.toFixed(st.metric==='gd'?2:1)+unit+'</div>';
    el.appendChild(div);});
}

function render(){
  document.getElementById('mapView').style.display=st.view==='map'?'block':'none';
  document.getElementById('timeView').style.display=st.view==='time'?'block':'none';
  document.getElementById('boardView').style.display=st.view==='board'?'block':'none';
  document.getElementById('modeSeg').style.display=st.view==='map'?'inline-flex':'none';
  document.getElementById('season').style.display=st.view==='map'?'inline-block':'none';
  document.getElementById('find').style.display=st.view==='map'?'inline-block':'none';
  document.getElementById('clr').style.display=(st.view==='map'&&st.focus)?'inline-block':'none';
  if(st.view==='map')drawMap();else if(st.view==='time')drawTime();else drawBoard();
}
const press=(id,on)=>document.getElementById(id).setAttribute('aria-pressed',on);
document.getElementById('find').oninput=e=>{st.find=e.target.value;if(st.view==='map')drawMap();};
document.getElementById('clr').onclick=()=>{st.focus=null;drawMap();};
sel.onchange=()=>{st.season=sel.value;drawMap();};
document.getElementById('vMap').onclick=()=>{st.view='map';press('vMap',1);press('vTime',0);press('vBoard',0);render();};
document.getElementById('vTime').onclick=()=>{st.view='time';press('vTime',1);press('vMap',0);press('vBoard',0);render();};
document.getElementById('vBoard').onclick=()=>{st.view='board';press('vBoard',1);press('vMap',0);press('vTime',0);render();};
document.getElementById('mDef').onclick=()=>{st.mode='def';press('mDef',1);press('mOff',0);press('mRush',0);drawMap();};
document.getElementById('mOff').onclick=()=>{st.mode='off';press('mOff',1);press('mDef',0);press('mRush',0);drawMap();};
document.getElementById('mRush').onclick=()=>{st.mode='rush';press('mRush',1);press('mDef',0);press('mOff',0);drawMap();};
document.getElementById('bXg').onclick=()=>{st.metric='xg';press('bXg',1);press('bGd',0);press('bWin',0);drawBoard();};
document.getElementById('bGd').onclick=()=>{st.metric='gd';press('bGd',1);press('bXg',0);press('bWin',0);drawBoard();};
document.getElementById('bWin').onclick=()=>{st.metric='win';press('bWin',1);press('bXg',0);press('bGd',0);drawBoard();};
new MutationObserver(()=>render()).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',()=>render());
addEventListener('resize',()=>{if(st.view==='map')drawMap();});
render();
</script>'''

html = html.replace('__FLAT__', FLAT_JS).replace('__CHANGE__', CHANGE_JS)
from _fetch import write_page
write_page(OUT, html)
print(f"wrote {OUT}: {len(html)} bytes")
