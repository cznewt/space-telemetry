"""HTTP server: /metrics (Prometheus), / (info page), /status (JSON), /health(z).

``prometheus_client.start_http_server`` answers every path with metrics; this
threading server routes them explicitly and adds a human-readable index that
reflects the collectors (solar-system + celestial bodies, satellites, space weather)
and every configured observer.
"""

from __future__ import annotations

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
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet">
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  html,body,#map{height:100%;margin:0}
  #hud,#legend{position:absolute;background:rgba(18,18,24,.85);color:#eee;
    font:13px system-ui,-apple-system,sans-serif;padding:7px 12px;border-radius:8px;z-index:1}
  #hud{top:10px;left:10px}
  #legend{bottom:22px;left:10px;line-height:1.75}
  #legend b{font-size:11px;opacity:.6;text-transform:uppercase;letter-spacing:.05em}
  #legend .row{display:flex;align-items:center;gap:7px}
  #legend .dot{width:11px;height:11px;border-radius:50%}
  .maplibregl-popup-content{font:13px system-ui;padding:8px 12px;color:#111}
</style></head><body>
<div id="map"></div>
<div id="hud">\U0001f6f0️ space-telemetry · <b id="count">…</b> satellites · <span id="ago"></span></div>
<div id="legend"></div>
<script>
const GROUPS=[['iss','#e02b2b'],['css','#ff8f1f'],['weather','#3b82f6'],['noaa','#22c55e'],['goes','#a855f7'],['stations','#9aa0aa']];
const colorExpr=['match',['get','group']]; for(const [g,c] of GROUPS) colorExpr.push(g,c); colorExpr.push('#888');
const map=new maplibregl.Map({container:'map',hash:true,
  style:{version:8,sources:{osm:{type:'raster',tiles:['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    tileSize:256,attribution:'© OpenStreetMap contributors'}},layers:[{id:'osm',type:'raster',source:'osm'}]},
  center:[12,25],zoom:1.4,maxZoom:8,renderWorldCopies:true});
map.addControl(new maplibregl.NavigationControl(),'top-right');
function tracksFC(sats){const f=[];for(const s of sats){if(!s.track||s.track.length<2)continue;let seg=[],prev=null;
  for(const [lat,lon] of s.track){if(prev!==null&&Math.abs(lon-prev)>180){if(seg.length>1)f.push({type:'Feature',properties:{group:s.group},geometry:{type:'LineString',coordinates:seg}});seg=[];}
    seg.push([lon,lat]);prev=lon;}
  if(seg.length>1)f.push({type:'Feature',properties:{group:s.group},geometry:{type:'LineString',coordinates:seg}});}
  return {type:'FeatureCollection',features:f};}
function pointsFC(sats){return {type:'FeatureCollection',features:sats.map(s=>({type:'Feature',
  properties:{name:s.name,group:s.group,alt:s.alt_km,el:s.elevation,sunlit:s.sunlit?1:0},
  geometry:{type:'Point',coordinates:[s.lon,s.lat]}}))};}
let last=0;
async function refresh(){try{const d=await (await fetch('/api/satellites.json')).json();const sats=d.satellites||[];
  map.getSource('tracks').setData(tracksFC(sats));map.getSource('sats').setData(pointsFC(sats));
  document.getElementById('count').textContent=sats.length;last=Date.now();
  const cnt={};for(const s of sats)cnt[s.group]=(cnt[s.group]||0)+1;
  document.getElementById('legend').innerHTML='<b>groups</b>'+GROUPS.filter(([g])=>cnt[g]).map(([g,c])=>
    '<div class="row"><span class="dot" style="background:'+c+'"></span>'+g+' <span style="opacity:.55">'+cnt[g]+'</span></div>').join('');
}catch(e){console.error(e);}}
setInterval(()=>{if(last){document.getElementById('ago').textContent=Math.round((Date.now()-last)/1000)+'s ago';}},1000);
map.on('load',()=>{
  map.addSource('tracks',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addSource('sats',{type:'geojson',data:{type:'FeatureCollection',features:[]}});
  map.addLayer({id:'tracks',type:'line',source:'tracks',paint:{'line-color':colorExpr,'line-width':1.3,'line-opacity':.5}});
  map.addLayer({id:'sat-dots',type:'circle',source:'sats',paint:{'circle-radius':5,'circle-color':colorExpr,'circle-stroke-width':1,'circle-stroke-color':'#111'}});
  map.addLayer({id:'sat-labels',type:'symbol',source:'sats',layout:{'text-field':['get','name'],'text-size':11,'text-offset':[0,1.1],'text-anchor':'top','text-optional':true},paint:{'text-color':'#fff','text-halo-color':'#000','text-halo-width':1.3}});
  map.on('click','sat-dots',e=>{const p=e.features[0].properties;new maplibregl.Popup().setLngLat(e.lngLat)
    .setHTML('<b>'+p.name+'</b><br>group '+p.group+'<br>alt '+p.alt+' km · el '+p.el+'°'+(+p.sunlit?' · ☀ sunlit':'')).addTo(map);});
  map.on('mouseenter','sat-dots',()=>map.getCanvas().style.cursor='pointer');
  map.on('mouseleave','sat-dots',()=>map.getCanvas().style.cursor='');
  refresh();setInterval(refresh,15000);
});
</script></body></html>"""


def make_server(host: str, port: int, info_fn, satellites_fn=None) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "space-telemetry"

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
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
                self._send(200, json.dumps(data).encode(), "application/json")
            else:
                self._send(404, b"not found\n", "text/plain; charset=utf-8")

        do_HEAD = do_GET

        def log_message(self, *args):  # keep logs quiet; scrapes are frequent
            pass

    return ThreadingHTTPServer((host, port), Handler)
