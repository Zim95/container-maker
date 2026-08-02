#!/bin/bash
# Deploy container-maker (PROD). Sources the generated env.mk for all envsubst vars.
set -euo pipefail
set -a; source env.mk; set +a
envsubst < ./infra/k8s/deployment/deployment.yaml | kubectl apply -f -
echo "container-maker (prod) applied to namespace ${NAMESPACE}"
