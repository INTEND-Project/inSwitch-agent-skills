ARG AGENT_IMAGE=songhui/inswitch:latest
FROM ${AGENT_IMAGE}

ARG KUBECTL_VERSION=v1.32.0
ARG HELM_VERSION=v3.16.4

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in amd64|arm64) ;; *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; esac; \
    curl -fsSLo /tmp/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${arch}/kubectl"; \
    curl -fsSLo /tmp/kubectl.sha256 "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${arch}/kubectl.sha256"; \
    echo "$(cat /tmp/kubectl.sha256)  /tmp/kubectl" | sha256sum -c -; \
    install -m 0755 /tmp/kubectl /usr/local/bin/kubectl; \
    curl -fsSLo /tmp/helm.tar.gz "https://get.helm.sh/helm-${HELM_VERSION}-linux-${arch}.tar.gz"; \
    curl -fsSLo /tmp/helm.sha256 "https://get.helm.sh/helm-${HELM_VERSION}-linux-${arch}.tar.gz.sha256sum"; \
    echo "$(cut -d' ' -f1 /tmp/helm.sha256)  /tmp/helm.tar.gz" | sha256sum -c -; \
    cd /tmp; \
    tar -xzf helm.tar.gz "linux-${arch}/helm"; \
    install -m 0755 "linux-${arch}/helm" /usr/local/bin/helm; \
    rm -rf /tmp/kubectl /tmp/kubectl.sha256 /tmp/helm.tar.gz /tmp/helm.sha256 "/tmp/linux-${arch}" /var/lib/apt/lists/*
