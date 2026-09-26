# modules
import os
from typing import Dict
from src.common.config import REPO_NAME

# Cluster CIDRs used by the per-user-namespace NetworkPolicies (isolation): the "allow internet"
# egress rule carves these out so in-cluster targets stay unreachable. If these don't match the
# CLUSTER'S REAL ranges, the carve-out silently fails to exclude anything meaningful and the
# untrusted user pod's egress can reach other tenants/Postgres/Redis/MinIO despite this policy
# appearing to deny it (P21 - verified against a real k3d/k3s cluster: `kubectl get pods -A` /
# `kubectl get svc -A` show actual pod IPs under 10.42.0.0/16 and ClusterIPs under 10.43.0.0/16 -
# k3s's own defaults, which apply the same whether it's a k3d-wrapped dev cluster or a bare
# single-node k3s prod host - NOT docker-desktop's Kubernetes ranges this previously defaulted
# to, which were 10.1.0.0/16 / 10.96.0.0/12 and never matched any real k3s cluster this project
# runs on). Always confirm against the real target cluster before relying on these defaults;
# override via env for any cluster with different ranges (e.g. Calico/Cilium with a non-default
# CIDR).
POD_CIDR: str = os.getenv("POD_CIDR", "10.42.0.0/16")
SERVICE_CIDR: str = os.getenv("SERVICE_CIDR", "10.43.0.0/16")

# RuntimeClass stamped on USER pods only (the untrusted root shell) so they run under a sandboxed
# runtime (gVisor's runsc) instead of sharing the host kernel directly — the load-bearing control for
# multi-tenant untrusted code. container-maker's own control-plane pod is unaffected (stays runc).
# Empty/unset -> None -> k8s omits runtimeClassName -> the node's default runtime (runc): this keeps
# clusters WITHOUT gVisor installed (e.g. docker-desktop dev) working unchanged. Prod k3s (where
# setup.k3s.sh installs runsc + registers the `gvisor` RuntimeClass) sets this to "gvisor".
USER_POD_RUNTIME_CLASS: str | None = os.getenv("USER_POD_RUNTIME_CLASS", "").strip() or None

# ---------------------------------------------------------------------------------------------
# Per-tenant resource tiers (ResourceQuota + LimitRange -> user_namespace_quota.yaml).
#
# Each tier is the FULL substitution set for the quota template. The quota/LimitRange are applied
# at namespace creation and PATCHED when a user changes plan (NamespaceManager.update_resource_limits),
# so these numbers are the *current* entitlement, NOT a permanent ceiling — resizing a user up/down
# is "pick a different tier and re-apply".
#
# Subscriptions/payments are disabled project-wide for now (browseterm-server-local's app.py:
# "we don't need subscriptions for now"), and there has never actually been a gRPC field to select
# a tier at all (CreateNamespaceDataClass.tier defaults to "free" and nothing overrides it) - every
# namespace this project has ever created was silently pinned to the numbers below, forever,
# regardless of the owning device's real capacity. Terminal creation is meant to be gated ONLY by
# the active device's own remaining resource quota now (Cloud's POST /containers, which validates
# against allocated-minus-used capacity) - this ResourceQuota/LimitRange is meant to be a coarse,
# generous per-tenant safety ceiling underneath that (protects a shared cluster from one runaway
# tenant), not an independent, tighter limit a legitimately-sized request could still hit. The
# original "free" numbers here (2 CPU / 2Gi / 4 pods total) were sized as a billing tier's cheapest
# plan, not as that safety ceiling - on a real device with more than ~2 cores/2Gi worth of
# containers, or even a single container requesting more than 1 core (the old
# MAX_CPU_PER_CONTAINER), Cloud would approve the request and this K8s-level quota would then
# reject it anyway with a raw "exceeded quota" API error - which is exactly the "still says you've
# exceeded your plan's quota" behavior reported after subscription gating was removed elsewhere.
# Raised well above what a real device's allocation is expected to need; "pro" below is currently
# unreachable dead code (no caller can select it) and is left as-is.
DEFAULT_TIER: str = os.getenv("DEFAULT_TIER", "free")

TIERS: Dict[str, Dict[str, str]] = {
    "free": {
        "MAX_PODS": "12",
        "MAX_PVCS": "8",
        "TOTAL_STORAGE": "200Gi",
        "TOTAL_CPU_REQUESTS": "16",
        "TOTAL_CPU_LIMITS": "32",
        "TOTAL_MEMORY_REQUESTS": "16Gi",
        "TOTAL_MEMORY_LIMITS": "64Gi",
        "DEFAULT_REQUEST_CPU": "100m",
        "DEFAULT_REQUEST_MEMORY": "128Mi",
        "DEFAULT_CPU": "500m",
        "DEFAULT_MEMORY": "512Mi",
        "MAX_CPU_PER_CONTAINER": "8",
        "MAX_MEMORY_PER_CONTAINER": "32Gi",
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

# Timeout for pod uptime. 80s was too tight for a cold image pull (observed 88-105s for the
# ~110MB ssh_ubuntu image); 180s gives headroom while still failing fast on a genuinely stuck pod.
POD_UPTIME_TIMEOUT: float = 180.0
POD_IP_TIMEOUT_SECONDS: float = 20.0
# Bumped 2026-09-26 alongside fixing poll_termination's own polling-interval bug (it never
# actually enforced this value as a deadline before - see that method's docstring): a real
# observed delete took ~20s to confirm terminated (matching Kubernetes' default 30s
# terminationGracePeriodSeconds, no override set anywhere in this repo), so 20s left virtually no
# headroom once this value started being enforced as a real timeout instead of an unused sleep
# duration. 60s gives real headroom over the default grace period plus gVisor sandbox teardown
# overhead, same "measured + headroom" reasoning POD_UPTIME_TIMEOUT's own comment already uses.
POD_TERMINATION_TIMEOUT: float = 60.0

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
# Must stay comfortably ABOVE the Job's own active_deadline_seconds (job_manager.py, 3900s/65min):
# that field is the authoritative hard cap on total Job runtime (all retries combined). If this
# wait loop timed out first, container-maker would give up and report failure to the user while
# the Job kept running in the background - the same "caller abandons a still-running async
# operation" bug as the pod-creation timeout fixed earlier this session (bug #6). 4200s (70min)
# gives the Job's own deadline room to be the one that actually fires first.
SNAPSHOT_JOB_TIMEOUT_SECONDS: float = 4200.0
SNAPSHOT_JOB_SERVICE_ACCOUNT: str = 'snapshot-job-sa'
# Requests/limits for the snapshot Job's pod. It runs privileged (needs a Docker daemon) and does
# real work (tar extraction, image build, push) but must not be free to consume the whole node -
# an unbounded build contributed to real cluster-wide instability observed in practice (health
# check timeouts cascading into HPA scale-up under node contention). Sized similarly to the
# DEFAULT_TIER ceiling already used for user pods in the TIERS config above.
SNAPSHOT_JOB_CPU_REQUEST: str = '250m'
SNAPSHOT_JOB_MEMORY_REQUEST: str = '256Mi'
SNAPSHOT_JOB_CPU_LIMIT: str = '1'
SNAPSHOT_JOB_MEMORY_LIMIT: str = '1Gi'

# Save-status reconciler: catches saves stuck at Pending/Running because the snapshot Job's own
# pod was killed outright (node eviction, OOM, host disk I/O contention) before it got a chance to
# run its own except-block DB write -- a genuinely dead process can't record its own death.
# Deliberately NOT a duration-based guess for the common case: it checks the Job's actual live
# state in Kubernetes (does it still exist, is it terminally Failed) rather than assuming "stuck
# for N seconds" means orphaned, which would need re-tuning per cluster/image size. How often to
# sweep is env-overridable since it trades reconciliation latency for load on the k8s API + DB.
SAVE_RECONCILER_INTERVAL_SECONDS: float = float(os.getenv("SAVE_RECONCILER_INTERVAL_SECONDS", "90"))
# Pending is set by browseterm-server BEFORE the Job exists (build_tar + Job creation happen after),
# so "Pending with no Job yet" is normal for a short window and needs an age check, unlike Running
# (only ever set by the Job itself, so "Running with no Job" is unconditionally orphaned). 15min is
# generous against the ~1min this should normally take.
SAVE_RECONCILER_PENDING_GRACE_SECONDS: float = float(os.getenv("SAVE_RECONCILER_PENDING_GRACE_SECONDS", "900"))

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
