# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.resources.job_manager import JobManager, DB_CREDENTIALS_SECRET_NAME


class TestCreateSnapshotJobEnv(TestCase):
    '''
    Unit test for JobManager.create_snapshot_job (no live cluster: the client checks, RBAC
    provisioning and the actual Job creation call are mocked).

    Guards:
      1. The Job is created in the TRUSTED namespace (job_namespace), not the user's.
      2. DB credentials are NOT literal env vars — they come from the browseterm-db-credentials
         Secret via envFrom.
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
             patch.object(JobManager, '_ensure_snapshot_job_rbac', return_value=None), \
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

        self.assertEqual(result['job_name'], f'{self.pod_name}-snapshot-job')
        # Runs in the TRUSTED namespace, not the user's.
        self.assertEqual(result['namespace_name'], self.job_namespace)
        self.assertTrue(mock_batch_api.create_namespaced_job.called)
        _, kwargs = mock_batch_api.create_namespaced_job.call_args
        self.assertEqual(kwargs['namespace'], self.job_namespace)
        return kwargs['body'].spec.template.spec.containers[0]

    def test_job_runs_in_trusted_namespace(self) -> None:
        print('Test: test_job_runs_in_trusted_namespace')
        self._invoke()  # the namespace assertions live in _invoke

    def test_db_creds_come_from_secret_not_env(self) -> None:
        print('Test: test_db_creds_come_from_secret_not_env')
        container = self._invoke()
        env_names = [ev.name for ev in (container.env or [])]
        # No DB_* literal env vars.
        self.assertEqual([n for n in env_names if n.startswith('DB_')], [])
        # DB creds arrive via envFrom the credentials Secret.
        secret_refs = [s.secret_ref.name for s in (container.env_from or []) if s.secret_ref]
        self.assertIn(DB_CREDENTIALS_SECRET_NAME, secret_refs)

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
