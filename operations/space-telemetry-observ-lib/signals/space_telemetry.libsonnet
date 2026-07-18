local signal = import 'libs/common-lib/signal/main.libsonnet';

// Signals for the space-telemetry metrics. Body/satellite signals filter on the
// per-dashboard $body / $name multi-select variables; global space-weather signals
// filter on job only. `legend` sets the series legend (e.g. the body/satellite name).
function(cfg)
  local sig(name, expr, unit, sel, legend='') =
    local base = signal.new(name, 'prometheus', cfg.datasource, expr, unit).filteringSelector(sel);
    if legend != '' then base.withLegendFormat(legend) else base;
  {
    // Exporter health
    up: sig('Exporter up', 'up{%(queriesSelector)s}', 'short', cfg.jobSelector),
    scrapeDuration: sig('Scrape duration', 'satellite_scrape_duration_seconds{%(queriesSelector)s}', 's', cfg.jobSelector),

    // Solar-system bodies (filtered by $body)
    bodyAltitude: sig('Body altitude', 'body_altitude_degrees{%(queriesSelector)s}', 'degree', cfg.bodySelector, '{{body}}'),
    bodiesUp: sig('Bodies above horizon', 'sum by (observer) (body_above_horizon{%(queriesSelector)s})', 'short', cfg.observerSelector),
    // avg without (instance, pod): those labels change on a pod restart, so aggregating
    // them away keeps a single stable series instead of duplicating across the old+new pod.
    moonIllum: sig('Moon illuminated', 'avg without (instance, pod) (moon_illuminated_fraction{%(queriesSelector)s})', 'percentunit', cfg.observerSelector),
    moonPhase: sig('Moon phase', 'avg without (instance, pod) (moon_phase_degrees{%(queriesSelector)s})', 'degree', cfg.observerSelector),

    // Celestial bodies (stars)
    starAltitude: sig('Star altitude', 'star_altitude_degrees{%(queriesSelector)s}', 'degree', cfg.observerSelector, '{{star}}'),

    // Satellites (filtered by $name)
    trackedCount: sig('Satellites tracked', 'satellite_tracked_count{%(queriesSelector)s}', 'short', cfg.observerSelector),
    catalogSize: sig('Catalog size', 'satellite_catalog_size{%(queriesSelector)s}', 'short', cfg.jobSelector),
    satElevation: sig('Satellite elevation', 'satellite_elevation_degrees{%(queriesSelector)s}', 'degree', cfg.satSelector, '{{name}}'),
    satAltitude: sig('Satellite altitude', 'satellite_altitude_meters{%(queriesSelector)s}', 'lengthm', cfg.satSelector, '{{name}}'),
    tleAge: sig('TLE age', 'max by (name) (satellite_tle_age_seconds{%(queriesSelector)s})', 's', cfg.satSelector, '{{name}}'),
    nextPassMaxEl: sig('Next pass max elevation', 'max by (name) (satellite_next_pass_max_elevation_degrees{%(queriesSelector)s})', 'degree', cfg.satSelector, '{{name}}'),
    satSourcesOk: sig('Satellite sources healthy', 'sum(satellite_data_update_success{%(queriesSelector)s})', 'short', cfg.jobSelector),
    satSourceOk: sig('Source status', 'satellite_data_update_success{%(queriesSelector)s}', 'short', cfg.jobSelector, '{{source}}'),
    satSourceAge: sig('Source age', 'satellite_data_age_seconds{%(queriesSelector)s}', 's', cfg.jobSelector, '{{source}}'),

    // Space weather (global — job only)
    kp: sig('Planetary Kp', 'space_weather_planetary_k_index{%(queriesSelector)s}', 'short', cfg.jobSelector),
    solarWind: sig('Solar wind speed', 'space_weather_solar_wind_speed_km_per_second{%(queriesSelector)s}', 'short', cfg.jobSelector),
    imfBz: sig('IMF Bz', 'space_weather_imf_bz_nanotesla{%(queriesSelector)s}', 'short', cfg.jobSelector),
    xray: sig('GOES X-ray flux', 'space_weather_goes_xray_flux_watts_per_m2{%(queriesSelector)s}', 'short', cfg.jobSelector),
    f107: sig('F10.7 flux', 'space_weather_f107_solar_radio_flux{%(queriesSelector)s}', 'short', cfg.jobSelector),
    swSourcesOk: sig('SWPC sources healthy', 'sum(space_weather_data_update_success{%(queriesSelector)s})', 'short', cfg.jobSelector),
  }
