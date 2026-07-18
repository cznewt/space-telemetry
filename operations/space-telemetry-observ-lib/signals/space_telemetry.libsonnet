local signal = import 'libs/common-lib/signal/main.libsonnet';

// Signals for the space-telemetry metrics. Sky + satellite signals filter on the
// observer selector; global space-weather signals filter on job only.
function(cfg)
  local sig(name, expr, unit, sel) =
    signal.new(name, 'prometheus', cfg.datasource, expr, unit).filteringSelector(sel);
  {
    // Exporter health
    up: sig('Exporter up', 'up{%(queriesSelector)s}', 'short', cfg.jobSelector),
    scrapeDuration: sig(
      'Scrape duration',
      'satellite_scrape_duration_seconds{%(queriesSelector)s}',
      's',
      cfg.jobSelector,
    ),

    // Solar-system bodies
    bodyAltitude: sig('Body altitude', 'body_altitude_degrees{%(queriesSelector)s}', 'degree', cfg.observerSelector),
    bodiesUp: sig('Bodies above horizon', 'sum by (observer) (body_above_horizon{%(queriesSelector)s})', 'short', cfg.observerSelector),
    moonIllum: sig('Moon illuminated', 'moon_illuminated_fraction{%(queriesSelector)s}', 'percentunit', cfg.observerSelector),
    moonPhase: sig('Moon phase', 'moon_phase_degrees{%(queriesSelector)s}', 'degree', cfg.observerSelector),

    // Celestial bodies (stars)
    starAltitude: sig('Star altitude', 'star_altitude_degrees{%(queriesSelector)s}', 'degree', cfg.observerSelector),

    // Satellites
    trackedCount: sig('Satellites tracked', 'satellite_tracked_count{%(queriesSelector)s}', 'short', cfg.observerSelector),
    satElevation: sig('Satellite elevation', 'satellite_elevation_degrees{%(queriesSelector)s}', 'degree', cfg.observerSelector),
    satAltitude: sig('Satellite altitude', 'satellite_altitude_meters{%(queriesSelector)s}', 'lengthm', cfg.observerSelector),
    tleAge: sig('TLE age', 'max by (name) (satellite_tle_age_seconds{%(queriesSelector)s})', 's', cfg.observerSelector),
    nextPassMaxEl: sig('Next pass max elevation', 'satellite_next_pass_max_elevation_degrees{%(queriesSelector)s}', 'degree', cfg.observerSelector),
    satSourcesOk: sig('Satellite sources healthy', 'sum(satellite_data_update_success{%(queriesSelector)s})', 'short', cfg.jobSelector),

    // Space weather (global — job only)
    kp: sig('Planetary Kp', 'space_weather_planetary_k_index{%(queriesSelector)s}', 'short', cfg.jobSelector),
    solarWind: sig('Solar wind speed', 'space_weather_solar_wind_speed_km_per_second{%(queriesSelector)s}', 'short', cfg.jobSelector),
    imfBz: sig('IMF Bz', 'space_weather_imf_bz_nanotesla{%(queriesSelector)s}', 'short', cfg.jobSelector),
    xray: sig('GOES X-ray flux', 'space_weather_goes_xray_flux_watts_per_m2{%(queriesSelector)s}', 'short', cfg.jobSelector),
    f107: sig('F10.7 flux', 'space_weather_f107_solar_radio_flux{%(queriesSelector)s}', 'short', cfg.jobSelector),
  }
