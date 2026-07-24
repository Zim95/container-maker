# modules
import os
from src.common.config import REPO_NAME

# Cluster CIDRs used by the per-user-namespace NetworkPolicies (isolation): the "allow internet"
# egress rule carves these out so in-cluster targets stay unreachable. Defaults are docker-desktop's
# ranges; override per cluster (e.g. Calico/Cilium) via env.
POD_CIDR: str = os.getenv("POD_CIDR", "10.1.0.0/16")
SERVICE_CIDR: str = os.getenv("SERVICE_CIDR", "10.96.0.0/12")

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
SNAPSHOT_JOB_ROLE_NAME: str = 'snapshot-job-role'
SNAPSHOT_JOB_ROLE_BINDING_NAME: str = 'snapshot-job-binding'

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
