#!/bin/bash
# Deploy container-maker (PROD). Values come from make-expanded args (NOT `source env.mk`, since
# env.mk is Makefile syntax). No HOSTPATH — code is baked into the image, not hostPath-mounted.
set -euo pipefail
if [ $# -lt 3 ]; then
    echo "Usage: $0 <namespace> <repo-name> <repo-password> <ingress-host> <storage-layer> <minio-endpoint> <minio-bucket> <minio-secure> [browseterm-cloud-api-url] [cloud-ingress-host] [cloud-ingress-host-ip]"
    exit 1
fi
YAML=./infra/k8s/deployment/deployment.yaml
export NAMESPACE=$1
export REPO_NAME=$2
export REPO_PASSWORD=$3
export INGRESS_HOST=${4:-}
export STORAGE_LAYER=${5:-minio}
export MINIO_ENDPOINT=${6:-}
export MINIO_BUCKET=${7:-}
export MINIO_SECURE=${8:-false}
# container-maker no longer holds a Postgres credential of its own - it talks to Cloud's internal
# container API instead (src/cloud_client.py; CLOUD_INTERNAL_API_TOKEN comes from the existing
# browseterm-internal-api-token Secret, referenced directly in the manifest, not templated here).
export BROWSETERM_CLOUD_API_URL=${9:-http://browseterm.cloud.com:9999}
# On a single-Mac two-cluster local dev setup, BROWSETERM_CLOUD_API_URL's hostname resolves
# inside this cluster's own pods to whatever the Mac's own /etc/hosts maps it to (127.0.0.1, for
# the developer's browser), not the real Cloud cluster - see browseterm-server-local's identical
# hostAliases override for the full explanation. Required for the Cloud API calls above to work
# at all from inside browseterm-k3s-local.
export CLOUD_INGRESS_HOST=${10:-browseterm.cloud.com}
export CLOUD_INGRESS_HOST_IP=${11:-}
envsubst < "$YAML" | kubectl apply -f -
echo "container-maker (prod) applied to namespace ${NAMESPACE}"
