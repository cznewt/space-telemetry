// satmap.libsonnet — current satellite positions, as a Geomap and a Table.
//
// The geomap colours markers by group. Geomap can only colour NUMERIC fields (a string
// group falls back to numeric thresholds), so we encode the group as a numeric id in
// PromQL (0=iss … 5=stations) and give each id a colour + legend text via value mappings
// — that drives both the marker colour and the map legend. The table keeps the group as
// a readable string. Joined by `name` (joinByField; joinByLabels does not work here).
local panel = import 'custom/panel.libsonnet';
local query = import 'custom/query.libsonnet';

local q(cfg, refid, metric) =
  query.prometheus.new(cfg.datasource, 'max by (name) (' + metric + '{' + cfg.satSelector + '})')
  + query.prometheus.withRefId(refid)
  + query.prometheus.withInstant(true)
  + query.prometheus.withFormat('table');

// group order = numeric id (0..5) used for the map colour.
local GROUPS = [['iss', '0'], ['css', '1'], ['weather', '2'], ['noaa', '3'], ['goes', '4'], ['stations', '5']];

// per-satellite numeric group id: `satellite_info{group=g} * id`, OR-ed across groups.
local qgrpid(cfg) =
  local term(p) = 'satellite_info{group="' + p[0] + '", ' + cfg.jobSelector + '} * ' + p[1];
  query.prometheus.new(cfg.datasource, 'max by (name) (' + std.join(' or ', [term(p) for p in GROUPS]) + ')')
  + query.prometheus.withRefId('grp')
  + query.prometheus.withInstant(true)
  + query.prometheus.withFormat('table');

// group as a string (for the table).
local qgrpname(cfg) =
  query.prometheus.new(cfg.datasource, 'max by (name, group) (satellite_info{' + cfg.jobSelector + '})')
  + query.prometheus.withRefId('grp')
  + query.prometheus.withInstant(true)
  + query.prometheus.withFormat('table');

local latlon(cfg) = [
  q(cfg, 'lat', 'satellite_subpoint_latitude_degrees'),
  q(cfg, 'lon', 'satellite_subpoint_longitude_degrees'),
];

local joinName = { id: 'joinByField', options: { byField: 'name', mode: 'outer' } };
local timeCols = { Time: true, 'Time #lat': true, 'Time #lon': true, 'Time #elev': true, 'Time #alt': true, 'Time #grp': true };

// group id -> colour + legend text (numeric value mappings). Also used by the pie.
local groupMappings = [{
  type: 'value',
  options: {
    '0': { color: 'red', text: 'iss', index: 0 },
    '1': { color: 'orange', text: 'css', index: 1 },
    '2': { color: 'blue', text: 'weather', index: 2 },
    '3': { color: 'green', text: 'noaa', index: 3 },
    '4': { color: 'purple', text: 'goes', index: 4 },
    '5': { color: 'semi-dark-gray', text: 'stations', index: 5 },
  },
}];
local groupOverrides = [
  { matcher: { id: 'byName', options: o.name }, properties: [{ id: 'color', value: { mode: 'fixed', fixedColor: o.color } }] }
  for o in [
    { name: 'iss', color: 'red' }, { name: 'css', color: 'orange' }, { name: 'weather', color: 'blue' },
    { name: 'noaa', color: 'green' }, { name: 'goes', color: 'purple' }, { name: 'stations', color: 'semi-dark-gray' },
  ]
];

{
  table(cfg)::
    panel.base('table', 'Satellite positions')
    + panel.withDescription('Current sub-satellite point, elevation, altitude and group per tracked satellite.')
    + panel.withTargets(latlon(cfg) + [
      q(cfg, 'elev', 'satellite_elevation_degrees'),
      q(cfg, 'alt', 'satellite_altitude_meters'),
      qgrpname(cfg),
    ])
    + panel.withTransformations([
      joinName,
      { id: 'organize', options: {
        renameByName: { 'Value #lat': 'latitude', 'Value #lon': 'longitude', 'Value #elev': 'elevation', 'Value #alt': 'altitude' },
        excludeByName: timeCols { 'Value #grp': true },
      } },
    ]),

  map(cfg)::
    panel.base('geomap', 'Satellite positions — map')
    + panel.withDescription('Current sub-satellite point of each tracked satellite, coloured and legended by group.')
    + panel.withTargets(latlon(cfg) + [qgrpid(cfg)])
    + panel.withTransformations([
      joinName,
      { id: 'organize', options: {
        renameByName: { 'Value #lat': 'latitude', 'Value #lon': 'longitude', 'Value #grp': 'group' },
        excludeByName: timeCols,
      } },
    ])
    // geomap colours numeric fields by THRESHOLDS (value mappings are ignored for
    // colour); step boundaries at .5 put each group id in its own colour band.
    + panel.withFieldConfigDefaults({ color: { mode: 'thresholds' } })
    + panel.withThresholds([
      { value: null, color: 'red' },            // 0 iss
      { value: 0.5, color: 'orange' },          // 1 css
      { value: 1.5, color: 'blue' },            // 2 weather
      { value: 2.5, color: 'green' },           // 3 noaa
      { value: 3.5, color: 'purple' },          // 4 goes
      { value: 4.5, color: 'semi-dark-gray' },  // 5 stations
    ])
    + panel.withMappings(groupMappings)
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
              color: { field: 'group' },  // numeric group id -> colour via value mappings
              opacity: 0.9,
              symbol: { fixed: 'img/icons/marker/circle.svg' },
              text: { mode: 'field', field: 'name', fixed: '' },
              textConfig: { fontSize: 10, offsetX: 0, offsetY: -12, textAlign: 'center', textBaseline: 'bottom' },
            },
          },
        },
      ],
    }),

  // Pie of satellites per group, coloured to match the map (a second, always-working legend).
  bygroup(cfg)::
    panel.base('pieChart', 'By group')
    + panel.withDescription('Tracked satellites per group.')
    + panel.withTargets([
      query.prometheus.new(cfg.datasource, 'count by (group) (satellite_info{' + cfg.jobSelector + '})')
      + query.prometheus.withRefId('A')
      + query.prometheus.withInstant(true)
      + query.prometheus.withLegendFormat('{{group}}'),
    ])
    + panel.withOverrides(groupOverrides)
    + panel.withOptions({
      legend: { showLegend: true, placement: 'right', displayMode: 'table', values: ['value'] },
      pieType: 'donut',
      reduceOptions: { calcs: ['lastNotNull'], fields: '', values: false },
    }),
}
