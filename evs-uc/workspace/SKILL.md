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

# Deploy new cache and register it to the storage

Step 1:
Install the new cache:

```
helm upgrade --install nginx-us-central-1 ./charts/nginx-cache \
-n intend-infrastructure \
-f c./nginx-cache/nginx-cache/values.edge-us-central.yaml \
--kubeconfig /credentials/dell-cluster
```

Step 2
Register the cache with the Storage API, otherwise the API doesn't know the
region exists:
```
helm upgrade intend-storage-api ./charts/application \
-n intend-infrastructure \
--reuse-values \
-f ./nginx-cache/application/values.nodes-us-central.yaml \
--kubeconfig /credentials/dell-cluster
```

The working directory for Helm should be /credentials/. Otherwise, revise the relative paths by the absolute ones.

Current deployment is tested with region name use-central. Other values may be supported based on the available value files. However, by default, the three other regions are already available. 

# Undo the deployment

Step 1: uninstall the cache
```
helm uninstall nginx-us-central-1 -n intend-infrastructure
```

Step 2: reconfigure the storage API

```
```
helm upgrade intend-storage-api ./charts/application \
-n intend-infrastructure \
--reuse-values \
-f ./nginx-cache/application/values.nodes-original-three.yaml \
--kubeconfig /credentials/dell-cluster
```