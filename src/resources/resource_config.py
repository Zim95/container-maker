# modules
from src.common.config import REPO_NAME

# Timeout for getting IP addresses
INGRESS_IP_TIMEOUT_SECONDS: float = 60.0
INGRESS_TERMINATION_TIMEOUT: float = 20.0

# Timeout for pod uptime
POD_UPTIME_TIMEOUT: float = 40.0
POD_IP_TIMEOUT_SECONDS: float = 20.0
POD_TERMINATION_TIMEOUT: float = 20.0

# Timeout for service uptime
SERVICE_IP_TIMEOUT_SECONDS: float = 20.0
SERVICE_TERMINATION_TIMEOUT: float = 20.0

# Saving the Pod
SNAPSHOT_DIR: str = '/mnt/snapshot'
SNAPSHOT_FILE_NAME: str = 'full_fs_snapshot'
SNAPSHOT_SIDECAR_NAME: str = 'snapshot-sidecar'
SNAPSHOT_SIDECAR_IMAGE_NAME: str = f'{REPO_NAME}/snapshot_sidecar:latest'

# Timeout for building the image
IMAGE_BUILD_TIMEOUT_MINUTES: int = 25