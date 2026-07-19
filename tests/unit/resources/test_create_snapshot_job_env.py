# builtins
import os
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.resources.job_manager import JobManager


class TestCreateSnapshotJobEnv(TestCase):
    '''
    Unit test for JobManager.create_snapshot_job env assembly.

    This is a UNIT test: it does NOT require a live cluster. The Kubernetes
    client checks, RBAC/PVC provisioning and the actual Job creation call are
    all mocked, so we only exercise the in-memory building of the container env.

    The bug being guarded against: previously the whole storage_env_vars dict
    was stuffed into a single "STORAGE_ENV_VARS" env var. Now each storage var
    must appear as its own V1EnvVar entry, alongside the DB_* / CONTAINER_ID /
    POD_NAME env vars, and no "STORAGE_ENV_VARS" var should exist.
    '''

    def setUp(self) -> None:
        print('Test: setUp TestCreateSnapshotJobEnv')
        self.namespace_name: str = 'test-namespace'
        self.pod_name: str = 'test-pod'
        self.container_id: str = 'test-container-id'
        self.repo_name: str = 'dummy-repo'
        self.repo_password: str = 'dummy-password'
        self.db_host: str = 'testhost'
        self.db_port: int = 5432
        self.db_username: str = 'testuser'
        self.db_password: str = 'testpassword'
        self.db_database: str = 'testdatabase'
        self.snapshot_path: str = 'snapshots/test-pod'
        self.storage_env_vars: dict = {
            'STORAGE_LAYER': 'minio',
            'MINIO_ENDPOINT': 'minio.example.com:9000',
            'MINIO_BUCKET': 'snapshots',
            'MINIO_SECURE': 'false',
        }

    def _invoke(self) -> list:
        '''
        Invoke create_snapshot_job with the k8s-touching parts mocked out and
        return the list of V1EnvVar objects assigned to the job container.
        '''
        mock_batch_api = MagicMock()
        with patch.object(JobManager, 'check_kubernetes_client', return_value=None), \
             patch.object(JobManager, '_ensure_snapshot_job_rbac', return_value=None), \
             patch.object(JobManager, '_ensure_snapshot_pvc', return_value=None), \
             patch('src.resources.job_manager.BatchV1Api', return_value=mock_batch_api):
            result: dict = JobManager.create_snapshot_job(
                namespace_name=self.namespace_name,
                pod_name=self.pod_name,
                container_id=self.container_id,
                repo_name=self.repo_name,
                repo_password=self.repo_password,
                db_host=self.db_host,
                db_port=self.db_port,
                db_username=self.db_username,
                db_password=self.db_password,
                db_database=self.db_database,
                snapshot_path=self.snapshot_path,
                storage_env_vars=self.storage_env_vars,
            )

        # job name is returned correctly
        self.assertEqual(result['job_name'], f'{self.pod_name}-snapshot-job')
        self.assertEqual(result['namespace_name'], self.namespace_name)

        # the job body handed to create_namespaced_job carries our env
        self.assertTrue(mock_batch_api.create_namespaced_job.called)
        _, kwargs = mock_batch_api.create_namespaced_job.call_args
        job = kwargs['body']
        return job.spec.template.spec.containers[0].env

    def test_storage_vars_are_individual_env_entries(self) -> None:
        print('Test: test_storage_vars_are_individual_env_entries')
        env_vars = self._invoke()
        env_map = {ev.name: ev.value for ev in env_vars}

        # Each storage var must be its own entry.
        self.assertEqual(env_map['STORAGE_LAYER'], 'minio')
        self.assertEqual(env_map['MINIO_ENDPOINT'], 'minio.example.com:9000')
        self.assertEqual(env_map['MINIO_BUCKET'], 'snapshots')
        self.assertEqual(env_map['MINIO_SECURE'], 'false')

    def test_no_stringified_storage_env_vars_key(self) -> None:
        print('Test: test_no_stringified_storage_env_vars_key')
        env_vars = self._invoke()
        env_names = [ev.name for ev in env_vars]
        # The old bug: the whole dict stuffed into one var named STORAGE_ENV_VARS.
        self.assertNotIn('STORAGE_ENV_VARS', env_names)

    def test_db_and_metadata_vars_present(self) -> None:
        print('Test: test_db_and_metadata_vars_present')
        env_vars = self._invoke()
        env_map = {ev.name: ev.value for ev in env_vars}

        self.assertEqual(env_map['DB_HOST'], self.db_host)
        self.assertEqual(env_map['DB_PORT'], str(self.db_port))
        self.assertEqual(env_map['DB_USERNAME'], self.db_username)
        self.assertEqual(env_map['DB_PASSWORD'], self.db_password)
        self.assertEqual(env_map['DB_DATABASE'], self.db_database)
        self.assertEqual(env_map['CONTAINER_ID'], self.container_id)
        self.assertEqual(env_map['POD_NAME'], self.pod_name)
        self.assertEqual(env_map['SNAPSHOT_PATH'], self.snapshot_path)

    def test_none_valued_storage_vars_are_skipped(self) -> None:
        print('Test: test_none_valued_storage_vars_are_skipped')
        self.storage_env_vars = {
            'STORAGE_LAYER': 'local',
            'MINIO_ENDPOINT': None,  # should be dropped
        }
        env_vars = self._invoke()
        env_names = [ev.name for ev in env_vars]
        self.assertIn('STORAGE_LAYER', env_names)
        self.assertNotIn('MINIO_ENDPOINT', env_names)
