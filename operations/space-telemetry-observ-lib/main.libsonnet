// observ-viz pack for space-telemetry (built on cznewt/observ-viz).
//
// Renders THREE dashboards — Space Weather, Satellites, Bodies & Stars — each with its
// own $job/$observer plus a per-dashboard multi-select ($name for satellites, $body for
// bodies) driven by the pack's native varMetric/varLabels. Satellites carries the
// positions map + table as extra tabs.
local pack = import 'libs/common-lib/pack.libsonnet';
local satmap = import 'satmap.libsonnet';

{
  new(config={}):
    local cfg = (import 'config.libsonnet') + config;
    local s = cfg.signals.space_telemetry;
    local allSignals = { ['space_telemetry_' + k]: s[k] for k in std.objectFields(s) };

    // Per-dashboard configs. varMetric drives $job; varLabels add cascading multi-selects.
    local weatherCfg = cfg { uid: 'space-telemetry-weather', dashboardTitle: 'Space Weather', dashboardTags: ['space-telemetry', 'space-weather'], varMetric: 'space_weather_planetary_k_index', varLabels: [] };
    // observer -> group cascade (drop the $name cascade: $group=$__all does not expand
    // inside the nested $name query, which pinned everything to the first group).
    local satCfg = cfg { uid: 'space-telemetry-satellites', dashboardTitle: 'Satellites', dashboardTags: ['space-telemetry', 'satellites'], varMetric: 'satellite_altitude_meters', varLabels: ['observer', 'group'] };
    local bodyCfg = cfg { uid: 'space-telemetry-bodies', dashboardTitle: 'Bodies & Stars', dashboardTags: ['space-telemetry', 'astronomy'], varMetric: 'body_altitude_degrees', varLabels: ['observer', 'body'] };

    // ---------------- Space Weather ----------------
    local weatherGroups = [
      { title: 'Now', width: 4, height: 5, elements: {
        kp_stat: s.kp.asStat('Kp index'),
        wind_stat: s.solarWind.asStat('Solar wind km/s'),
        bz_stat: s.imfBz.asStat('IMF Bz nT'),
        xray_stat: s.xray.asStat('X-ray W/m2'),
        f107_stat: s.f107.asStat('F10.7'),
        sw_sources: s.swSourcesOk.asStat('SWPC sources OK'),
      } },
      { title: 'Trends', width: 12, height: 8, elements: {
        kp_ts: s.kp.asTimeSeries('Planetary Kp'),
        wind_ts: s.solarWind.asTimeSeries('Solar wind speed'),
        bz_ts: s.imfBz.asTimeSeries('IMF Bz'),
        xray_ts: s.xray.asTimeSeries('GOES X-ray flux'),
        f107_ts: s.f107.asTimeSeries('F10.7 flux'),
      } },
      { title: 'Health', width: 24, height: 6, elements: { scrape_ts: s.scrapeDuration.asTimeSeries('Scrape duration') } },
    ];

    // ---------------- Satellites ----------------
    local satGroups = [
      { title: 'Overview', width: 4, height: 5, elements: {
        tracked_stat: s.trackedCount.asStat('Tracked live'),
        catalog_stat: s.catalogSize.asStat('Catalog size'),
        sat_sources: s.satSourcesOk.asStat('Sources healthy'),
      } },
      { title: 'By group (colour key for the map)', width: 8, height: 7, elements: {
        bygroup: satmap.bygroup(satCfg),
      } },
      { title: 'External data sources (CelesTrak / SatNOGS)', width: 12, height: 6, elements: {
        src_status: s.satSourceOk.asTable('Source sync (1 = ok)'),
        src_age: s.satSourceAge.asTable('Source age'),
      } },
      { title: 'Live (filtered by $name)', width: 12, height: 8, elements: {
        elev_ts: s.satElevation.asTimeSeries('Elevation'),
        alt_ts: s.satAltitude.asTimeSeries('Altitude'),
      } },
      { title: 'Passes', width: 12, height: 8, elements: {
        tle_table: s.tleAge.asTable('TLE age'),
        pass_table: s.nextPassMaxEl.asTable('Next pass max elevation'),
      } },
    ];
    local satTabs = [
      { title: 'Positions — map', width: 24, height: 20, elements: { posmap: satmap.map(satCfg) } },
      { title: 'Positions — table', width: 24, height: 16, elements: { postable: satmap.table(satCfg) } },
    ];

    // ---------------- Bodies & Stars ----------------
    local bodyGroups = [
      { title: 'Overview', width: 6, height: 5, elements: {
        bodies_stat: s.bodiesUp.asStat('Bodies above horizon'),
        moon_stat: s.moonIllum.asStat('Moon illuminated'),
        phase_stat: s.moonPhase.asStat('Moon phase'),
      } },
      { title: 'Solar-system bodies (filtered by $body)', width: 12, height: 8, elements: {
        body_alt_ts: s.bodyAltitude.asTimeSeries('Body altitude'),
        body_table: s.bodyAltitude.asTable('Body altitude now'),
      } },
      { title: 'Celestial bodies (stars)', width: 12, height: 8, elements: {
        star_alt_ts: s.starAltitude.asTimeSeries('Star altitude'),
      } },
    ];

    // ---------------- Alerts + recording rules ----------------
    local alerts = [
      {
        name: 'space-telemetry',
        rules: [
          { alert: 'SpaceTelemetryExporterDown', expr: 'up{' + cfg.exporterSelector + '} == 0', 'for': cfg.downFor, labels: { severity: 'critical' }, annotations: { summary: 'space-telemetry exporter is down.', description: '{{ $labels.instance }} has been unreachable for more than ' + cfg.downFor + '.' } },
          { alert: 'SpaceTelemetrySourceFailing', expr: 'satellite_data_update_success{' + cfg.exporterSelector + '} == 0 or space_weather_data_update_success{' + cfg.exporterSelector + '} == 0', 'for': cfg.staleFor, labels: { severity: 'warning' }, annotations: { summary: 'A space-telemetry data source is failing.', description: 'Source {{ $labels.source }} on {{ $labels.instance }} last fetch did not succeed.' } },
          { alert: 'SpaceTelemetryTLEStale', expr: 'max(satellite_tle_age_seconds{' + cfg.exporterSelector + '}) > ' + cfg.tleStaleSeconds, 'for': '1h', labels: { severity: 'warning' }, annotations: { summary: 'Satellite TLEs are stale.', description: 'The oldest element set is over ' + cfg.tleStaleSeconds + 's old; the updater may be stuck.' } },
          { alert: 'GeomagneticStorm', expr: 'space_weather_planetary_k_index{' + cfg.exporterSelector + '} >= 5', 'for': '0m', labels: { severity: 'info' }, annotations: { summary: 'Geomagnetic storm in progress (Kp {{ $value }}).', description: 'The planetary K-index has reached storm level (>= 5).' } },
          { alert: 'SolarFlareMClass', expr: 'space_weather_goes_xray_flux_watts_per_m2{' + cfg.exporterSelector + '} >= 1e-5', 'for': '0m', labels: { severity: 'info' }, annotations: { summary: 'M-class (or stronger) solar flare.', description: 'GOES long-band X-ray flux has reached >= 1e-5 W/m^2.' } },
        ],
      },
    ];
    local rules = [
      {
        name: 'space-telemetry',
        rules: [
          { record: 'observer:body_above_horizon:sum', expr: 'sum by (observer) (body_above_horizon{' + cfg.exporterSelector + '})' },
          { record: 'job:satellite_tracked_count:sum', expr: 'sum(satellite_tracked_count{' + cfg.exporterSelector + '})' },
        ],
      },
    ];

    local weather = pack.build(weatherCfg, allSignals, weatherGroups, [], []);
    local sats = pack.build(satCfg, allSignals, satGroups, [], [], satTabs);
    local bodies = pack.build(bodyCfg, allSignals, bodyGroups, [], []);

    {
      config: cfg,
      prometheus: { alerts: alerts, rules: rules },
      grafana: {
        dashboards: {
          'space-telemetry-weather.json': weather.grafana.dashboard,
          'space-telemetry-satellites.json': sats.grafana.dashboard,
          'space-telemetry-bodies.json': bodies.grafana.dashboard,
        },
      },
    },
}
