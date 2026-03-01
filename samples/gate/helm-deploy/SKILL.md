---
name: helm-deploy
description: Inspect and validate GATE smart city Helm charts — list deployed releases, show chart metadata and values, check dependencies, and lint charts. Use when the user wants to inspect, validate, or query Helm releases or charts for the smart city platform.
compatibility: Requires helm. Install via apt-get if not present (see Setup section below).
---

# Helm Deploy

## Chart Location

All smart city Helm charts live in:
```
service_helm_charts/
```
This folder is relative to the directory of this skill. Use it as the `PATH` argument for any command that operates on a local chart.

## Setup: Install Helm

If `helm` is not available in the container, install it with:

```bash
apt-get install -y curl gpg apt-transport-https
curl -fsSL https://packages.buildkite.com/helm-linux/helm-debian/gpgkey \
  | gpg --dearmor \
  | tee /usr/share/keyrings/helm.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/helm.gpg] https://packages.buildkite.com/helm-linux/helm-debian/any/ any main" \
  | tee /etc/apt/sources.list.d/helm-stable-debian.list
apt-get update
apt-get install -y helm
```

Verify with:
```bash
helm version
```

---

## Read-Only Commands

The following commands are safe to run at any time — they do not modify the cluster or any chart.

### helm list — List Deployed Releases

Show all releases in the current namespace:
```bash
helm list
```

Show releases across all namespaces:
```bash
helm list -A
```

Filter by name pattern (regex):
```bash
helm list -f '<pattern>'
```

Output as JSON or YAML for programmatic use:
```bash
helm list -A -o json
helm list -A -o yaml
```

Show only failed releases:
```bash
helm list --failed -A
```

---

### helm show — Inspect a Chart

Operates on a local chart directory or a chart name in a repo.

Show everything (chart metadata + default values + README):
```bash
helm show all service_helm_charts/<chart-name>
```

Show only the chart definition (`Chart.yaml`):
```bash
helm show chart service_helm_charts/<chart-name>
```

Show only the default values (`values.yaml`):
```bash
helm show values service_helm_charts/<chart-name>
```

Show only the README:
```bash
helm show readme service_helm_charts/<chart-name>
```

Show CRD definitions bundled with the chart:
```bash
helm show crds service_helm_charts/<chart-name>
```

---

### helm dependency — Inspect Chart Dependencies

List dependencies declared in `Chart.yaml` for a local chart:
```bash
helm dependency list service_helm_charts/<chart-name>
```

Download/update dependencies into the chart's `charts/` directory:
```bash
helm dependency update service_helm_charts/<chart-name>
```

Rebuild the `charts/` directory from `Chart.lock` (uses pinned versions):
```bash
helm dependency build service_helm_charts/<chart-name>
```

> Run `dependency update` or `dependency build` before linting or installing a chart that has dependencies, otherwise Helm will report missing sub-charts.

---

### helm lint — Validate a Chart

Run the linter against a local chart:
```bash
helm lint service_helm_charts/<chart-name>
```

Treat warnings as errors (stricter check):
```bash
helm lint --strict service_helm_charts/<chart-name>
```

Lint with a custom values file:
```bash
helm lint -f my-values.yaml service_helm_charts/<chart-name>
```

Lint including sub-charts:
```bash
helm lint --with-subcharts service_helm_charts/<chart-name>
```

Output interpretation:
- `[ERROR]` — the chart will fail to install; must be fixed.
- `[WARNING]` — convention violation; should be reviewed.

---

## Workflow: Inspect Before Acting

When a user asks about a smart city service, follow this sequence:

1. `helm list -A` — confirm whether a release is already deployed and its current status.
2. `helm show chart service_helm_charts/<chart>` — check the chart version and description.
3. `helm show values service_helm_charts/<chart>` — review configurable parameters.
4. `helm dependency list service_helm_charts/<chart>` — check if sub-charts are present.
5. `helm lint service_helm_charts/<chart>` — validate before any further action.

---

## Notes

- The `service_helm_charts/` folder is excluded from version control (`.gitignore`). If the folder is missing, ask the user to provide or mount the charts.
- Intrusive commands (install, upgrade, rollback, uninstall) will be added in a future iteration of this skill.
