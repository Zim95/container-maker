#!/bin/bash

# Check if enough arguments are provided
if [ $# -lt 3 ]; then
    echo "Usage: $0 <namespace> <absolute-path-to-current-working-directory> <docker-repo-name> <docker-repo-password> <ingress-host> <storage-layer>"
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
DB_HOST=${10:-}
DB_PORT=${11:-5432}
DB_USERNAME=${12:-}
DB_DATABASE=${13:-}

export NAMESPACE=$NAMESPACE
export HOSTPATH=$HOSTPATH
export REPO_NAME=$REPO_NAME
export REPO_PASSWORD=$REPO_PASSWORD
export INGRESS_HOST=$INGRESS_HOST
export STORAGE_LAYER=$STORAGE_LAYER
export MINIO_ENDPOINT=$MINIO_ENDPOINT
export MINIO_BUCKET=$MINIO_BUCKET
export MINIO_SECURE=$MINIO_SECURE
export DB_HOST=$DB_HOST
export DB_PORT=$DB_PORT
export DB_USERNAME=$DB_USERNAME
export DB_DATABASE=$DB_DATABASE
envsubst < $YAML | kubectl apply -f -
