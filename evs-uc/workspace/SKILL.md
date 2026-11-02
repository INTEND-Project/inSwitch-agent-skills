---
name: inspect-kubernetes-cluster
description: Inspect the Kubernetes cluster and Helm releases using the installed kubectl and Helm command-line tools.
---

# Inspect the Kubernetes cluster

`kubectl` and `helm` are installed in the container. Cluster configuration and
credentials are available under `/credentials`. Use the appropriate kubeconfig
from that directory, for example by setting `KUBECONFIG` or passing
`--kubeconfig` to the commands. If the configuration is missing, ambiguous, or
cannot connect, explain the issue to the user. Do not expose credential values.

Use basic read-only commands to explore the cluster and answer the user's
questions. Choose the commands and namespace that fit the request, such as:

- `kubectl get namespaces`
- `kubectl get nodes`
- `kubectl get pods -A`
- `kubectl get deployments,services -n <namespace>`
- `helm list -A`
- `helm status <release> -n <namespace>`

Summarize the relevant results and report any access or connection errors.

Default namespace is intend-infrastructure, and default cluster configuration is /credentials/dell-cluster
