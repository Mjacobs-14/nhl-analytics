import json, sys
from collections import defaultdict
from _fetch import load

# Datasets + their SQL live in queries.py (MATCHUP: st / gp / rush / goalies).
data, OUT = load('matchup')

def f(x): return None if x is None else float(x)

ST = []
for r in data['st']:
    if r['strength'] == 'sh':      # shorthanded offense excluded from pricing (tiny)
        continue
    ST.append({'s': str(r['season']), 't': r['team'], 'v': r['venue'], 'k': r['strength'],
               'sf': r['sf'] or 0, 'oh': f(r['off_hd']), 'om': f(r['off_md']),
               'sa': r['sa'] or 0, 'dh': f(r['def_hd']), 'dm': f(r['def_md'])})
GP = {f"{r['season']}|{r['team']}|{r['venue']}": r['gp'] for r in data['gp']}
RUSH = {f"{r['season']}|{r['team']}": [f(r['rush_for']), f(r['rush_against'])] for r in data['rush']}
GK = [{'s': str(r['season']), 't': r['team'], 'n': r['gk_name'], 'sh': r['shots'],
       'gh': f(r['sv_hd']), 'gm': f(r['sv_md']), 'gl': f(r['sv_ld'])} for r in data['goalies']]

seasons = sorted({d['s'] for d in ST})
assert len(seasons) == 8, seasons
ev_sf = sum(d['sf'] for d in ST if d['k'] == 'ev')
pp_sf = sum(d['sf'] for d in ST if d['k'] == 'pp')
assert 0.15 < pp_sf / ev_sf < 0.35, (ev_sf, pp_sf)   # PP ~ 20-25% of EV volume
assert len(RUSH) > 240 and len(GP) > 490
assert all('`' not in g['n'] and '${' not in g['n'] for g in GK)
print(f"OK: {len(ST)} strength rows, ev/pp shot ratio {pp_sf/ev_sf:.2f}, {len(RUSH)} rush rows, {len(GK)} goalies")

ST_JS = json.dumps(ST, separators=(',', ':'))
GP_JS = json.dumps(GP, separators=(',', ':'))
RUSH_JS = json.dumps(RUSH, separators=(',', ':'))
GK_JS = json.dumps(GK, separators=(',', ':'))

html = r'''<meta charset="utf-8">
<title>Matchup Lab — NHL Style-Clash Previews</title>
<style>
:root{--paper:#f8f8f5;--ink:#17181b;--ink-2:#5b5f66;--ink-3:#989ca4;--line:#e5e5e0;--card:#fff;
  --hd:#e34948;--md:#eda100;--ld:#8f97a3;--accent:#2a78d6;--chipbg:#f0f0eb;--pos:#1baf7a;--neg:#e34948;--pp:#4a3aa7;}
@media (prefers-color-scheme:dark){:root{--paper:#151515;--ink:#f1f1ee;--ink-2:#a8acb3;--ink-3:#6c7077;
  --line:#333330;--card:#1f1f1e;--hd:#e66767;--md:#c98500;--ld:#7c8390;--accent:#3987e5;--chipbg:#2a2a28;--pos:#199e70;--neg:#e66767;--pp:#9085e9;}}
:root[data-theme=dark]{--paper:#151515;--ink:#f1f1ee;--ink-2:#a8acb3;--ink-3:#6c7077;--line:#333330;--card:#1f1f1e;--hd:#e66767;--md:#c98500;--ld:#7c8390;--accent:#3987e5;--chipbg:#2a2a28;--pos:#199e70;--neg:#e66767;--pp:#9085e9;}
:root[data-theme=light]{--paper:#f8f8f5;--ink:#17181b;--ink-2:#5b5f66;--ink-3:#989ca4;--line:#e5e5e0;--card:#fff;--hd:#e34948;--md:#eda100;--ld:#8f97a3;--accent:#2a78d6;--chipbg:#f0f0eb;--pos:#1baf7a;--neg:#e34948;--pp:#4a3aa7;}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 "Segoe UI",system-ui,sans-serif;
  font-variant-numeric:tabular-nums;padding:26px clamp(14px,4vw,44px) 46px;}
h1{font-size:clamp(20px,3vw,27px);letter-spacing:-.02em;margin:0 0 2px;font-weight:750;}
.sub{color:var(--ink-2);margin:0 0 18px;max-width:76ch;}
.bar{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin-bottom:18px;}
select{background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:7px;padding:7px 10px;font:inherit;}
.chip{border:1px solid var(--line);background:var(--chipbg);color:var(--ink-2);border-radius:999px;padding:6px 13px;font:600 13px/1 inherit;cursor:pointer;}
.chip[aria-pressed=true]{color:var(--ink);border-color:var(--ink-3);}
select:focus-visible,.chip:focus-visible{outline:2px solid var(--accent);outline-offset:2px;}
.score{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 22px;margin-bottom:14px;
  display:flex;align-items:center;justify-content:center;gap:26px;flex-wrap:wrap;}
.score .tm{font-size:clamp(18px,2.4vw,24px);font-weight:750;}
.score .tm .vtag{display:block;font-size:11px;color:var(--ink-3);font-weight:600;text-align:center;letter-spacing:.04em;}
.score .xg{font-size:clamp(26px,4vw,38px);font-weight:750;letter-spacing:-.02em;text-align:center;}
.score .xg .bd{display:block;font-size:11.5px;color:var(--ink-3);font-weight:600;}
.score .vs{color:var(--ink-3);font-size:13px;text-align:center;}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;}
@media(max-width:860px){.grid{grid-template-columns:1fr;}}
.panel{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:16px 18px;}
.panel h2{margin:0 0 3px;font-size:15.5px;font-weight:700;}
.panel .sm{color:var(--ink-2);font-size:12.5px;margin-bottom:12px;}
.mixlab{display:flex;justify-content:space-between;color:var(--ink-2);font-size:12px;margin:10px 0 3px;font-weight:600;}
.mix{display:flex;height:22px;border-radius:6px;overflow:hidden;}
.mix div{height:100%;}
.mixnum{display:flex;justify-content:space-between;color:var(--ink-3);font-size:11.5px;margin-top:3px;}
.strow{margin-top:12px;padding:10px 12px;background:var(--chipbg);border-radius:9px;font-size:12.5px;color:var(--ink-2);}
.strow b{color:var(--ink);}
.strow .pp{color:var(--pp);font-weight:700;}
.gk{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);}
.gk .hd{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;}
.gk .nm{font-weight:700;font-size:13.5px;}
.gk select{padding:4px 8px;font-size:12.5px;}
.bandrow{display:grid;grid-template-columns:80px 1fr auto;gap:8px;align-items:center;font-size:12.5px;margin-top:5px;}
.bandrow .lb{color:var(--ink-2);font-weight:600;}
.bandrow .tr{position:relative;height:12px;background:var(--chipbg);border-radius:3px;}
.bandrow .fl{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--accent);opacity:.8;}
.bandrow .tick{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink-3);}
.bandrow .dv{font-weight:700;}
.clash{background:var(--card);border:1px solid var(--line);border-radius:13px;padding:14px 18px;margin-top:14px;color:var(--ink-2);font-size:13.5px;}
.clash b{color:var(--ink);}
.note{color:var(--ink-3);font-size:12.5px;margin-top:16px;max-width:90ch;}
.legend{display:inline-flex;gap:14px;align-items:center;color:var(--ink-2);font-size:12.5px;}
.legend .k{display:inline-flex;gap:5px;align-items:center;}.legend .b{width:11px;height:11px;border-radius:3px;}
</style>
<h1>Matchup Lab</h1>
<p class="sub">A style-clash preview for any two teams: even-strength shot diets and concession profiles (road vs home),
a separate power-play-vs-penalty-kill term, the transition (rush) clash, and the goalie&rsquo;s danger-band save % —
all priced in expected goals. Override either goalie for a confirmed starter.</p>
<div class="bar">
  <select id="season" aria-label="Season"></select>
  <select id="ta" aria-label="Road team"></select>
  <span style="color:var(--ink-3);font-weight:600">at</span>
  <select id="tb" aria-label="Home team"></select>
  <button class="chip" id="swap">⇄ swap</button>
  <button class="chip" id="venue" aria-pressed="true">home/road split: ON</button>
  <span class="legend"><span class="k"><span class="b" style="background:var(--hd)"></span>high danger</span>
    <span class="k"><span class="b" style="background:var(--md)"></span>medium</span>
    <span class="k"><span class="b" style="background:var(--ld)"></span>low</span></span>
</div>
<div class="score" id="score"></div>
<div class="grid" id="grid"></div>
<div class="clash" id="clash"></div>
<p class="note" id="method"></p>
<script>
const ST=__ST__, GP=__GP__, RUSH=__RUSH__, GK=__GK__;
const LSV={h:0.804,m:0.903,l:0.975};
const seasons=[...new Set(ST.map(d=>d.s))].sort().reverse();
const sel=document.getElementById('season'),ta=document.getElementById('ta'),tb=document.getElementById('tb');
seasons.forEach(k=>{const o=document.createElement('option');o.value=k;o.textContent=k.slice(0,4)+'–'+k.slice(6);sel.appendChild(o);});
let state={venue:true,gkA:null,gkB:null};
function teamsIn(s){return [...new Set(ST.filter(d=>d.s===s).map(d=>d.t))].sort();}
function fillTeams(){const ts=teamsIn(sel.value);
  [ta,tb].forEach(x=>{const cur=x.value;x.innerHTML='';ts.forEach(t=>{const o=document.createElement('option');o.value=t;o.textContent=t;x.appendChild(o);});
    if(ts.includes(cur))x.value=cur;});
  if(ta.value===tb.value)tb.value=ts.find(t=>t!==ta.value);}
sel.value=seasons[0];fillTeams();
if(teamsIn(sel.value).includes('DAL'))ta.value='DAL';
if(teamsIn(sel.value).includes('VGK'))tb.value='VGK';
function gpOf(s,t,v){return state.venue?(GP[s+'|'+t+'|'+v]||41):((GP[s+'|'+t+'|home']||0)+(GP[s+'|'+t+'|road']||0));}
// merged strength profile for team at venue (or both venues when split off)
function prof(s,t,v,k){
  const rows=ST.filter(d=>d.s===s&&d.t===t&&d.k===k&&(state.venue?d.v===v:true));
  if(!rows.length)return null;
  const sf=rows.reduce((a,d)=>a+d.sf,0),sa=rows.reduce((a,d)=>a+d.sa,0);
  const wo=(key)=>sf?rows.reduce((a,d)=>a+(d[key]||0)*d.sf,0)/sf:0;
  const wd=(key)=>sa?rows.reduce((a,d)=>a+(d[key]||0)*d.sa,0)/sa:0;
  const oh=wo('oh'),om=wo('om'),dh=wd('dh'),dm=wd('dm');
  return{sf,sa,oh,om,ol:100-oh-om,dh,dm,dl:100-dh-dm};}
function leagueK(s,k){const rs=ST.filter(d=>d.s===s&&d.k===k);
  const sa=rs.reduce((a,d)=>a+d.sa,0);
  const gp=Object.keys(GP).filter(key=>key.startsWith(s+'|')).reduce((a,key)=>a+GP[key],0);
  const dh=rs.reduce((a,d)=>a+(d.dh||0)*d.sa,0)/sa,dm=rs.reduce((a,d)=>a+(d.dm||0)*d.sa,0)/sa;
  return{sapg:sa/gp,h:dh,m:dm,l:100-dh-dm};}
function gkList(s,t){return GK.filter(g=>g.s===s&&g.t===t);}
function pickGk(s,t,ov){const l=gkList(s,t);if(ov){const m=l.find(g=>g.n===ov);if(m)return m;}return l[0]||null;}
function term(A,B,L,gk,gpA,gpB){
  if(!A||!B||!A.sf||!B.sa)return{shots:0,mix:{h:0,m:0,l:0},xg:0,xgb:{h:0,m:0,l:0}};
  const shots=(A.sf/gpA)*(B.sa/gpB)/L.sapg;
  let mh=(A.oh*B.dh)/L.h,mm=(A.om*B.dm)/L.m,ml=(A.ol*B.dl)/L.l;
  const tot=mh+mm+ml;mh/=tot;mm/=tot;ml/=tot;
  const sv={h:gk&&gk.gh!=null?gk.gh:LSV.h,m:gk&&gk.gm!=null?gk.gm:LSV.m,l:gk&&gk.gl!=null?gk.gl:LSV.l};
  return{shots,mix:{h:mh*100,m:mm*100,l:ml*100},
    xg:shots*(mh*(1-sv.h)+mm*(1-sv.m)+ml*(1-sv.l)),
    xgb:{h:shots*mh*(1-sv.h),m:shots*mm*(1-sv.m),l:shots*ml*(1-sv.l)}};}
function direction(s,tA,vA,tB,vB,gk){
  const gpA=gpOf(s,tA,vA),gpB=gpOf(s,tB,vB);
  const ev=term(prof(s,tA,vA,'ev'),prof(s,tB,vB,'ev'),leagueK(s,'ev'),gk,gpA,gpB);
  const pp=term(prof(s,tA,vA,'pp'),prof(s,tB,vB,'pp'),leagueK(s,'pp'),gk,gpA,gpB);
  return{ev,pp,xg:ev.xg+pp.xg};}
const mixBar=(h,m,l)=>'<div class="mix"><div style="width:'+h+'%;background:var(--hd)"></div>'+
  '<div style="width:'+m+'%;background:var(--md)"></div><div style="width:'+l+'%;background:var(--ld)"></div></div>'+
  '<div class="mixnum"><span>'+h.toFixed(1)+'% HD</span><span>'+m.toFixed(1)+'% MD</span><span>'+l.toFixed(1)+'% LD</span></div>';
function gkPanel(side,teamName,gk,list,d){
  const opts=list.map(g=>'<option value="'+g.n+'"'+(gk&&g.n===gk.n?' selected':'')+'>'+g.n+' ('+g.sh+' shots)</option>').join('');
  const rows=[['High danger',gk?gk.gh:null,LSV.h],['Medium',gk?gk.gm:null,LSV.m],['Low danger',gk?gk.gl:null,LSV.l]];
  const small=gk&&gk.gh==null;
  return '<div class="gk"><div class="hd"><span class="nm">🥅</span>'+
    '<select data-side="'+side+'" class="gksel" aria-label="Goalie for '+teamName+'">'+opts+'</select>'+
    (small?'<span style="color:var(--ink-3);font-size:11.5px">&lt;1500 career shots — league-avg rates used</span>':'')+'</div>'+
    rows.map(([lb,v,lg])=>{const val=v??lg,lo=0.75,hi=1.0;
      const w=Math.max(0,Math.min(100,(val-lo)/(hi-lo)*100)),tk=(lg-lo)/(hi-lo)*100,dd=v==null?null:v-lg;
      return '<div class="bandrow"><div class="lb">'+lb+'</div>'+
        '<div class="tr"><div class="fl" style="width:'+w+'%"></div><div class="tick" style="left:'+tk+'%"></div></div>'+
        '<div class="dv">.'+Math.round(val*1000)+(dd==null?'':' <span style="color:var(--'+(dd>=0?'pos':'neg')+')">('+(dd>=0?'+':'')+(dd*100).toFixed(1)+')</span>')+'</div></div>';}).join('')+
    '<div class="mixnum" style="margin-top:5px"><span>grey tick = league band save % · total xGA by band: HD '+
    (d.ev.xgb.h+d.pp.xgb.h).toFixed(2)+' · MD '+(d.ev.xgb.m+d.pp.xgb.m).toFixed(2)+' · LD '+(d.ev.xgb.l+d.pp.xgb.l).toFixed(2)+'</span></div></div>';}
function render(){
  fillTeams();
  const s=sel.value;
  if(ta.value===tb.value){document.getElementById('score').textContent='Pick two different teams.';return;}
  const gkA=pickGk(s,ta.value,state.gkA),gkB=pickGk(s,tb.value,state.gkB);
  const ab=direction(s,ta.value,'road',tb.value,'home',gkB);
  const ba=direction(s,tb.value,'home',ta.value,'road',gkA);
  const vA=state.venue?'ROAD':'ALL',vB=state.venue?'HOME':'ALL';
  document.getElementById('score').innerHTML=
    '<span class="tm">'+ta.value+'<span class="vtag">'+vA+'</span></span>'+
    '<span class="xg">'+ab.xg.toFixed(2)+'<span class="bd">EV '+ab.ev.xg.toFixed(2)+' · PP '+ab.pp.xg.toFixed(2)+'</span></span>'+
    '<span class="vs">expected goals<br>('+s.slice(0,4)+'–'+s.slice(6)+' profiles)</span>'+
    '<span class="xg">'+ba.xg.toFixed(2)+'<span class="bd">EV '+ba.ev.xg.toFixed(2)+' · PP '+ba.pp.xg.toFixed(2)+'</span></span>'+
    '<span class="tm">'+tb.value+'<span class="vtag">'+vB+'</span></span>';
  const panel=(tX,tY,vx,vy,d,side,gk)=>{
    const Aev=prof(s,tX,vx==='HOME'?'home':'road','ev'),Bev=prof(s,tY,vy==='HOME'?'home':'road','ev');
    const App=prof(s,tX,vx==='HOME'?'home':'road','pp'),Bpp=prof(s,tY,vy==='HOME'?'home':'road','pp');
    const gpX=gpOf(s,tX,vx==='HOME'?'home':'road'),gpY=gpOf(s,tY,vy==='HOME'?'home':'road');
    return '<div class="panel"><h2>'+tX+' ('+vx.toLowerCase()+') attacking '+tY+' ('+vy.toLowerCase()+')</h2>'+
    '<div class="sm">Even strength: '+tX+' generates '+(Aev.sf/gpX).toFixed(1)+' on-net/gm · '+tY+' allows '+(Bev.sa/gpY).toFixed(1)+' → blended <b>'+d.ev.shots.toFixed(1)+'</b> for <b>'+d.ev.xg.toFixed(2)+' xG</b></div>'+
    '<div class="mixlab"><span>'+tX+' wants (EV)</span><span>blend</span><span>'+tY+' concedes (EV)</span></div>'+
    mixBar(Aev.oh,Aev.om,Aev.ol)+'<div style="height:7px"></div>'+mixBar(d.ev.mix.h,d.ev.mix.m,d.ev.mix.l)+
    '<div class="mixnum"><span>&uarr; blended EV attack mix</span></div><div style="height:7px"></div>'+mixBar(Bev.dh,Bev.dm,Bev.dl)+
    '<div class="strow"><span class="pp">⚡ Special teams:</span> '+tX+'&rsquo;s PP puts <b>'+(App&&App.sf?(App.sf/gpX).toFixed(1):'0')+'</b> shots/gm on net ('+(App?App.oh.toFixed(0):0)+'% HD) · '+tY+'&rsquo;s PK concedes <b>'+(Bpp&&Bpp.sa?(Bpp.sa/gpY).toFixed(1):'0')+'</b>/gm ('+(Bpp?Bpp.dh.toFixed(0):0)+'% HD) → <b>'+d.pp.xg.toFixed(2)+' PP xG</b></div>'+
    gkPanel(side,tY,gk,gkList(s,tY),d)+'</div>';};
  document.getElementById('grid').innerHTML=
    panel(ta.value,tb.value,vA,vB,ab,'B',gkB)+panel(tb.value,ta.value,vB,vA,ba,'A',gkA);
  document.querySelectorAll('.gksel').forEach(el=>{el.onchange=()=>{
    if(el.dataset.side==='B')state.gkB=el.value;else state.gkA=el.value;render();};});
  // narratives
  const bits=[];
  const Lev=leagueK(s,'ev');
  const Aev=prof(s,ta.value,'road','ev'),Bev=prof(s,tb.value,'home','ev');
  if(Aev.oh-Lev.h>1.5&&Bev.dh-Lev.h<-1.5)bits.push('<b>'+ta.value+'</b> hunts the slot at evens ('+Aev.oh.toFixed(1)+'% HD) but <b>'+tb.value+'</b> concedes only '+Bev.dh.toFixed(1)+'% — a genuine style fight.');
  else if(Aev.oh-Lev.h>1.5&&Bev.dh-Lev.h>1.5)bits.push('<b>'+ta.value+'</b> hunts the slot AND <b>'+tb.value+'</b> bleeds it ('+Bev.dh.toFixed(1)+'% HD allowed) — the danger zone lights up.');
  const ppGap=ab.pp.xg-ba.pp.xg;
  if(Math.abs(ppGap)>0.12)bits.push('Special-teams edge: <b>'+(ppGap>0?ta.value:tb.value)+'</b> by '+Math.abs(ppGap).toFixed(2)+' PP xG — '+(ppGap>0?ta.value+'&rsquo;s power play vs '+tb.value+'&rsquo;s kill':tb.value+'&rsquo;s power play vs '+ta.value+'&rsquo;s kill')+' is the mismatch.');
  const rA=RUSH[s+'|'+ta.value],rB=RUSH[s+'|'+tb.value],LR=9.7;
  if(rA&&rB){
    if(rA[0]>LR+0.7&&rB[1]>LR+0.5)bits.push('Transition: <b>'+ta.value+'</b> plays rush hockey ('+rA[0].toFixed(1)+'% of attempts) and <b>'+tb.value+'</b> gives up rush chances ('+rB[1].toFixed(1)+'% allowed) — watch odd-man traffic.');
    else if(rA[0]>LR+0.7&&rB[1]<LR-0.4)bits.push('Transition: <b>'+ta.value+'</b> wants to rush ('+rA[0].toFixed(1)+'%) but <b>'+tb.value+'</b> shuts the door in the neutral zone ('+rB[1].toFixed(1)+'% allowed).');
    if(rB[0]>LR+0.7&&rA[1]>LR+0.5)bits.push('Other way: <b>'+tb.value+'</b> attacks off the rush ('+rB[0].toFixed(1)+'%) into <b>'+ta.value+'</b>&rsquo;s leaky transition D ('+rA[1].toFixed(1)+'% allowed).');}
  const eB=gkB&&gkB.gh!=null?gkB.gh-LSV.h:0,eA=gkA&&gkA.gh!=null?gkA.gh-LSV.h:0;
  if(Math.abs(eB-eA)>0.01)bits.push('Goalie edge on high-danger: <b>'+(eB>eA?gkB.n+' ('+tb.value+')':gkA.n+' ('+ta.value+')')+'</b> by '+(Math.abs(eB-eA)*100).toFixed(1)+' points of HD save %.');
  document.getElementById('clash').innerHTML='<b>Style clash:</b> '+(bits.length?bits.join(' '):'No extreme mismatches — both teams close to league-average profiles.');
  document.getElementById('method').innerHTML='How it works: expected goals = an <b>even-strength term</b> + a <b>power-play term</b>, each: attacker shots/gm &times; defender allowed/gm &divide; league average at that strength, with the attack mix from an odds-ratio blend of shot diet &times; concession profile, priced by the selected goalie&rsquo;s career danger-band save % (high &ge; .15 xG / mid / low; league .804/.903/.975). '+
    (state.venue?'Road team uses road profiles, home team home profiles (toggle off for full-season — venue splits halve samples). ':'Full-season profiles (venue split off). ')+
    'PP volume bakes in penalty rates and PP efficiency together. Shorthanded offense (~3% of shots) is ignored. Rush is shown as a style clash, not priced — rush shots are already valued through their locations. Goalie bands are career, pooled across strengths. <b>A descriptive style-clash preview with predictive-leaning structure, not a betting model</b> — no rest, injuries, or current form.';
}
document.getElementById('swap').onclick=()=>{const x=ta.value;ta.value=tb.value;tb.value=x;
  const g=state.gkA;state.gkA=state.gkB;state.gkB=g;render();};
document.getElementById('venue').onclick=e=>{state.venue=!state.venue;
  e.currentTarget.setAttribute('aria-pressed',state.venue);
  e.currentTarget.textContent='home/road split: '+(state.venue?'ON':'OFF');render();};
sel.onchange=()=>{state.gkA=state.gkB=null;render();};
ta.onchange=()=>{state.gkA=null;render();};
tb.onchange=()=>{state.gkB=null;render();};
new MutationObserver(()=>render()).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
render();
</script>'''

html = (html.replace('__ST__', ST_JS).replace('__GP__', GP_JS)
            .replace('__RUSH__', RUSH_JS).replace('__GK__', GK_JS))
from _fetch import write_page
write_page(OUT, html)
print(f"wrote {OUT}: {len(html)} bytes")
