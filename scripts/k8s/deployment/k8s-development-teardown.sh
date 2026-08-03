#!/bin/bash
# Remove container-maker (PROD). Only NAMESPACE matters for delete (kubectl matches kind+name+ns).
set -uo pipefail
export NAMESPACE=${1:-browseterm}
envsubst < ./infra/k8s/deployment/deployment.yaml | kubectl delete -f - --ignore-not-found
echo "container-maker (prod) torn down"
