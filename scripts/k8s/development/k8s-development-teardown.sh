#!/bin/bash

# Check if enough arguments are provided
if [ $# -lt 1 ]; then
    echo "Usage: $0 <namespace>"
    exit 1
fi

YAML=./infra/k8s/development/development.yaml
NAMESPACE=$1

# Delete cluster-scoped resources
echo "Deleting cluster-scoped resources..."
kubectl delete clusterrole resources-cluster-role --ignore-not-found
kubectl delete clusterrolebinding resources-cluster-role-binding --ignore-not-found

# Delete namespace-scoped resources with the provided namespace
echo "Deleting namespace-scoped resources in namespace $NAMESPACE..."
envsubst < "$YAML" | kubectl delete -n "$NAMESPACE" -f -
