# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.resources.job_manager import JobManager


class TestCreateSnapshotJobEnv(TestCase):
    '''
    Unit test for JobManager.create_snapshot_job (no live cluster: the client checks, RBAC
    provisioning and the actual Job creation call are mocked).

    Guards:
      1. The Job is created in the TRUSTED namespace (job_namespace), not the user's.
      2. The Job holds no Postgres OR Cloud credential of its own at all (no envFrom, no DB_*
         literal env vars, no BROWSETERM_CLOUD_API_URL/CLOUD_INTERNAL_API_TOKEN) - finishing
         Part 12, it reports progress and its own structural save-attempt state through Device
         Agent's local API instead (DEVICE_AGENT_LOCAL_API_URL's own default, a short ClusterIP
         DNS name, resolves correctly since the Job runs in the same trusted namespace Device
         Agent does - no explicit env var injection needed here).
      3. NAMESPACE_NAME (used to locate the tar in MinIO) is the USER namespace.
      4. Each storage var is its own env entry (not a single stringified "STORAGE_ENV_VARS").
    '''

    def setUp(self) -> None:
        print('Test: setUp TestCreateSnapshotJobEnv')
        self.job_namespace: str = 'browseterm'         # trusted ns the Job runs in
        self.user_namespace: str = 'user-42-namespace'  # tenant ns (only for the MinIO key)
        self.pod_name: str = 'test-pod'
        self.container_id: str = 'test-container-id'
        self.repo_name: str = 'dummy-repo'
        self.repo_password: str = 'dummy-password'
        self.snapshot_path: str = 'snapshots/test-pod'
        self.storage_env_vars: dict = {
            'STORAGE_LAYER': 'minio',
            'MINIO_ENDPOINT': 'minio.example.com:9000',
            'MINIO_BUCKET': 'snapshots',
            'MINIO_SECURE': 'false',
        }

    def _invoke(self):
        '''Invoke create_snapshot_job with the cluster mocked; return the job container.'''
        mock_batch_api = MagicMock()
        with patch.object(JobManager, 'check_kubernetes_client', return_value=None), \
             patch.object(JobManager, '_ensure_snapshot_job_sa', return_value=None), \
             patch('src.resources.job_manager.BatchV1Api', return_value=mock_batch_api):
            result: dict = JobManager.create_snapshot_job(
                job_namespace=self.job_namespace,
                user_namespace=self.user_namespace,
                pod_name=self.pod_name,
                container_id=self.container_id,
                repo_name=self.repo_name,
                repo_password=self.repo_password,
                snapshot_path=self.snapshot_path,
                storage_env_vars=self.storage_env_vars,
            )

        # Job names are unique-per-attempt (a short random suffix), not deterministic.
        self.assertTrue(result['job_name'].startswith(f'{self.pod_name}-snapshot-job-'))
        # Runs in the TRUSTED namespace, not the user's.
        self.assertEqual(result['namespace_name'], self.job_namespace)
        self.assertTrue(mock_batch_api.create_namespaced_job.called)
        _, kwargs = mock_batch_api.create_namespaced_job.call_args
        self.assertEqual(kwargs['namespace'], self.job_namespace)
        self._last_job_body = kwargs['body']
        return kwargs['body'].spec.template.spec.containers[0]

    def test_job_runs_in_trusted_namespace(self) -> None:
        print('Test: test_job_runs_in_trusted_namespace')
        self._invoke()  # the namespace assertions live in _invoke

    def test_no_postgres_or_cloud_credential_of_its_own(self) -> None:
        print('Test: test_no_postgres_or_cloud_credential_of_its_own')
        container = self._invoke()
        env_names = [ev.name for ev in (container.env or [])]
        # No DB_* literal env vars, no envFrom a DB credentials Secret at all, and (finishing
        # Part 12) no BROWSETERM_CLOUD_API_URL/CLOUD_INTERNAL_API_TOKEN either - the Job reports
        # progress and structural save-attempt state through Device Agent's local API instead.
        self.assertEqual([n for n in env_names if n.startswith('DB_')], [])
        self.assertFalse(container.env_from)
        self.assertNotIn('BROWSETERM_CLOUD_API_URL', env_names)
        self.assertNotIn('CLOUD_INTERNAL_API_TOKEN', env_names)

    def test_metadata_vars_present_and_namespace_is_user_ns(self) -> None:
        print('Test: test_metadata_vars_present_and_namespace_is_user_ns')
        env_map = {ev.name: ev.value for ev in self._invoke().env}
        self.assertEqual(env_map['CONTAINER_ID'], self.container_id)
        self.assertEqual(env_map['POD_NAME'], self.pod_name)
        self.assertEqual(env_map['SNAPSHOT_PATH'], self.snapshot_path)
        # NAMESPACE_NAME is the USER namespace (to locate the MinIO tar), not the trusted one.
        self.assertEqual(env_map['NAMESPACE_NAME'], self.user_namespace)

    def test_storage_vars_are_individual_env_entries(self) -> None:
        print('Test: test_storage_vars_are_individual_env_entries')
        env_map = {ev.name: ev.value for ev in self._invoke().env}
        self.assertEqual(env_map['STORAGE_LAYER'], 'minio')
        self.assertEqual(env_map['MINIO_ENDPOINT'], 'minio.example.com:9000')
        self.assertEqual(env_map['MINIO_BUCKET'], 'snapshots')
        self.assertEqual(env_map['MINIO_SECURE'], 'false')

    def test_no_stringified_storage_env_vars_key(self) -> None:
        print('Test: test_no_stringified_storage_env_vars_key')
        env_names = [ev.name for ev in self._invoke().env]
        self.assertNotIn('STORAGE_ENV_VARS', env_names)

    def test_none_valued_storage_vars_are_skipped(self) -> None:
        print('Test: test_none_valued_storage_vars_are_skipped')
        self.storage_env_vars = {'STORAGE_LAYER': 'minio', 'MINIO_ENDPOINT': None}
        env_names = [ev.name for ev in self._invoke().env]
        self.assertIn('STORAGE_LAYER', env_names)
        self.assertNotIn('MINIO_ENDPOINT', env_names)

    def test_pod_template_carries_the_networkpolicy_selector_label(self) -> None:
        '''Found 2026-10-04: a Job's own metadata.labels (set below on the Job object) are NOT
        copied onto the Pods it spawns by Kubernetes - only job-name/controller-uid are. Device
        Agent's local-api NetworkPolicy selects ingress on `app: snapshot-job`, so the POD
        TEMPLATE itself (not just the Job object) must carry that label, or every
        AllocateSnapshot/ReportSnapshotResult call from the Job to Device Agent silently times
        out (the real cause of Save hanging on "Didn't hear back in time").'''
        print('Test: test_pod_template_carries_the_networkpolicy_selector_label')
        self._invoke()
        pod_template_labels = self._last_job_body.spec.template.metadata.labels
        self.assertEqual(pod_template_labels.get('app'), 'snapshot-job')
