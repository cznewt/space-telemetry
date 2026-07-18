"""Prometheus collector for NOAA space-weather metrics."""

from __future__ import annotations

from time import perf_counter

from prometheus_client.core import GaugeMetricFamily

_HELP = {
    "space_weather_planetary_k_index": "Planetary K-index (0-9; geomagnetic activity).",
    "space_weather_solar_wind_speed_km_per_second": "Solar-wind bulk speed (km/s).",
    "space_weather_imf_bz_nanotesla": "Interplanetary magnetic field Bz, GSM (nT).",
    "space_weather_imf_bt_nanotesla": "Interplanetary magnetic field magnitude Bt (nT).",
    "space_weather_f107_solar_radio_flux": "10.7 cm solar radio flux, F10.7 (sfu).",
    "space_weather_goes_xray_flux_watts_per_m2": "GOES long-band (0.1-0.8 nm) X-ray flux (W/m^2).",
}


class SpaceWeatherCollector:
    def __init__(self, updater):
        self.updater = updater

    def collect(self):
        start = perf_counter()

        for name, value in self.updater.latest().items():
            gauge = GaugeMetricFamily(name, _HELP.get(name, "NOAA space-weather metric."))
            gauge.add_metric([], value)
            yield gauge

        ok = GaugeMetricFamily("space_weather_data_update_success",
                               "1 if the product's last fetch attempt succeeded.", labels=["source"])
        updated = GaugeMetricFamily("space_weather_data_update_timestamp_seconds",
                                    "Last successful fetch per product (UNIX seconds).", labels=["source"])
        data_age = GaugeMetricFamily("space_weather_data_age_seconds",
                                     "Seconds since the product's last successful fetch.", labels=["source"])
        for h in self.updater.health():
            ok.add_metric([h.source], 1.0 if h.success else 0.0)
            if h.last_success_ts is not None:
                updated.add_metric([h.source], h.last_success_ts)
            if h.age_s is not None:
                data_age.add_metric([h.source], h.age_s)
        yield from (ok, updated, data_age)

        duration = GaugeMetricFamily("space_weather_scrape_duration_seconds",
                                     "Seconds spent building the space-weather snapshot for this scrape.")
        duration.add_metric([], perf_counter() - start)
        yield duration
