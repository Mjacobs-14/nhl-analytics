import json, sys

from _fetch import load

# SQL lives in queries.py (GOALIE)
rows, OUT = load('goalie')

G = []
for r in rows:
    tl = r['timeline'] or {}
    # per season: list of sv*1000 ints, in date order
    seasons = {s: [int(x) for x in seq.split('.')] for s, seq in tl.items()}
    total_starts = sum(len(v) for v in seasons.values())
    G.append({
        'n': r['full_name'], 'st': r['starts'],
        'sv': round(float(r['career_sv_pct']) * 1000),
        'hr': round(float(r['hot_rate']) * 100, 1),
        'lh': r['longest_hot_streak'], 'lc': r['longest_cold_streak'],
        'ahr': float(r['avg_hot_run']), 'acr': float(r['avg_cold_run']),
        'phh': round(float(r['p_hot_after_hot']) * 100, 1),
        'phc': round(float(r['p_hot_after_cold']) * 100, 1),
        'sk': round(float(r['streakiness']) * 1000),
        'tl': [[s, seasons[s]] for s in sorted(seasons)],
        '_ts': total_starts,
    })

assert 60 < len(G) < 200, len(G)
for g in G:
    assert 850 < g['sv'] < 940, (g['n'], g['sv'])
    # timeline start count should be within a few of reported starts (relief games differ)
    assert abs(g['_ts'] - g['st']) < g['st'] * 0.15 + 5, (g['n'], g['_ts'], g['st'])
    del g['_ts']
    assert '`' not in g['n'] and '${' not in g['n']
print(f"OK: {len(G)} goalies (>=100 starts), "
      f"streakiest {max(G,key=lambda g:g['sk'])['n']} (+{max(g['sk'] for g in G)/1000:.3f})")

G_JS = json.dumps(G, separators=(',', ':'))

html = r'''<meta charset="utf-8">
<title>The Hot Hand — NHL Goalie Streakiness</title>
<style>
:root{--paper:#f7f9fb;--ink:#14181d;--ink-2:#586573;--ink-3:#93a0ad;--line:#e2e8ee;--card:#fff;
  --hot:#e34948;--cold:#2a78d6;--accent:#2a78d6;--chipbg:#eef2f6;}
@media (prefers-color-scheme:dark){:root{--paper:#101317;--ink:#eef1f4;--ink-2:#9aa7b4;--ink-3:#616d79;
  --line:#262d34;--card:#181c21;--hot:#e66767;--cold:#3987e5;--accent:#3987e5;--chipbg:#20262c;}}
:root[data-theme=dark]{--paper:#101317;--ink:#eef1f4;--ink-2:#9aa7b4;--ink-3:#616d79;--line:#262d34;--card:#181c21;--hot:#e66767;--cold:#3987e5;--accent:#3987e5;--chipbg:#20262c;}
:root[data-theme=light]{--paper:#f7f9fb;--ink:#14181d;--ink-2:#586573;--ink-3:#93a0ad;--line:#e2e8ee;--card:#fff;--hot:#e34948;--cold:#2a78d6;--accent:#2a78d6;--chipbg:#eef2f6;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 "Segoe UI",system-ui,sans-serif;
  font-variant-numeric:tabular-nums;padding:26px clamp(14px,4vw,44px) 42px;}
h1{font-size:clamp(20px,3vw,27px);letter-spacing:-.02em;margin:0 0 2px;font-weight:750;}
.sub{color:var(--ink-2);margin:0 0 18px;max-width:74ch;}
.bar{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:14px;}
input[type=search]{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:7px 10px;font:inherit;width:210px;}
.chip{border:1px solid var(--line);background:var(--chipbg);color:var(--ink-2);border-radius:999px;padding:6px 13px;font:600 13px/1 inherit;cursor:pointer;}
.chip[aria-pressed=true]{color:var(--ink);border-color:var(--ink-3);}
.chip:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
.legend{display:inline-flex;gap:14px;align-items:center;color:var(--ink-2);font-size:12.5px;}
.legend .k{display:inline-flex;gap:5px;align-items:center;}.legend .b{width:11px;height:11px;border-radius:3px;}
.wrap{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 6px 4px;}
#cv{width:100%;display:block;cursor:crosshair;}
.note{color:var(--ink-3);font-size:12.5px;margin-top:12px;max-width:84ch;}
#tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 11px;font-size:13px;box-shadow:0 4px 14px rgba(0,0,0,.16);opacity:0;z-index:9;}
#tip .nm{font-weight:700;}#tip .q{color:var(--ink-2);font-size:12px;}
/* detail card */
#fp{display:none;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-top:14px;}
#fp h3{margin:0 0 2px;font-size:17px;}
#fp .tag{display:inline-block;font-size:11.5px;font-weight:700;padding:2px 9px;border-radius:999px;margin-left:8px;vertical-align:middle;}
#fp .meta{color:var(--ink-2);font-size:12.5px;margin:6px 0 14px;}
#fp .meta b{color:var(--ink);}
.tlrow{display:grid;grid-template-columns:58px 1fr;gap:8px;align-items:center;margin:3px 0;}
.tlrow .yr{color:var(--ink-2);font-size:11.5px;text-align:right;font-weight:600;}
.tlrow .cells{display:flex;flex-wrap:wrap;gap:2px;}
.cell{width:12px;height:15px;border-radius:2px;cursor:default;}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin-top:6px;}
th,td{padding:6px 10px;text-align:right;border-bottom:1px solid var(--line);}
th{color:var(--ink-2);font-weight:600;white-space:nowrap;}
th:first-child,td:first-child{text-align:left;}
#tblwrap{display:none;max-height:540px;overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--card);padding:0 8px 8px;}
</style>
<h1>The Hot Hand</h1>
<p class="sub">Which goalies run hot and cold in streaks, and which are metronomes. A start is
&ldquo;hot&rdquo; at .900+ save percentage. <b>Streakiness</b> = how much a hot start predicts another hot one
(above &amp; beyond how good the goalie is). Regular season, 2018&ndash;2026, min 100 starts.</p>
<div class="bar">
  <input type="search" id="find" placeholder="Find a goalie…" aria-label="Find a goalie">
  <button class="chip" id="tbl" aria-pressed="false">Table view</button>
  <span class="legend"><span class="k"><span class="b" style="background:var(--hot)"></span>hot start</span>
    <span class="k"><span class="b" style="background:var(--cold)"></span>cold start</span></span>
</div>
<div class="wrap" id="cvwrap"><canvas id="cv"></canvas></div>
<div id="tblwrap"><table id="t"><thead></thead><tbody></tbody></table></div>
<div id="fp"></div>
<p class="note">X-axis: streakiness (P(hot after hot) &minus; P(hot after cold)). Right of the dashed line = results cluster
(streaky); near zero = start-to-start independent (consistent). Y-axis: career save percentage. Click any goalie for their
full start-by-start hot/cold timeline &mdash; you can see the clusters. Streakiness is the clean signal; raw hot-streak
length and bounce-back rate also reflect how good the goalie is.</p>
<div id="tip" role="status"></div>
<script>
const G=__GOALIES__;
const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
let state={find:'',table:false,focus:null};
const median=a=>{const b=[...a].sort((x,y)=>x-y),m=b.length>>1;return b.length%2?b[m]:(b[m-1]+b[m])/2;};
const cv=document.getElementById('cv'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
let pts=[],geom=null;
const svMed=median(G.map(g=>g.sv));
function render(){
  const W=Math.max(360,cv.parentElement.clientWidth-14),H=Math.max(440,Math.min(580,innerHeight*.62)),dpr=devicePixelRatio||1;
  cv.width=W*dpr;cv.height=H*dpr;cv.style.height=H+'px';ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,W,H);
  const P={l:58,r:16,t:24,b:46};
  const xr=Math.max(0.14,Math.max(...G.map(g=>Math.abs(g.sk/1000)))*1.08);
  const y0=Math.min(...G.map(g=>g.sv))-2,y1=Math.max(...G.map(g=>g.sv))+2;
  const X=v=>P.l+((v+xr)/(2*xr))*(W-P.l-P.r),Y=v=>H-P.b-((v-y0)/(y1-y0))*(H-P.t-P.b);
  geom={X,Y,W,H};
  ctx.strokeStyle=css('--line');ctx.lineWidth=1;ctx.fillStyle=css('--ink-3');ctx.font='11.5px system-ui';ctx.textAlign='center';
  for(let i=0;i<=4;i++){const vx=-xr+2*xr*i/4;ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(X(vx),P.t);ctx.lineTo(X(vx),H-P.b);ctx.stroke();
    ctx.globalAlpha=1;ctx.fillText((vx>0?'+':'')+vx.toFixed(2),X(vx),H-P.b+16);}
  ctx.textAlign='right';
  for(let s=Math.ceil(y0/5)*5;s<=y1;s+=5){ctx.globalAlpha=.5;ctx.beginPath();ctx.moveTo(P.l,Y(s));ctx.lineTo(W-P.r,Y(s));ctx.stroke();
    ctx.globalAlpha=1;ctx.fillText('.'+s,P.l-7,Y(s)+4);}
  ctx.save();ctx.setLineDash([5,4]);ctx.strokeStyle=css('--ink-3');ctx.lineWidth=1.4;
  ctx.beginPath();ctx.moveTo(X(0),P.t);ctx.lineTo(X(0),H-P.b);ctx.stroke();
  ctx.beginPath();ctx.moveTo(P.l,Y(svMed));ctx.lineTo(W-P.r,Y(svMed));ctx.stroke();ctx.restore();
  ctx.fillStyle=css('--ink-3');ctx.font='600 11px system-ui';ctx.textAlign='center';ctx.fillText('independent',X(0),P.t+11);
  ctx.font='700 12px system-ui';ctx.globalAlpha=.7;ctx.textAlign='left';
  ctx.fillText('STEADY ELITE',P.l+10,P.t+26);ctx.fillText('STEADY, BEATABLE',P.l+10,H-P.b-12);
  ctx.textAlign='right';ctx.fillText('STREAKY STARS',W-P.r-10,P.t+26);ctx.fillText('ROLLERCOASTER',W-P.r-10,H-P.b-12);ctx.globalAlpha=1;
  const q=state.find.trim().toLowerCase();
  pts=G.map(g=>({g,px:X(g.sk/1000),py:Y(g.sv)}));
  pts.forEach(p=>{const foc=state.focus===p.g.n,hit=q&&p.g.n.toLowerCase().includes(q);
    ctx.globalAlpha=(state.focus||q)?((foc||hit)?1:.12):.82;
    ctx.fillStyle=p.g.sk>=0?css('--hot'):css('--cold');
    ctx.beginPath();ctx.arc(p.px,p.py,(foc||hit)?7:4.6,0,7);ctx.fill();
    if(foc||hit){ctx.strokeStyle=css('--card');ctx.lineWidth=2;ctx.stroke();
      ctx.fillStyle=css('--ink');ctx.font='700 12px system-ui';ctx.textAlign='left';ctx.fillText(p.g.n,p.px+9,p.py+4);}});
  ctx.globalAlpha=1;
  if(state.focus==null&&!q){const pick=f=>pts.reduce((a,b)=>f(a,b)?a:b);
    const lab=new Set([pick((a,b)=>a.g.sk>b.g.sk),pick((a,b)=>a.g.sk<b.g.sk),pick((a,b)=>a.g.sv>b.g.sv),pick((a,b)=>a.g.lc>b.g.lc)]);
    ctx.font='700 12px system-ui';
    lab.forEach(p=>{ctx.strokeStyle=css('--card');ctx.lineWidth=2;ctx.beginPath();ctx.arc(p.px,p.py,5.6,0,7);
      ctx.fillStyle=p.g.sk>=0?css('--hot'):css('--cold');ctx.fill();ctx.stroke();
      ctx.fillStyle=css('--ink');ctx.textAlign=p.px>W-150?'right':'left';ctx.fillText(p.g.n,p.px+(p.px>W-150?-9:9),p.py+4);});}
  ctx.fillStyle=css('--ink-2');ctx.font='600 12px system-ui';ctx.textAlign='center';
  ctx.fillText('Streakiness  —  hot-after-hot minus hot-after-cold',(P.l+W-P.r)/2,H-10);
  ctx.save();ctx.translate(13,(P.t+H-P.b)/2);ctx.rotate(-Math.PI/2);ctx.fillText('Career save %',0,0);ctx.restore();}
function label(g){const sk=g.sk/1000;
  if(sk>=0.09)return['STREAKY','var(--hot)'];if(sk<=-0.06)return['BOUNCE-BACK','var(--cold)'];
  if(Math.abs(sk)<=0.02)return['METRONOME','var(--ink-2)'];return['MILD LEAN','var(--ink-2)'];}
function fp(){const el=document.getElementById('fp');
  if(state.focus==null){el.style.display='none';return;}
  const g=G.find(x=>x.n===state.focus);if(!g){el.style.display='none';return;}
  const [tg,tc]=label(g);
  let strips='';
  g.tl.forEach(([s,seq])=>{const cells=seq.map(v=>{const hot=v>=900;
    const col=hot?'--hot':'--cold';const op=hot?(0.45+Math.min(1,(v-900)/60)*0.55):(0.45+Math.min(1,(900-v)/80)*0.55);
    return '<div class="cell" style="background:'+ 'var('+col+')' +';opacity:'+op.toFixed(2)+'" title="'+s.slice(0,4)+' · .'+v+'"></div>';}).join('');
    strips+='<div class="tlrow"><div class="yr">'+s.slice(0,4)+'&ndash;'+s.slice(6,8)+'</div><div class="cells">'+cells+'</div></div>';});
  el.style.display='block';
  el.innerHTML='<h3>'+g.n+'<span class="tag" style="background:var(--chipbg);color:'+tc+'">'+tg+'</span></h3>'+
    '<div class="meta"><b>'+g.st+'</b> starts · .'+g.sv+' career SV% · <b>'+g.hr+'%</b> hot · '+
    'streakiness <b>'+(g.sk>0?'+':'')+(g.sk/1000).toFixed(3)+'</b> · longest hot <b>'+g.lh+'</b> / cold <b>'+g.lc+'</b> · '+
    'hot after hot '+g.phh+'% vs after cold '+g.phc+'%</div>'+strips+
    '<div class="note" style="margin-top:8px">Each square is one start in date order, by season. '+
    'Deeper red = higher save %, deeper blue = lower. Clusters of one colour are the streaks.</div>';}
cv.addEventListener('mousemove',e=>{if(!geom||state.table)return;
  const r=cv.getBoundingClientRect(),mx=(e.clientX-r.left)*geom.W/r.width,my=(e.clientY-r.top)*geom.H/r.height;
  let best=null,bd=200;pts.forEach(p=>{const dx=p.px-mx,dy=p.py-my,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;best=p;}});
  if(best){const g=best.g;tip.innerHTML='<div class="nm">'+g.n+'</div>.'+g.sv+' SV% · streakiness '+(g.sk>0?'+':'')+(g.sk/1000).toFixed(3)+
    ' · hot '+g.hr+'%<div class="q">longest hot '+g.lh+' / cold '+g.lc+' — click for timeline</div>';
    tip.style.opacity=1;tip.style.left=Math.min(e.clientX+14,innerWidth-230)+'px';tip.style.top=(e.clientY-14)+'px';}
  else tip.style.opacity=0;});
cv.addEventListener('mouseleave',()=>{tip.style.opacity=0;});
cv.addEventListener('click',e=>{if(!geom||state.table)return;
  const r=cv.getBoundingClientRect(),mx=(e.clientX-r.left)*geom.W/r.width,my=(e.clientY-r.top)*geom.H/r.height;
  let best=null,bd=280;pts.forEach(p=>{const dx=p.px-mx,dy=p.py-my,dd=dx*dx+dy*dy;if(dd<bd){bd=dd;best=p;}});
  state.focus=best?((state.focus===best.g.n)?null:best.g.n):null;
  if(state.focus==null){document.getElementById('find').value='';state.find='';}
  render();fp();});
function tbl(){const q=state.find.trim().toLowerCase();
  const rows=[...G].filter(g=>!q||g.n.toLowerCase().includes(q)).sort((a,b)=>b.sk-a.sk);
  document.querySelector('#t thead').innerHTML='<tr><th>Goalie</th><th>Starts</th><th>SV%</th><th>Hot%</th><th>Longest hot</th><th>Longest cold</th><th>Hot after hot</th><th>Hot after cold</th><th>Streakiness</th></tr>';
  document.querySelector('#t tbody').innerHTML=rows.map(g=>'<tr><td>'+g.n+'</td><td>'+g.st+'</td><td>.'+g.sv+'</td><td>'+g.hr+'</td><td>'+g.lh+'</td><td>'+g.lc+'</td><td>'+g.phh+'</td><td>'+g.phc+'</td><td>'+(g.sk>0?'+':'')+(g.sk/1000).toFixed(3)+'</td></tr>').join('');}
document.getElementById('tbl').onclick=e=>{state.table=!state.table;e.currentTarget.setAttribute('aria-pressed',state.table);
  document.getElementById('tblwrap').style.display=state.table?'block':'none';
  document.getElementById('cvwrap').style.display=state.table?'none':'block';
  if(state.table){tbl();}else{render();}};
document.getElementById('find').oninput=e=>{state.find=e.target.value;const q=state.find.trim().toLowerCase();
  const m=q?G.find(g=>g.n.toLowerCase().includes(q)):null;state.focus=m?m.n:null;
  if(state.table){tbl();}else{render();fp();}};
new MutationObserver(()=>{render();fp();}).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>{render();fp();});
addEventListener('resize',()=>{if(!state.table)render();});
render();
</script>'''

html = html.replace('__GOALIES__', G_JS)
from _fetch import write_page
write_page(OUT, html)
print(f"wrote {OUT}: {len(html)} bytes")
