#!/bin/bash

# Check if enough arguments are provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <namespace> <absolute-path-to-current-working-directory>"
    exit 1
fi

YAML=./infra/k8s/development/development.yaml
NAMESPACE=$1
HOSTPATH=$2

export NAMESPACE=$NAMESPACE
export HOSTPATH=$HOSTPATH
envsubst < $YAML | kubectl apply -f -
