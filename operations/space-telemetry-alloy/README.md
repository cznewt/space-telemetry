# space-telemetry-alloy

A [Grafana Alloy](https://grafana.com/docs/alloy/) module fragment that scrapes
the space-telemetry exporter and forwards its metrics to a Prometheus receiver.
It sets `job="space-telemetry"` so the [observ-lib](../space-telemetry-observ-lib/)
dashboard and alerts (which select `job=~"$job"`) match.

## Use

Import the module and call it with your exporter target(s) and a receiver:

```alloy
prometheus.remote_write "mimir" {
  endpoint { url = "http://mimir:9009/api/v1/push" }
}

import.file "space_telemetry" {
  filename = "space-telemetry.alloy"
}

space_telemetry.scrape "default" {
  targets    = [{ "__address__" = "space-telemetry:9110" }]
  forward_to = [prometheus.remote_write.mimir.receiver]
}
```

Several observers/exporters? Pass more targets, or call `space_telemetry.scrape`
again with a different label.

## Arguments

| Argument | Required | Default | Meaning |
| --- | --- | --- | --- |
| `targets` | yes | — | exporter target(s), e.g. `[{ "__address__" = "space-telemetry:9110" }]` |
| `forward_to` | yes | — | list of Prometheus receivers |
| `job_name` | no | `space-telemetry` | `job` label (keep it so the observ-lib packs match) |
| `scrape_interval` | no | `15s` | scrape interval |

## Validate

```bash
alloy fmt space-telemetry.alloy
```
