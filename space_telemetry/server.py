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
        sat_html = (
            "<h2>Satellites</h2>"
            f"<p>groups <code>{groups}</code> · watchlist <code>{watch}</code></p>"
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
        '<li><a href="/metrics">/metrics</a> — Prometheus metrics</li>'
        '<li><a href="/status">/status</a> — status as JSON</li>'
        '<li><a href="/health">/health</a> — health check (alias <code>/healthz</code>)</li>'
        '<li><a href="/api/satellites.json">/api/satellites.json</a> — live positions + ground tracks</li>'
        "</ul></body></html>"
    )


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
  #legend{bottom:22px;left:10px;line-height:1.9;min-width:152px}
  #legend b{font-size:11px;opacity:.55;text-transform:uppercase;letter-spacing:.04em}
  #legend .row{display:flex;align-items:center;gap:8px;cursor:pointer;user-select:none}
  #legend .row.off{opacity:.38}
  #legend .dot{width:11px;height:11px;border-radius:50%;flex:none}
  #legend .ct{opacity:.55;margin-left:auto;padding-left:12px}
  #passes{bottom:22px;right:10px;max-height:48vh;overflow:auto;min-width:214px;max-width:264px;line-height:1.5}
  #passes b{font-size:11px;opacity:.55;text-transform:uppercase;letter-spacing:.04em;display:block;margin-bottom:6px}
  #passes .prow{display:flex;align-items:center;gap:7px;padding:1px 0;cursor:pointer}
  #passes .prow:hover{opacity:.75}
  #passes .dot{width:9px;height:9px;border-radius:50%;flex:none}
  #passes .pn{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #passes .pw{opacity:.85;font-variant-numeric:tabular-nums}
  #passes .pe{opacity:.55;width:32px;text-align:right;font-variant-numeric:tabular-nums}
  #passes .now{color:#33d17a;font-weight:600}
  .maplibregl-popup-content{font:13px system-ui;padding:8px 12px;color:#111}
</style></head><body>
<div id="map"></div>
<div id="ctrl" class="panel">
  <input id="search" type="text" placeholder="\U0001f50d search satellite…" autocomplete="off">
  <label><input type="checkbox" id="lbl" checked> labels</label>
  <label><input type="checkbox" id="foot" checked> footprints</label>
  <label><input type="checkbox" id="globe"> globe</label>
</div>
<div id="hud" class="panel"><b id="count">…</b> sat · <span id="ago"></span></div>
<div id="legend" class="panel"></div>
<div id="passes" class="panel"></div>
<script>
const GROUPS=[['iss','#e02b2b'],['css','#ff8f1f'],['weather','#3b82f6'],['noaa','#22c55e'],['goes','#a855f7'],['stations','#9aa0aa']];
const colorExpr=['match',['get','group']]; for(const [g,c] of GROUPS) colorExpr.push(g,c); colorExpr.push('#888');
const hidden=new Set(); let lastSats=[]; const $=id=>document.getElementById(id);
const map=new maplibregl.Map({container:'map',hash:true,
  style:{version:8,glyphs:'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]},
  center:[12,25],zoom:1.4,maxZoom:8,renderWorldCopies:true});
map.addControl(new maplibregl.NavigationControl(),'top-right');
function tracksFC(sats){const f=[];for(const s of sats){const tr=s.track;if(!tr||tr.length<2)continue;
  const N=tr.length-1;let seg=[[tr[0][1],tr[0][0]]];let segStart=0;
  const push=st=>f.push({type:'Feature',properties:{group:s.group,name:s.name,t:st/N},geometry:{type:'LineString',coordinates:seg}});
  for(let i=1;i<tr.length;i++){const lat=tr[i][0],lon=tr[i][1],plat=tr[i-1][0],plon=tr[i-1][1];
    if(Math.abs(lon-plon)>180){const east=lon<plon;const dl=east?(lon+360-plon):(lon-360-plon);
      const ef=east?180:-180,et=east?-180:180;const il=plat+(lat-plat)*((ef-plon)/dl);
      seg.push([ef,il]);push(segStart);seg=[[et,il]];segStart=i;}
    seg.push([lon,lat]);}
  if(seg.length>1)push(segStart);}
  return {type:'FeatureCollection',features:f};}
function obsFC(obs){return {type:'FeatureCollection',features:(obs||[]).map(o=>({type:'Feature',properties:{name:o.name},geometry:{type:'Point',coordinates:[o.lon,o.lat]}}))};}
function pointsFC(sats){return {type:'FeatureCollection',features:sats.map(s=>({type:'Feature',
  properties:{name:s.name,group:s.group,alt:s.alt_km,el:s.elevation,sunlit:s.sunlit?1:0,fp:s.footprint_km,up:(s.elevation>=0?1:0)},
  geometry:{type:'Point',coordinates:[s.lon,s.lat]}}))};}
function circlePoly(lat,lon,km,n){n=n||48;const R=6371,d=km/R,la=lat*Math.PI/180,lo=lon*Math.PI/180,c=[];
  for(let i=0;i<=n;i++){const b=2*Math.PI*i/n;
    const l2=Math.asin(Math.sin(la)*Math.cos(d)+Math.cos(la)*Math.sin(d)*Math.cos(b));
    const o2=lo+Math.atan2(Math.sin(b)*Math.sin(d)*Math.cos(la),Math.cos(d)-Math.sin(la)*Math.sin(l2));
    c.push([o2*180/Math.PI,l2*180/Math.PI]);}
  return c;}
function footprintsFC(sats){const f=[];for(const s of sats){if(s.footprint_km==null)continue;
  f.push({type:'Feature',properties:{group:s.group,name:s.name,up:(s.elevation>=0?1:0)},
    geometry:{type:'Polygon',coordinates:[circlePoly(s.lat,s.lon,s.footprint_km)]}});}
  return {type:'FeatureCollection',features:f};}
function applyFilters(){const groups=GROUPS.map(([g])=>g).filter(g=>!hidden.has(g));
  const q=$('search').value.trim().toLowerCase();
  const gf=['in',['get','group'],['literal',groups]];
  const flt=q?['all',gf,['in',q,['downcase',['get','name']]]]:gf;
  for(const l of ['sat-dots','sat-labels','tracks','footprint-fill','footprint-line']) if(map.getLayer(l)) map.setFilter(l,flt);}
let last=0;
async function refresh(){try{const d=await (await fetch('/api/satellites.json')).json();lastSats=d.satellites||[];
  map.getSource('sats').setData(pointsFC(lastSats));
  map.getSource('footprints').setData(footprintsFC(lastSats));
  map.getSource('obs').setData(obsFC(d.observers));
  $('count').textContent=lastSats.length;last=Date.now();
  const cnt={};for(const s of lastSats)cnt[s.group]=(cnt[s.group]||0)+1;
  $('legend').innerHTML='<b>groups · click to hide</b>'+GROUPS.filter(([g])=>cnt[g]).map(([g,c])=>
    '<div class="row'+(hidden.has(g)?' off':'')+'" data-g="'+g+'"><span class="dot" style="background:'+c+'"></span>'+g+'<span class="ct">'+cnt[g]+'</span></div>').join('');
  $('legend').querySelectorAll('.row').forEach(r=>r.onclick=()=>{const g=r.dataset.g;hidden.has(g)?hidden.delete(g):hidden.add(g);r.classList.toggle('off');applyFilters();});
  applyFilters();
}catch(e){console.error(e);}}
async function refreshTracks(){try{const d=await(await fetch('/api/tracks.json')).json();
  map.getSource('tracks').setData(tracksFC(d.tracks||[]));applyFilters();
}catch(e){console.error('tracks',e);}}
async function refreshPasses(){try{const d=await(await fetch('/api/passes.json')).json();const now=Date.now()/1000;
  const ps=d.passes||[];
  const rows=ps.slice(0,16).map(p=>{const mins=Math.round((p.aos-now)/60);
    const when=p.up_now?'<span class="now">● now</span>':(mins<1?'in <1m':(mins<90?'in '+mins+'m':'in '+(mins/60).toFixed(1)+'h'));
    const col=(GROUPS.find(g=>g[0]===p.group)||[])[1]||'#888';
    const tip='max el '+(p.max_elev!=null?Math.round(p.max_elev)+'°':'?')+(p.duration_s?' · '+Math.round(p.duration_s/60)+' min':'')+' · footprint ~'+p.footprint_km+' km';
    return '<div class="prow" data-norad="'+p.norad+'" title="'+tip+'"><span class="dot" style="background:'+col+'"></span>'
      +'<span class="pn">'+p.name+'</span><span class="pw">'+when+'</span>'
      +'<span class="pe">'+(p.max_elev!=null?Math.round(p.max_elev)+'°':'')+'</span></div>';}).join('');
  $('passes').innerHTML='<b>next passes over observer</b>'+(rows||'<span style="opacity:.5">none in next 24 h</span>');
  $('passes').querySelectorAll('.prow').forEach(r=>r.onclick=()=>{const s=lastSats.find(x=>x.norad==r.dataset.norad);
    if(s)map.flyTo({center:[s.lon,s.lat],zoom:Math.max(map.getZoom(),3)});});
}catch(e){console.error('passes',e);}}
setInterval(()=>{if(last)$('ago').textContent=Math.round((Date.now()-last)/1000)+'s ago';},1000);
$('search').addEventListener('input',()=>{applyFilters();const q=$('search').value.trim().toLowerCase();
  if(q){const m=lastSats.find(s=>s.name.toLowerCase().includes(q));if(m)map.flyTo({center:[m.lon,m.lat],zoom:Math.max(map.getZoom(),3)});}});
$('lbl').addEventListener('change',()=>map.setLayoutProperty('sat-labels','visibility',$('lbl').checked?'visible':'none'));
$('globe').addEventListener('change',()=>map.setProjection({type:$('globe').checked?'globe':'mercator'}));
$('foot').addEventListener('change',()=>{const v=$('foot').checked?'visible':'none';['footprint-fill','footprint-line'].forEach(l=>map.getLayer(l)&&map.setLayoutProperty(l,'visibility',v));});
map.on('load',()=>{
  map.addSource('footprints',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'footprint-fill',type:'fill',source:'footprints',paint:{'fill-color':colorExpr,'fill-opacity':['case',['==',['get','up'],1],0.5,0]}});
  map.addLayer({id:'footprint-line',type:'line',source:'footprints',paint:{'line-color':colorExpr,'line-width':1,'line-opacity':['case',['==',['get','up'],1],0.75,0.18]}});
  map.addSource('tracks',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addSource('sats',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'tracks',type:'line',source:'tracks',paint:{'line-color':['interpolate',['linear'],['get','t'],0,'#3b82f6',0.5,'#c026d3',1,'#ef4444'],'line-width':1.3,'line-opacity':.6}});
  map.addLayer({id:'sat-dots',type:'circle',source:'sats',paint:{'circle-radius':6,'circle-color':colorExpr,'circle-stroke-width':2,'circle-stroke-color':'#fff'}});
  map.addLayer({id:'sat-labels',type:'symbol',source:'sats',layout:{'text-field':['get','name'],'text-font':['Open Sans Regular'],'text-size':11,'text-offset':[0,1.1],'text-anchor':'top','text-allow-overlap':true},paint:{'text-color':'#fff','text-halo-color':'#000','text-halo-width':1.3}});
  map.addSource('obs',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'obs-dot',type:'circle',source:'obs',paint:{'circle-radius':7,'circle-color':'#ffd400','circle-stroke-width':2,'circle-stroke-color':'#000'}});
  map.addLayer({id:'obs-label',type:'symbol',source:'obs',layout:{'text-field':['get','name'],'text-font':['Open Sans Regular'],'text-size':12,'text-offset':[0,1.3],'text-anchor':'top','text-allow-overlap':true},paint:{'text-color':'#ffd400','text-halo-color':'#000','text-halo-width':1.6}});
  map.on('click','sat-dots',e=>{const p=e.features[0].properties;new maplibregl.Popup().setLngLat(e.lngLat)
    .setHTML('<b>'+p.name+'</b><br>group '+p.group+'<br>alt '+p.alt+' km · el '+p.el+'°'+(+p.sunlit?' · ☀ sunlit':'')+'<br>footprint ~'+Math.round(p.fp)+' km radius'+(+p.up?' · <b>over you now</b>':'')).addTo(map);});
  const hov=new maplibregl.Popup({closeButton:false,closeOnClick:false,offset:12});
  map.on('mouseenter','sat-dots',e=>{map.getCanvas().style.cursor='pointer';hov.setLngLat(e.lngLat).setHTML('<b>'+e.features[0].properties.name+'</b>').addTo(map);});
  map.on('mousemove','sat-dots',e=>{if(e.features.length)hov.setLngLat(e.lngLat).setHTML('<b>'+e.features[0].properties.name+'</b>');});
  map.on('mouseleave','sat-dots',()=>{map.getCanvas().style.cursor='';hov.remove();});
  refresh();refreshTracks();refreshPasses();setInterval(refresh,15000);setInterval(refreshTracks,180000);setInterval(refreshPasses,60000);
});
</script></body></html>"""


def make_server(host: str, port: int, info_fn, satellites_fn=None, tracks_fn=None,
                passes_fn=None) -> ThreadingHTTPServer:
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
            elif path == "/api/satellites.json":
                data = satellites_fn() if satellites_fn else {"satellites": []}
                self._send(200, json.dumps(data, separators=(",", ":")).encode(), "application/json")
            elif path == "/api/tracks.json":
                data = tracks_fn() if tracks_fn else {"tracks": []}
                self._send(200, json.dumps(data, separators=(",", ":")).encode(), "application/json")
            elif path == "/api/passes.json":
                data = passes_fn() if passes_fn else {"passes": []}
                self._send(200, json.dumps(data, separators=(",", ":")).encode(), "application/json")
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8")

        do_HEAD = do_GET

        def log_message(self, *args):  # keep logs quiet; scrapes are frequent
            pass

    return ThreadingHTTPServer((host, port), Handler)
