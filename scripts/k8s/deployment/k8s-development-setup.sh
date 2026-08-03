#!/bin/bash
# Deploy container-maker (PROD). Values come from make-expanded args (NOT `source env.mk`, since
# env.mk is Makefile syntax). No HOSTPATH — code is baked into the image, not hostPath-mounted.
set -euo pipefail
if [ $# -lt 3 ]; then
    echo "Usage: $0 <namespace> <repo-name> <repo-password> <ingress-host> <storage-layer> <minio-endpoint> <minio-bucket> <minio-secure> <db-host> <db-port> <db-username> <db-database>"
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
export DB_HOST=${9:-}
export DB_PORT=${10:-5432}
export DB_USERNAME=${11:-}
export DB_DATABASE=${12:-}
envsubst < "$YAML" | kubectl apply -f -
echo "container-maker (prod) applied to namespace ${NAMESPACE}"
