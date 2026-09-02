# builtins
from datetime import datetime, timezone, timedelta
from unittest import TestCase
from unittest.mock import MagicMock, patch

# modules
from src.resources import save_reconciler
from src.cloud_client import CloudClientError
from browseterm_db.models.containers import SaveStatus


def _row(save_status: str, updated_at) -> dict:
    return {
        "id": "container-1",
        "save_status": save_status,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _job_state(exists: bool, active: bool = False, terminal_failed: bool = False, failure_reason=None) -> dict:
    return {"exists": exists, "job_name": "some-job" if exists else None,
            "active": active, "terminal_failed": terminal_failed, "failure_reason": failure_reason}


class TestReconcileRow(TestCase):
    '''
    UNIT tests (no cluster/Cloud): reconcile_row's decision table, the core of the save
    reconciler. JobManager.find_snapshot_job_for_container and the Cloud client are both
    mocked; these assert exactly which rows get marked Failed and which are left alone.
    '''

    def setUp(self) -> None:
        self.cloud_client = MagicMock()
        self.now = datetime.now(timezone.utc)

    def _run(self, row: dict, job_state: dict):
        with patch.object(save_reconciler.JobManager, 'find_snapshot_job_for_container', return_value=job_state):
            save_reconciler.reconcile_row(self.cloud_client, row, trusted_namespace='browseterm')

    def test_running_with_no_job_is_marked_failed(self) -> None:
        print('Test: test_running_with_no_job_is_marked_failed')
        # RUNNING is only ever written by the Job itself, after it exists -- so a missing Job
        # here is unconditionally orphaned, no age check needed.
        self._run(_row(SaveStatus.RUNNING.value, self.now), _job_state(exists=False))
        self.cloud_client.update_container.assert_called_once()
        container_id, fields = self.cloud_client.update_container.call_args.args
        self.assertEqual(container_id, "container-1")
        self.assertEqual(fields['save_status'], SaveStatus.FAILED.value)
        self.assertIn('disappeared', fields['save_error'])

    def test_running_with_terminal_failed_job_is_marked_failed(self) -> None:
        print('Test: test_running_with_terminal_failed_job_is_marked_failed')
        self._run(
            _row(SaveStatus.RUNNING.value, self.now),
            _job_state(exists=True, terminal_failed=True, failure_reason='BackoffLimitExceeded: gave up'),
        )
        self.cloud_client.update_container.assert_called_once()
        _, fields = self.cloud_client.update_container.call_args.args
        self.assertEqual(fields['save_status'], SaveStatus.FAILED.value)
        self.assertIn('BackoffLimitExceeded', fields['save_error'])

    def test_running_with_active_job_is_left_alone(self) -> None:
        print('Test: test_running_with_active_job_is_left_alone')
        self._run(_row(SaveStatus.RUNNING.value, self.now), _job_state(exists=True, active=True))
        self.cloud_client.update_container.assert_not_called()

    def test_pending_with_no_job_within_grace_is_left_alone(self) -> None:
        print('Test: test_pending_with_no_job_within_grace_is_left_alone')
        recent = self.now - timedelta(seconds=5)
        self._run(_row(SaveStatus.PENDING.value, recent), _job_state(exists=False))
        self.cloud_client.update_container.assert_not_called()

    def test_pending_with_no_job_past_grace_is_marked_failed(self) -> None:
        print('Test: test_pending_with_no_job_past_grace_is_marked_failed')
        stale = self.now - timedelta(seconds=save_reconciler.SAVE_RECONCILER_PENDING_GRACE_SECONDS + 60)
        self._run(_row(SaveStatus.PENDING.value, stale), _job_state(exists=False))
        self.cloud_client.update_container.assert_called_once()
        _, fields = self.cloud_client.update_container.call_args.args
        self.assertEqual(fields['save_status'], SaveStatus.FAILED.value)

    def test_pending_with_job_already_created_is_left_alone_regardless_of_age(self) -> None:
        print('Test: test_pending_with_job_already_created_is_left_alone_regardless_of_age')
        stale = self.now - timedelta(seconds=save_reconciler.SAVE_RECONCILER_PENDING_GRACE_SECONDS + 60)
        self._run(_row(SaveStatus.PENDING.value, stale), _job_state(exists=True, active=True))
        self.cloud_client.update_container.assert_not_called()

    def test_job_lookup_error_is_swallowed_and_skips_the_row(self) -> None:
        print('Test: test_job_lookup_error_is_swallowed_and_skips_the_row')
        with patch.object(save_reconciler.JobManager, 'find_snapshot_job_for_container',
                           side_effect=Exception('transient k8s API error')):
            save_reconciler.reconcile_row(
                self.cloud_client, _row(SaveStatus.RUNNING.value, self.now), trusted_namespace='browseterm')
        self.cloud_client.update_container.assert_not_called()

    def test_cloud_client_error_marking_failed_is_swallowed(self) -> None:
        print('Test: test_cloud_client_error_marking_failed_is_swallowed')
        self.cloud_client.update_container.side_effect = CloudClientError(500, 'cloud down')
        # must not raise - a failure to record the reconciliation must not kill the sweep.
        self._run(_row(SaveStatus.RUNNING.value, self.now), _job_state(exists=False))


class TestReconcileOnce(TestCase):
    '''UNIT test: reconcile_once wires find_stuck_saves() -> reconcile_row() for every
    candidate row, and tolerates a failed find_stuck_saves() call without raising.'''

    def test_examines_every_row_from_find_stuck_saves(self) -> None:
        print('Test: test_examines_every_row_from_find_stuck_saves')
        rows = [
            _row(SaveStatus.RUNNING.value, datetime.now(timezone.utc)),
            _row(SaveStatus.PENDING.value, datetime.now(timezone.utc)),
        ]
        mock_client = MagicMock()
        mock_client.find_stuck_saves.return_value = rows
        with patch.object(save_reconciler, 'CloudClient', return_value=mock_client), \
             patch.object(save_reconciler, 'reconcile_row') as mock_reconcile_row:
            examined = save_reconciler.reconcile_once()
        self.assertEqual(examined, 2)
        self.assertEqual(mock_reconcile_row.call_count, 2)

    def test_find_stuck_saves_failure_returns_zero_without_raising(self) -> None:
        print('Test: test_find_stuck_saves_failure_returns_zero_without_raising')
        mock_client = MagicMock()
        mock_client.find_stuck_saves.side_effect = CloudClientError(500, 'db down')
        with patch.object(save_reconciler, 'CloudClient', return_value=mock_client):
            examined = save_reconciler.reconcile_once()
        self.assertEqual(examined, 0)
