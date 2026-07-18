// observ-viz pack for space-telemetry (built on cznewt/observ-viz).
//
//   local p = (import 'main.libsonnet').new({});
//   p.grafana.dashboard      // a Grafana dashboard (.toResource() for JSON)
//   p.asMonitoringMixin()    // { grafanaDashboards+, prometheusAlerts+ }
local pack = import 'libs/common-lib/pack.libsonnet';

{
  new(config={}):
    local cfg = (import 'config.libsonnet') + config;
    local s = cfg.signals.space_telemetry;

    // Dashboard panel groups. Filter with the $observer dropdown.
    local groups = [
      {
        title: 'Overview',
        width: 6,
        height: 6,
        elements: {
          up: s.up.asStat('Exporter up'),
          tracked: s.trackedCount.asStat('Satellites tracked'),
          kp: s.kp.asStat('Planetary Kp'),
          wind: s.solarWind.asStat('Solar wind (km/s)'),
        },
      },
      {
        title: 'Solar-system bodies',
        width: 12,
        height: 8,
        elements: {
          altitude: s.bodyAltitude.asTimeSeries('Body altitude'),
          moon: s.moonIllum.asStat('Moon illuminated'),
        },
      },
      {
        title: 'Celestial bodies',
        width: 24,
        height: 8,
        elements: {
          star_altitude: s.starAltitude.asTimeSeries('Star altitude'),
        },
      },
      {
        title: 'Satellites',
        width: 12,
        height: 8,
        elements: {
          elevation: s.satElevation.asTimeSeries('Satellite elevation'),
          altitude: s.satAltitude.asTimeSeries('Satellite altitude'),
          tle_age: s.tleAge.asTable('TLE age by satellite'),
          next_pass: s.nextPassMaxEl.asTable('Next pass max elevation'),
        },
      },
      {
        title: 'Space weather',
        width: 8,
        height: 7,
        elements: {
          bz: s.imfBz.asTimeSeries('IMF Bz'),
          xray: s.xray.asTimeSeries('GOES X-ray flux'),
          f107: s.f107.asStat('F10.7 flux'),
        },
      },
      {
        title: 'Health',
        width: 12,
        height: 6,
        elements: {
          scrape: s.scrapeDuration.asTimeSeries('Scrape duration'),
          sources: s.satSourcesOk.asStat('Satellite sources healthy'),
        },
      },
    ];

    local allSignals = { ['space_telemetry_' + k]: s[k] for k in std.objectFields(s) };

    local alerts = [
      {
        name: 'space-telemetry',
        rules: [
          {
            alert: 'SpaceTelemetryExporterDown',
            expr: 'up{' + cfg.exporterSelector + '} == 0',
            'for': cfg.downFor,
            labels: { severity: 'critical' },
            annotations: {
              summary: 'space-telemetry exporter is down.',
              description: '{{ $labels.instance }} has been unreachable for more than ' + cfg.downFor + '.',
            },
          },
          {
            alert: 'SpaceTelemetrySourceFailing',
            expr: 'satellite_data_update_success{' + cfg.exporterSelector + '} == 0 or space_weather_data_update_success{' + cfg.exporterSelector + '} == 0',
            'for': cfg.staleFor,
            labels: { severity: 'warning' },
            annotations: {
              summary: 'A space-telemetry data source is failing.',
              description: 'Source {{ $labels.source }} on {{ $labels.instance }} last fetch did not succeed.',
            },
          },
          {
            alert: 'SpaceTelemetryTLEStale',
            expr: 'max(satellite_tle_age_seconds{' + cfg.exporterSelector + '}) > ' + cfg.tleStaleSeconds,
            'for': '1h',
            labels: { severity: 'warning' },
            annotations: {
              summary: 'Satellite TLEs are stale.',
              description: 'The oldest element set is over ' + cfg.tleStaleSeconds + 's old; the updater may be stuck.',
            },
          },
          {
            alert: 'GeomagneticStorm',
            expr: 'space_weather_planetary_k_index{' + cfg.exporterSelector + '} >= 5',
            'for': '0m',
            labels: { severity: 'info' },
            annotations: {
              summary: 'Geomagnetic storm in progress (Kp {{ $value }}).',
              description: 'The planetary K-index has reached storm level (>= 5).',
            },
          },
          {
            alert: 'SolarFlareMClass',
            expr: 'space_weather_goes_xray_flux_watts_per_m2{' + cfg.exporterSelector + '} >= 1e-5',
            'for': '0m',
            labels: { severity: 'info' },
            annotations: {
              summary: 'M-class (or stronger) solar flare.',
              description: 'GOES long-band X-ray flux has reached >= 1e-5 W/m^2.',
            },
          },
        ],
      },
    ];

    local rules = [
      {
        name: 'space-telemetry',
        rules: [
          {
            record: 'observer:body_above_horizon:sum',
            expr: 'sum by (observer) (body_above_horizon{' + cfg.exporterSelector + '})',
          },
          {
            record: 'job:satellite_tracked_count:sum',
            expr: 'sum(satellite_tracked_count{' + cfg.exporterSelector + '})',
          },
        ],
      },
    ];

    local built = pack.build(cfg, allSignals, groups, alerts);

    built + {
      prometheus+: { rules: rules },
      grafana+: {
        dashboards: { [cfg.uid + '.json']: built.grafana.dashboard },
      },
    },
}
