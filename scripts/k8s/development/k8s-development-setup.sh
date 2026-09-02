#!/bin/bash

# Check if enough arguments are provided
if [ $# -lt 3 ]; then
    echo "Usage: $0 <namespace> <absolute-path-to-current-working-directory> <docker-repo-name> <docker-repo-password> <ingress-host> <storage-layer> [minio-endpoint] [minio-bucket] [minio-secure] [browseterm-cloud-api-url]"
    exit 1
fi

YAML=./infra/k8s/development/development.yaml
NAMESPACE=$1
HOSTPATH=$2
REPO_NAME=$3
REPO_PASSWORD=$4
INGRESS_HOST=$5
STORAGE_LAYER=${6:-local}
MINIO_ENDPOINT=${7:-}
MINIO_BUCKET=${8:-}
MINIO_SECURE=${9:-false}
# container-maker no longer holds a Postgres credential of its own - it talks to Cloud's
# internal container API instead (src/cloud_client.py; CLOUD_INTERNAL_API_TOKEN itself comes
# from the existing browseterm-internal-api-token Secret, referenced directly in the manifest,
# not templated here). Defaults to the project's standard Cloud DNS convention.
BROWSETERM_CLOUD_API_URL=${10:-http://browseterm.cloud.com:9999}

export NAMESPACE=$NAMESPACE
export HOSTPATH=$HOSTPATH
export REPO_NAME=$REPO_NAME
export REPO_PASSWORD=$REPO_PASSWORD
export INGRESS_HOST=$INGRESS_HOST
export STORAGE_LAYER=$STORAGE_LAYER
export MINIO_ENDPOINT=$MINIO_ENDPOINT
export MINIO_BUCKET=$MINIO_BUCKET
export MINIO_SECURE=$MINIO_SECURE
export BROWSETERM_CLOUD_API_URL=$BROWSETERM_CLOUD_API_URL
envsubst < $YAML | kubectl apply -f -
