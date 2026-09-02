"""
Save-status reconciler.

Detects saves stuck at Pending/Running because the snapshot Job that was supposed to finish them
is dead: its pod was killed outright (node eviction, OOM, host disk I/O contention) before the
Job's own process got a chance to run its own except-block and record Failed in the DB. A killed
process cannot record its own death -- something outside it has to notice.

Deliberately NOT primarily duration-based: for each candidate row, it asks Kubernetes for the
actual current state of that save's Job (does it still exist, is it terminally Failed, is it still
genuinely active) rather than guessing "stuck for N seconds means orphaned". That guess would need
separate tuning per cluster/image size and could either falsely fail a legitimately slow save or
leave a truly dead one spinning far too long. A duration check is used only where there is no Job
to ask yet at all (a fresh Pending row, before the Job has been created).

Runs inside container-maker itself (see app.py) rather than as a separate service: any live
replica can reconcile any stuck row on its next tick, decoupled from which specific pod/process
handled the original (now-dead) save request. Writes go through Cloud's internal container API
(src/cloud_client.py) -- the same path browseterm-server and the snapshot Job itself use -- so
the existing Postgres NOTIFY -> SSE pipeline relays the fix to the frontend for free.
"""
# built-ins
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

# modules
from browseterm_db.models.containers import SaveStatus
from src.cloud_client import CloudClient, CloudClientError
from src.common.config import BROWSETERM_CLOUD_API_URL, CLOUD_INTERNAL_API_TOKEN
from src.resources.job_manager import JobManager
from src.resources.resource_config import (
    SAVE_RECONCILER_INTERVAL_SECONDS,
    SAVE_RECONCILER_PENDING_GRACE_SECONDS,
)
from src.common.logging_setup import get_logger

logger = get_logger("save_reconciler")


def _seconds_since(timestamp) -> float:
    """Container.to_dict() serializes timestamps to ISO strings (naive, but always written as
    UTC wall-clock -- see ContainerOps.update()'s updated_at stamping), so parse before comparing."""
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - timestamp).total_seconds()


def _mark_failed(cloud_client: CloudClient, container_id: str, reason: str) -> None:
    try:
        cloud_client.update_container(
            container_id, {"save_status": SaveStatus.FAILED.value, "save_error": reason[:1000]}
        )
        logger.info("reconciled stuck save", extra={"container_id": container_id, "reason": reason})
    except CloudClientError as e:
        logger.error(
            "failed to reconcile stuck save",
            extra={"container_id": container_id, "reason": reason, "cloud_error": e.message},
        )


def reconcile_row(cloud_client: CloudClient, row: dict, trusted_namespace: str) -> None:
    """Decide the fate of one Pending/Running row. Never raises -- errors are logged and skipped,
    so one bad row (or a transient k8s API blip) doesn't stop the rest of the sweep."""
    container_id = row["id"]
    save_status = row["save_status"]
    updated_at = row.get("updated_at")

    try:
        job_state = JobManager.find_snapshot_job_for_container(trusted_namespace, container_id)
    except Exception:
        logger.warning("could not check job state, skipping this tick", extra={"container_id": container_id}, exc_info=True)
        return

    if save_status == SaveStatus.RUNNING.value:
        # RUNNING is only ever set by the Job itself (snapshot_job/main.py), after it has already
        # started -- so the Job existing is a hard prerequisite of this state ever being written.
        # If it's gone now, it died without finishing; there is no legitimate "still starting up".
        if not job_state["exists"]:
            _mark_failed(
                cloud_client, container_id,
                "Save job disappeared without reporting completion (likely killed by node "
                "eviction/pressure). Please retry.",
            )
            return
        if job_state["terminal_failed"]:
            _mark_failed(cloud_client, container_id, f"Save job failed: {job_state['failure_reason']}")
            return
        # exists and (active or between-poll-ticks) -- leave it, still a legitimate in-progress save.
        return

    if save_status == SaveStatus.PENDING.value:
        # PENDING is set by browseterm-server BEFORE the Job exists (filesystem snapshot + Job
        # creation happen after), so "no Job yet" is expected for a short window.
        if job_state["exists"]:
            return
        if updated_at is None or _seconds_since(updated_at) < SAVE_RECONCILER_PENDING_GRACE_SECONDS:
            return
        _mark_failed(
            cloud_client, container_id,
            "Save never progressed past being queued (no snapshot job was ever created). Please retry.",
        )
        return


def reconcile_once() -> int:
    """Run one sweep. Returns the number of rows examined (not the number fixed)."""
    trusted_namespace = os.getenv("NAMESPACE", "browseterm")
    cloud_client = CloudClient(BROWSETERM_CLOUD_API_URL, CLOUD_INTERNAL_API_TOKEN)

    try:
        rows = cloud_client.find_stuck_saves()
    except CloudClientError as e:
        logger.error("could not list in-progress saves", extra={"cloud_error": e.message})
        return 0

    for row in rows:
        reconcile_row(cloud_client, row, trusted_namespace)
    return len(rows)


def run_loop(stop_event: Optional[threading.Event] = None) -> None:
    """Sweep forever on SAVE_RECONCILER_INTERVAL_SECONDS, until stop_event is set (or forever, if
    no stop_event is given -- the normal case, run as a daemon thread for the process lifetime)."""
    stop_event = stop_event or threading.Event()
    logger.info("save reconciler started", extra={"interval_seconds": SAVE_RECONCILER_INTERVAL_SECONDS})
    while not stop_event.is_set():
        try:
            examined = reconcile_once()
            if examined:
                logger.info("save reconciler sweep complete", extra={"rows_examined": examined})
        except Exception:
            # A single bad sweep (e.g. a transient DB/k8s API blip) must not kill the loop --
            # that would silently disable the whole safety net until the next pod restart.
            logger.error("save reconciler sweep failed, will retry next tick", exc_info=True)
        stop_event.wait(SAVE_RECONCILER_INTERVAL_SECONDS)
