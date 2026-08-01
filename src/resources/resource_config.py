# modules
import os
from typing import Dict
from src.common.config import REPO_NAME

# Cluster CIDRs used by the per-user-namespace NetworkPolicies (isolation): the "allow internet"
# egress rule carves these out so in-cluster targets stay unreachable. Defaults are docker-desktop's
# ranges; override per cluster (e.g. Calico/Cilium) via env.
POD_CIDR: str = os.getenv("POD_CIDR", "10.1.0.0/16")
SERVICE_CIDR: str = os.getenv("SERVICE_CIDR", "10.96.0.0/12")

# ---------------------------------------------------------------------------------------------
# Per-tenant resource tiers (ResourceQuota + LimitRange -> user_namespace_quota.yaml).
#
# Each tier is the FULL substitution set for the quota template. The quota/LimitRange are applied
# at namespace creation and PATCHED when a user changes plan (NamespaceManager.update_resource_limits),
# so these numbers are the *current* entitlement, NOT a permanent ceiling — resizing a user up/down
# is "pick a different tier and re-apply".
#
# NOTE: placeholder values here are sensible starting points; the real numbers will be driven by the
# subscription/payments service (Go) once it lands. The tier name will come from the user's plan.
DEFAULT_TIER: str = os.getenv("DEFAULT_TIER", "free")

TIERS: Dict[str, Dict[str, str]] = {
    "free": {
        "MAX_PODS": "4",                 # 1 workspace pod (+ headroom for a snapshot job / recreate overlap)
        "MAX_PVCS": "2",
        "TOTAL_STORAGE": "20Gi",
        "TOTAL_CPU_REQUESTS": "1",
        "TOTAL_CPU_LIMITS": "2",
        "TOTAL_MEMORY_REQUESTS": "1Gi",
        "TOTAL_MEMORY_LIMITS": "2Gi",
        "DEFAULT_REQUEST_CPU": "100m",
        "DEFAULT_REQUEST_MEMORY": "128Mi",
        "DEFAULT_CPU": "500m",
        "DEFAULT_MEMORY": "512Mi",
        "MAX_CPU_PER_CONTAINER": "1",
        "MAX_MEMORY_PER_CONTAINER": "2Gi",
    },
    "pro": {
        "MAX_PODS": "8",
        "MAX_PVCS": "4",
        "TOTAL_STORAGE": "100Gi",
        "TOTAL_CPU_REQUESTS": "4",
        "TOTAL_CPU_LIMITS": "8",
        "TOTAL_MEMORY_REQUESTS": "4Gi",
        "TOTAL_MEMORY_LIMITS": "16Gi",
        "DEFAULT_REQUEST_CPU": "250m",
        "DEFAULT_REQUEST_MEMORY": "256Mi",
        "DEFAULT_CPU": "1",
        "DEFAULT_MEMORY": "1Gi",
        "MAX_CPU_PER_CONTAINER": "4",
        "MAX_MEMORY_PER_CONTAINER": "8Gi",
    },
}


def tier_substitutions(namespace_name: str, tier: str) -> Dict[str, str]:
    '''
    Build the ${...} substitution set for user_namespace_quota.yaml for a given namespace + tier.
    Falls back to DEFAULT_TIER for an unknown tier name.
    '''
    values: Dict[str, str] = TIERS.get(tier, TIERS[DEFAULT_TIER])
    return {"NAMESPACE": namespace_name, **values}

# Timeout for getting IP addresses
INGRESS_IP_TIMEOUT_SECONDS: float = 60.0
INGRESS_TERMINATION_TIMEOUT: float = 20.0

# Timeout for pod uptime
POD_UPTIME_TIMEOUT: float = 80.0
POD_IP_TIMEOUT_SECONDS: float = 20.0
POD_TERMINATION_TIMEOUT: float = 20.0

# Timeout for service uptime
SERVICE_IP_TIMEOUT_SECONDS: float = 20.0
SERVICE_TERMINATION_TIMEOUT: float = 20.0
SERVICE_ENDPOINTS_TIMEOUT_SECONDS: float = 30.0

# Saving the Pod
SNAPSHOT_DIR: str = '/mnt/snapshot'
SNAPSHOT_FILE_NAME: str = 'full_fs_snapshot'
SNAPSHOT_PVC_NAME: str = os.getenv('SNAPSHOT_PVC_NAME', 'snapshot-pvc')
SNAPSHOT_PVC_SIZE: str = '20Gi'  # Storage size for snapshot PVC

# Snapshot Job
SNAPSHOT_JOB_IMAGE_NAME: str = f'{REPO_NAME}/snapshot-job:latest'
SNAPSHOT_JOB_TIMEOUT_SECONDS: float = 1800.0  # 30 minutes for job completion
SNAPSHOT_JOB_SERVICE_ACCOUNT: str = 'snapshot-job-sa'

# Pod status
STATUS_SIDECAR_NAME: str = 'status-sidecar'
STATUS_SIDECAR_IMAGE_NAME: str = f'{REPO_NAME}/status_sidecar:latest'

# Timeout for building the image
IMAGE_BUILD_TIMEOUT_MINUTES: int = 25
IMAGE_PUSH_TIMEOUT_MINUTES: int = 25

# Timeout for container readiness check
CONTAINER_READINESS_TIMEOUT_SECONDS: float = 30.0

# Docker login retry configuration
DOCKER_LOGIN_MAX_RETRIES: int = 3
DOCKER_LOGIN_RETRY_DELAY_SECONDS: float = 2.0

# Docker build retry configuration
DOCKER_BUILD_MAX_RETRIES: int = 3
DOCKER_BUILD_RETRY_DELAY_SECONDS: float = 5.0
