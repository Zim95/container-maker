# builtins
from datetime import datetime, timezone, timedelta
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.resources.job_manager import JobManager


def _make_job(name: str, created_seconds_ago: int, active: int = 0, conditions: list = None) -> MagicMock:
    job = MagicMock()
    job.metadata.name = name
    job.metadata.creation_timestamp = datetime.now(timezone.utc) - timedelta(seconds=created_seconds_ago)
    job.status.active = active
    job.status.conditions = conditions or []
    return job


def _failed_condition(reason: str = 'BackoffLimitExceeded', message: str = 'Job has reached the specified backoff limit') -> MagicMock:
    cond = MagicMock()
    cond.type = 'Failed'
    cond.status = 'True'
    cond.reason = reason
    cond.message = message
    return cond


class TestFindSnapshotJobForContainer(TestCase):
    '''
    UNIT tests (no cluster): JobManager.find_snapshot_job_for_container is the save
    reconciler's only way to ask Kubernetes "is there still a live Job for this save".
    Exercises the label-selector lookup, the newest-wins tie-break when a stale finished
    Job is still lingering within its TTL, and the exists/active/terminal_failed shape the
    reconciler's decision table depends on.
    '''

    def _invoke(self, jobs: list):
        mock_batch_api = MagicMock()
        mock_batch_api.list_namespaced_job.return_value = MagicMock(items=jobs)
        with patch.object(JobManager, 'check_kubernetes_client', return_value=None), \
             patch('src.resources.job_manager.BatchV1Api', return_value=mock_batch_api):
            result = JobManager.find_snapshot_job_for_container('browseterm', 'container-id-1')
        return result, mock_batch_api

    def test_uses_container_id_label_selector_in_trusted_namespace(self) -> None:
        print('Test: test_uses_container_id_label_selector_in_trusted_namespace')
        _, mock_batch_api = self._invoke([])
        _, kwargs = mock_batch_api.list_namespaced_job.call_args
        self.assertEqual(kwargs['namespace'], 'browseterm')
        self.assertEqual(kwargs['label_selector'], 'container-id=container-id-1')

    def test_no_matching_job_reports_does_not_exist(self) -> None:
        print('Test: test_no_matching_job_reports_does_not_exist')
        result, _ = self._invoke([])
        self.assertEqual(result, {
            'exists': False, 'job_name': None, 'active': False,
            'terminal_failed': False, 'failure_reason': None,
        })

    def test_active_job_is_not_terminal_failed(self) -> None:
        print('Test: test_active_job_is_not_terminal_failed')
        job = _make_job('pod-snapshot-job-abc123', created_seconds_ago=30, active=1)
        result, _ = self._invoke([job])
        self.assertTrue(result['exists'])
        self.assertTrue(result['active'])
        self.assertFalse(result['terminal_failed'])
        self.assertIsNone(result['failure_reason'])

    def test_job_with_failed_condition_is_terminal_failed(self) -> None:
        print('Test: test_job_with_failed_condition_is_terminal_failed')
        job = _make_job('pod-snapshot-job-def456', created_seconds_ago=30, active=0,
                         conditions=[_failed_condition()])
        result, _ = self._invoke([job])
        self.assertTrue(result['exists'])
        self.assertFalse(result['active'])
        self.assertTrue(result['terminal_failed'])
        self.assertIn('BackoffLimitExceeded', result['failure_reason'])

    def test_newest_job_wins_when_a_stale_ttl_job_still_lingers(self) -> None:
        print('Test: test_newest_job_wins_when_a_stale_ttl_job_still_lingers')
        old_finished = _make_job('pod-snapshot-job-old', created_seconds_ago=3000,
                                  conditions=[_failed_condition()])
        newest_active = _make_job('pod-snapshot-job-new', created_seconds_ago=10, active=1)
        result, _ = self._invoke([old_finished, newest_active])
        self.assertEqual(result['job_name'], 'pod-snapshot-job-new')
        self.assertTrue(result['active'])
        self.assertFalse(result['terminal_failed'])
