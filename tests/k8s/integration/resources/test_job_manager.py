# builtins
import os
from unittest import TestCase

# third party
from kubernetes.client import BatchV1Api, V1DeleteOptions

# modules
from src.resources.job_manager import JobManager
from src.resources.namespace_manager import NamespaceManager
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass


NAMESPACE_NAME: str = 'test-job-manager'
POD_NAME: str = 'test-job-manager-pod'


class TestJobManager(TestCase):

    def setUp(self) -> None:
        print('Setup: setUp')
        self.namespace_name: str = NAMESPACE_NAME
        self.pod_name: str = POD_NAME
        self.container_id: str = 'test-container-id'
        self.repo_name: str = 'dummy-repo'
        self.repo_password: str = 'dummy-password'
        self.db_host: str = 'testhost'
        self.db_port: int = 5432
        self.db_username: str = 'testuser'
        self.db_password: str = 'testpassword'
        self.db_database: str = 'testdatabase'

        NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': self.namespace_name}))

    def test_create_snapshot_job(self) -> None:
        print('Test: test_create_snapshot_job')
        original_storage_layer = os.environ.get('STORAGE_LAYER')
        os.environ['STORAGE_LAYER'] = 'minio'
        try:
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
                environment_variables={
                    "CONTAINER_ID": self.container_id,
                    "DB_HOST": self.db_host,
                    "DB_PORT": str(self.db_port),
                    "DB_USERNAME": self.db_username,
                    "DB_PASSWORD": self.db_password,
                    "DB_DATABASE": self.db_database,
                },
            )
        finally:
            if original_storage_layer is None:
                os.environ.pop('STORAGE_LAYER', None)
            else:
                os.environ['STORAGE_LAYER'] = original_storage_layer

        job_name = result.get('job_name')
        self.assertEqual(job_name, f"{self.pod_name}-snapshot-job")

        batch_v1 = BatchV1Api()
        job = batch_v1.read_namespaced_job(name=job_name, namespace=self.namespace_name)
        self.assertEqual(job.metadata.name, job_name)

        batch_v1.delete_namespaced_job(
            name=job_name,
            namespace=self.namespace_name,
            body=V1DeleteOptions(propagation_policy='Background')
        )


class ZZZ_Cleanup(TestCase):

    def test_cleanup(self) -> None:
        print('Cleanup: test_cleanup')
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))
