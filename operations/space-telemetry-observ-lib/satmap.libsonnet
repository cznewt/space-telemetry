// satmap.libsonnet — current satellite positions, as a Geomap and a Table.
//
// One instant table query per field (sub-point lat/lon, elevation, altitude), reduced to
// (name), joined by the `name` FIELD (joinByField — joinByLabels does not work in this
// Grafana). A single `organize` step renames the value columns and drops the per-query
// Time columns (filterFieldsByName was too fragile and broke the map).
local panel = import 'custom/panel.libsonnet';
local query = import 'custom/query.libsonnet';

local q(cfg, refid, metric) =
  query.prometheus.new(cfg.datasource, 'max by (name) (' + metric + '{' + cfg.observerSelector + '})')
  + query.prometheus.withRefId(refid)
  + query.prometheus.withInstant(true)
  + query.prometheus.withFormat('table');

local latlon(cfg) = [
  q(cfg, 'lat', 'satellite_subpoint_latitude_degrees'),
  q(cfg, 'lon', 'satellite_subpoint_longitude_degrees'),
];
local full(cfg) = latlon(cfg) + [
  q(cfg, 'elev', 'satellite_elevation_degrees'),
  q(cfg, 'alt', 'satellite_altitude_meters'),
];

local joinName = { id: 'joinByField', options: { byField: 'name', mode: 'outer' } };
// instant queries still carry a Time field; joinByField fans it out per refId.
local timeCols = { Time: true, 'Time #lat': true, 'Time #lon': true, 'Time #elev': true, 'Time #alt': true };
local organize(rename) = { id: 'organize', options: { renameByName: rename, excludeByName: timeCols } };

{
  table(cfg)::
    panel.base('table', 'Satellite positions')
    + panel.withDescription('Current sub-satellite point, elevation and altitude per tracked satellite.')
    + panel.withTargets(full(cfg))
    + panel.withTransformations([
      joinName,
      organize({ 'Value #lat': 'latitude', 'Value #lon': 'longitude', 'Value #elev': 'elevation', 'Value #alt': 'altitude' }),
    ]),

  map(cfg)::
    panel.base('geomap', 'Satellite positions — map')
    + panel.withDescription('Current sub-satellite point of each tracked satellite.')
    + panel.withTargets(latlon(cfg))
    + panel.withTransformations([
      joinName,
      organize({ 'Value #lat': 'latitude', 'Value #lon': 'longitude' }),
    ])
    + panel.withOptions({
      view: { id: 'zero', lat: 0, lon: 0, zoom: 1 },
      basemap: { type: 'default', name: 'Basemap' },
      controls: { showZoom: true, mouseWheelZoom: true, showAttribution: true, showScale: false, showMeasure: false, showDebug: false },
      tooltip: { mode: 'details' },
      layers: [
        {
          type: 'markers',
          name: 'satellites',
          location: { mode: 'auto' },
          config: {
            showLegend: true,
            style: {
              size: { fixed: 7 },
              color: { fixed: 'dark-red' },
              opacity: 0.9,
              symbol: { fixed: 'img/icons/marker/circle.svg' },
              textConfig: { fontSize: 10, offsetY: -10, textAlign: 'center', textBaseline: 'middle' },
            },
            text: { field: 'name', fixed: '' },
          },
        },
      ],
    }),
}
