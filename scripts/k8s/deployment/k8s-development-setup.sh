#!/bin/bash
# Deploy container-maker (PROD). Values come from make-expanded args (NOT `source env.mk`, since
# env.mk is Makefile syntax). No HOSTPATH — code is baked into the image, not hostPath-mounted.
set -euo pipefail
if [ $# -lt 3 ]; then
    echo "Usage: $0 <namespace> <repo-name> <repo-password> <ingress-host> <storage-layer> <minio-endpoint> <minio-bucket> <minio-secure> [browseterm-cloud-api-url]"
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
envsubst < "$YAML" | kubectl apply -f -
echo "container-maker (prod) applied to namespace ${NAMESPACE}"
