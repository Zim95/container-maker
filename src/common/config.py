import os

INGRESS_HOST: str = os.getenv('INGRESS_HOST', 'localhost')

REPO_NAME: str = os.getenv('REPO_NAME')
REPO_PASSWORD: str = os.getenv('REPO_PASSWORD')

# Cloud control plane - owns Postgres. container-maker previously held a direct Postgres
# credential of its own (DB_HOST/PORT/USERNAME/PASSWORD/DATABASE); that's gone (see
# src/cloud_client.py) - all container state now goes through Cloud's authenticated internal API,
# same shared secret every other trusted-SYSTEM caller (status_monitor, snapshot_job, reaper,
# Local) uses.
BROWSETERM_CLOUD_API_URL: str = os.getenv('BROWSETERM_CLOUD_API_URL', 'http://browseterm.cloud.com:9999').rstrip('/')
CLOUD_INTERNAL_API_TOKEN: str = os.getenv('CLOUD_INTERNAL_API_TOKEN', '')
