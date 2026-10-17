"""HTTP server: /metrics (Prometheus), / (info page), /status (JSON), /health(z).

``prometheus_client.start_http_server`` answers every path with metrics; this
threading server routes them explicitly and adds a human-readable index that
reflects the collectors (solar-system + celestial bodies, satellites, space weather)
and every configured observer.
"""

from __future__ import annotations

import gzip
import html
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, generate_latest

_STYLE = """
<style>
:root { color-scheme: light dark; }
body { font: 15px/1.55 system-ui, -apple-system, sans-serif; max-width: 46rem;
       margin: 2.5rem auto; padding: 0 1rem; }
h1 { margin: 0; }
h1 .v { font-size: .55em; opacity: .55; font-weight: 400; }
.sub { opacity: .7; margin: .2rem 0 0; }
h2 { margin: 1.7rem 0 .4rem; border-bottom: 1px solid #8884; padding-bottom: .2rem; font-size: 1.05rem; }
h3 { margin: 1rem 0 .2rem; font-size: .95rem; opacity: .85; }
code { background: #8882; padding: .1em .35em; border-radius: 4px; }
table { border-collapse: collapse; }
td, th { text-align: left; padding: .2rem 1.2rem .2rem 0; }
a { color: #3b82f6; text-decoration: none; }
a:hover { text-decoration: underline; }
.ok { color: #16a34a; } .bad { color: #dc2626; }
ul { padding-left: 1.1rem; }
</style>
"""


def _sources_table(sources) -> str:
    rows = ""
    for s in sources:
        mark = '<span class="ok">✓</span>' if s["success"] else '<span class="bad">✗</span>'
        age = f'{s["age_seconds"]}s' if s.get("age_seconds") is not None else "—"
        rows += (f"<tr><td><code>{html.escape(s['source'])}</code></td>"
                 f"<td>{mark}</td><td>{age}</td></tr>")
    return ("<table><thead><tr><th>source</th><th>ok</th><th>age</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def _render_html(info: dict) -> str:
    col = info["collectors"]
    sat, sw = col["satellites"], col["space_weather"]

    observers_html = "<table><tbody>" + "".join(
        f"<tr><td><b>{html.escape(o['name'])}</b></td>"
        f"<td>{o['latitude_deg']:.4f}, {o['longitude_deg']:.4f}</td>"
        f"<td>{o['elevation_m']:.0f} m</td></tr>"
        for o in info["observers"]
    ) + "</tbody></table>"

    ssb = ", ".join(html.escape(b) for b in col["solar_system_bodies"]) or "—"
    cb = ", ".join(html.escape(s) for s in col["celestial_bodies"]) or "—"

    if sat.get("enabled"):
        groups = ", ".join(html.escape(g) for g in sat.get("groups", [])) or "—"
        watch = ", ".join(str(w) for w in sat.get("watchlist", [])) or "—"
        focus = ", ".join(str(w) for w in sat.get("focus", [])) or "—"
        sat_html = (
            "<h2>Satellites</h2>"
            f"<p>groups <code>{groups}</code> · watchlist <code>{watch}</code>"
            f" · focus <code>{focus}</code></p>"
            f"<p>catalog <b>{sat.get('catalog_size', 0)}</b> satellites "
            f"({sat.get('with_transmitters', 0)} with transmitters)</p>"
            + _sources_table(sat.get("sources", []))
        )
    else:
        sat_html = "<h2>Satellites</h2><p>disabled</p>"

    if sw.get("enabled"):
        products = ", ".join(html.escape(p) for p in sw.get("products", [])) or "—"
        sw_html = (
            "<h2>Space weather</h2>"
            f"<p>products <code>{products}</code></p>"
            + _sources_table(sw.get("sources", []))
        )
    else:
        sw_html = "<h2>Space weather</h2><p>disabled</p>"

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>space-telemetry</title>" + _STYLE + "</head><body>"
        f'<h1>space-telemetry <span class="v">v{html.escape(info["version"])}</span></h1>'
        '<p class="sub">Prometheus / OTel exporter for space telemetry</p>'
        "<h2>Observers</h2>" + observers_html +
        f"<h2>Solar-system bodies</h2><p><code>{ssb}</code></p>"
        f"<h2>Celestial bodies</h2><p><code>{cb}</code></p>"
        + sat_html + sw_html +
        "<h2>Endpoints</h2><ul>"
        '<li><a href="/map">/map</a> — live satellite map (MapLibre GL + OpenStreetMap)</li>'
        '<li><a href="/table">/table</a> — focus pass plan, satellites, passes, bodies, stars</li>'
        '<li><a href="/metrics">/metrics</a> — Prometheus metrics</li>'
        '<li><a href="/status">/status</a> — status as JSON</li>'
        '<li><a href="/health">/health</a> — health check (alias <code>/healthz</code>)</li>'
        '<li><a href="/api/satellites.json">/api/satellites.json</a> — live positions + ground tracks</li>'
        '<li><a href="/api/focus.json">/api/focus.json</a> — focus satellites: every pass in the lookahead window</li>'
        "</ul></body></html>"
    )


# Satellite filter panel shared by /map and /table (spliced in at /*SF_CSS*/ and //SF_JS).
_FILTER_CSS = r"""
  .sf{font-size:12.5px;line-height:1.5}
  .sf-head{display:flex;align-items:center;gap:6px 8px;flex-wrap:wrap}
  .sf-head b{font-size:11px;opacity:.55;text-transform:uppercase;letter-spacing:.04em;cursor:pointer;user-select:none}
  .sf-n{opacity:.7;font-variant-numeric:tabular-nums;white-space:nowrap}
  .sf-reset{color:#8ab4ff;cursor:pointer;margin-left:auto}
  .sf-reset[hidden]{display:none}
  .sf-fold{opacity:.6;cursor:pointer;user-select:none;margin-left:auto;width:14px;text-align:center}
  .sf-reset:not([hidden])+.sf-fold{margin-left:0}
  .sf.folded .sf-body{display:none}
  .sf-sec{margin-top:10px}
  .sf-t{font-size:10.5px;opacity:.5;text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px}
  .sf-chips{display:flex;flex-wrap:wrap;gap:4px}
  .sf-c{background:#ffffff10;border:1px solid #ffffff26;color:inherit;border-radius:11px;padding:1px 8px;font:inherit;font-size:12px;cursor:pointer;display:inline-flex;gap:5px;align-items:center}
  .sf-c:hover{background:#ffffff1f}
  .sf-c i{font-style:normal;opacity:.55;font-size:11px}
  .sf-c.on{background:#3b82f6;border-color:#3b82f6;color:#fff}
  .sf-c.on i{opacity:.85}
  .sf-g{display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none}
  .sf-g.off{opacity:.38}
  .sf-car{width:12px;opacity:.6;text-align:center;flex:none}
  .sf-dot{width:10px;height:10px;border-radius:50%;flex:none}
  .sf-ct{opacity:.55;margin-left:auto;padding-left:8px;font-variant-numeric:tabular-nums}
  .sf-only{color:#8ab4ff;font-size:11px;visibility:hidden}
  .sf-g:hover .sf-only,.sf-s:hover .sf-only{visibility:visible}
  .sf-list{margin:1px 0 5px 5px;padding-left:12px;border-left:1px solid #ffffff1f;max-height:30vh;overflow:auto}
  .sf-s{display:flex;gap:6px;align-items:center;cursor:pointer;user-select:none;white-space:nowrap}
  .sf-s .nm{overflow:hidden;text-overflow:ellipsis;flex:1}
  .sf-s.off{opacity:.4}
  .sf-s.dim .nm{opacity:.5;font-style:italic}
  .sf-alt{display:grid;grid-template-columns:auto 1fr;gap:2px 8px;align-items:center}
  .sf-alt span{font-size:11px;opacity:.6}
  .sf-alt .sf-altv{opacity:.85;font-variant-numeric:tabular-nums}
  .sf-alt input{width:100%;margin:0;accent-color:#3b82f6;cursor:pointer}
  .sf-sel{display:flex;flex-wrap:wrap;gap:6px 12px;margin-top:7px}
  .sf select{color-scheme:dark;background:#0004;color:inherit;border:1px solid #fff3;border-radius:6px;font:inherit;font-size:12px;padding:1px 3px}
  .sf-pin{display:flex;gap:6px;align-items:center;margin-top:9px;cursor:pointer;user-select:none}
  .sf-q{background:#0004;border:1px solid #fff3;color:inherit;border-radius:6px;padding:3px 8px;font:inherit;flex:0 1 190px;min-width:110px;outline:none}
  .sf-table{background:#14141c;border:1px solid #ffffff14;border-radius:10px;padding:10px 14px;margin-top:24px}
  .sf-table .sf-body{display:flex;flex-wrap:wrap;gap:0 30px}
  .sf-table .sf-sec{flex:1 1 200px;max-width:330px}
"""

_FILTER_JS = r"""
// Shared satellite filters for /map and /table: groups with per-satellite toggles, orbit
// class, altitude range, radio band + mode (active SatNOGS downlinks), visibility / next
// pass. The state lives in the URL query (shareable; the map <-> table links carry it)
// and is remembered in this browser. SF.visible() is the set of NORAD ids that pass.
const SF=(()=>{
const GROUPS=[['iss','#e02b2b'],['css','#ff8f1f'],['weather','#3b82f6'],['noaa','#22c55e'],['goes','#a855f7'],['stations','#9aa0aa'],['other','#cbd5e1']];
// [key, chip, from MHz, to MHz, tooltip]; the hobby sub-bands come first so they win over the wide bands
const BANDS=[['137','137 MHz',137,138,'137–138 MHz · λ ≈ 2.2 m · weather pictures (Meteor LRPT)'],
  ['2m','2 m',144,148,'144–148 MHz · λ ≈ 2 m · amateur: ISS voice, APRS, SSTV'],
  ['70cm','70 cm',430,440,'430–440 MHz · λ ≈ 69 cm · amateur: cubesats, ISS'],
  ['hf','HF',0,30,'below 30 MHz · λ over 10 m'],
  ['vhf','VHF',30,300,'other 30–300 MHz · λ 1–10 m'],
  ['uhf','UHF',300,1000,'other 300–1000 MHz · λ 30 cm–1 m'],
  ['l','L',1000,2000,'1–2 GHz · λ 15–30 cm · HRPT/AHRPT, GOES HRIT'],
  ['s','S',2000,4000,'2–4 GHz · λ 7.5–15 cm · telemetry and control'],
  ['c','C',4000,7000,'4–7 GHz · λ 4.3–7.5 cm'],
  ['x','X',7000,12000,'7–12 GHz · λ 2.5–4.3 cm · bulk image and science downloads'],
  ['ku','Ku',12000,18000,'12–18 GHz · λ 1.7–2.5 cm'],
  ['ka','Ka',18000,1e9,'above 18 GHz · λ under 1.7 cm']];
const ORBITS=[['LEO','low Earth orbit · apogee under 2,000 km'],['MEO','medium Earth orbit · 2,000 km up to GEO'],
  ['GEO','geosynchronous · ~35,786 km, one orbit a day'],['HEO','highly elliptical (Molniya, Tundra) or beyond GEO']];
const WIN=[0,1,3,6,12,24],PEAK=[0,10,20,30,45,60,75],AMIN=200,AMAX=40000,KEY='space-telemetry.filters';
const bandOf=f=>{for(const b of BANDS)if(f>=b[2]&&f<b[3])return b[0];return '';};
const altKm=v=>{const k=AMIN*Math.pow(AMAX/AMIN,v/1000),p=Math.pow(10,Math.max(0,Math.floor(Math.log10(k))-1));
  return Math.round(k/p)*p;};  // log scale, rounded to two significant digits (300, 1,000, 36k km)
const altPos=km=>Math.round(1000*Math.log(km/AMIN)/Math.log(AMAX/AMIN));
const fmtKm=k=>k>=10000?Math.round(k/1000)+'k km':k.toLocaleString('en-US')+' km';
const snap=(a,v)=>v?(a.find(x=>x>=v)||a[a.length-1]):0;
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fresh=()=>({hg:new Set(),hs:new Set(),only:new Set(),orb:new Set(),band:new Set(),mode:new Set(),
  up:false,sun:false,win:0,peak:0,amin:0,amax:0,pin:true,q:''});
const st=fresh(),open=new Set(),$=id=>document.getElementById(id);
let sats=[],passes={},root=null,opts={},saveT=0;
function query(){const o=[],l=(k,s)=>{if(s.size)o.push(k+'='+[...s].map(encodeURIComponent).join(','));};
  l('hg',st.hg);l('hs',st.hs);l('only',st.only);l('orb',st.orb);l('band',st.band);l('mode',st.mode);
  if(st.up)o.push('up=1');if(st.sun)o.push('sun=1');if(st.win)o.push('win='+st.win);if(st.peak)o.push('peak='+st.peak);
  if(st.amin)o.push('amin='+st.amin);if(st.amax)o.push('amax='+st.amax);if(!st.pin)o.push('pin=0');
  if(st.q)o.push('q='+encodeURIComponent(st.q));return o.join('&');}
function load(s){const p=new URLSearchParams(s),set=k=>new Set((p.get(k)||'').split(',').filter(Boolean)),
    ids=k=>new Set([...set(k)].map(Number).filter(n=>n>0)),num=k=>Math.max(0,Math.round(+p.get(k)||0));
  Object.assign(st,{hg:set('hg'),hs:ids('hs'),only:ids('only'),orb:set('orb'),band:set('band'),mode:set('mode'),
    up:p.get('up')==='1',sun:p.get('sun')==='1',win:snap(WIN,num('win')),peak:snap(PEAK,num('peak')),
    amin:num('amin'),amax:num('amax'),pin:p.get('pin')!=='0',q:(p.get('q')||'').trim().toLowerCase()});}
function save(){const s=query();
  document.querySelectorAll('a[data-keepq]').forEach(a=>a.href=a.dataset.keepq+(s?'?'+s:''));
  clearTimeout(saveT);saveT=setTimeout(()=>{  // debounced: browsers rate-limit replaceState
    try{history.replaceState(history.state,'',location.pathname+(s?'?'+s:'')+location.hash);}catch(e){}
    try{localStorage.setItem(KEY,s);}catch(e){}},300);}
const active=()=>!!(st.hg.size||st.hs.size||st.only.size||st.orb.size||st.band.size||st.mode.size||st.up||st.sun
  ||st.win||st.peak||st.amin||st.amax||!st.pin||st.q);
const picked=n=>st.only.size?st.only.has(n):!st.hs.has(n);  // the per-satellite checkbox
function match(s,now){
  if(!picked(s.norad))return false;                         // per-satellite choices always win
  if(st.q&&!s.name.toLowerCase().includes(st.q))return false;
  if(st.pin&&s.focus)return true;                           // ★ focus satellites skip the rest
  if(st.hg.has(s.group)||st.orb.size&&!st.orb.has(s.orbit))return false;
  if((st.band.size||st.mode.size)&&!(s.tx||[]).some(([f,m])=>(!st.band.size||st.band.has(bandOf(f)))
    &&(!st.mode.size||st.mode.has(m))))return false;        // one downlink must match band AND mode
  if(st.amin&&s.alt_km<st.amin||st.amax&&s.alt_km>st.amax)return false;
  const up=s.elevation>=0,p=passes[s.norad];
  if(st.up&&!up||st.sun&&!s.sunlit)return false;
  if(st.win&&!(up||p&&p.aos-now<=st.win*3600))return false;
  if(st.peak){const pk=p&&p.max_elev!=null?p.max_elev:(up?s.elevation:null);if(pk==null||pk<st.peak)return false;}
  return true;}
function visible(){const now=Date.now()/1000;return new Set(sats.filter(s=>match(s,now)).map(s=>s.norad));}
const chip=(k,v,label,n,on,tip)=>'<button type="button" class="sf-c'+(on?' on':'')+'" data-k="'+k+'" data-v="'+esc(v)+'"'
  +(tip?' title="'+esc(tip)+'"':'')+'>'+esc(label)+(n!=null?'<i>'+n+'</i>':'')+'</button>';
function render(){if(!root)return;
  const vis=visible(),c={g:{},orb:{},band:{},mode:{}},inc=(o,k)=>{o[k]=(o[k]||0)+1;};
  for(const s of sats){inc(c.g,s.group);inc(c.orb,s.orbit);const bs=new Set(),ms=new Set();
    for(const [f,m] of s.tx||[]){bs.add(bandOf(f));if(m)ms.add(m);}
    bs.forEach(b=>inc(c.band,b));ms.forEach(m=>inc(c.mode,m));}
  $('sf-n').textContent=!sats.length?'':vis.size===sats.length?sats.length+' satellites':vis.size+' of '+sats.length+' shown';
  $('sf-reset').hidden=!active();
  $('sf-fold').textContent=root.classList.contains('folded')?'▸':'▾';
  const g=[];
  for(const [k,col] of GROUPS){if(!c.g[k])continue;
    const mem=sats.filter(s=>s.group===k).sort((a,b)=>(b.focus?1:0)-(a.focus?1:0)||a.name.localeCompare(b.name));
    const n=mem.filter(s=>vis.has(s.norad)).length;
    g.push('<div class="sf-g'+(st.hg.has(k)?' off':'')+'" data-g="'+k+'" title="click to hide · alt-click or only: just this group">'
      +'<span class="sf-car" data-car="'+k+'" title="list the satellites">'+(open.has(k)?'▾':'▸')+'</span>'
      +'<span class="sf-dot" style="background:'+col+'"></span>'+k+'<span class="sf-only" data-only-g="'+k+'">only</span>'
      +'<span class="sf-ct">'+(n===mem.length?n:n+'/'+mem.length)+'</span></div>');
    if(open.has(k))g.push('<div class="sf-list">'+mem.map(s=>{const on=picked(s.norad),v=vis.has(s.norad);
      return '<div class="sf-s'+(on?'':' off')+(on&&!v?' dim':'')+'" data-n="'+s.norad+'" title="NORAD '+s.norad
        +(on&&!v?' · hidden by the other filters':'')+'"><span>'+(on?'☑':'☐')+'</span><span class="nm">'+(s.focus?'★ ':'')
        +esc(s.name)+'</span><span class="sf-only" data-only-n="'+s.norad+'">only</span></div>';}).join('')+'</div>');}
  $('sf-groups').innerHTML=g.join('');
  $('sf-orb').innerHTML=ORBITS.filter(([o])=>c.orb[o]||st.orb.has(o)).map(([o,t])=>chip('orb',o,o,c.orb[o]||0,st.orb.has(o),t)).join('');
  $('sf-band').innerHTML=BANDS.filter(([b])=>c.band[b]||st.band.has(b)).map(([b,l,,,t])=>chip('band',b,l,c.band[b]||0,st.band.has(b),t)).join('');
  const modes=[...new Set([...Object.keys(c.mode),...st.mode])].sort((a,b)=>(c.mode[b]||0)-(c.mode[a]||0)||a.localeCompare(b));
  $('sf-mode').innerHTML=modes.map(m=>chip('mode',m,m,c.mode[m]||0,st.mode.has(m))).join('');
  $('sf-vis').innerHTML=chip('up','','▲ above horizon',null,st.up,'above the observer’s horizon'+(opts.map?' at the map time':' now'))
    +chip('sun','','☀ sunlit',null,st.sun,'in sunlight, so visible to the eye from a dark sky');
  const a=$('sf-amin'),b=$('sf-amax');
  if(document.activeElement!==a)a.value=st.amin?altPos(st.amin):0;
  if(document.activeElement!==b)b.value=st.amax?altPos(st.amax):1000;
  $('sf-altl').textContent=(st.amin?fmtKm(st.amin):'0 km')+' – '+(st.amax?fmtKm(st.amax):'all');
  $('sf-win').value=st.win;$('sf-peak').value=st.peak;$('sf-pin').checked=st.pin;
  const q=$('sf-q');if(q&&document.activeElement!==q)q.value=st.q;}
function changed(){save();render();if(opts.onchange)opts.onchange();}
function soloGroup(g){const others=[...new Set(sats.map(s=>s.group))].filter(x=>x!==g);
  const already=!st.hg.has(g)&&others.length&&others.every(x=>st.hg.has(x));
  st.hg=already?new Set():new Set(others);}
function soloSat(n){st.only=st.only.size===1&&st.only.has(n)?new Set():new Set([n]);st.hs=new Set();}
function toggleSat(n){const s=st.only.size?st.only:st.hs;s.has(n)?s.delete(n):s.add(n);}
function init(el,o){root=el;opts=o||{};
  let s=location.search.slice(1);if(!s){try{s=localStorage.getItem(KEY)||'';}catch(e){}}
  load(s);root.classList.add('sf');
  root.innerHTML='<div class="sf-head"><b data-fold title="fold / unfold">filters</b><span class="sf-n" id="sf-n"></span>'
    +(opts.search?'<input id="sf-q" class="sf-q" type="text" placeholder="search satellite…" autocomplete="off">':'')
    +'<a id="sf-reset" class="sf-reset" hidden>reset</a><span class="sf-fold" id="sf-fold" data-fold></span></div>'
    +'<div class="sf-body">'
    +'<div class="sf-sec"><div class="sf-t">groups · ▸ lists satellites</div><div id="sf-groups"></div></div>'
    +'<div class="sf-sec"><div class="sf-t">orbit</div><div class="sf-chips" id="sf-orb"></div>'
    +'<div class="sf-t" style="margin-top:9px">altitude</div><div class="sf-alt">'
    +'<span>from</span><input type="range" id="sf-amin" min="0" max="1000" value="0">'
    +'<span>to</span><input type="range" id="sf-amax" min="0" max="1000" value="1000">'
    +'<span></span><span class="sf-altv" id="sf-altl"></span></div></div>'
    +'<div class="sf-sec"><div class="sf-t" title="from the active SatNOGS downlinks">radio band</div><div class="sf-chips" id="sf-band"></div>'
    +'<div class="sf-t" style="margin-top:9px">mode</div><div class="sf-chips" id="sf-mode"></div></div>'
    +'<div class="sf-sec"><div class="sf-t">visibility</div><div class="sf-chips" id="sf-vis"></div><div class="sf-sel">'
    +'<label>pass within <select id="sf-win">'+WIN.map(h=>'<option value="'+h+'">'+(h?h+' h':'any')+'</option>').join('')+'</select></label>'
    +'<label>peak ≥ <select id="sf-peak">'+PEAK.map(d=>'<option value="'+d+'">'+(d?d+'°':'any')+'</option>').join('')+'</select></label></div>'
    +'<label class="sf-pin"><input type="checkbox" id="sf-pin"> ★ always show focus satellites</label></div></div>';
  let f=null;try{f=localStorage.getItem(KEY+'.fold'+location.pathname);}catch(e){}
  if(f==='1'||(f==null&&opts.map&&innerWidth<700))root.classList.add('folded');
  root.addEventListener('click',e=>{
    const t=e.target.closest('#sf-reset,[data-fold],[data-only-g],[data-only-n],[data-car],[data-n],[data-g],[data-k]');
    if(!t||!root.contains(t))return;const d=t.dataset;
    if(t.id==='sf-reset')Object.assign(st,fresh());
    else if(d.fold!=null){const on=root.classList.toggle('folded');
      try{localStorage.setItem(KEY+'.fold'+location.pathname,on?'1':'0');}catch(err){}return render();}
    else if(d.car!=null){open.has(d.car)?open.delete(d.car):open.add(d.car);return render();}
    else if(d.onlyG!=null)soloGroup(d.onlyG);
    else if(d.onlyN!=null)soloSat(+d.onlyN);
    else if(d.n!=null){if(e.altKey)soloSat(+d.n);else toggleSat(+d.n);}
    else if(d.g!=null){if(e.altKey)soloGroup(d.g);else if(st.hg.has(d.g))st.hg.delete(d.g);else st.hg.add(d.g);}
    else if(d.k==='up'||d.k==='sun')st[d.k]=!st[d.k];
    else{const set=st[d.k];if(set.has(d.v))set.delete(d.v);else set.add(d.v);}
    changed();});
  $('sf-amin').addEventListener('input',e=>{const v=+e.target.value;st.amin=v<=0?0:altKm(v);
    if(st.amax&&st.amin>st.amax)st.amax=st.amin;changed();});
  $('sf-amax').addEventListener('input',e=>{const v=+e.target.value;st.amax=v>=1000?0:altKm(v);
    if(st.amax&&st.amin>st.amax)st.amin=st.amax;changed();});
  $('sf-win').addEventListener('change',e=>{st.win=+e.target.value;changed();});
  $('sf-peak').addEventListener('change',e=>{st.peak=+e.target.value;changed();});
  $('sf-pin').addEventListener('change',e=>{st.pin=e.target.checked;changed();});
  const q=$('sf-q');if(q)q.addEventListener('input',()=>{st.q=q.value.trim().toLowerCase();changed();});
  save();render();}
return {GROUPS,BANDS,bandOf,init,visible,state:()=>st,
  setSats(s){sats=s||[];render();},
  setPasses(p){passes={};for(const x of p||[])passes[x.norad]=x;render();},
  setQuery(v){st.q=(v||'').trim().toLowerCase();changed();}};
})();
"""

_MAP_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>space-telemetry · map</title>
<link href="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.js"></script>
<style>
  html,body,#map{height:100%;margin:0}
  .panel{position:absolute;background:rgba(18,18,24,.88);color:#eee;z-index:1;
    font:13px system-ui,-apple-system,sans-serif;padding:9px 12px;border-radius:9px}
  #ctrl{top:10px;left:10px;display:flex;gap:12px;align-items:center}
  #ctrl input[type=text]{background:#0004;border:1px solid #fff3;color:#fff;border-radius:6px;
    padding:5px 9px;font:13px system-ui;width:200px;outline:none}
  #ctrl label{display:flex;gap:5px;align-items:center;cursor:pointer;user-select:none;opacity:.9}
  #hud{top:10px;right:52px;opacity:.85}
  #filters{top:58px;left:10px;width:252px;max-height:calc(100vh - 150px);overflow:auto}
  #passes{bottom:22px;right:10px;max-height:48vh;overflow:auto;min-width:214px;max-width:264px;line-height:1.5}
  #passes b{font-size:11px;opacity:.55;text-transform:uppercase;letter-spacing:.04em;display:block;margin-bottom:6px}
  #passes .prow{display:flex;align-items:center;gap:7px;padding:1px 0;cursor:pointer}
  #passes .prow:hover{opacity:.75}
  #passes .dot{width:9px;height:9px;border-radius:50%;flex:none}
  #passes .pn{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #passes .pw{opacity:.85;font-variant-numeric:tabular-nums}
  #passes .pe{opacity:.55;width:32px;text-align:right;font-variant-numeric:tabular-nums}
  #passes .now{color:#33d17a;font-weight:600}
  #passes .fx{color:#ffd400;font-weight:600}
  #timectrl{bottom:14px;left:50%;transform:translateX(-50%);display:flex;align-items:center;gap:11px;padding:8px 14px}
  #timectrl input[type=range]{width:min(52vw,540px);accent-color:#c026d3;cursor:pointer}
  #timectrl .tl{font-variant-numeric:tabular-nums;min-width:56px;text-align:center;font-weight:600}
  #timectrl button{background:#fff2;border:1px solid #fff3;color:#fff;border-radius:6px;padding:4px 9px;cursor:pointer;font:12px system-ui}
  #timectrl button:hover{background:#fff3}
  .maplibregl-popup-content{font:13px system-ui;padding:8px 12px;color:#111}
/*SF_CSS*/
</style></head><body>
<div id="map"></div>
<div id="ctrl" class="panel">
  <input id="search" type="text" placeholder="\U0001f50d search satellite…" autocomplete="off">
  <label><input type="checkbox" id="lbl" checked> labels</label>
  <label><input type="checkbox" id="foot" checked> footprints</label>
  <label><input type="checkbox" id="globe"> globe</label>
</div>
<div id="hud" class="panel"><b id="count">…</b> sat · <span id="ago"></span> · <a href="/table" data-keepq="/table" style="color:#8ab4ff;text-decoration:none">▦ table</a></div>
<div id="filters" class="panel"></div>
<div id="passes" class="panel"></div>
<div id="timectrl" class="panel">
  <span class="tl" id="timelbl">now</span>
  <input id="time" type="range" min="-1440" max="1440" value="0" step="5">
  <button id="timenow">now</button>
</div>
<script>
//SF_JS
const GROUPS=SF.GROUPS;
const colorExpr=['match',['get','group']]; for(const [g,c] of GROUPS) colorExpr.push(g,c); colorExpr.push('#888');
const isFocus=['==',['get','focus'],1], byFocus=(a,b)=>['case',isFocus,a,b];
let lastSats=[],lastPasses=[],timeOffset=0; const $=id=>document.getElementById(id);
const fmtOffset=m=>{if(!m)return'now';const s=m<0?'−':'+';m=Math.abs(m);if(m>=1440)return s+(m/1440).toFixed(m%1440?1:0)+'d';const h=(m/60)|0,mm=m%60;return s+(h?h+'h ':'')+((mm||!h)?mm+'m':'');};
const map=new maplibregl.Map({container:'map',hash:true,
  style:{version:8,glyphs:'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]},
  center:[12,25],zoom:1.4,maxZoom:8,renderWorldCopies:true});
map.addControl(new maplibregl.NavigationControl(),'top-right');
function tracksFC(sats){const f=[];for(const s of sats){const tr=s.track;if(!tr||tr.length<2)continue;
  const N=tr.length-1;let seg=[[tr[0][1],tr[0][0]]];let segStart=0;
  const push=st=>f.push({type:'Feature',properties:{norad:s.norad,group:s.group,name:s.name,alt:s.alt,t:st/N,focus:s.focus?1:0},geometry:{type:'LineString',coordinates:seg}});
  for(let i=1;i<tr.length;i++){const lat=tr[i][0],lon=tr[i][1],plat=tr[i-1][0],plon=tr[i-1][1];
    if(Math.abs(lon-plon)>180){const east=lon<plon;const dl=east?(lon+360-plon):(lon-360-plon);
      const ef=east?180:-180,et=east?-180:180;const il=plat+(lat-plat)*((ef-plon)/dl);
      seg.push([ef,il]);push(segStart);seg=[[et,il]];segStart=i;}
    seg.push([lon,lat]);}
  if(seg.length>1)push(segStart);}
  return {type:'FeatureCollection',features:f};}
function obsFC(obs){return {type:'FeatureCollection',features:(obs||[]).map(o=>({type:'Feature',properties:{name:o.name},geometry:{type:'Point',coordinates:[o.lon,o.lat]}}))};}
function pointsFC(sats){return {type:'FeatureCollection',features:sats.map(s=>({type:'Feature',
  properties:{norad:s.norad,name:s.name,group:s.group,alt:s.alt_km,el:s.elevation,sunlit:s.sunlit?1:0,fp:s.footprint_km,up:(s.elevation>=0?1:0),focus:s.focus?1:0},
  geometry:{type:'Point',coordinates:[s.lon,s.lat]}}))};}
function circlePoly(lat,lon,km,n){n=n||48;const R=6371,d=km/R,la=lat*Math.PI/180,lo=lon*Math.PI/180,c=[];
  for(let i=0;i<=n;i++){const b=2*Math.PI*i/n;
    const l2=Math.asin(Math.sin(la)*Math.cos(d)+Math.cos(la)*Math.sin(d)*Math.cos(b));
    const o2=lo+Math.atan2(Math.sin(b)*Math.sin(d)*Math.cos(la),Math.cos(d)-Math.sin(la)*Math.sin(l2));
    c.push([o2*180/Math.PI,l2*180/Math.PI]);}
  return c;}
function footprintsFC(sats){const f=[];for(const s of sats){if(s.footprint_km==null)continue;
  f.push({type:'Feature',properties:{norad:s.norad,group:s.group,name:s.name,alt:s.alt_km,up:(s.elevation>=0?1:0),focus:s.focus?1:0},
    geometry:{type:'Polygon',coordinates:[circlePoly(s.lat,s.lon,s.footprint_km)]}});}
  return {type:'FeatureCollection',features:f};}
function applyFilters(){const vis=SF.visible(),flt=['in',['get','norad'],['literal',[...vis]]];  // one NORAD set drives every layer
  for(const l of ['sat-dots','sat-labels','tracks','footprint-fill','footprint-line']) if(map.getLayer(l)) map.setFilter(l,flt);
  $('count').textContent=(vis.size===lastSats.length?'':vis.size+'/')+lastSats.length;
  if($('search').value.trim().toLowerCase()!==SF.state().q)$('search').value=SF.state().q;  // after a reset
  renderPasses(vis);}
SF.init($('filters'),{map:true,onchange:applyFilters});
$('search').value=SF.state().q;
let last=0;
async function refresh(){try{const u='/api/satellites.json'+(timeOffset?('?t='+timeOffset):'');const d=await (await fetch(u)).json();lastSats=d.satellites||[];
  map.getSource('sats').setData(pointsFC(lastSats));
  map.getSource('footprints').setData(footprintsFC(lastSats));
  map.getSource('obs').setData(obsFC(d.observers));
  last=Date.now();SF.setSats(lastSats);applyFilters();
}catch(e){console.error(e);}}
async function refreshTracks(){try{const d=await(await fetch('/api/tracks.json')).json();
  map.getSource('tracks').setData(tracksFC(d.tracks||[]));applyFilters();
}catch(e){console.error('tracks',e);}}
async function refreshPasses(){try{const d=await(await fetch('/api/passes.json')).json();
  lastPasses=d.passes||[];SF.setPasses(lastPasses);applyFilters();
}catch(e){console.error('passes',e);}}
function renderPasses(vis){const now=Date.now()/1000;
  const ps=lastPasses.filter(p=>vis.has(p.norad)).sort((a,b)=>(b.focus?1:0)-(a.focus?1:0)||a.aos-b.aos);  // focus first
  const rows=ps.slice(0,16).map(p=>{const mins=Math.round((p.aos-now)/60);
    const when=p.up_now?'<span class="now">● now</span>':(mins<1?'in <1m':(mins<90?'in '+mins+'m':'in '+(mins/60).toFixed(1)+'h'));
    const col=(GROUPS.find(g=>g[0]===p.group)||[])[1]||'#888';
    const tip='max el '+(p.max_elev!=null?Math.round(p.max_elev)+'°':'?')+(p.duration_s?' · '+Math.round(p.duration_s/60)+' min':'')+' · footprint ~'+p.footprint_km+' km';
    return '<div class="prow" data-norad="'+p.norad+'" title="'+tip+'"><span class="dot" style="background:'+col+'"></span>'
      +'<span class="pn'+(p.focus?' fx':'')+'">'+(p.focus?'★ ':'')+p.name+'</span><span class="pw">'+when+'</span>'
      +'<span class="pe">'+(p.max_elev!=null?Math.round(p.max_elev)+'°':'')+'</span></div>';}).join('');
  $('passes').innerHTML='<b>next passes over observer</b>'+(rows||'<span style="opacity:.5">'+(lastPasses.length?'none match the filters':'none in next 24 h')+'</span>');
  $('passes').querySelectorAll('.prow').forEach(r=>r.onclick=()=>{const s=lastSats.find(x=>x.norad==r.dataset.norad);
    if(s)map.flyTo({center:[s.lon,s.lat],zoom:Math.max(map.getZoom(),3)});});}
setInterval(()=>{if(last)$('ago').textContent=Math.round((Date.now()-last)/1000)+'s ago';},1000);
$('search').addEventListener('input',()=>{SF.setQuery($('search').value);const q=SF.state().q;
  if(q){const m=lastSats.find(s=>s.name.toLowerCase().includes(q));if(m)map.flyTo({center:[m.lon,m.lat],zoom:Math.max(map.getZoom(),3)});}});
$('lbl').addEventListener('change',()=>map.setLayoutProperty('sat-labels','visibility',$('lbl').checked?'visible':'none'));
$('globe').addEventListener('change',()=>map.setProjection({type:$('globe').checked?'globe':'mercator'}));
$('foot').addEventListener('change',()=>{const v=$('foot').checked?'visible':'none';['footprint-fill','footprint-line'].forEach(l=>map.getLayer(l)&&map.setLayoutProperty(l,'visibility',v));});
let tThr=0;
$('time').addEventListener('input',()=>{timeOffset=+$('time').value;$('timelbl').textContent=fmtOffset(timeOffset);
  const n=Date.now();if(n-tThr>250){tThr=n;refresh();}});
$('time').addEventListener('change',()=>{timeOffset=+$('time').value;refresh();});
$('timenow').addEventListener('click',()=>{$('time').value=0;timeOffset=0;$('timelbl').textContent='now';refresh();});
map.on('load',()=>{
  map.addSource('footprints',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'footprint-fill',type:'fill',source:'footprints',paint:{'fill-color':colorExpr,'fill-opacity':['case',['==',['get','up'],1],0.5,0]}});
  map.addLayer({id:'footprint-line',type:'line',source:'footprints',paint:{'line-color':colorExpr,'line-width':1,'line-opacity':['case',['==',['get','up'],1],0.75,0.18]}});
  map.addSource('tracks',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addSource('sats',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'tracks',type:'line',source:'tracks',paint:{'line-color':['interpolate',['linear'],['get','t'],0,'#3b82f6',0.5,'#c026d3',1,'#ef4444'],'line-width':byFocus(2.8,1.3),'line-opacity':byFocus(.95,.6)}});
  // focus sats: bigger dot with a gold ring and a gold label, drawn on top
  map.addLayer({id:'sat-dots',type:'circle',source:'sats',layout:{'circle-sort-key':byFocus(1,0)},paint:{'circle-radius':byFocus(9,6),'circle-color':colorExpr,'circle-stroke-width':byFocus(3,2),'circle-stroke-color':byFocus('#ffd400','#fff')}});
  map.addLayer({id:'sat-labels',type:'symbol',source:'sats',layout:{'text-field':['get','name'],'text-font':['Open Sans Regular'],'text-size':byFocus(13,11),'text-offset':[0,1.1],'text-anchor':'top','text-allow-overlap':true},paint:{'text-color':byFocus('#ffd400','#fff'),'text-halo-color':'#000','text-halo-width':1.3}});
  map.addSource('obs',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'obs-dot',type:'circle',source:'obs',paint:{'circle-radius':7,'circle-color':'#ffd400','circle-stroke-width':2,'circle-stroke-color':'#000'}});
  map.addLayer({id:'obs-label',type:'symbol',source:'obs',layout:{'text-field':['get','name'],'text-font':['Open Sans Regular'],'text-size':12,'text-offset':[0,1.3],'text-anchor':'top','text-allow-overlap':true},paint:{'text-color':'#ffd400','text-halo-color':'#000','text-halo-width':1.6}});
  map.on('click','sat-dots',e=>{const p=e.features[0].properties;new maplibregl.Popup().setLngLat(e.lngLat)
    .setHTML('<b>'+p.name+'</b>'+(+p.focus?' <span style="color:#b45309">★ focus</span>':'')+'<br>group '+p.group+'<br>alt '+p.alt+' km · el '+p.el+'°'+(+p.sunlit?' · ☀ sunlit':'')+'<br>footprint ~'+Math.round(p.fp)+' km radius'+(+p.up?' · <b>over you now</b>':'')).addTo(map);});
  const hov=new maplibregl.Popup({closeButton:false,closeOnClick:false,offset:12});
  map.on('mouseenter','sat-dots',e=>{map.getCanvas().style.cursor='pointer';hov.setLngLat(e.lngLat).setHTML('<b>'+e.features[0].properties.name+'</b>').addTo(map);});
  map.on('mousemove','sat-dots',e=>{if(e.features.length)hov.setLngLat(e.lngLat).setHTML('<b>'+e.features[0].properties.name+'</b>');});
  map.on('mouseleave','sat-dots',()=>{map.getCanvas().style.cursor='';hov.remove();});
  refresh();refreshTracks();refreshPasses();setInterval(refresh,15000);setInterval(refreshTracks,180000);setInterval(refreshPasses,60000);
});
</script></body></html>"""


_TABLE_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>space-telemetry · tables</title>
<style>
  :root{color-scheme:dark}
  body{margin:0;background:#0d0d12;color:#e8e8ee;font:14px system-ui,-apple-system,sans-serif}
  header{position:sticky;top:0;background:#14141c;padding:12px 20px;display:flex;align-items:center;gap:16px;border-bottom:1px solid #ffffff14;z-index:2}
  header h1{font-size:15px;margin:0;font-weight:600}
  header nav{display:flex;gap:14px;margin-left:auto}
  header a{color:#8ab4ff;text-decoration:none}
  header a:hover{text-decoration:underline}
  header a.on{color:#e8e8ee;font-weight:600}
  .wrap{padding:6px 20px 40px;max-width:1180px;margin:0 auto}
  h2{font-size:12px;text-transform:uppercase;letter-spacing:.05em;opacity:.55;margin:26px 0 8px;display:flex;gap:10px;align-items:baseline}
  h2 .ago{margin-left:auto;font-weight:400;opacity:.6;text-transform:none;letter-spacing:0}
  .ov{overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
  th,td{text-align:left;padding:5px 10px;border-bottom:1px solid #ffffff0e;white-space:nowrap}
  th{font-size:11px;text-transform:uppercase;letter-spacing:.04em;opacity:.5;font-weight:600}
  td.num,th.num{text-align:right}
  tr:hover td{background:#ffffff08}
  .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:middle}
  .up{color:#4ade80}.down{opacity:.45}
  .star{color:#facc15}.good{color:#facc15;font-weight:600}tr.low td{opacity:.5}
/*SF_CSS*/
</style></head><body>
<header><h1>space-telemetry</h1>
  <nav><a href="/map" data-keepq="/map">map</a><a href="/table" class="on">tables</a><a href="/status">status</a><a href="/metrics">metrics</a></nav>
</header>
<div class="wrap">
  <div id="focus" style="display:none">
  <h2>Focus · pass plan <span id="fc"></span><span class="ago" id="fmeta"></span></h2>
  <div class="ov"><table><thead><tr><th>Satellite</th><th>AOS</th><th>LOS</th><th class="num">Duration</th><th class="num">Max el</th><th>Direction</th><th>Downlink</th></tr></thead><tbody id="ftb"></tbody></table></div>
  </div>
  <h2>Solar-system bodies <span id="bc"></span></h2>
  <div class="ov"><table><thead><tr><th>Body</th><th class="num">Alt</th><th class="num">Az</th><th class="num">Distance</th><th>Rise / set</th><th>Moon</th></tr></thead><tbody id="btb"></tbody></table></div>
  <div id="filters" class="sf-table"></div>
  <h2>Satellites over observer <span id="sc"></span><span class="ago" id="ago"></span></h2>
  <div class="ov"><table><thead><tr><th>Satellite</th><th>Group</th><th class="num">Alt km</th><th class="num">El</th><th class="num">Footprint</th><th>Sub-point</th><th>Next pass</th><th>Sun</th></tr></thead><tbody id="stb"></tbody></table></div>
  <h2>Upcoming passes over observer <span id="pc"></span></h2>
  <div class="ov"><table><thead><tr><th>Satellite</th><th>Group</th><th>AOS</th><th>LOS</th><th class="num">Duration</th><th class="num">Max el</th><th class="num">Footprint</th></tr></thead><tbody id="ptb"></tbody></table></div>
  <h2>Bright stars <span id="tc"></span><span class="ago" style="font-weight:400;opacity:.5;text-transform:none;letter-spacing:0">HYG catalog</span></h2>
  <div class="ov"><table><thead><tr><th>Star</th><th class="num">Mag</th><th class="num">Alt</th><th class="num">Az</th><th>Con</th><th class="num">Distance</th><th>Rise / set</th><th>Spectral</th></tr></thead><tbody id="ttb"></tbody></table></div>
</div>
<script>
//SF_JS
const GC=Object.fromEntries(SF.GROUPS);
const STAR='<span class="star">★</span> ';
const dir=a=>['N','NE','E','SE','S','SW','W','NW'][Math.round((((a%360)+360)%360)/45)%8];
const $=id=>document.getElementById(id);
const cap=s=>s.charAt(0).toUpperCase()+s.slice(1);
const hm=ts=>{if(!ts)return'—';return new Date(ts*1000).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});};
const inMin=ts=>{if(!ts)return'';const m=Math.round((ts-Date.now()/1000)/60);return m<0?'':(m<90?'in '+m+'m':'in '+(m/60).toFixed(1)+'h');};
const dist=km=>km>=1e6?(km/149597870.7).toFixed(3)+' AU':km.toLocaleString('en-US')+' km';
async function bodies(){try{const b=(await(await fetch('/api/bodies.json')).json()).bodies||[];
  $('bc').textContent=b.length?'· '+b.length:'';
  $('btb').innerHTML=b.map(x=>{const u=x.up?'up':'down';const moon=x.illum!=null?('◐ '+x.illum+'% · phase '+x.phase+'°'):'';
    return '<tr><td class="'+u+'">'+cap(x.name)+'</td><td class="num '+u+'">'+x.altitude.toFixed(1)+'°</td>'
      +'<td class="num">'+x.azimuth.toFixed(0)+'°</td><td class="num">'+dist(x.distance_km)+'</td>'
      +'<td>'+(x.up?'sets '+hm(x['set']):'rises '+hm(x.rise))+'</td><td>'+moon+'</td></tr>';}).join('')
      ||'<tr><td colspan=6 style="opacity:.5">none enabled</td></tr>';
}catch(e){console.error(e);}}
let sd=null,pd=null;  // last satellites + passes payloads, redrawn on every filter change
async function sats(){try{[sd,pd]=await Promise.all([fetch('/api/satellites.json').then(r=>r.json()),fetch('/api/passes.json').then(r=>r.json())]);
  $('ago').textContent='updated '+new Date().toLocaleTimeString();
  SF.setSats(sd.satellites||[]);SF.setPasses(pd.passes||[]);drawSats();
}catch(e){console.error(e);}}
function drawSats(){if(!sd||!pd)return;const vis=SF.visible(),all=sd.satellites||[];
  const s=all.filter(x=>vis.has(x.norad));const pm={};(pd.passes||[]).forEach(p=>pm[p.norad]=p);
  s.sort((a,b)=>(b.focus?1:0)-(a.focus?1:0)||b.elevation-a.elevation);  // focus sats pinned on top
  $('sc').textContent='· '+(s.length===all.length?all.length:s.length+' of '+all.length);
  $('stb').innerHTML=s.map(x=>{const p=pm[x.norad];const up=x.elevation>=0;
    const np=p?(p.up_now?'<span class="up">now</span>':(inMin(p.aos)+(p.max_elev!=null?' · '+Math.round(p.max_elev)+'°':''))):'—';
    return '<tr><td>'+(x.focus?STAR:'')+x.name+'</td><td><span class="dot" style="background:'+(GC[x.group]||'#888')+'"></span>'+x.group+'</td>'
      +'<td class="num">'+Math.round(x.alt_km)+'</td><td class="num '+(up?'up':'down')+'">'+x.elevation.toFixed(1)+'°</td>'
      +'<td class="num">'+x.footprint_km+'</td><td>'+x.lat.toFixed(1)+', '+x.lon.toFixed(1)+'</td>'
      +'<td>'+np+'</td><td>'+(x.sunlit?'☀':'')+'</td></tr>';}).join('')
    ||'<tr><td colspan=8 style="opacity:.5">'+(all.length?'no satellite matches the filters':'none tracked')+'</td></tr>';
  const ps=(pd.passes||[]).filter(p=>vis.has(p.norad));
  $('pc').textContent=ps.length?'· '+ps.length:'';
  $('ptb').innerHTML=ps.map(p=>{const col=GC[p.group]||'#888';
    const aos=p.up_now?'<span class="up">now</span>':(inMin(p.aos)+' · '+hm(p.aos));
    return '<tr><td>'+(p.focus?STAR:'')+p.name+'</td><td><span class="dot" style="background:'+col+'"></span>'+p.group+'</td>'
      +'<td>'+aos+'</td><td>'+hm(p['los'])+'</td><td class="num">'+(p.duration_s?Math.round(p.duration_s/60)+' min':'')+'</td>'
      +'<td class="num">'+(p.max_elev!=null?Math.round(p.max_elev)+'°':'')+'</td><td class="num">'+p.footprint_km+' km</td></tr>';}).join('')
    ||'<tr><td colspan=7 style="opacity:.5">'+((pd.passes||[]).length?'none match the filters':'none in next 24 h')+'</td></tr>';}
async function focus(){try{const d=await(await fetch('/api/focus.json')).json();const f=d.focus||[];
  $('focus').style.display=f.length?'':'none';if(!f.length)return;
  const rows=[];for(const s of f)for(const p of s.passes)rows.push([s,p]);
  rows.sort((a,b)=>a[1].aos-b[1].aos);
  $('fc').textContent='· '+f.map(s=>s.name).join(', ');
  $('fmeta').textContent='next '+d.lookahead_hours+' h over '+(d.observer||'observer')+' · ★ = peaks ≥ '+d.min_elevation+'°';
  $('ftb').innerHTML=rows.map(([s,p])=>{
    const aos=p.now?'<span class="up">now · '+Math.round(s.elevation)+'°</span>':(inMin(p.aos)+' · '+hm(p.aos));
    const dl=s.downlinks||[];const modes=[...new Set(dl.map(x=>x.mode).filter(Boolean))].join('/');
    return '<tr class="'+(p.good?'':'low')+'"><td><span class="dot" style="background:'+(GC[s.group]||'#888')+'"></span>'+(p.good?STAR:'')+s.name+'</td>'
      +'<td>'+aos+'</td><td>'+hm(p.los)+'</td><td class="num">'+Math.round(p.duration_s/60)+' min</td>'
      +'<td class="num'+(p.good?' good':'')+'">'+(p.max_elev!=null?Math.round(p.max_elev)+'°':'')+'</td>'
      +'<td>'+dir(p.aos_az)+' → '+dir(p.los_az)+'</td>'
      +'<td>'+(dl.length?dl.map(x=>x.mhz.toFixed(3)).join(' · ')+' MHz'+(modes?' '+modes:''):'')+'</td></tr>';}).join('')
    ||'<tr><td colspan=7 style="opacity:.5">no passes in the next '+d.lookahead_hours+' h</td></tr>';
}catch(e){console.error(e);}}
async function stars(){try{const t=(await(await fetch('/api/stars.json')).json()).stars||[];
  $('tc').textContent=t.length?'· '+t.length:'';
  $('ttb').innerHTML=t.map(x=>{const up=x.up;
    const rs=(x.rise==null&&x['set']==null)?(up?'always up':'never'):(up?'sets '+hm(x['set']):'rises '+hm(x.rise));
    return '<tr><td class="'+(up?'up':'down')+'">'+x.name+'</td><td class="num">'+x.mag.toFixed(2)+'</td>'
      +'<td class="num '+(up?'up':'down')+'">'+x.altitude.toFixed(1)+'°</td><td class="num">'+x.azimuth.toFixed(0)+'°</td>'
      +'<td>'+x.con+'</td><td class="num">'+(x.dist_ly!=null?x.dist_ly+' ly':'')+'</td>'
      +'<td>'+rs+'</td><td>'+(x.spect||'')+'</td></tr>';}).join('');
}catch(e){console.error(e);}}
SF.init($('filters'),{search:true,onchange:drawSats});
focus();bodies();sats();stars();setInterval(focus,30000);setInterval(sats,15000);setInterval(stars,15000);setInterval(bodies,30000);
</script></body></html>"""

_MAP_HTML = _MAP_HTML.replace("/*SF_CSS*/", _FILTER_CSS).replace("//SF_JS", _FILTER_JS)
_TABLE_HTML = _TABLE_HTML.replace("/*SF_CSS*/", _FILTER_CSS).replace("//SF_JS", _FILTER_JS)


def make_server(host: str, port: int, info_fn, satellites_fn=None, tracks_fn=None,
                passes_fn=None, bodies_fn=None, stars_fn=None, focus_fn=None) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "space-telemetry"

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            # gzip larger payloads (the /map track feed is big and rides a slow tunnel)
            if len(body) > 1400 and "gzip" in (self.headers.get("Accept-Encoding") or ""):
                body = gzip.compress(body, 5)
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Vary", "Accept-Encoding")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            path, _, query = self.path.partition("?")
            if path == "/metrics":
                self._send(200, generate_latest(REGISTRY), CONTENT_TYPE_LATEST)
            elif path in ("/health", "/healthz"):
                self._send(200, b'{"status": "ok"}\n', "application/json")
            elif path == "/status":
                self._send(200, (json.dumps(info_fn(), indent=2) + "\n").encode(), "application/json")
            elif path == "/":
                info = info_fn()
                wants_json = "format=json" in query or "application/json" in (self.headers.get("Accept") or "")
                if wants_json:
                    self._send(200, (json.dumps(info, indent=2) + "\n").encode(), "application/json")
                else:
                    self._send(200, _render_html(info).encode(), "text/html; charset=utf-8")
            elif path == "/map":
                self._send(200, _MAP_HTML.encode(), "text/html; charset=utf-8")
            elif path == "/table":
                self._send(200, _TABLE_HTML.encode(), "text/html; charset=utf-8")
            elif path == "/api/satellites.json":
                off = 0.0
                if query:
                    try:  # ?t=<minutes from now>, ±1 day, for the map time scrubber
                        off = max(-1440.0, min(1440.0, float(urllib.parse.parse_qs(query).get("t", ["0"])[0])))
                    except ValueError:
                        off = 0.0
                data = satellites_fn(off) if satellites_fn else {"satellites": []}
                self._send(200, json.dumps(data, separators=(",", ":")).encode(), "application/json")
            elif path == "/api/tracks.json":
                data = tracks_fn() if tracks_fn else {"tracks": []}
                self._send(200, json.dumps(data, separators=(",", ":")).encode(), "application/json")
            elif path == "/api/passes.json":
                data = passes_fn() if passes_fn else {"passes": []}
                self._send(200, json.dumps(data, separators=(",", ":")).encode(), "application/json")
            elif path == "/api/focus.json":
                data = focus_fn() if focus_fn else {"focus": []}
                self._send(200, json.dumps(data, separators=(",", ":")).encode(), "application/json")
            elif path == "/api/bodies.json":
                data = bodies_fn() if bodies_fn else {"bodies": []}
                self._send(200, json.dumps(data, separators=(",", ":")).encode(), "application/json")
            elif path == "/api/stars.json":
                data = stars_fn() if stars_fn else {"stars": []}
                self._send(200, json.dumps(data, separators=(",", ":")).encode(), "application/json")
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8")

        do_HEAD = do_GET

        def log_message(self, *args):  # keep logs quiet; scrapes are frequent
            pass

    return ThreadingHTTPServer((host, port), Handler)
