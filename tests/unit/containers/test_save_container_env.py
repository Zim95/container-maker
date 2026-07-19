# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.containers.containers import KubernetesContainerManager, KubernetesContainerHelper
from src.containers.dataclasses.save_container_dataclass import SaveContainerDataClass


class TestSaveContainerEnvFromEnviron(TestCase):
    '''
    Unit test for KubernetesContainerManager.save().

    This is a UNIT test: it does NOT require a cluster or a DB. The namespace lookup,
    the DB lookup (ContainerOps.find_one), the pod/service/ingress helper lookups and
    PodManager.save are all mocked.

    Guards two behaviours:
      1. The request's container_id is the DB id; save() resolves the pod's kubernetes_id
         from the DB and looks up the pod by THAT k8s id (not the DB id).
      2. DB credentials for the snapshot job come from container-maker's OWN environment
         (os.getenv) and are forwarded via SavePodDataClass.environment_variables, and
         CONTAINER_ID stays the DB id (so the Job updates the right DB row).
    '''

    def setUp(self) -> None:
        print('Test: setUp TestSaveContainerEnvFromEnviron')
        self.container_id: str = 'test-db-id'          # DB id (what the request carries)
        self.kubernetes_id: str = 'test-k8s-id'        # resolved from the DB row
        self.namespace_name: str = 'test-namespace'
        self.pod_name: str = 'test-pod'
        self.data: SaveContainerDataClass = SaveContainerDataClass(
            container_id=self.container_id,
            network_name=self.namespace_name,
            # deliberately different from the environment values below to prove
            # the request values are NOT the source of truth for the job.
            db_host='request-host',
            db_username='request-user',
            db_password='request-pass',
            db_database='request-db',
        )
        self.fake_env: dict = {
            'DB_HOST': 'env-host',
            'DB_PORT': '6543',
            'DB_USERNAME': 'env-user',
            'DB_PASSWORD': 'env-pass',
            'DB_DATABASE': 'env-db',
        }

    def _mock_container_ops(self):
        '''ContainerOps(...) -> instance whose find_one returns a row with kubernetes_id.'''
        ops_instance = MagicMock()
        ops_instance.find_one.return_value = MagicMock(data={
            'id': self.container_id,
            'kubernetes_id': self.kubernetes_id,
        })
        return MagicMock(return_value=ops_instance)

    def test_save_pod_resolves_k8s_id_and_sources_db_creds_from_environment(self) -> None:
        print('Test: test_save_pod_resolves_k8s_id_and_sources_db_creds_from_environment')
        mock_save = MagicMock(return_value={'pod_name': self.pod_name})
        mock_check_pod = MagicMock(return_value={'pod_name': self.pod_name})
        with patch('src.containers.containers.ContainerOps', self._mock_container_ops()), \
             patch('src.containers.containers.NamespaceManager.get', return_value={'namespace_name': self.namespace_name}), \
             patch.object(KubernetesContainerHelper, 'check_pod', mock_check_pod), \
             patch.object(KubernetesContainerHelper, 'check_service', return_value=None), \
             patch.object(KubernetesContainerHelper, 'check_ingress', return_value=None), \
             patch('src.containers.containers.PodManager.save', mock_save), \
             patch.dict('src.containers.containers.os.environ', self.fake_env, clear=True):
            result: list = KubernetesContainerManager.save(self.data)

        # returns the saved pod wrapped in a list
        self.assertEqual(result, [{'pod_name': self.pod_name}])

        # the pod is looked up by the resolved kubernetes_id, NOT the DB id
        self.assertEqual(mock_check_pod.call_args.kwargs.get('container_id'), self.kubernetes_id)

        # PodManager.save was called with a SavePodDataClass
        self.assertTrue(mock_save.called)
        save_pod_data = mock_save.call_args.args[0]
        env = save_pod_data.environment_variables

        # DB creds must come from the environment, NOT from the request dataclass
        self.assertEqual(env['DB_HOST'], 'env-host')
        self.assertEqual(env['DB_PORT'], '6543')
        self.assertEqual(env['DB_USERNAME'], 'env-user')
        self.assertEqual(env['DB_PASSWORD'], 'env-pass')
        self.assertEqual(env['DB_DATABASE'], 'env-db')
        # CONTAINER_ID stays the DB id so the Job updates the correct DB row
        self.assertEqual(env['CONTAINER_ID'], self.container_id)

        # and the pod name / namespace are forwarded correctly
        self.assertEqual(save_pod_data.pod_name, self.pod_name)
        self.assertEqual(save_pod_data.namespace_name, self.namespace_name)

    def test_db_port_defaults_when_absent_from_environment(self) -> None:
        print('Test: test_db_port_defaults_when_absent_from_environment')
        env_without_port = {k: v for k, v in self.fake_env.items() if k != 'DB_PORT'}
        mock_save = MagicMock(return_value={'pod_name': self.pod_name})
        with patch('src.containers.containers.ContainerOps', self._mock_container_ops()), \
             patch('src.containers.containers.NamespaceManager.get', return_value={'namespace_name': self.namespace_name}), \
             patch.object(KubernetesContainerHelper, 'check_pod', return_value={'pod_name': self.pod_name}), \
             patch.object(KubernetesContainerHelper, 'check_service', return_value=None), \
             patch.object(KubernetesContainerHelper, 'check_ingress', return_value=None), \
             patch('src.containers.containers.PodManager.save', mock_save), \
             patch.dict('src.containers.containers.os.environ', env_without_port, clear=True):
            KubernetesContainerManager.save(self.data)

        save_pod_data = mock_save.call_args.args[0]
        self.assertEqual(save_pod_data.environment_variables['DB_PORT'], '5432')
