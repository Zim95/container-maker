import os

INGRESS_HOST: str = os.getenv('INGRESS_HOST', 'localhost')

REPO_NAME: str = os.getenv('REPO_NAME')
REPO_PASSWORD: str = os.getenv('REPO_PASSWORD')

# Cloud control plane - owns Postgres. container-maker previously held a direct Postgres
# credential of its own (DB_HOST/PORT/USERNAME/PASSWORD/DATABASE); that's gone (see
# src/cloud_client.py) - all container state now goes through Cloud's authenticated internal API,
# same shared secret every other trusted-SYSTEM caller (status_monitor, snapshot_job, reaper,
# Local) uses. Still required for save_reconciler.py's own stuck-saves sweep only (genuinely
# cluster-wide, not device-scoped, so it can't move to the per-device local-API path below) -
# finishing Part 12 moved containers.py's own `save()` self-heal lookup off this entirely.
BROWSETERM_CLOUD_API_URL: str = os.getenv('BROWSETERM_CLOUD_API_URL', 'http://browseterm.cloud.com:9999').rstrip('/')
CLOUD_INTERNAL_API_TOKEN: str = os.getenv('CLOUD_INTERNAL_API_TOKEN', '')

# Device Agent's private, ClusterIP-only local API (migration Part 12, completed) - see
# browseterm-device-agent/infra/deployment.yaml for the Service this targets (port 50061,
# NetworkPolicy-restricted to the known caller workloads, including container-maker itself as of
# Part 12's completion). Used by src/device_agent_client.py for containers.py's save() self-heal.
DEVICE_AGENT_LOCAL_API_URL: str = os.getenv('DEVICE_AGENT_LOCAL_API_URL', 'browseterm-device-agent-local:50061')
