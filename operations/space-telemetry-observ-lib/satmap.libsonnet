// satmap.libsonnet — a Geomap of the tracked satellites' ground tracks.
//
// Two instant/table queries (track latitude + longitude, labelled by time offset
// -1h … +1h) are joined by (name, offset) and renamed to latitude/longitude, then
// plotted as markers. Uses the satellite_track_*_degrees metrics (offset label).
local panel = import 'custom/panel.libsonnet';
local query = import 'custom/query.libsonnet';

function(cfg)
  local q(refid, metric) =
    query.prometheus.new(cfg.datasource, metric + '{' + cfg.jobSelector + '}')
    + { spec+: { refId: refid, query+: { spec+: { format: 'table', instant: true, range: false } } } };

  panel.base('geomap', 'Satellite ground track')
  + panel.withDescription('Sub-satellite point at each time offset (-1h … +1h) for the tracked satellites.')
  + panel.withTargets([
    q('lat', 'satellite_track_latitude_degrees'),
    q('lon', 'satellite_track_longitude_degrees'),
  ])
  + panel.withTransformations([
    { id: 'joinByLabels', options: { value: 'Value', join: ['name', 'offset'] } },
    {
      id: 'organize',
      options: {
        renameByName: {
          satellite_track_latitude_degrees: 'latitude',
          satellite_track_longitude_degrees: 'longitude',
        },
      },
    },
  ])
  + panel.withOptions({
    view: { id: 'zero', lat: 0, lon: 0, zoom: 1 },
    basemap: { type: 'default', name: 'Basemap' },
    controls: { showZoom: true, mouseWheelZoom: true, showAttribution: true, showScale: false, showMeasure: false, showDebug: false },
    tooltip: { mode: 'details' },
    layers: [
      {
        type: 'markers',
        name: 'ground track',
        location: { mode: 'coords', latitude: 'latitude', longitude: 'longitude' },
        config: {
          showLegend: true,
          style: {
            size: { fixed: 6 },
            color: { fixed: 'dark-blue' },
            opacity: 0.8,
            symbol: { fixed: 'img/icons/marker/circle.svg' },
            textConfig: { fontSize: 10, offsetX: 0, offsetY: -9, textAlign: 'center', textBaseline: 'middle' },
          },
          text: { field: 'offset', fixed: '' },
        },
      },
    ],
  })
