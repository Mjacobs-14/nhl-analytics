import json, sys
from collections import defaultdict
from _fetch import load, write_page

# SQL lives in queries.py (CLUTCH -> player_clutch_v).
rows, OUT = load('clutch')

# ---------------------------------------------------------------- compaction
# The page stores one delimited record per player-season to keep the file small:
#   idx . season . teamIdx . gp . tied.up1.up2.up3.down1.down2.down3 . lc . glc . ot
# decoded by parse() in the page: st = fields 4..10, lc/glc/ot = 11/12/13.
# One DICT entry per player_id. NOTE: the original snapshot keyed DICT by NAME,
# which silently merged distinct players sharing an abbreviated name — Jamie Benn
# ('L') and Jordie Benn ('D') both became a single "J. Benn", as did the two
# Elias Petterssons, C. Smith and J. Larsson. Keying by player_id fixes that
# (1051 name-keyed entries -> 1056 real players), so a rebuild intentionally
# does NOT reproduce the old page byte-for-byte.
_info = {}
for r in rows:
    _info.setdefault(r['player_id'], (r['full_name'], r['position']))
_order = sorted(_info, key=lambda pid: (_info[pid][0], pid))
didx   = {pid: i for i, pid in enumerate(_order)}
names  = [f"{_info[pid][0]}|{_info[pid][1]}" for pid in _order]
KEY = lambda r: r['player_id']
teams = sorted({r['primary_team'] for r in rows if r['primary_team']})
tidx  = {t: i for i, t in enumerate(teams)}

ST = ['pts_tied','pts_up1','pts_up2','pts_up3p','pts_down1','pts_down2','pts_down3p']

by_season = defaultdict(list)
for r in rows:
    by_season[str(r['season'])].append(r)

RAW, LG = {}, {}
for season in sorted(by_season):
    rs = sorted(by_season[season], key=lambda r: didx[KEY(r)])
    recs = []
    for r in rs:
        a = [didx[KEY(r)], int(r['season']), tidx.get(r['primary_team'], -1), r['gp']]
        a += [r[k] for k in ST]
        a += [r['pts_late_close'], r['goals_late_close'], r['pts_ot']]
        recs.append('.'.join(str(int(x)) for x in a))
    RAW[season] = ';'.join(recs)

    # league shares for the season: [t,u1,u2,u3,d1,d2,d3, close, late]
    tot = sum(r['pts'] for r in rs) or 1
    LG[season] = [round(100.0*sum(r[k] for r in rs)/tot, 1) for k in ST] + [
        round(100.0*sum(r['pts_close'] for r in rs)/tot, 1),
        round(100.0*sum(r['pts_late_close'] for r in rs)/tot, 1)]

assert len(LG) == 8, sorted(LG)
assert all(len(v) == 9 for v in LG.values())
assert 90 < sum(LG[max(LG)][:7]) < 110, LG[max(LG)]
print(f"OK: {len(rows)} player-seasons, {len(names)} players, {len(teams)} teams, {len(RAW)} seasons")

DICT_S  = ';'.join(names)
TEAMS_S = ';'.join(teams)
# RAW values are backtick-quoted in the page, so it is assembled by hand.
RAW_JS  = '{' + ','.join(f'"{k}":`{v}`' for k, v in RAW.items()) + '}'
LG_JS   = json.dumps(LG, separators=(',', ':'))

html = r'''<meta charset="utf-8">
<title>Clutch or Cushion? — NHL Game-State Scoring</title>
<style>
:root{--paper:#fbfaf8;--ink:#191817;--ink-2:#5d5a55;--ink-3:#9b968e;--line:#e7e3dc;--card:#fff;
  --f:#2a78d6;--d:#1baf7a;--hot:#e34948;--chipbg:#f2efe9;}
@media (prefers-color-scheme:dark){:root{--paper:#181716;--ink:#f2f0ec;--ink-2:#aaa69e;--ink-3:#6f6b64;
  --line:#343230;--card:#211f1e;--f:#3987e5;--d:#199e70;--hot:#e66767;--chipbg:#2b2927;}}
:root[data-theme=dark]{--paper:#181716;--ink:#f2f0ec;--ink-2:#aaa69e;--ink-3:#6f6b64;--line:#343230;--card:#211f1e;--f:#3987e5;--d:#199e70;--hot:#e66767;--chipbg:#2b2927;}
:root[data-theme=light]{--paper:#fbfaf8;--ink:#191817;--ink-2:#5d5a55;--ink-3:#9b968e;--line:#e7e3dc;--card:#fff;--f:#2a78d6;--d:#1baf7a;--hot:#e34948;--chipbg:#f2efe9;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 "Segoe UI",system-ui,sans-serif;
  font-variant-numeric:tabular-nums;padding:26px clamp(14px,4vw,44px) 42px;}
h1{font-size:clamp(20px,3vw,27px);letter-spacing:-.02em;margin:0 0 2px;font-weight:750;}
.sub{color:var(--ink-2);margin:0 0 18px;max-width:74ch;}
.bar{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:14px;}
select,input[type=search]{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:7px 10px;font:inherit;}
input[type=search]{width:190px}
.chip{border:1px solid var(--line);background:var(--chipbg);color:var(--ink-2);border-radius:999px;padding:6px 13px;font:600 13px/1 inherit;cursor:pointer;display:inline-flex;gap:7px;align-items:center;}
.chip .sw{width:10px;height:10px;border-radius:50%;}
.chip[aria-pressed=true]{color:var(--ink);border-color:var(--ink-3);}
.chip:focus-visible,select:focus-visible,input:focus-visible{outline:2px solid var(--f);outline-offset:2px;}
.wrap{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 6px 4px;}
#cv{width:100%;display:block;cursor:crosshair;}
.note{color:var(--ink-3);font-size:12.5px;margin-top:12px;max-width:84ch;}
#tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 11px;font-size:13px;box-shadow:0 4px 14px rgba(0,0,0,.15);opacity:0;z-index:9;}
#tip .nm{font-weight:700;}#tip .q{color:var(--ink-2);font-size:12px;}
/* fingerprint card */
#fp{display:none;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-top:14px;}
#fp h3{margin:0 0 2px;font-size:16px;}
#fp .meta{color:var(--ink-2);font-size:12.5px;margin-bottom:12px;}
#fp .meta b{color:var(--ink);}
.st{display:grid;grid-template-columns:64px 1fr 92px;gap:10px;align-items:center;margin:4px 0;font-size:12.5px;}
.st .lb{color:var(--ink-2);text-align:right;font-weight:600;}
.st .tr{position:relative;height:16px;background:var(--chipbg);border-radius:4px;overflow:visible;}
.st .fill{position:absolute;left:0;top:0;bottom:0;border-radius:4px;}
.st .lg{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink-3);}
.st .vv{color:var(--ink-2);}
.st .vv b{color:var(--ink);}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:6px;}
th,td{padding:6px 10px;text-align:right;border-bottom:1px solid var(--line);}
th{color:var(--ink-2);font-weight:600;white-space:nowrap;cursor:pointer;user-select:none;}
th:first-child,td:first-child{text-align:left;}
th:nth-child(2),td:nth-child(2),th:nth-child(3),td:nth-child(3){text-align:center;}
#tblwrap{display:none;max-height:540px;overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--card);padding:0 8px 8px;}
</style>
<h1>Clutch or Cushion?</h1>
<p class="sub">Where a player&rsquo;s points come from: tied games and one-goal nail-biters, or blowouts that were already
decided. League-wide, ~69% of points come in close situations &mdash; the interesting players are the ones who deviate.
Regular season, min 30 points for the map.</p>
<div class="bar">
  <select id="season" aria-label="Season"></select>
  <select id="team" aria-label="Team"></select>
  <button class="chip" id="cF" aria-pressed="true"><span class="sw" style="background:var(--f)"></span>Forwards</button>
  <button class="chip" id="cD" aria-pressed="true"><span class="sw" style="background:var(--d)"></span>Defense</button>
  <input type="search" id="find" placeholder="Any player, any year…" aria-label="Find a player">
  <button class="chip" id="tbl" aria-pressed="false">Table view</button>
</div>
<div class="wrap" id="cvwrap"><canvas id="cv"></canvas></div>
<div id="tblwrap"><table id="t"><thead></thead><tbody></tbody></table></div>
<div id="fp"></div>
<p class="note">X-axis: share of points in close situations (tied or &plusmn;1) minus the league&rsquo;s share that season &mdash;
right of the line means clutch-tilted, left means the production came when games weren&rsquo;t close. Y-axis: points per game.
&ldquo;Late &amp; close&rdquo; = 3rd period or OT, tied or within one. Click or search any player &mdash; including
retired ones &mdash; for their full game-state fingerprint.</p>
<div id="tip" role="status"></div>
<script>
const DICT=`__DICT__`.split(';').map(s=>{const i=s.lastIndexOf('|');return{n:s.slice(0,i),p:s.slice(i+1)};});
const TEAMS=`__TEAMS__`.split(';');
const RAW=__RAW__;
const LG=__LG__; // [t,u1,u2,u3,d1,d2,d3, close, late]
const ST_LB=['Tied','Up 1','Up 2','Up 3+','Down 1','Down 2','Down 3+'];
const isF=p=>p!=='D';
const SEASONS=Object.keys(RAW).sort().reverse();
const parse=k=>RAW[k].split(';').map(r=>{const a=r.split('.').map(Number);const d=DICT[a[0]];
  const st=a.slice(4,11),pts=st.reduce((x,y)=>x+y,0);
  return{i:a[0],n:d.n,p:d.p,season:k,team:a[2]>=0?TEAMS[a[2]]:'',gp:a[3],st,pts,lc:a[11],glc:a[12],ot:a[13]};});
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const sel=document.getElementById('season'),teamSel=document.getElementById('team');
{const o=document.createElement('option');o.value='ALL';o.textContent='All seasons';sel.appendChild(o);}
SEASONS.forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k.slice(0,4)+'–'+k.slice(6);sel.appendChild(o);});
sel.value=SEASONS[0];
{const o=document.createElement('option');o.value='';o.textContent='All NHL';teamSel.appendChild(o);
 TEAMS.forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;teamSel.appendChild(o);});}
let state={season:SEASONS[0],team:'',F:true,D:true,find:'',table:false,focus:null};
function leagueShare(){if(state.season!=='ALL')return LG[state.season];
  const n=SEASONS.length,s=Array(9).fill(0);SEASONS.forEach(k=>LG[k].forEach((v,i)=>s[i]+=v/n));return s;}
function pool(){ // player rows for current season selection, aggregated if ALL
  if(state.season!=='ALL')return parse(state.season);
  const m=new Map();
  SEASONS.forEach(k=>parse(k).forEach(r=>{const e=m.get(r.i);
    if(!e){m.set(r.i,{...r,st:[...r.st],season:'ALL'});}
    else{e.gp+=r.gp;e.pts+=r.pts;e.lc+=r.lc;e.glc+=r.glc;e.ot+=r.ot;r.st.forEach((v,j)=>e.st[j]+=v);e.team=r.team||e.team;}}));
  return[...m.values()];}
const median=a=>{const b=[...a].sort((x,y)=>x-y),m=b.length>>1;return b.length%2?b[m]:(b[m-1]+b[m])/2;};
const cv=document.getElementById('cv'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
let pts=[],geom=null;
const closeShare=r=>100*(r.st[0]+r.st[1]+r.st[4])/r.pts;
function load(){const lg=leagueShare();
  pts=pool().filter(r=>r.pts>=30&&r.gp>0&&(isF(r.p)?state.F:state.D)&&(!state.team||r.team===state.team))
    .map(r=>({...r,x:closeShare(r)-lg[7],y:r.pts/r.gp}));
  render();fp();}
function render(){
  const W=Math.max(360,cv.parentElement.clientWidth-14),H=Math.max(430,Math.min(570,innerHeight*.6)),dpr=devicePixelRatio||1;
  cv.width=W*dpr;cv.height=H*dpr;cv.style.height=H+'px';ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,W,H);
  const P={l:56,r:16,t:24,b:46};
  if(!pts.length){geom=null;return;}
  const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);
  const xr=Math.max(12,Math.max(...xs.map(Math.abs))*1.08);
  const y1=Math.max(.8,Math.max(...ys))*1.06;
  const X=v=>P.l+((v+xr)/(2*xr))*(W-P.l-P.r),Y=v=>H-P.b-(v/y1)*(H-P.t-P.b);
  geom={X,Y,W,H};
  const my=median(ys);
  ctx.strokeStyle=css('--line');ctx.lineWidth=1;ctx.fillStyle=css('--ink-3');ctx.font='11.5px system-ui';ctx.textAlign='center';
  for(let x=Math.ceil(-xr/5)*5;x<=xr;x+=5){ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(X(x),P.t);ctx.lineTo(X(x),H-P.b);ctx.stroke();
    ctx.globalAlpha=1;ctx.fillText((x>0?'+':'')+x,X(x),H-P.b+16);}
  ctx.textAlign='right';
  for(let y=0;y<=y1;y+=.25){ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(P.l,Y(y));ctx.lineTo(W-P.r,Y(y));ctx.stroke();
    ctx.globalAlpha=1;ctx.fillText(y.toFixed(2),P.l-7,Y(y)+4);}
  ctx.save();ctx.setLineDash([5,4]);ctx.strokeStyle=css('--ink-3');ctx.lineWidth=1.4;
  ctx.beginPath();ctx.moveTo(X(0),P.t);ctx.lineTo(X(0),H-P.b);ctx.stroke();
  ctx.beginPath();ctx.moveTo(P.l,Y(my));ctx.lineTo(W-P.r,Y(my));ctx.stroke();ctx.restore();
  ctx.fillStyle=css('--ink-3');ctx.font='600 11px system-ui';ctx.textAlign='left';
  ctx.fillText('league tilt',X(0)+6,P.t+11);
  ctx.font='700 12px system-ui';ctx.globalAlpha=.7;
  ctx.textAlign='right';ctx.fillText('CLUTCH STARS',W-P.r-10,P.t+26);ctx.fillText('COLD-BLOODED ROLE PLAYERS',W-P.r-10,H-P.b-12);
  ctx.textAlign='left';ctx.fillText('FRONT-RUNNERS',P.l+10,P.t+26);ctx.fillText('GARBAGE-TIME HEROES',P.l+10,H-P.b-12);
  ctx.globalAlpha=1;
  pts.forEach(d=>{d.px=X(d.x);d.py=Y(d.y);
    ctx.globalAlpha=state.focus!=null?(d.i===state.focus?1:.12):.8;
    ctx.fillStyle=isF(d.p)?css('--f'):css('--d');
    ctx.beginPath();ctx.arc(d.px,d.py,d.i===state.focus?6.5:4.5,0,7);ctx.fill();
    if(d.i===state.focus){ctx.strokeStyle=css('--card');ctx.lineWidth=2;ctx.stroke();
      ctx.fillStyle=css('--ink');ctx.font='700 12px system-ui';ctx.textAlign='left';ctx.fillText(d.n,d.px+9,d.py+4);}});
  ctx.globalAlpha=1;
  if(state.focus==null){
    const pick=f=>pts.reduce((a,b)=>f(a,b)?a:b);
    const lbl=new Set([pick((a,b)=>a.x>b.x),pick((a,b)=>a.x<b.x),pick((a,b)=>a.y>b.y),
      pick((a,b)=>a.x/12+a.y>b.x/12+b.y)]);
    ctx.font='700 12px system-ui';
    lbl.forEach(d=>{ctx.strokeStyle=css('--card');ctx.lineWidth=2;ctx.beginPath();ctx.arc(d.px,d.py,5.5,0,7);
      ctx.fillStyle=isF(d.p)?css('--f'):css('--d');ctx.fill();ctx.stroke();
      ctx.fillStyle=css('--ink');ctx.textAlign=d.px>W-150?'right':'left';
      ctx.fillText(d.n,d.px+(d.px>W-150?-9:9),d.py+4);});}
  ctx.fillStyle=css('--ink-2');ctx.font='600 12px system-ui';ctx.textAlign='center';
  ctx.fillText('Clutch tilt — close-game share vs league (percentage points)',(P.l+W-P.r)/2,H-10);
  ctx.save();ctx.translate(13,(P.t+H-P.b)/2);ctx.rotate(-Math.PI/2);ctx.fillText('Points per game',0,0);ctx.restore();}
function fp(){const el=document.getElementById('fp');
  if(state.focus==null){el.style.display='none';return;}
  // fingerprint from current selection if present, else across all seasons
  let rows=pool().filter(r=>r.i===state.focus);
  let scope=state.season==='ALL'?'all seasons':state.season.slice(0,4)+'–'+state.season.slice(6);
  if(!rows.length){const m=new Map();
    SEASONS.forEach(k=>parse(k).forEach(r=>{if(r.i!==state.focus)return;const e=m.get(r.i);
      if(!e)m.set(r.i,{...r,st:[...r.st]});
      else{e.gp+=r.gp;e.pts+=r.pts;e.lc+=r.lc;e.glc+=r.glc;e.ot+=r.ot;r.st.forEach((v,j)=>e.st[j]+=v);}}));
    rows=[...m.values()];scope='career (not in current filter)';}
  if(!rows.length){el.style.display='none';return;}
  const r=rows[0],lg=leagueShare(),d=DICT[state.focus];
  const tilt=closeShare(r)-lg[7];
  const mx=Math.max(...r.st.map(v=>100*v/r.pts),...lg.slice(0,7))*1.15;
  el.style.display='block';
  el.innerHTML='<h3>'+d.n+' <span style="color:var(--ink-2);font-weight:400">· '+d.p+(r.team?' · '+r.team:'')+' · '+scope+'</span></h3>'+
    '<div class="meta"><b>'+r.pts+'</b> pts in '+r.gp+' GP · clutch tilt <b>'+(tilt>0?'+':'')+tilt.toFixed(1)+'pp</b>'+
    ' · late &amp; close <b>'+r.lc+'</b> pts ('+r.glc+' G) · OT <b>'+r.ot+'</b></div>'+
    ST_LB.map((lb,j)=>{const pv=100*r.st[j]/r.pts;
      return '<div class="st"><div class="lb">'+lb+'</div><div class="tr">'+
      '<div class="fill" style="width:'+(pv/mx*100)+'%;background:'+(j===0||j===1||j===4?'var(--hot)':'var(--ink-3)')+';opacity:.85"></div>'+
      '<div class="lg" style="left:'+(lg[j]/mx*100)+'%"></div></div>'+
      '<div class="vv"><b>'+pv.toFixed(1)+'%</b> <span style="color:var(--ink-3)">lg '+lg[j].toFixed(1)+'%</span></div></div>';}).join('')+
    '<div class="note" style="margin-top:8px">Red bars = close situations; grey tick = league share. Bars right of their tick mean the player over-indexes there.</div>';}
cv.addEventListener('mousemove',e=>{if(!geom||state.table)return;
  const r=cv.getBoundingClientRect(),mx=(e.clientX-r.left)*geom.W/r.width,my=(e.clientY-r.top)*geom.H/r.height;
  let best=null,bd=196;pts.forEach(d=>{const dx=d.px-mx,dy=d.py-my,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;best=d;}});
  if(best){tip.innerHTML='<div class="nm">'+best.n+' · '+best.p+(best.team?' · '+best.team:'')+'</div>'+
    best.pts+' pts · tilt '+(best.x>0?'+':'')+best.x.toFixed(1)+'pp · late&close '+best.lc+
    '<div class="q">click for full fingerprint</div>';
    tip.style.opacity=1;tip.style.left=Math.min(e.clientX+14,innerWidth-210)+'px';tip.style.top=(e.clientY-14)+'px';}
  else tip.style.opacity=0;});
cv.addEventListener('mouseleave',()=>{tip.style.opacity=0;});
cv.addEventListener('click',e=>{if(!geom||state.table)return;
  const r=cv.getBoundingClientRect(),mx=(e.clientX-r.left)*geom.W/r.width,my=(e.clientY-r.top)*geom.H/r.height;
  let best=null,bd=260;pts.forEach(d=>{const dx=d.px-mx,dy=d.py-my,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;best=d;}});
  state.focus=best?((state.focus===best.i)?null:best.i):null;
  if(state.focus==null){document.getElementById('find').value='';state.find='';}
  render();fp();});
function tbl(){const lg=leagueShare(),q=state.find.trim().toLowerCase();
  const rows=pts.filter(d=>!q||d.n.toLowerCase().includes(q)).sort((a,b)=>b.lc-a.lc);
  document.querySelector('#t thead').innerHTML='<tr><th>Player</th><th>Pos</th><th>Team</th><th>Pts</th><th>Tilt pp</th><th>Late&amp;close</th><th>LC goals</th><th>OT</th></tr>';
  document.querySelector('#t tbody').innerHTML=rows.map(d=>'<tr><td>'+d.n+'</td><td>'+d.p+'</td><td>'+(d.team||'—')+'</td><td>'+d.pts+'</td><td>'+(d.x>0?'+':'')+d.x.toFixed(1)+'</td><td>'+d.lc+'</td><td>'+d.glc+'</td><td>'+d.ot+'</td></tr>').join('');}
document.getElementById('tbl').onclick=e=>{state.table=!state.table;e.currentTarget.setAttribute('aria-pressed',state.table);
  document.getElementById('tblwrap').style.display=state.table?'block':'none';
  document.getElementById('cvwrap').style.display=state.table?'none':'block';
  if(state.table){tbl();}else{render();}};
sel.onchange=()=>{state.season=sel.value;load();if(state.table)tbl();};
teamSel.onchange=()=>{state.team=teamSel.value;load();if(state.table)tbl();};
[['cF','F'],['cD','D']].forEach(pair=>{const b=document.getElementById(pair[0]);
  b.onclick=()=>{state[pair[1]]=!state[pair[1]];b.setAttribute('aria-pressed',state[pair[1]]);load();if(state.table)tbl();}});
document.getElementById('find').oninput=e=>{state.find=e.target.value;const q=state.find.trim().toLowerCase();
  const m=q?DICT.findIndex(d=>d.n.toLowerCase().includes(q)):-1;
  state.focus=m>=0?m:null;render();fp();if(state.table)tbl();};
new MutationObserver(()=>{render();fp();}).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{render();fp();});
addEventListener('resize',()=>{if(!state.table)render();});
load();
</script>'''

html = (html.replace('__DICT__', DICT_S).replace('__TEAMS__', TEAMS_S)
            .replace('__RAW__', RAW_JS).replace('__LG__', LG_JS))
write_page(OUT, html)
