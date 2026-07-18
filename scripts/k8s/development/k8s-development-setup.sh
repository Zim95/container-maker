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

export NAMESPACE=$NAMESPACE
export HOSTPATH=$HOSTPATH
export REPO_NAME=$REPO_NAME
export REPO_PASSWORD=$REPO_PASSWORD
export INGRESS_HOST=$INGRESS_HOST
export STORAGE_LAYER=$STORAGE_LAYER
envsubst < $YAML | kubectl apply -f -
