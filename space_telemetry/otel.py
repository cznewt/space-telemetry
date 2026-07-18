"""Optional OTLP push exporter mirroring the Prometheus gauges.

Enabled only when ``otlp_endpoint`` is set. Requires the ``otel`` extra
(``pip install .[otel]``); if that isn't installed we log and no-op so the
Prometheus path keeps working. Iterates every observer's sampler/provider.
"""

from __future__ import annotations


def attach_otel(samplers, settings, sat_providers=None):
    try:
        from opentelemetry import metrics
        from opentelemetry.metrics import Observation
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    except ImportError:
        print("[space-telemetry] OTLP endpoint set but opentelemetry is missing; run `pip install .[otel]`")
        return None

    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=settings.otlp_endpoint, insecure=True)
    )
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)
    meter = provider.get_meter("space_telemetry")

    def body_observed(pick):
        def callback(_options):
            out = []
            for sampler in samplers:
                snap = sampler.sample()
                for b in snap.bodies:
                    value = pick(b)
                    if value is not None:
                        out.append(Observation(float(value), {"body": b.body, "observer": snap.observer.name}))
            return out
        return callback

    meter.create_observable_gauge("body_altitude_degrees", callbacks=[body_observed(lambda b: b.altitude_deg)], unit="deg")
    meter.create_observable_gauge("body_azimuth_degrees", callbacks=[body_observed(lambda b: b.azimuth_deg)], unit="deg")
    meter.create_observable_gauge("body_distance_meters", callbacks=[body_observed(lambda b: b.distance_m)], unit="m")
    meter.create_observable_gauge(
        "body_above_horizon", callbacks=[body_observed(lambda b: 1.0 if b.above_horizon else 0.0)]
    )

    if sat_providers:
        def sat_observed(pick):
            def callback(_options):
                out = []
                for provider in sat_providers:
                    obs = provider.observer.name
                    for s in provider.states():
                        value = pick(s)
                        if value is not None:
                            out.append(Observation(
                                float(value),
                                {"norad": str(s.norad_id), "name": s.name, "observer": obs},
                            ))
                return out
            return callback

        meter.create_observable_gauge("satellite_elevation_degrees",
                                      callbacks=[sat_observed(lambda s: s.elevation_deg)], unit="deg")
        meter.create_observable_gauge("satellite_range_meters",
                                      callbacks=[sat_observed(lambda s: s.range_m)], unit="m")
        meter.create_observable_gauge("satellite_above_horizon",
                                      callbacks=[sat_observed(lambda s: 1.0 if s.above_horizon else 0.0)])

    print(f"[space-telemetry] OTLP metrics -> {settings.otlp_endpoint}")
    return provider
