#!/bin/bash
# Remove container-maker (PROD). Best-effort.
set -uo pipefail
set -a; source env.mk; set +a
envsubst < ./infra/k8s/deployment/deployment.yaml | kubectl delete -f - --ignore-not-found
echo "container-maker (prod) torn down"
