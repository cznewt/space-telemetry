// Default config for the space-telemetry observ-viz pack.
// Override any field by passing it to main.new({ ... }).
{
  local this = self,

  uid: 'space-telemetry',
  dashboardTitle: 'Space Telemetry',
  dashboardTags: ['space-telemetry', 'astronomy', 'space-weather'],
  datasource: '${datasource}',

  // observer_info carries job+observer and exists for every observer, so it
  // drives the $job / $observer dropdowns.
  varMetric: 'observer_info',
  varLabels: ['observer'],

  // Per-signal selectors: sky/satellite metrics carry `observer`; space-weather
  // metrics are global (job only). bodySelector/satSelector also filter on the
  // per-dashboard $body / $name multi-select variables (created via varMetric).
  observerSelector: 'job=~"$job", observer=~"$observer"',
  jobSelector: 'job=~"$job"',
  selector: 'job=~"$job", observer=~"$observer"',
  bodySelector: 'job=~"$job", observer=~"$observer", body=~"$body"',
  satSelector: 'job=~"$job", observer=~"$observer", name=~"$name"',

  // Static selector for ALERT expressions (alerts cannot use dashboard vars).
  exporterSelector: 'job="space-telemetry"',

  // Alert tuning.
  downFor: '5m',
  staleFor: '15m',
  tleStaleSeconds: 259200,  // 3 days

  signals: {
    space_telemetry: (import './signals/space_telemetry.libsonnet')(this),
  },
}
